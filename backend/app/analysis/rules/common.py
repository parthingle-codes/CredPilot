"""Shared environment-variable checks used by all three formats."""

from __future__ import annotations

import re

from ..constants import DOCS, Category, Severity
from ...security import (
    contains_embedded_credentials,
    is_placeholder,
    is_public_client_key,
    is_weak_secret,
    looks_secret_key,
    redact_assignment,
    redact_text,
    redact_url_credentials,
    unique_provider_for_key,
)
from ..models import AnalysisContext, FindingDraft, ParsedDocument

TRUTHY = {"1", "true", "yes", "on", "y", "enabled"}
LOCAL_HOST_RE = re.compile(
    r"(?i)(?:localhost|127\.0\.0\.1|\[::1\]|0\.0\.0\.0)"
)
SQLITE_RE = re.compile(r"(?i)^sqlite(?:\+[a-z0-9]+)?:")
CORS_KEYS = {"CORS_ORIGINS", "CORS_ORIGIN", "ALLOWED_ORIGINS", "ALLOW_ORIGINS", "ORIGINS"}
HOST_KEYS = {"HOST", "BIND_HOST", "UVICORN_HOST", "FLASK_RUN_HOST", "SERVER_HOST"}
DEBUG_KEYS = {"DEBUG", "FLASK_DEBUG", "DJANGO_DEBUG", "APP_DEBUG", "NEXT_DEBUG"}


def evidence(doc: ParsedDocument, line: int | None, fallback: str) -> str:
    if line is not None and 1 <= line <= len(doc.lines):
        return redact_text(doc.lines[line - 1], max_length=220)
    return redact_text(fallback, max_length=220)


def base_finding(
    *,
    rule_id: str,
    title: str,
    severity: Severity,
    category: Category,
    message: str,
    why: str,
    remediation: str,
    doc: ParsedDocument,
    line: int | None,
    snippet: str,
    docs_url: str | None = None,
    resource: str | None = None,
) -> FindingDraft:
    return FindingDraft(
        rule_id=rule_id,
        title=title,
        severity=severity,
        category=category,
        message=message,
        why=why,
        remediation=remediation,
        file=doc.path,
        line=line,
        snippet=redact_text(snippet, max_length=240),
        docs_url=docs_url,
        resource=resource,
    )


def _truthy(value: str) -> bool:
    return value.strip().strip("\"'").lower() in TRUTHY


def _unquoted(value: str) -> str:
    return value.strip().strip("\"'")


def secret_finding(
    *,
    doc: ParsedDocument,
    key: str,
    value: object,
    line: int | None,
    resource: str | None,
    rule_id: str,
    source: str,
    remediation: str,
    is_example: bool = False,
) -> FindingDraft | None:
    """Create a hardcoded-credential finding, or None when not applicable."""
    if not looks_secret_key(key) or is_placeholder(value):
        return None
    text = str(value)
    if contains_embedded_credentials(text):
        # Handled once by common_env_checks with a URL-specific explanation.
        return None

    public = is_public_client_key(key)
    weak = is_weak_secret(text)

    if public:
        title = "Credential will be exposed in the client bundle"
        severity: Severity = "critical"
        message = (
            f"`{key}` uses a public client prefix and contains a non-placeholder value. "
            "Client-prefixed variables are embedded into browser JavaScript."
        )
        why = (
            "Anyone who loads the site can read the value. Rotating it later does not "
            "remove copies already downloaded or cached."
        )
        docs = DOCS["vite_env"]
    elif is_example:
        title = "Example env file contains a real-looking value"
        severity = "high"
        message = (
            f"`{key}` in an example file contains a value that is not a placeholder. "
            "Example files are commonly committed to Git."
        )
        why = (
            "If this is a live credential, it may already be in repository history and "
            "in every clone. CredPilot cannot tell whether the value is real."
        )
        docs = DOCS["github_remove_secret"]
    else:
        title = "Hardcoded credential in configuration"
        severity = "critical"
        message = (
            f"`{key}` contains a literal value in {source}. This puts the credential "
            "in the configuration file rather than a secret store."
        )
        why = (
            "Configuration is often committed to Git, shared in chat, or visible to "
            "everyone with dashboard access. A leaked key can authorize usage or data "
            "access outside this project."
        )
        docs = DOCS["github_remove_secret"]

    if weak:
        message += " The value also looks like a common or short default."
        why += " Predictable defaults are especially easy to guess if the service is reachable."

    return base_finding(
        rule_id=rule_id,
        title=title,
        severity=severity,
        category="security",
        message=message,
        why=why,
        remediation=remediation,
        doc=doc,
        line=line,
        snippet=redact_assignment(key, value),
        docs_url=docs,
        resource=resource or key,
    )


def common_env_checks(
    *,
    doc: ParsedDocument,
    key: str,
    value: object,
    line: int | None,
    resource: str | None,
    ctx: AnalysisContext,
    snippet: str | None = None,
) -> list[FindingDraft]:
    """Checks that make sense for Render, Compose, and dotenv values."""
    ctx.tick()
    value_text = "" if value is None else str(value).strip()
    lower_value = _unquoted(value_text).lower()
    upper_key = key.strip().upper()
    findings: list[FindingDraft] = []
    snippet_text = snippet or f"{key}={value_text}"

    if value_text and contains_embedded_credentials(value_text):
        findings.append(
            base_finding(
                rule_id="env-embedded-credentials",
                title="Password embedded in a connection URL",
                severity="critical",
                category="security",
                message=(
                    f"`{key}` includes a username and password inside the URL. "
                    "The password travels with the configuration value."
                ),
                why=(
                    "Connection strings are frequently logged, copied into issues, or "
                    "committed. A database password in the URL exposes the database even "
                    "if the password variable is handled separately."
                ),
                remediation=(
                    "Rotate the database password, remove it from the URL, and reference "
                    "a secret value from the platform. Redact the URL in screenshots and logs."
                ),
                doc=doc,
                line=line,
                snippet=redact_url_credentials(snippet_text),
                docs_url=DOCS["github_remove_secret"],
                resource=resource or key,
            )
        )

    provider = unique_provider_for_key(key)
    if (
        provider
        and value_text
        and not is_placeholder(value_text)
        and (doc.path, provider) not in ctx.metered_seen
    ):
        ctx.metered_seen.add((doc.path, provider))
        findings.append(
            base_finding(
                rule_id="env-metered-provider",
                title=f"Metered provider credential configured: {provider}",
                severity="low",
                category="billing",
                message=(
                    f"`{key}` authorizes {provider} usage. CredPilot cannot see the "
                    "account's plan, quota, balance, or current rates."
                ),
                why=(
                    "A configured provider key can authorize usage beyond a free allowance. "
                    "The billing risk depends on the provider account, which is outside this scan."
                ),
                remediation=(
                    "Confirm the current free quota in the provider dashboard, set a budget "
                    "or spend alert, and rotate the key after the demo if it was shared."
                ),
                doc=doc,
                line=line,
                snippet=f"{key}=<configured>",
                resource=resource or key,
            )
        )

    if upper_key in DEBUG_KEYS and _truthy(value_text):
        findings.append(
            base_finding(
                rule_id="env-debug-enabled",
                title="Debug mode is enabled",
                severity="medium",
                category="security",
                message=f"`{key}` is enabled in this configuration.",
                why=(
                    "Debug mode can expose stack traces, environment values, and interactive "
                    "debuggers. It is useful locally but risky on a public demo URL."
                ),
                remediation=(
                    "Set debug to false for the deployed environment and verify the deployed "
                    "response no longer includes tracebacks."
                ),
                doc=doc,
                line=line,
                snippet=snippet_text,
                resource=resource,
            )
        )

    if upper_key == "NODE_ENV" and lower_value in {"development", "test"}:
        findings.append(
            base_finding(
                rule_id="env-node-development",
                title="Node environment is not production",
                severity="medium",
                category="deployment",
                message=f"`NODE_ENV={_unquoted(value_text)}` in this configuration.",
                why=(
                    "Development mode can enable verbose errors, disable caching, and change "
                    "framework behavior compared with the production build."
                ),
                remediation="Set NODE_ENV=production for the deployed service and re-test the demo path.",
                doc=doc,
                line=line,
                snippet=snippet_text,
                resource=resource,
            )
        )

    if upper_key in CORS_KEYS and "*" in value_text:
        findings.append(
            base_finding(
                rule_id="env-cors-wildcard",
                title="CORS allows every origin",
                severity="high",
                category="security",
                message=f"`{key}` includes a wildcard origin.",
                why=(
                    "Any website can make browser requests to the API. This matters more if "
                    "the deployment later adds cookies, sessions, or user data."
                ),
                remediation=(
                    "List the exact frontend origin(s), including the deployed URL, and re-test "
                    "the browser flow."
                ),
                doc=doc,
                line=line,
                snippet=snippet_text,
                docs_url=DOCS["mdn_cors"],
                resource=resource,
            )
        )

    if upper_key in HOST_KEYS and (local_value := _unquoted(value_text).lower()):
        if local_value in {"127.0.0.1", "localhost", "::1"}:
            findings.append(
                base_finding(
                    rule_id="env-loopback-host",
                    title="Server is configured to bind only to loopback",
                    severity="high",
                    category="deployment",
                    message=f"`{key}={_unquoted(value_text)}` prevents external connections.",
                    why=(
                        "Most container hosts route public traffic to an address such as "
                        "0.0.0.0. A loopback bind can make a healthy process unreachable."
                    ),
                    remediation=(
                        "Bind to 0.0.0.0 (or the host provided by the platform) and keep the "
                        "port from the platform's PORT variable where applicable."
                    ),
                    doc=doc,
                    line=line,
                    snippet=snippet_text,
                    resource=resource,
                )
            )

    if value_text and LOCAL_HOST_RE.search(value_text):
        if "://" in value_text and upper_key not in HOST_KEYS:
            findings.append(
                base_finding(
                    rule_id="env-localhost-url",
                    title="Localhost URL will not reach the deployed service",
                    severity="medium",
                    category="deployment",
                    message=f"`{key}` points at a local address.",
                    why=(
                        "Inside a deployed container, localhost refers to that container. "
                        "A database or API on another host will be unreachable."
                    ),
                    remediation=(
                        "Replace it with the provider's private/internal hostname or a rendered "
                        "reference (for example, fromDatabase on Render)."
                    ),
                    doc=doc,
                    line=line,
                    snippet=snippet_text,
                    docs_url=DOCS["render_blueprint"],
                    resource=resource,
                )
            )

    if SQLITE_RE.search(_unquoted(value_text)) and ":memory:" not in value_text:
        findings.append(
            base_finding(
                rule_id="env-sqlite-ephemeral",
                title="SQLite file will not survive a container restart",
                severity="medium",
                category="deployment",
                message=f"`{key}` uses a SQLite file path.",
                why=(
                    "Local container filesystems are often ephemeral. A demo that writes to a "
                    "SQLite file can lose its data on redeploy, restart, or spin-down."
                ),
                remediation=(
                    "For demo data, seed it on startup or use a managed database. If the file "
                    "must persist, attach a persistent disk and back it up."
                ),
                doc=doc,
                line=line,
                snippet=snippet_text,
                docs_url=DOCS["render_free"],
                resource=resource,
            )
        )

    return findings
