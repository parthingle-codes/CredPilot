"""File format detection and path normalization."""

from __future__ import annotations

import re

from ..constants import Format

ENV_LINE_RE = re.compile(
    r"^\s*(?:export\s+)?[A-Za-z_][A-Za-z0-9_.-]*\s*=", re.MULTILINE
)


def normalize_path(path: str) -> str:
    cleaned = path.strip().replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    cleaned = re.sub(r"/+", "/", cleaned)
    return cleaned


def basename(path: str) -> str:
    return normalize_path(path).rsplit("/", 1)[-1].lower()


def detect_format(path: str, content: str) -> Format:
    name = basename(path)

    if name in {"render.yaml", "render.yml"}:
        return "render"
    if name in {
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
    } or name.startswith("docker-compose."):
        return "compose"
    if name == ".env" or name.startswith(".env.") or name.endswith(".env"):
        return "dotenv"

    # Unknown filename: infer from structure. YAML detection comes first so a
    # compose file containing KEY=value strings is not misread as dotenv.
    stripped = content.lstrip("\ufeff \t\r\n")
    if stripped.startswith("{"):
        # JSON is valid YAML; let the structural checks below decide.
        pass

    try:
        import yaml

        loaded = yaml.safe_load(content)
    except Exception:
        loaded = None

    if isinstance(loaded, dict):
        services = loaded.get("services")
        if isinstance(services, list):
            has_render_markers = any(
                key in loaded for key in ("databases", "envVarGroups", "previews")
            )
            if not has_render_markers and isinstance(services, list):
                has_render_markers = any(
                    isinstance(item, dict) and "type" in item for item in services
                )
            if has_render_markers:
                return "render"
        if isinstance(services, dict):
            return "compose"

    if ENV_LINE_RE.search(content) and not re.search(
        r"^\s*(?:services|databases|envVarGroups)\s*:", content, re.MULTILINE
    ):
        return "dotenv"

    return "unknown"
