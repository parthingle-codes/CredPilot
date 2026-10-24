"""Shared constants for the deterministic analysis engine."""

from __future__ import annotations

from typing import Literal

ENGINE_NAME = "credpilot-rules"
ENGINE_VERSION = "0.1.0"
RULES_VERSION = "2026.10.1"
ANALYSIS_VERSION = "1"

Format = Literal["render", "compose", "dotenv", "unknown"]
Severity = Literal["critical", "high", "medium", "low", "info"]
Category = Literal["billing", "deployment", "security", "cleanup"]
Priority = Literal["now", "before-demo", "after-demo"]
RiskLevel = Literal["clear", "low", "elevated", "high", "critical"]

FORMAT_LABELS: dict[Format, str] = {
    "render": "Render Blueprint",
    "compose": "Docker Compose",
    "dotenv": "Dotenv (.env)",
    "unknown": "Unrecognized",
}

SEVERITY_RANK: dict[Severity, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}

CATEGORY_RANK: dict[Category, int] = {
    "billing": 0,
    "security": 1,
    "deployment": 2,
    "cleanup": 3,
}

SEVERITY_WEIGHT: dict[Severity, int] = {
    "critical": 60,
    "high": 25,
    "medium": 10,
    "low": 3,
    "info": 0,
}

DOCS = {
    "render_free": "https://render.com/docs/free",
    "render_blueprint": "https://render.com/docs/blueprint-spec",
    "render_disks": "https://render.com/docs/disks",
    "render_scaling": "https://render.com/docs/scaling",
    "render_previews": "https://render.com/docs/preview-environments",
    "render_env": "https://render.com/docs/configure-environment-variables",
    "render_health": "https://render.com/docs/health-checks",
    "render_postgres": "https://render.com/docs/postgresql",
    "render_keyvalue": "https://render.com/docs/key-value",
    "compose_services": "https://docs.docker.com/reference/compose-file/services/",
    "compose_ports": "https://docs.docker.com/reference/compose-file/services/#ports",
    "compose_env": "https://docs.docker.com/reference/compose-file/services/#environment",
    "compose_volumes": "https://docs.docker.com/reference/compose-file/volumes/",
    "compose_resources": "https://docs.docker.com/reference/compose-file/deploy/#resources",
    "docker_security": "https://docs.docker.com/engine/security/",
    "vite_env": "https://vite.dev/guide/env-and-mode",
    "next_env": "https://nextjs.org/docs/app/guides/environment-variables",
    "hf_tokens": "https://huggingface.co/docs/hub/security-tokens",
    "github_remove_secret": (
        "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/"
        "removing-sensitive-data-from-a-repository"
    ),
    "mdn_cors": "https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS",
}

SENSITIVE_COMPOSE_PORTS: dict[str, str] = {
    "5432": "PostgreSQL",
    "3306": "MySQL/MariaDB",
    "6379": "Redis",
    "27017": "MongoDB",
    "27018": "MongoDB",
    "9200": "Elasticsearch",
    "5984": "CouchDB",
    "11211": "Memcached",
    "1433": "SQL Server",
}

DISCLAIMERS = [
    "CredPilot inspects configuration text only. It cannot see your provider account, "
    "usage, balance, quotas, or current prices.",
    "Findings are deterministic heuristics, not proof that a deployment is safe and "
    "not a prediction of charges or savings.",
    "No cloud resources are created, paused, or deleted. Every cleanup action is manual.",
    "Gemma explanations are optional, generated only from the findings shown, and do "
    "not add checks or verified facts.",
    "Never paste live production credentials. Use redacted values or the synthetic demo.",
]
