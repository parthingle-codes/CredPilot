"""Render Blueprint rules (render.yaml)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..constants import DOCS
from ...security import looks_secret_key
from ..models import AnalysisContext, FindingDraft, ParsedDocument
from ..parsers.lines import line_at, meta_line
from .common import base_finding, common_env_checks, secret_finding

RENDER_SECRET_REMEDIATION = (
    "Rotate the credential at the provider, remove the literal from the Blueprint, "
    "and use `sync: false` so Render prompts for it (or `generateValue: true`)."
)


@dataclass(frozen=True)
class RenderContainer:
    label: str | None
    services: tuple[dict[str, Any], ...]
    databases: tuple[dict[str, Any], ...]
    env_groups: tuple[dict[str, Any], ...]


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def get_str(mapping: dict[str, Any], key: str) -> str | None:
    value = mapping.get(key)
    if value is None or isinstance(value, (dict, list)):
        return None
    text = str(value).strip()
    return text or None


def get_int(mapping: dict[str, Any], key: str) -> int | None:
    value = mapping.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _containers(doc: ParsedDocument) -> list[RenderContainer]:
    data = doc.data or {}
    containers = [
        RenderContainer(
            label=None,
            services=tuple(item for item in _as_list(data.get("services")) if isinstance(item, dict)),
            databases=tuple(item for item in _as_list(data.get("databases")) if isinstance(item, dict)),
            env_groups=tuple(
                item for item in _as_list(data.get("envVarGroups")) if isinstance(item, dict)
            ),
        )
    ]

    for project in _as_list(data.get("projects")):
        if not isinstance(project, dict):
            continue
        project_name = get_str(project, "name") or "project"
        for environment in _as_list(project.get("environments")):
            if not isinstance(environment, dict):
                continue
            environment_name = get_str(environment, "name") or "environment"
            containers.append(
                RenderContainer(
                    label=f"{project_name}/{environment_name}",
                    services=tuple(
                        item
                        for item in _as_list(environment.get("services"))
                        if isinstance(item, dict)
                    ),
                    databases=tuple(
                        item
                        for item in _as_list(environment.get("databases"))
                        if isinstance(item, dict)
                    ),
                    env_groups=tuple(
                        item
                        for item in _as_list(environment.get("envVarGroups"))
                        if isinstance(item, dict)
                    ),
                )
            )
    return containers


def _resource_name(mapping: dict[str, Any], fallback: str) -> str:
    return get_str(mapping, "name") or fallback


def _label(name: str, container: RenderContainer) -> str:
    return f"{container.label}/{name}" if container.label else name


def _snippet(doc: ParsedDocument, line: int | None, fallback: str) -> str:
    return line_at(doc.lines, line) or fallback


def _services(doc: ParsedDocument):
    for container in _containers(doc):
        for service in container.services:
            name = _resource_name(service, "unnamed service")
            yield service, name, container


def _databases(doc: ParsedDocument):
    for container in _containers(doc):
        for database in container.databases:
            name = _resource_name(database, "unnamed database")
            yield database, name, container


def _env_groups(doc: ParsedDocument):
    for container in _containers(doc):
        for group in container.env_groups:
            name = _resource_name(group, "unnamed env group")
            yield group, name, container


def _is_static(service: dict[str, Any]) -> bool:
    return (get_str(service, "runtime") or "").lower() == "static"


def check_plans(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    for service, name, container in _services(doc):
        ctx.tick()
        service_type = (get_str(service, "type") or "web").lower()
        runtime = (get_str(service, "runtime") or "").lower()
        if runtime == "static":
            continue
        if service_type == "workflow":
            continue

        resource = _label(name, container)
        plan = get_str(service, "plan")
        line = meta_line(service, "plan") or meta_line(service)
        fallback = f"type: {service_type}"
        snippet = _snippet(doc, line, fallback)

        if plan is None:
            if service_type in {"keyvalue", "redis"}:
                default_note = "the paid 256 MB Key Value plan"
            else:
                default_note = "the paid 0.5c-512mb compute plan"
            findings.append(
                base_finding(
                    rule_id="render-plan-default",
                    title="No free plan selected; a paid default applies",
                    severity="high",
                    category="billing",
                    message=(
                        f"Service `{resource}` does not set `plan`. Render documents "
                        f"{default_note} as the default for new instances."
                    ),
                    why=(
                        "A demo service created without an explicit free plan can keep consuming "
                        "paid instance time after judging, especially if the Blueprint is re-synced."
                    ),
                    remediation=(
                        "Set `plan: free` when the demo fits free-tier limits. Otherwise confirm "
                        "the current price in the Render dashboard and add a deletion reminder."
                    ),
                    doc=doc,
                    line=line,
                    snippet=snippet,
                    docs_url=DOCS["render_blueprint"],
                    resource=resource,
                )
            )
        elif plan.lower() != "free":
            findings.append(
                base_finding(
                    rule_id="render-plan-paid",
                    title="Paid compute plan selected",
                    severity="high",
                    category="billing",
                    message=f"Service `{resource}` uses `plan: {plan}`.",
                    why=(
                        "Paid instances continue to consume account resources while they exist, "
                        "even when the demo receives no traffic. CredPilot does not know the "
                        "current rate or your account balance."
                    ),
                    remediation=(
                        "Confirm the current price and free-tier fit in Render. For a throwaway "
                        "demo, use `plan: free` where supported and delete the service afterward."
                    ),
                    doc=doc,
                    line=line,
                    snippet=snippet,
                    docs_url=DOCS["render_blueprint"],
                    resource=resource,
                )
            )
        elif service_type in {"worker", "cron", "pserv"}:
            findings.append(
                base_finding(
                    rule_id="render-free-unsupported",
                    title="Free plan is not documented for this service type",
                    severity="high",
                    category="deployment",
                    message=(
                        f"Service `{resource}` (`type: {service_type}`) sets `plan: free`."
                    ),
                    why=(
                        "Render's free instance type is documented for web services and free "
                        "datastores. A Blueprint using free compute for workers, cron jobs, or "
                        "private services may fail validation or deploy with a different plan."
                    ),
                    remediation=(
                        "Check the service type's supported plans in Render, choose the smallest "
                        "plan that fits, and set a cleanup date."
                    ),
                    doc=doc,
                    line=line,
                    snippet=snippet,
                    docs_url=DOCS["render_free"],
                    resource=resource,
                )
            )

    return findings


def check_disks(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    for service, name, container in _services(doc):
        disk = service.get("disk")
        if not isinstance(disk, dict) or not disk:
            continue
        ctx.tick()
        resource = _label(name, container)
        line = meta_line(service, "disk")
        disk_name = get_str(disk, "name") or "unnamed disk"
        mount = get_str(disk, "mountPath")
        findings.append(
            base_finding(
                rule_id="render-persistent-disk",
                title="Persistent disk attached",
                severity="high",
                category="billing",
                message=(
                    f"Service `{resource}` attaches disk `{disk_name}`"
                    + (f" at `{mount}`" if mount else "")
                    + "."
                ),
                why=(
                    "Persistent disks are a paid capability, retain data independently of the "
                    "service, and must be cleaned up explicitly. They are also incompatible with "
                    "some scaling configurations."
                ),
                remediation=(
                    "Confirm the current disk price in Render. If the demo does not need durable "
                    "local files, remove the disk before creating the service; otherwise delete it "
                    "with the service after the demo."
                ),
                doc=doc,
                line=line,
                snippet=_snippet(doc, line, "disk:"),
                docs_url=DOCS["render_disks"],
                resource=resource,
            )
        )

        if (get_str(service, "plan") or "").lower() == "free":
            findings.append(
                base_finding(
                    rule_id="render-free-disk",
                    title="Free compute cannot attach a persistent disk",
                    severity="high",
                    category="deployment",
                    message=f"Service `{resource}` combines `plan: free` with a disk.",
                    why=(
                        "Render's free web instances do not support persistent disks, so this "
                        "Blueprint is likely to fail validation or require a paid plan."
                    ),
                    remediation=(
                        "Remove the disk and keep the demo stateless, or choose a paid plan and "
                        "schedule deletion after the demo."
                    ),
                    doc=doc,
                    line=line,
                    snippet=_snippet(doc, line, "disk:"),
                    docs_url=DOCS["render_disks"],
                    resource=resource,
                )
            )
    return findings


def check_always_on(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    for service, name, container in _services(doc):
        service_type = (get_str(service, "type") or "").lower()
        if service_type not in {"worker", "pserv", "cron", "workflow"}:
            continue
        ctx.tick()
        resource = _label(name, container)
        line = meta_line(service, "type") or meta_line(service)
        if service_type == "worker":
            title = "Background worker runs without demo traffic"
            severity = "high"
            message = f"`{resource}` is a background worker."
            why = (
                "Workers normally run continuously to process a queue. They can consume instance "
                "time between the last test and the actual demo."
            )
        elif service_type == "pserv":
            title = "Private service runs continuously"
            severity = "high"
            message = f"`{resource}` is a private service."
            why = (
                "Private services stay available on the private network even when no judge is "
                "using the demo, so they can outlive the event unnoticed."
            )
        elif service_type == "cron":
            schedule = get_str(service, "schedule")
            title = "Cron job runs between demos"
            severity = "medium"
            message = f"`{resource}` is a cron job" + (
                f" with schedule `{schedule}`" if schedule else ""
            ) + "."
            why = (
                "Scheduled jobs run independently of demo traffic. A frequent or retrying job can "
                "keep consuming compute after the presentation."
            )
        else:
            title = "Workflow can run after the demo"
            severity = "medium"
            message = f"`{resource}` is a workflow service."
            why = (
                "Workflow runs are triggered separately from the demo UI and can continue after "
                "the event if triggers or retries remain active."
            )
        findings.append(
            base_finding(
                rule_id="render-always-on",
                title=title,
                severity=severity,
                category="billing",
                message=message,
                why=why,
                remediation=(
                    "Decide whether this service is essential for the demo. Pause execution or "
                    "delete the service after judging, and confirm the cleanup in the dashboard."
                ),
                doc=doc,
                line=line,
                snippet=_snippet(doc, line, f"type: {service_type}"),
                docs_url=DOCS["render_scaling"],
                resource=resource,
            )
        )
    return findings


def check_scaling(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    for service, name, container in _services(doc):
        scaling = service.get("scaling")
        resource = _label(name, container)
        if isinstance(scaling, dict):
            minimum = get_int(scaling, "minInstances") or 0
            maximum = get_int(scaling, "maxInstances") or 0
            if minimum <= 1 and maximum <= 1:
                continue
            ctx.tick()
            severity = "high" if minimum > 1 else "medium"
            line = (
                meta_line(scaling, "minInstances")
                or meta_line(scaling, "maxInstances")
                or meta_line(service, "scaling")
            )
            findings.append(
                base_finding(
                    rule_id="render-autoscaling",
                    title="Autoscaling can add instances",
                    severity=severity,
                    category="billing",
                    message=(
                        f"`{resource}` autoscales from {minimum} to {maximum} instance(s)."
                    ),
                    why=(
                        "Every additional instance consumes compute. A traffic spike, retry loop, "
                        "or load test can leave the service larger than expected."
                    ),
                    remediation=(
                        "Set the minimum to the smallest viable value, cap the maximum, and check "
                        "the instance count after the demo before deleting the service."
                    ),
                    doc=doc,
                    line=line,
                    snippet=_snippet(doc, line, "scaling:"),
                    docs_url=DOCS["render_scaling"],
                    resource=resource,
                )
            )
            continue

        instances = get_int(service, "numInstances")
        if instances is not None and instances > 1:
            ctx.tick()
            line = meta_line(service, "numInstances")
            findings.append(
                base_finding(
                    rule_id="render-manual-scaling",
                    title="Multiple instances configured",
                    severity="high",
                    category="billing",
                    message=f"`{resource}` runs {instances} instances.",
                    why=(
                        "Manual scaling multiplies the compute footprint. Forgotten extra instances "
                        "are easy to miss in a dashboard after the demo."
                    ),
                    remediation=(
                        "Use one instance for the demo unless load requires more, then scale back "
                        "and verify the instance count during cleanup."
                    ),
                    doc=doc,
                    line=line,
                    snippet=_snippet(doc, line, "numInstances:"),
                    docs_url=DOCS["render_scaling"],
                    resource=resource,
                )
            )
    return findings


def check_previews(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    data = doc.data or {}
    previews = data.get("previews")
    generation = get_str(previews, "generation") if isinstance(previews, dict) else None
    legacy_enabled = data.get("previewsEnabled") is True
    if (generation or "").lower() == "automatic" or legacy_enabled:
        ctx.tick()
        line = meta_line(previews, "generation") if isinstance(previews, dict) else meta_line(data, "previewsEnabled")
        expire = get_int(previews, "expireAfterDays") if isinstance(previews, dict) else None
        expiry_note = (
            f" It expires after {expire} day(s) without updates."
            if expire
            else " No automatic expiry is configured."
        )
        findings.append(
            base_finding(
                rule_id="render-preview-environments",
                title="Preview environments are generated automatically",
                severity="high",
                category="billing",
                message="The Blueprint enables automatic preview environments." + expiry_note,
                why=(
                    "Each preview can create its own services and databases. Pull requests that "
                    "are merged, abandoned, or forgotten can leave duplicate infrastructure behind."
                ),
                remediation=(
                    "Use manual previews for a hackathon, or set `previews.expireAfterDays` and "
                    "remove preview environments during cleanup."
                ),
                doc=doc,
                line=line,
                snippet=_snippet(doc, line, "previews:"),
                docs_url=DOCS["render_previews"],
                resource="preview environments",
            )
        )

    for service, name, container in _services(doc):
        service_previews = service.get("previews")
        service_generation = (
            get_str(service_previews, "generation")
            if isinstance(service_previews, dict)
            else None
        )
        enabled = (service_generation or "").lower() == "automatic"
        enabled = enabled or service.get("pullRequestPreviewsEnabled") is True
        if not enabled:
            continue
        ctx.tick()
        resource = _label(name, container)
        line = (
            meta_line(service_previews, "generation")
            if isinstance(service_previews, dict)
            else meta_line(service, "pullRequestPreviewsEnabled")
        )
        findings.append(
            base_finding(
                rule_id="render-service-previews",
                title="Pull request previews are enabled",
                severity="medium",
                category="billing",
                message=f"Service `{resource}` creates preview instances for pull requests.",
                why=(
                    "Review apps are useful, but each preview is another deployment that can be "
                    "forgotten after a pull request closes."
                ),
                remediation=(
                    "Disable automatic previews for the hackathon or delete preview instances "
                    "after merging the last pull request."
                ),
                doc=doc,
                line=line,
                snippet=_snippet(doc, line, "previews:"),
                docs_url=DOCS["render_previews"],
                resource=resource,
            )
        )
    return findings


def check_free_web(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    for service, name, container in _services(doc):
        if (get_str(service, "type") or "web").lower() != "web":
            continue
        if _is_static(service):
            continue
        if (get_str(service, "plan") or "").lower() != "free":
            continue
        ctx.tick()
        resource = _label(name, container)
        line = meta_line(service, "plan")
        findings.append(
            base_finding(
                rule_id="render-free-spindown",
                title="Free web service spins down when idle",
                severity="medium",
                category="deployment",
                message=(
                    f"`{resource}` uses the free web instance type. Render spins it down after "
                    "15 minutes without inbound traffic; the next request takes about a minute to wake."
                ),
                why=(
                    "The first judge or visitor can hit a cold-start loading page. It can look like "
                    "the demo is broken even though the deploy is healthy."
                ),
                remediation=(
                    "Open the demo URL a few minutes before presenting, keep a local fallback ready, "
                    "or choose a paid instance if instant response is essential."
                ),
                doc=doc,
                line=line,
                snippet=_snippet(doc, line, "plan: free"),
                docs_url=DOCS["render_free"],
                resource=resource,
            )
        )
    return findings


def check_databases(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    for database, name, container in _databases(doc):
        resource = _label(name, container)
        plan = get_str(database, "plan")
        line = meta_line(database, "plan") or meta_line(database)

        ctx.tick()
        if plan is None:
            findings.append(
                base_finding(
                    rule_id="render-database-plan-default",
                    title="Database uses a paid default plan",
                    severity="high",
                    category="billing",
                    message=(
                        f"Database `{resource}` does not set `plan`. Render documents the paid "
                        "0.1c-256mb plan as the default for new databases."
                    ),
                    why=(
                        "A database created by the Blueprint can outlive the demo and continue "
                        "consuming account resources. CredPilot cannot see its current usage."
                    ),
                    remediation=(
                        "Set `plan: free` if the demo fits the free database limits, or confirm the "
                        "current price and delete the database after the event."
                    ),
                    doc=doc,
                    line=line,
                    snippet=_snippet(doc, line, f"name: {name}"),
                    docs_url=DOCS["render_postgres"],
                    resource=resource,
                )
            )
        elif plan.lower() == "free":
            findings.append(
                base_finding(
                    rule_id="render-database-free-expiry",
                    title="Free database expires after 30 days",
                    severity="medium",
                    category="deployment",
                    message=(
                        f"Database `{resource}` uses the free plan. Render documents a 30-day "
                        "lifetime plus a 14-day upgrade grace period before deletion."
                    ),
                    why=(
                        "Demo data can disappear during judging, a portfolio review, or a later "
                        "follow-up if the database reaches its expiry date."
                    ),
                    remediation=(
                        "Export any data you need before the deadline, or upgrade if the project "
                        "must remain online. Add the expiry date to the cleanup checklist."
                    ),
                    doc=doc,
                    line=line,
                    snippet=_snippet(doc, line, "plan: free"),
                    docs_url=DOCS["render_free"],
                    resource=resource,
                )
            )
        else:
            findings.append(
                base_finding(
                    rule_id="render-database-paid",
                    title="Paid database plan selected",
                    severity="high",
                    category="billing",
                    message=f"Database `{resource}` uses `plan: {plan}`.",
                    why=(
                        "Databases are separate resources from the web service. Deleting the app "
                        "does not necessarily delete its database."
                    ),
                    remediation=(
                        "Confirm the current database price in Render, use a free plan where it fits, "
                        "and delete the database explicitly during cleanup."
                    ),
                    doc=doc,
                    line=line,
                    snippet=_snippet(doc, line, f"plan: {plan}"),
                    docs_url=DOCS["render_postgres"],
                    resource=resource,
                )
            )

        replicas = database.get("readReplicas")
        if isinstance(replicas, list) and replicas:
            ctx.tick()
            replica_line = meta_line(database, "readReplicas")
            findings.append(
                base_finding(
                    rule_id="render-database-replicas",
                    title="Read replicas add database compute",
                    severity="high",
                    category="billing",
                    message=(
                        f"Database `{resource}` defines {len(replicas)} read replica(s)."
                    ),
                    why=(
                        "Each replica is separately provisioned infrastructure. Replicas are easy to "
                        "forget because the primary database still looks like one resource."
                    ),
                    remediation=(
                        "Remove replicas that the demo does not need, and delete every replica "
                        "explicitly during cleanup."
                    ),
                    doc=doc,
                    line=replica_line,
                    snippet=_snippet(doc, replica_line, "readReplicas:"),
                    docs_url=DOCS["render_postgres"],
                    resource=resource,
                )
            )

        high_availability = database.get("highAvailability")
        if isinstance(high_availability, dict) and high_availability.get("enabled") is True:
            ctx.tick()
            ha_line = meta_line(high_availability, "enabled") or meta_line(database, "highAvailability")
            findings.append(
                base_finding(
                    rule_id="render-database-ha",
                    title="High-availability database standby enabled",
                    severity="high",
                    category="billing",
                    message=f"Database `{resource}` enables a high-availability standby.",
                    why=(
                        "A standby is additional database infrastructure that remains after the "
                        "demo unless the database is removed."
                    ),
                    remediation=(
                        "Disable high availability for a throwaway demo, or confirm the current "
                        "cost in Render and include the database in cleanup."
                    ),
                    doc=doc,
                    line=ha_line,
                    snippet=_snippet(doc, ha_line, "highAvailability:"),
                    docs_url=DOCS["render_postgres"],
                    resource=resource,
                )
            )

        autoscaling = database.get("storageAutoscalingEnabled")
        if autoscaling is True:
            ctx.tick()
            auto_line = meta_line(database, "storageAutoscalingEnabled")
            findings.append(
                base_finding(
                    rule_id="render-database-storage-autoscaling",
                    title="Database storage can grow automatically",
                    severity="medium",
                    category="billing",
                    message=f"Database `{resource}` enables storage autoscaling.",
                    why=(
                        "A logging or retry bug can grow storage without a deploy. Growth is not "
                        "visible in the Blueprint after it happens."
                    ),
                    remediation=(
                        "Disable autoscaling for a short demo or monitor storage and set a manual "
                        "cap where Render supports one."
                    ),
                    doc=doc,
                    line=auto_line,
                    snippet=_snippet(doc, auto_line, "storageAutoscalingEnabled: true"),
                    docs_url=DOCS["render_postgres"],
                    resource=resource,
                )
            )

        allow_list = database.get("ipAllowList")
        publicly_open = allow_list is None
        if isinstance(allow_list, list):
            publicly_open = any(
                isinstance(item, dict) and str(item.get("source", "")).strip() == "0.0.0.0/0"
                for item in allow_list
            )
        if publicly_open:
            ctx.tick()
            ip_line = meta_line(database, "ipAllowList") or meta_line(database)
            findings.append(
                base_finding(
                    rule_id="render-database-public-network",
                    title="Database network access is not restricted",
                    severity="medium",
                    category="security",
                    message=(
                        f"Database `{resource}` "
                        + ("has no `ipAllowList`." if allow_list is None else "allows `0.0.0.0/0`.")
                    ),
                    why=(
                        "Render documents that an omitted database IP allow list permits connections "
                        "from any IP (credentials are still required). A leaked password then has "
                        "fewer network barriers."
                    ),
                    remediation=(
                        "Use the app's private/internal connection where possible, restrict entries "
                        "to known ranges, and rotate exposed passwords."
                    ),
                    doc=doc,
                    line=ip_line,
                    snippet=_snippet(doc, ip_line, f"name: {name}"),
                    docs_url=DOCS["render_postgres"],
                    resource=resource,
                )
            )
    return findings


def check_keyvalue(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    for service, name, container in _services(doc):
        service_type = (get_str(service, "type") or "").lower()
        if service_type not in {"keyvalue", "redis"}:
            continue
        resource = _label(name, container)
        if (get_str(service, "plan") or "").lower() == "free":
            ctx.tick()
            line = meta_line(service, "plan")
            findings.append(
                base_finding(
                    rule_id="render-keyvalue-free-limits",
                    title="Free Key Value instance is small and non-persistent",
                    severity="low",
                    category="deployment",
                    message=(
                        f"`{resource}` uses the free Key Value plan: 25 MB with data persistence "
                        "unavailable on free instances."
                    ),
                    why=(
                        "Cache data can disappear after a restart, and a demo that stores sessions "
                        "or queues there may behave differently than expected."
                    ),
                    remediation=(
                        "Keep demo-critical state in a database, or use a paid Key Value plan if "
                        "persistence is required."
                    ),
                    doc=doc,
                    line=line,
                    snippet=_snippet(doc, line, "plan: free"),
                    docs_url=DOCS["render_keyvalue"],
                    resource=resource,
                )
            )

        allow_list = service.get("ipAllowList")
        if allow_list is None:
            ctx.tick()
            line = meta_line(service)
            findings.append(
                base_finding(
                    rule_id="render-keyvalue-allowlist-missing",
                    title="Key Value instance is missing its required IP allow list",
                    severity="high",
                    category="deployment",
                    message=f"`{resource}` does not define `ipAllowList`.",
                    why=(
                        "Render requires an IP allow list for Key Value instances. The Blueprint "
                        "sync can fail before the demo is deployed."
                    ),
                    remediation=(
                        "Add `ipAllowList: []` for private-only access, or list the specific CIDR "
                        "ranges that need external access."
                    ),
                    doc=doc,
                    line=line,
                    snippet=_snippet(doc, line, f"name: {name}"),
                    docs_url=DOCS["render_keyvalue"],
                    resource=resource,
                )
            )
        elif isinstance(allow_list, list) and any(
            isinstance(item, dict) and str(item.get("source", "")).strip() == "0.0.0.0/0"
            for item in allow_list
        ):
            ctx.tick()
            line = meta_line(service, "ipAllowList")
            findings.append(
                base_finding(
                    rule_id="render-keyvalue-public-network",
                    title="Key Value instance allows every IP",
                    severity="medium",
                    category="security",
                    message=f"`{resource}` includes `0.0.0.0/0` in `ipAllowList`.",
                    why=(
                        "The instance accepts connections from any network. A leaked password or "
                        "misconfigured client exposes the data to a larger audience."
                    ),
                    remediation="Restrict the allow list to specific ranges or use `[]` for private-only access.",
                    doc=doc,
                    line=line,
                    snippet=_snippet(doc, line, "ipAllowList:"),
                    docs_url=DOCS["render_keyvalue"],
                    resource=resource,
                )
            )
    return findings


def _check_env_item(
    *,
    doc: ParsedDocument,
    item: dict[str, Any],
    resource: str,
    ctx: AnalysisContext,
    findings: list[FindingDraft],
) -> None:
    key = get_str(item, "key")
    if not key:
        return

    value = item.get("value")
    has_literal = value is not None and str(value).strip() != ""
    key_line = meta_line(item, "key") or meta_line(item)
    value_line = meta_line(item, "value") or key_line

    if has_literal:
        snippet = f"{key}={value}"
        common = common_env_checks(
            doc=doc,
            key=key,
            value=value,
            line=value_line,
            resource=resource,
            ctx=ctx,
            snippet=snippet,
        )
        findings.extend(common)
        finding = secret_finding(
            doc=doc,
            key=key,
            value=value,
            line=value_line,
            resource=resource,
            rule_id="render-secret-value",
            source="the Render Blueprint",
            remediation=RENDER_SECRET_REMEDIATION,
        )
        if finding:
            findings.append(finding)
        return

    if not looks_secret_key(key):
        return
    has_source = bool(
        item.get("generateValue") is True
        or item.get("fromDatabase")
        or item.get("fromService")
        or item.get("fromGroup")
        or item.get("sync") is False
    )
    if has_source:
        return

    ctx.tick()
    findings.append(
        base_finding(
            rule_id="render-secret-no-source",
            title="Secret environment variable has no value source",
            severity="medium",
            category="deployment",
            message=(
                f"`{key}` is declared under `{resource}` without a value, `sync: false`, or "
                "`generateValue`."
            ),
            why=(
                "A secret placeholder that is never populated can leave the deployed service with "
                "an empty credential, causing a runtime failure during the demo."
            ),
            remediation=(
                "Use `sync: false` so Render prompts for the value on creation, or "
                "`generateValue: true` for a generated secret."
            ),
            doc=doc,
            line=key_line,
            snippet=_snippet(doc, key_line, f"key: {key}"),
            docs_url=DOCS["render_env"],
            resource=resource,
        )
    )


def check_environment(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []

    for service, name, container in _services(doc):
        env_vars = service.get("envVars")
        if not isinstance(env_vars, list):
            continue
        resource = _label(name, container)
        for item in env_vars:
            if isinstance(item, dict):
                _check_env_item(
                    doc=doc, item=item, resource=resource, ctx=ctx, findings=findings
                )

    for group, name, container in _env_groups(doc):
        env_vars = group.get("envVars")
        if not isinstance(env_vars, list):
            continue
        resource = _label(f"{name} (env group)", container)
        for item in env_vars:
            if isinstance(item, dict):
                _check_env_item(
                    doc=doc, item=item, resource=resource, ctx=ctx, findings=findings
                )
    return findings


def check_service_readiness(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    for service, name, container in _services(doc):
        service_type = (get_str(service, "type") or "web").lower()
        runtime = (get_str(service, "runtime") or "").lower()
        resource = _label(name, container)
        service_line = meta_line(service, "type") or meta_line(service)

        ctx.tick()
        if not get_str(service, "type"):
            findings.append(
                base_finding(
                    rule_id="render-type-missing",
                    title="Service type is missing",
                    severity="high",
                    category="deployment",
                    message=f"`{resource}` has no `type`.",
                    why="Render needs a service type to provision the resource; the Blueprint will not validate.",
                    remediation="Set `type` to web, worker, cron, pserv, keyvalue, or workflow as appropriate.",
                    doc=doc,
                    line=service_line,
                    snippet=_snippet(doc, service_line, f"name: {name}"),
                    docs_url=DOCS["render_blueprint"],
                    resource=resource,
                )
            )
            continue

        if service_type in {"keyvalue", "redis"}:
            continue

        if not runtime:
            ctx.tick()
            findings.append(
                base_finding(
                    rule_id="render-runtime-missing",
                    title="Runtime is missing",
                    severity="medium",
                    category="deployment",
                    message=f"`{resource}` does not set `runtime`.",
                    why="Render needs a runtime (or Docker/image configuration) to build and start the service.",
                    remediation="Set `runtime` to the language/runtime used by the service.",
                    doc=doc,
                    line=service_line,
                    snippet=_snippet(doc, service_line, f"type: {service_type}"),
                    docs_url=DOCS["render_blueprint"],
                    resource=resource,
                )
            )

        if service_type == "web" and runtime == "static":
            if get_str(service, "plan"):
                ctx.tick()
                plan_line = meta_line(service, "plan")
                findings.append(
                    base_finding(
                        rule_id="render-static-plan",
                        title="Static sites do not use compute plans",
                        severity="low",
                        category="deployment",
                        message=f"Static site `{resource}` sets `plan`.",
                        why="Render static sites are served from a CDN and do not take a compute plan.",
                        remediation="Remove `plan` from the static site definition.",
                        doc=doc,
                        line=plan_line,
                        snippet=_snippet(doc, plan_line, "plan:"),
                        docs_url=DOCS["render_blueprint"],
                        resource=resource,
                    )
                )
            if not get_str(service, "staticPublishPath"):
                ctx.tick()
                findings.append(
                    base_finding(
                        rule_id="render-static-publish-path",
                        title="Static site publish path is missing",
                        severity="high",
                        category="deployment",
                        message=f"Static site `{resource}` has no `staticPublishPath`.",
                        why="Render needs to know which build output directory to serve.",
                        remediation="Set `staticPublishPath` to the generated directory (for example `./dist`).",
                        doc=doc,
                        line=service_line,
                        snippet=_snippet(doc, service_line, f"name: {name}"),
                        docs_url=DOCS["render_blueprint"],
                        resource=resource,
                    )
                )
            continue

        if service_type in {"web", "worker", "cron"} and runtime not in {"docker", "image"}:
            if not get_str(service, "startCommand"):
                ctx.tick()
                findings.append(
                    base_finding(
                        rule_id="render-start-command",
                        title="Start command is missing",
                        severity="high",
                        category="deployment",
                        message=f"`{resource}` has no `startCommand` for runtime `{runtime or 'unknown'}`.",
                        why="Native runtimes need an explicit process command; otherwise the deploy cannot start.",
                        remediation="Add the exact production start command, including the platform's port binding.",
                        doc=doc,
                        line=service_line,
                        snippet=_snippet(doc, service_line, f"type: {service_type}"),
                        docs_url=DOCS["render_blueprint"],
                        resource=resource,
                    )
                )

        if service_type == "cron" and not get_str(service, "schedule"):
            ctx.tick()
            findings.append(
                base_finding(
                    rule_id="render-cron-schedule",
                    title="Cron job schedule is missing",
                    severity="high",
                    category="deployment",
                    message=f"`{resource}` has no `schedule`.",
                    why="A cron job without a schedule cannot run and will fail Blueprint validation.",
                    remediation="Add a valid cron expression, or remove the cron service.",
                    doc=doc,
                    line=service_line,
                    snippet=_snippet(doc, service_line, f"type: {service_type}"),
                    docs_url=DOCS["render_blueprint"],
                    resource=resource,
                )
            )

        if service_type == "web" and runtime != "static":
            health = get_str(service, "healthCheckPath")
            if health is None:
                ctx.tick()
                findings.append(
                    base_finding(
                        rule_id="render-health-check",
                        title="No health check path configured",
                        severity="low",
                        category="deployment",
                        message=f"`{resource}` has no `healthCheckPath`.",
                        why=(
                            "Health checks help Render distinguish a cold start from a failed deploy. "
                            "Without one, diagnosis during a demo is harder."
                        ),
                        remediation="Expose a lightweight health endpoint and set `healthCheckPath` to it.",
                        doc=doc,
                        line=service_line,
                        snippet=_snippet(doc, service_line, f"name: {name}"),
                        docs_url=DOCS["render_health"],
                        resource=resource,
                    )
                )
            elif not health.startswith("/"):
                ctx.tick()
                health_line = meta_line(service, "healthCheckPath")
                findings.append(
                    base_finding(
                        rule_id="render-health-check-invalid",
                        title="Health check path is invalid",
                        severity="medium",
                        category="deployment",
                        message=f"`healthCheckPath` on `{resource}` does not start with `/`.",
                        why="Render requires a path beginning with `/`; the Blueprint will not validate.",
                        remediation="Use an absolute path such as `/api/health`.",
                        doc=doc,
                        line=health_line,
                        snippet=_snippet(doc, health_line, "healthCheckPath:"),
                        docs_url=DOCS["render_health"],
                        resource=resource,
                    )
                )
    return findings


RULES = (
    check_plans,
    check_disks,
    check_always_on,
    check_scaling,
    check_previews,
    check_free_web,
    check_databases,
    check_keyvalue,
    check_environment,
    check_service_readiness,
)
