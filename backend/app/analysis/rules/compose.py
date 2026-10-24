"""Docker Compose rules (docker-compose.yml / compose.yaml)."""

from __future__ import annotations

import re
from typing import Any

from ..constants import DOCS, SENSITIVE_COMPOSE_PORTS
from ...security import (
    contains_embedded_credentials,
    is_placeholder,
    looks_secret_key,
    redact_text,
)
from ..models import AnalysisContext, FindingDraft, ParsedDocument
from ..parsers.detect import normalize_path
from ..parsers.lines import find_line, line_at, meta_line
from .common import base_finding, common_env_checks, secret_finding

COMPOSE_SECRET_REMEDIATION = (
    "Do not put the literal in the Compose file. Read it from the host environment "
    "(for example `${POSTGRES_PASSWORD}`), keep the real .env out of Git, and rotate "
    "the credential. If the stack was deployed, rotate it immediately."
)


def _services(doc: ParsedDocument):
    services = (doc.data or {}).get("services")
    if not isinstance(services, dict):
        return
    for name, service in services.items():
        if name in {"__line__", "__lines__"}:
            continue
        if isinstance(service, dict):
            yield name, service, services


def _snippet(doc: ParsedDocument, line: int | None, fallback: str) -> str:
    return line_at(doc.lines, line) or fallback


def _service_line(services: dict[str, Any], name: str) -> int | None:
    return meta_line(services, name)


def _port_line(
    doc: ParsedDocument,
    service: dict[str, Any],
    raw: str,
    start: int | None,
    fallback_line: int | None,
) -> int | None:
    found = find_line(doc.lines, re.escape(raw), start=start or 1)
    if found:
        return found
    stripped = raw.strip().strip("\"'")
    if stripped != raw:
        found = find_line(doc.lines, re.escape(stripped), start=start or 1)
        if found:
            return found
    return meta_line(service, "ports") or fallback_line


def check_ports(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    for name, service, services in _services(doc):
        ports = service.get("ports")
        if not isinstance(ports, list):
            continue
        service_start = _service_line(services, name)
        seen: set[str] = set()

        for item in ports:
            container_port: int | None = None
            host_ip = ""
            raw = ""

            if isinstance(item, dict):
                target = item.get("target")
                published = item.get("published")
                host_ip = str(item.get("host_ip") or "")
                try:
                    container_port = int(str(target))
                except (TypeError, ValueError):
                    continue
                raw = f"{host_ip + ':' if host_ip else ''}{published or ''}:{target}"
                line = (
                    meta_line(item, "published")
                    or meta_line(item, "target")
                    or meta_line(item, "host_ip")
                )
            elif isinstance(item, (str, int)):
                raw = str(item)
                spec = raw.split("/", 1)[0].strip().strip("\"'")
                parts = spec.split(":")
                container_text = parts[-1]
                try:
                    container_port = int(container_text)
                except ValueError:
                    continue
                if len(parts) >= 3:
                    host_ip = parts[0]
                line = None
            else:
                continue

            if container_port is None:
                continue
            db_name = SENSITIVE_COMPOSE_PORTS.get(str(container_port))
            if not db_name:
                continue
            if host_ip.strip().strip("[]").lower() in {"127.0.0.1", "localhost", "::1"}:
                continue
            if str(container_port) in seen:
                continue
            seen.add(str(container_port))

            ctx.tick()
            evidence_line = (
                line
                if "line" in locals() and line
                else _port_line(doc, service, raw, service_start, service_start)
            )
            findings.append(
                base_finding(
                    rule_id="compose-published-datastore",
                    title=f"{db_name} port is published on the host",
                    severity="high",
                    category="security",
                    message=(
                        f"Compose service `{name}` publishes container port {container_port} "
                        f"({db_name})."
                    ),
                    why=(
                        "A published port is reachable through the host's network interfaces. "
                        "Docker port forwarding can bypass assumptions about host firewall rules, "
                        "so on a cloud VM this should be treated as internet-exposed until proven otherwise."
                    ),
                    remediation=(
                        "Remove the host-side port mapping and let other containers use the Compose "
                        "network. If host access is required, bind to `127.0.0.1` and keep the "
                        "datastore credentials private."
                    ),
                    doc=doc,
                    line=evidence_line,
                    snippet=_snippet(
                        doc, evidence_line, f'- "{raw}"'
                    ),
                    docs_url=DOCS["compose_ports"],
                    resource=name,
                )
            )
    return findings


def _env_pairs(
    doc: ParsedDocument,
    name: str,
    service: dict[str, Any],
    services: dict[str, Any],
) -> list[tuple[str, str, int | None]]:
    pairs: list[tuple[str, str, int | None]] = []
    environment = service.get("environment")
    service_start = _service_line(services, name)

    if isinstance(environment, dict):
        for key, value in environment.items():
            if key in {"__line__", "__lines__"}:
                continue
            if value is None:
                continue
            line = meta_line(environment, key) or meta_line(service, "environment")
            pairs.append((str(key), str(value), line))
    elif isinstance(environment, list):
        for item in environment:
            if not isinstance(item, str) or "=" not in item:
                continue
            key, value = item.split("=", 1)
            key = key.strip()
            value = value.strip()
            line = find_line(doc.lines, re.escape(item), start=service_start or 1)
            if line is None:
                line = find_line(
                    doc.lines,
                    rf"^\s*-\s*[\"']?{re.escape(key)}=",
                    start=service_start or 1,
                )
            pairs.append((key, value, line or meta_line(service, "environment")))
    return pairs


def check_environment(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    for name, service, services in _services(doc):
        for key, value, line in _env_pairs(doc, name, service, services):
            snippet = f"{key}={value}"
            findings.extend(
                common_env_checks(
                    doc=doc,
                    key=key,
                    value=value,
                    line=line,
                    resource=name,
                    ctx=ctx,
                    snippet=snippet,
                )
            )
            if contains_embedded_credentials(value):
                continue
            finding = secret_finding(
                doc=doc,
                key=key,
                value=value,
                line=line,
                resource=name,
                rule_id="compose-secret-value",
                source="the Compose service environment",
                remediation=COMPOSE_SECRET_REMEDIATION,
            )
            if finding:
                findings.append(finding)

        env_file = service.get("env_file")
        files: list[str] = []
        if isinstance(env_file, str):
            files = [env_file]
        elif isinstance(env_file, list):
            files = [str(item) for item in env_file if isinstance(item, (str, int))]
        for env_path in files:
            normalized = normalize_path(env_path)
            if normalized in ctx.file_paths:
                continue
            ctx.tick()
            line = meta_line(service, "env_file") or meta_line(service)
            findings.append(
                base_finding(
                    rule_id="compose-env-file-unchecked",
                    title="Environment file is outside this scan",
                    severity="info",
                    category="security",
                    message=(
                        f"Compose service `{name}` loads environment values from `{env_path}`, "
                        "which is not one of the submitted files."
                    ),
                    why=(
                        "CredPilot cannot inspect values that are not submitted. A real .env file "
                        "may contain committed or reused credentials."
                    ),
                    remediation=(
                        "Confirm the file is gitignored and injected at deploy time. To check it, "
                        "submit a redacted copy in the .env tab."
                    ),
                    doc=doc,
                    line=line,
                    snippet=_snippet(doc, line, f"env_file: {env_path}"),
                    docs_url=DOCS["compose_env"],
                    resource=name,
                )
            )
    return findings


def check_images(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    for name, service, services in _services(doc):
        image = service.get("image")
        if not isinstance(image, str) or not image.strip():
            continue
        image = image.strip()
        if "@sha256:" in image:
            continue
        last = image.rsplit("/", 1)[-1]
        if ":" not in last or last.rsplit(":", 1)[-1].lower() == "latest":
            ctx.tick()
            line = meta_line(service, "image")
            findings.append(
                base_finding(
                    rule_id="compose-image-unpinned",
                    title="Container image is not pinned to a version",
                    severity="medium",
                    category="deployment",
                    message=f"Compose service `{name}` uses image `{image}` without a fixed version.",
                    why=(
                        "An untagged or `latest` image can change between the test run and the demo. "
                        "A newly published image can break the deploy with no code change."
                    ),
                    remediation=(
                        "Pin a specific version tag or digest for the demo, then update it deliberately."
                    ),
                    doc=doc,
                    line=line,
                    snippet=_snippet(doc, line, f"image: {image}"),
                    docs_url=DOCS["compose_services"],
                    resource=name,
                )
            )
    return findings


def _has_limits(service: dict[str, Any]) -> bool:
    if service.get("mem_limit") or service.get("cpus"):
        return True
    deploy = service.get("deploy")
    if not isinstance(deploy, dict):
        return False
    resources = deploy.get("resources")
    if not isinstance(resources, dict):
        return False
    limits = resources.get("limits")
    return isinstance(limits, dict) and bool(
        limits.get("cpus") or limits.get("memory") or limits.get("pids")
    )


def check_resource_limits(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    for name, service, services in _services(doc):
        if not service.get("image") and not service.get("build"):
            continue
        if _has_limits(service):
            continue
        ctx.tick()
        line = meta_line(service, "deploy") or _service_line(services, name)
        findings.append(
            base_finding(
                rule_id="compose-no-resource-limits",
                title="No CPU or memory limit",
                severity="low",
                category="billing",
                message=f"Compose service `{name}` has no CPU or memory limit.",
                why=(
                    "A memory leak, retry loop, or runaway indexer can consume the whole host. "
                    "On a cloud VM, that can consume paid capacity and make the demo unresponsive."
                ),
                remediation=(
                    "Add `deploy.resources.limits` (CPU/memory) for the cloud deployment, or set "
                    "`mem_limit`/`cpus` where supported."
                ),
                doc=doc,
                line=line,
                snippet=_snippet(doc, line, f"{name}:"),
                docs_url=DOCS["compose_resources"],
                resource=name,
            )
        )
    return findings


def check_isolation(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    for name, service, services in _services(doc):
        if service.get("privileged") is True:
            ctx.tick()
            line = meta_line(service, "privileged")
            findings.append(
                base_finding(
                    rule_id="compose-privileged",
                    title="Container runs in privileged mode",
                    severity="high",
                    category="security",
                    message=f"Compose service `{name}` sets `privileged: true`.",
                    why=(
                        "A privileged container has broad access to host devices and kernel "
                        "capabilities. A vulnerable demo container becomes a host compromise."
                    ),
                    remediation=(
                        "Remove `privileged: true` and add only the specific Linux capabilities the "
                        "service needs."
                    ),
                    doc=doc,
                    line=line,
                    snippet=_snippet(doc, line, "privileged: true"),
                    docs_url=DOCS["docker_security"],
                    resource=name,
                )
            )

        network_mode = service.get("network_mode")
        if isinstance(network_mode, str) and network_mode.strip().lower() == "host":
            ctx.tick()
            line = meta_line(service, "network_mode")
            findings.append(
                base_finding(
                    rule_id="compose-host-network",
                    title="Container shares the host network",
                    severity="high",
                    category="security",
                    message=f"Compose service `{name}` uses `network_mode: host`.",
                    why=(
                        "Host networking removes the container network boundary. Every listening "
                        "port is exposed according to the host's network and firewall configuration."
                    ),
                    remediation=(
                        "Use the default Compose network and publish only the specific port that "
                        "must be reachable."
                    ),
                    doc=doc,
                    line=line,
                    snippet=_snippet(doc, line, "network_mode: host"),
                    docs_url=DOCS["docker_security"],
                    resource=name,
                )
            )

        volumes = service.get("volumes")
        if not isinstance(volumes, list):
            continue
        for volume in volumes:
            source = ""
            target = ""
            line: int | None = None
            if isinstance(volume, str):
                parts = volume.split(":")
                source = parts[0] if len(parts) > 1 else ""
                target = parts[1] if len(parts) > 1 else parts[0]
                line = find_line(doc.lines, re.escape(volume), start=_service_line(services, name) or 1)
            elif isinstance(volume, dict):
                source = str(volume.get("source") or "")
                target = str(volume.get("target") or "")
                line = meta_line(volume, "target") or meta_line(volume, "source")
            if "/var/run/docker.sock" in source or "/var/run/docker.sock" in target:
                ctx.tick()
                findings.append(
                    base_finding(
                        rule_id="compose-docker-socket",
                        title="Docker socket is mounted into a container",
                        severity="critical",
                        category="security",
                        message=f"Compose service `{name}` mounts the host Docker socket.",
                        why=(
                            "Access to the Docker socket is effectively root access to the host. "
                            "Any code execution in that container can control every other container."
                        ),
                        remediation=(
                            "Remove the socket mount. If the demo needs Docker control, use a "
                            "dedicated, isolated runner rather than mounting the host socket."
                        ),
                        doc=doc,
                        line=line or meta_line(service, "volumes"),
                        snippet=_snippet(
                            doc,
                            line or meta_line(service, "volumes"),
                            "volumes: /var/run/docker.sock",
                        ),
                        docs_url=DOCS["docker_security"],
                        resource=name,
                    )
                )
    return findings


def check_cleanup(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    for name, service, services in _services(doc):
        volumes = service.get("volumes")
        if isinstance(volumes, list) and volumes:
            ctx.tick()
            line = meta_line(service, "volumes")
            findings.append(
                base_finding(
                    rule_id="compose-persistent-volumes",
                    title="Persistent data will outlive the demo",
                    severity="low",
                    category="cleanup",
                    message=f"Compose service `{name}` mounts {len(volumes)} volume(s).",
                    why=(
                        "Named volumes survive a normal `docker compose down`, and bind mounts write "
                        "directly to the host. Demo databases and uploads can remain after the event."
                    ),
                    remediation=(
                        "Back up anything you need, then remove disposable data deliberately. "
                        "`docker compose down -v` deletes named/anonymous volumes and is destructive."
                    ),
                    doc=doc,
                    line=line,
                    snippet=_snippet(doc, line, "volumes:"),
                    docs_url=DOCS["compose_volumes"],
                    resource=name,
                )
            )

        restart = service.get("restart")
        if isinstance(restart, str) and restart.strip().lower() in {"always", "unless-stopped"}:
            ctx.tick()
            line = meta_line(service, "restart")
            findings.append(
                base_finding(
                    rule_id="compose-restart-policy",
                    title="Container restarts automatically",
                    severity="low",
                    category="cleanup",
                    message=f"Compose service `{name}` uses `restart: {restart}`.",
                    why=(
                        "The container can restart after a crash, daemon restart, or host reboot. "
                        "On a cloud VM, a forgotten demo stack can stay active after judging."
                    ),
                    remediation=(
                        "Stop the stack explicitly during cleanup and terminate any cloud VM. Use "
                        "the restart policy only where the service needs it."
                    ),
                    doc=doc,
                    line=line,
                    snippet=_snippet(doc, line, f"restart: {restart}"),
                    docs_url=DOCS["compose_services"],
                    resource=name,
                )
            )
    return findings


def check_scaling(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    for name, service, services in _services(doc):
        deploy = service.get("deploy")
        if not isinstance(deploy, dict):
            continue
        replicas = deploy.get("replicas")
        if isinstance(replicas, bool):
            continue
        if isinstance(replicas, int) and replicas > 1:
            ctx.tick()
            line = meta_line(deploy, "replicas") or meta_line(service, "deploy")
            findings.append(
                base_finding(
                    rule_id="compose-replicas",
                    title="Multiple container replicas configured",
                    severity="medium",
                    category="billing",
                    message=f"Compose service `{name}` requests {replicas} replicas.",
                    why=(
                        "Each replica consumes resources on the target host. A cloud deployment can "
                        "scale the demo beyond what the team intended."
                    ),
                    remediation=(
                        "Use one replica for the demo unless load testing requires more, and verify "
                        "the running container count during cleanup."
                    ),
                    doc=doc,
                    line=line,
                    snippet=_snippet(doc, line, "replicas:"),
                    docs_url=DOCS["compose_resources"],
                    resource=name,
                )
            )
    return findings


def check_required(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    for name, service, services in _services(doc):
        if service.get("image") or service.get("build"):
            continue
        ctx.tick()
        line = _service_line(services, name)
        findings.append(
            base_finding(
                rule_id="compose-missing-image",
                title="Service has neither an image nor a build context",
                severity="high",
                category="deployment",
                message=f"Compose service `{name}` has no `image` and no `build`.",
                why="Compose cannot create this container, so the demo stack will not start.",
                remediation="Add a versioned `image` or a `build` context with a Dockerfile.",
                doc=doc,
                line=line,
                snippet=_snippet(doc, line, f"{name}:"),
                docs_url=DOCS["compose_services"],
                resource=name,
            )
        )
    return findings


RULES = (
    check_ports,
    check_environment,
    check_images,
    check_resource_limits,
    check_isolation,
    check_cleanup,
    check_scaling,
    check_required,
)
