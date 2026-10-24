"""Dotenv rules (.env and friends)."""

from __future__ import annotations

from collections import defaultdict

from ..constants import DOCS
from ...security import contains_embedded_credentials
from ..models import AnalysisContext, FindingDraft, ParsedDocument
from ..parsers.detect import basename
from .common import base_finding, common_env_checks, secret_finding

EXAMPLE_NAMES = {".env.example", ".env.sample", ".env.template", ".env.dist"}

DOTENV_SECRET_REMEDIATION = (
    "Remove the value from the file, rotate it at the provider, and keep the real .env "
    "out of Git. On Render, use `sync: false` so the value is entered in the dashboard."
)


def _is_example(doc: ParsedDocument) -> bool:
    return basename(doc.path) in EXAMPLE_NAMES


def check_environment(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    example = _is_example(doc)

    for entry in doc.env_entries:
        if not example:
            findings.extend(
                common_env_checks(
                    doc=doc,
                    key=entry.key,
                    value=entry.value,
                    line=entry.line,
                    resource=basename(doc.path),
                    ctx=ctx,
                    snippet=entry.raw,
                )
            )

        if contains_embedded_credentials(entry.value):
            continue
        finding = secret_finding(
            doc=doc,
            key=entry.key,
            value=entry.value,
            line=entry.line,
            resource=basename(doc.path),
            rule_id="dotenv-secret-value",
            source="this dotenv file",
            remediation=DOTENV_SECRET_REMEDIATION,
            is_example=example,
        )
        if finding:
            findings.append(finding)

    return findings


def check_duplicates(doc: ParsedDocument, ctx: AnalysisContext) -> list[FindingDraft]:
    findings: list[FindingDraft] = []
    grouped: dict[str, list] = defaultdict(list)
    for entry in doc.env_entries:
        grouped[entry.key.upper()].append(entry)

    for key, entries in grouped.items():
        if len(entries) < 2:
            continue
        ctx.tick()
        duplicate = entries[-1]
        findings.append(
            base_finding(
                rule_id="dotenv-duplicate-key",
                title="Duplicate environment variable",
                severity="low",
                category="deployment",
                message=(
                    f"`{key}` is defined {len(entries)} times. The effective value depends on "
                    "the loader; some tools keep the first one and others keep the last."
                ),
                why=(
                    "A value changed at the bottom of the file may not take effect, or a real "
                    "value may be masked by an earlier placeholder."
                ),
                remediation="Keep one definition per key and remove stale copies.",
                doc=doc,
                line=duplicate.line,
                snippet=duplicate.raw,
                docs_url=DOCS["render_env"],
                resource=basename(doc.path),
            )
        )
    return findings


RULES = (
    check_environment,
    check_duplicates,
)
