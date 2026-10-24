"""Analysis orchestration: parse -> deterministic rules -> evidence -> tasks."""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone

from ..models import (
    AnalysisResponse,
    CleanupTask,
    EngineInfo,
    Evidence,
    Finding,
    ParseNote,
    Summary,
)
from ..security import redact_text
from .constants import (
    ANALYSIS_VERSION,
    CATEGORY_RANK,
    DISCLAIMERS,
    ENGINE_NAME,
    ENGINE_VERSION,
    FORMAT_LABELS,
    RULES_VERSION,
    SEVERITY_RANK,
    SEVERITY_WEIGHT,
)
from .models import AnalysisContext, FindingDraft, SourceFile
from .parsers import parse_file
from .parsers.detect import normalize_path
from .rules import RULES

PRIORITY_ORDER = {"now": 0, "before-demo": 1, "after-demo": 2}
TASK_SEVERITIES = {"critical", "high", "medium"}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def fingerprint(files: list[SourceFile]) -> str:
    chunks = sorted(f"{file.path}\0{file.content}" for file in files)
    digest = hashlib.sha256(
        (ANALYSIS_VERSION + "\0" + RULES_VERSION + "\0" + "\0".join(chunks)).encode(
            "utf-8"
        )
    ).hexdigest()
    return digest[:16]


def _task_id(title: str, source: str | None, file: str | None) -> str:
    digest = hashlib.sha1(f"{title}|{source}|{file}".encode("utf-8")).hexdigest()[:10]
    return f"task-{digest}"


def _risk_level(score: int) -> str:
    if score <= 0:
        return "clear"
    if score <= 19:
        return "low"
    if score <= 44:
        return "elevated"
    if score <= 74:
        return "high"
    return "critical"


def _parse_error_draft(doc) -> FindingDraft:
    return FindingDraft(
        rule_id="parse-error",
        title="Configuration could not be parsed",
        severity="high",
        category="deployment",
        message=(
            f"`{doc.path}` has a YAML syntax or shape error"
            + (f" near line {doc.error_line}." if doc.error_line else ".")
        ),
        why=(
            "Unparsed configuration is not checked. This file could still contain billing or "
            "security problems that are absent from the results below."
        ),
        remediation=(
            "Fix the syntax or structure, then run the pre-flight check again. Use the Render "
            "CLI or Docker Compose config validation for a second opinion."
        ),
        file=doc.path,
        line=doc.error_line,
        snippet="",
        docs_url="https://render.com/docs/blueprint-spec"
        if doc.format == "render"
        else "https://docs.docker.com/reference/compose-file/",
        resource=None,
    )


def _unsupported_draft(doc) -> FindingDraft:
    return FindingDraft(
        rule_id="unsupported-format",
        title="File format was not checked",
        severity="medium",
        category="deployment",
        message=(
            f"`{doc.path}` is not a recognized Render Blueprint, Docker Compose, or .env file."
        ),
        why=(
            "An unchecked file can hide billing or security problems. A low score here does "
            "not mean the deployment is safe."
        ),
        remediation=(
            "Submit `render.yaml`, `docker-compose.yml`, or `.env`, or review this file manually. "
            "Rename the file if it is one of the supported formats."
        ),
        file=doc.path,
        line=1,
        snippet="",
        resource=None,
    )


def _cleanup_tasks(findings: list[Finding]) -> list[CleanupTask]:
    tasks: dict[str, CleanupTask] = {}

    def add(
        *,
        title: str,
        detail: str,
        priority: str,
        category: str,
        source: str | None = None,
        file: str | None = None,
        line: int | None = None,
    ) -> None:
        identifier = _task_id(title, source, file)
        if identifier in tasks:
            return
        tasks[identifier] = CleanupTask(
            id=identifier,
            title=title,
            detail=detail,
            priority=priority,  # type: ignore[arg-type]
            category=category,  # type: ignore[arg-type]
            source_finding_id=source,
            evidence_file=file,
            evidence_line=line,
        )

    for finding in findings:
        if finding.severity not in TASK_SEVERITIES:
            continue
        location = finding.evidence.file + (
            f":{finding.evidence.line}" if finding.evidence.line else ""
        )
        resource = finding.resource or "this resource"

        if finding.category == "security":
            if finding.rule_id in {
                "dotenv-secret-value",
                "render-secret-value",
                "compose-secret-value",
                "env-embedded-credentials",
            }:
                add(
                    title=f"Rotate exposed credential in {resource}",
                    detail=(
                        f"{finding.title}. Evidence: {location}. Remove the value from the "
                        "configuration, rotate it in the provider dashboard, and verify old "
                        "copies are invalid. CredPilot does not rotate credentials."
                    ),
                    priority="now",
                    category="security",
                    source=finding.id,
                    file=finding.evidence.file,
                    line=finding.evidence.line,
                )
            elif finding.rule_id == "compose-docker-socket":
                add(
                    title="Remove Docker socket mount",
                    detail=(
                        f"Evidence: {location}. The Docker socket is root-equivalent host access. "
                        "Remove the mount before sharing or deploying the stack."
                    ),
                    priority="now",
                    category="security",
                    source=finding.id,
                    file=finding.evidence.file,
                    line=finding.evidence.line,
                )
            elif finding.rule_id == "compose-privileged":
                add(
                    title="Remove privileged container mode",
                    detail=(
                        f"Evidence: {location}. Drop `privileged: true` and add only the "
                        "capabilities the demo needs."
                    ),
                    priority="now",
                    category="security",
                    source=finding.id,
                    file=finding.evidence.file,
                    line=finding.evidence.line,
                )
            elif finding.rule_id in {"env-cors-wildcard"}:
                add(
                    title="Restrict CORS to known origins",
                    detail=(
                        f"Evidence: {location}. Replace the wildcard with the deployed frontend "
                        "origin and re-test the browser flow."
                    ),
                    priority="before-demo",
                    category="security",
                    source=finding.id,
                    file=finding.evidence.file,
                    line=finding.evidence.line,
                )
            else:
                add(
                    title=f"Review security finding: {finding.title}",
                    detail=f"Evidence: {location}. Review the finding before deploying.",
                    priority="before-demo",
                    category="security",
                    source=finding.id,
                    file=finding.evidence.file,
                    line=finding.evidence.line,
                )
        elif finding.category == "billing":
            add(
                title=f"Confirm billing exposure: {resource}",
                detail=(
                    f"{finding.title}. Evidence: {location}. Confirm the current plan and limits "
                    "in the provider dashboard, then choose a cleanup action. CredPilot has no "
                    "access to prices, balances, or usage."
                ),
                priority="before-demo",
                category="billing",
                source=finding.id,
                file=finding.evidence.file,
                line=finding.evidence.line,
            )
        elif finding.category == "deployment":
            if finding.rule_id == "render-free-spindown":
                add(
                    title="Warm up the demo URL before presenting",
                    detail=(
                        "Open the deployed URL a few minutes before judging and keep a local "
                        "fallback. Free Render services spin down after inactivity."
                    ),
                    priority="before-demo",
                    category="deployment",
                    source=finding.id,
                    file=finding.evidence.file,
                    line=finding.evidence.line,
                )
            elif finding.rule_id == "render-database-free-expiry":
                add(
                    title="Export data before the free database expires",
                    detail=(
                        f"Evidence: {location}. Free Render databases expire after 30 days plus a "
                        "14-day grace period. Export anything you need or upgrade deliberately."
                    ),
                    priority="after-demo",
                    category="deployment",
                    source=finding.id,
                    file=finding.evidence.file,
                    line=finding.evidence.line,
                )
            elif finding.rule_id in {"parse-error", "unsupported-format"}:
                add(
                    title=f"Review unchecked file: {finding.evidence.file}",
                    detail=(
                        f"{finding.title}. Fix the file or review it manually; no rule results "
                        "cover it yet."
                    ),
                    priority="before-demo",
                    category="deployment",
                    source=finding.id,
                    file=finding.evidence.file,
                    line=finding.evidence.line,
                )
            elif finding.rule_id in {"env-localhost-url", "env-loopback-host"}:
                add(
                    title="Fix deployed host and service URLs",
                    detail=(
                        f"Evidence: {location}. Replace localhost or loopback bindings with the "
                        "platform's host/port and private service addresses."
                    ),
                    priority="before-demo",
                    category="deployment",
                    source=finding.id,
                    file=finding.evidence.file,
                    line=finding.evidence.line,
                )
            else:
                add(
                    title=f"Resolve deployment limitation: {finding.title}",
                    detail=f"Evidence: {location}. Fix or explicitly accept this limitation before the demo.",
                    priority="before-demo",
                    category="deployment",
                    source=finding.id,
                    file=finding.evidence.file,
                    line=finding.evidence.line,
                )
        elif finding.category == "cleanup":
            add(
                title=f"Complete cleanup: {finding.title}",
                detail=f"Evidence: {location}. Remove demo data and resources deliberately after judging.",
                priority="after-demo",
                category="cleanup",
                source=finding.id,
                file=finding.evidence.file,
                line=finding.evidence.line,
            )

    # Always-useful tasks, independent of what the rules found.
    add(
        title="Set provider budget or spend alerts",
        detail=(
            "Open each provider's billing settings and enable an alert or budget. CredPilot "
            "cannot see balances, prices, or usage; this is a manual verification step."
        ),
        priority="before-demo",
        category="billing",
    )
    add(
        title="Confirm secret files are gitignored",
        detail=(
            "Run `git status` and verify `.env` and other real credential files are ignored. "
            "If a secret was committed, rotate it and clean history."
        ),
        priority="before-demo",
        category="security",
    )
    add(
        title="Delete or pause demo services after judging",
        detail=(
            "Check every resource type: web services, workers, cron jobs, databases, disks, "
            "Key Value instances, and preview environments. Deleting an app may not delete its database."
        ),
        priority="after-demo",
        category="cleanup",
    )
    add(
        title="Remove demo data and shared credentials",
        detail=(
            "Delete test uploads, seed data, and any API key shared in a public repo, chat, or "
            "recording. Rotate keys that were visible to others."
        ),
        priority="after-demo",
        category="security",
    )
    add(
        title="Re-run CredPilot after cleanup",
        detail=(
            "Run the updated configuration through the analyzer and confirm the remaining findings "
            "are intentional. A clear rule result is not a guarantee of zero charges."
        ),
        priority="after-demo",
        category="cleanup",
    )

    return sorted(
        tasks.values(),
        key=lambda task: (
            PRIORITY_ORDER.get(task.priority, 9),
            task.category,
            task.title.lower(),
        ),
    )


def analyze(
    files: list[SourceFile],
    *,
    project_name: str = "My hackathon project",
) -> AnalysisResponse:
    if not files:
        raise ValueError("at least one file is required")

    normalized_files = [
        SourceFile(path=normalize_path(file.path), content=file.content) for file in files
    ]
    ctx = AnalysisContext(file_paths={file.path for file in normalized_files})
    drafts: list[FindingDraft] = []
    parse_notes: list[ParseNote] = []
    formats: list[str] = []
    docs = []

    for source in normalized_files:
        ctx.tick()  # Count the format/parse pass for every submitted file.
        doc = parse_file(source)
        docs.append(doc)
        label = FORMAT_LABELS[doc.format]
        if label not in formats:
            formats.append(label)

        if doc.format == "unknown":
            parse_notes.append(
                ParseNote(
                    file=doc.path,
                    format=doc.format,
                    format_label=label,
                    ok=False,
                    message=doc.note,
                )
            )
            drafts.append(_unsupported_draft(doc))
            continue

        if doc.error:
            parse_notes.append(
                ParseNote(
                    file=doc.path,
                    format=doc.format,
                    format_label=label,
                    ok=False,
                    message=doc.note or doc.error,
                )
            )
            drafts.append(_parse_error_draft(doc))
            continue

        parse_notes.append(
            ParseNote(
                file=doc.path,
                format=doc.format,
                format_label=label,
                ok=True,
                message=doc.note,
            )
        )
        for rule in RULES[doc.format]:
            drafts.extend(rule(doc, ctx))

    # Deduplicate identical rule results, then sort deterministically.
    unique: list[FindingDraft] = []
    seen: set[tuple] = set()
    for draft in drafts:
        key = (draft.rule_id, draft.file, draft.line, draft.resource, draft.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(draft)

    unique.sort(
        key=lambda draft: (
            SEVERITY_RANK[draft.severity],
            CATEGORY_RANK[draft.category],
            draft.file.lower(),
            draft.line if draft.line is not None else 10**9,
            draft.title.lower(),
        )
    )

    findings: list[Finding] = []
    for index, draft in enumerate(unique, start=1):
        snippet = redact_text(draft.snippet, max_length=220)
        findings.append(
            Finding(
                id=f"F-{index:02d}",
                rule_id=draft.rule_id,
                title=draft.title,
                severity=draft.severity,
                category=draft.category,
                message=draft.message,
                why=draft.why,
                remediation=draft.remediation,
                evidence=Evidence(
                    file=draft.file,
                    line=draft.line,
                    snippet=snippet,
                ),
                docs_url=draft.docs_url,
                resource=draft.resource,
            )
        )

    counts = Counter(finding.severity for finding in findings)
    score = min(100, sum(SEVERITY_WEIGHT[finding.severity] for finding in findings))
    summary = Summary(
        score=score,
        risk_level=_risk_level(score),  # type: ignore[arg-type]
        counts={
            "critical": counts["critical"],
            "high": counts["high"],
            "medium": counts["medium"],
            "low": counts["low"],
            "info": counts["info"],
        },
        findings_total=len(findings),
        checks_run=ctx.checks,
        files_analyzed=len(docs),
        formats=formats,
    )

    return AnalysisResponse(
        project_name=project_name,
        generated_at=_iso_now(),
        fingerprint=fingerprint(normalized_files),
        engine=EngineInfo(
            name=ENGINE_NAME,
            version=ENGINE_VERSION,
            rules_version=RULES_VERSION,
        ),
        summary=summary,
        findings=findings,
        cleanup_tasks=_cleanup_tasks(findings),
        parse_notes=parse_notes,
        disclaimers=DISCLAIMERS,
    )
