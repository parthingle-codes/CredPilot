"""Parsers for the three supported configuration formats."""

from __future__ import annotations

import re

from ..constants import FORMAT_LABELS
from ..models import EnvEntry, ParsedDocument, SourceFile
from .detect import detect_format, normalize_path
from .lines import meta_line
from .yaml_loader import DocumentParseError, load_yaml_with_lines

DOTENV_RE = re.compile(
    r"^\s*(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_.-]*)\s*=\s*(?P<value>.*)$"
)


def _strip_dotenv_value(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value[0] in {"'", '"'}:
        quote = value[0]
        end = value.find(quote, 1)
        if end != -1:
            return value[1:end]
        return value[1:]
    # Remove an unquoted inline comment only when it is preceded by whitespace.
    match = re.search(r"\s+#", value)
    if match:
        value = value[: match.start()]
    return value.strip()


def parse_dotenv(path: str, content: str, lines: list[str]) -> ParsedDocument:
    entries: list[EnvEntry] = []
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = DOTENV_RE.match(line)
        if not match:
            continue
        key = match.group("key").strip()
        value = _strip_dotenv_value(match.group("value"))
        entries.append(
            EnvEntry(key=key, value=value, line=index, raw=line.strip())
        )

    note = (
        f"Parsed {len(entries)} environment variable(s). Values are used only for "
        "local checks and are redacted in results."
    )
    if not entries:
        note = "No KEY=value entries were found in this dotenv file."
    return ParsedDocument(
        path=path,
        format="dotenv",
        lines=lines,
        env_entries=entries,
        note=note,
    )


def _yaml_document(path: str, content: str, lines: list[str], fmt: str) -> ParsedDocument:
    try:
        data = load_yaml_with_lines(content)
    except DocumentParseError as exc:
        return ParsedDocument(
            path=path,
            format=fmt,  # type: ignore[arg-type]
            lines=lines,
            error=exc.message,
            error_line=exc.line,
            note=f"Could not parse YAML: {exc.message}",
        )

    if not isinstance(data, dict):
        return ParsedDocument(
            path=path,
            format=fmt,  # type: ignore[arg-type]
            lines=lines,
            error="Expected a mapping at the top level of this YAML file.",
            error_line=1,
            note="Could not parse YAML: top-level value is not a mapping.",
        )

    return ParsedDocument(
        path=path,
        format=fmt,  # type: ignore[arg-type]
        lines=lines,
        data=data,
    )


def parse_render(path: str, content: str, lines: list[str]) -> ParsedDocument:
    doc = _yaml_document(path, content, lines, "render")
    if doc.error or doc.data is None:
        return doc

    data = doc.data
    for key in ("services", "databases", "envVarGroups", "projects"):
        if key in data and not isinstance(data[key], list):
            doc.error = f"`{key}` must be a list."
            doc.error_line = meta_line(data, key)
            doc.note = f"Could not parse Render Blueprint: {doc.error}"
            return doc

    services = data.get("services") if isinstance(data.get("services"), list) else []
    databases = data.get("databases") if isinstance(data.get("databases"), list) else []
    groups = data.get("envVarGroups") if isinstance(data.get("envVarGroups"), list) else []
    projects = data.get("projects") if isinstance(data.get("projects"), list) else []
    doc.note = (
        f"Parsed {len(services)} service(s), {len(databases)} database(s), "
        f"{len(groups)} env group(s)"
        + (f", {len(projects)} project(s)." if projects else ".")
    )
    return doc


def parse_compose(path: str, content: str, lines: list[str]) -> ParsedDocument:
    doc = _yaml_document(path, content, lines, "compose")
    if doc.error or doc.data is None:
        return doc

    data = doc.data
    services = data.get("services")
    if not isinstance(services, dict):
        doc.error = "Docker Compose requires a top-level `services` mapping."
        doc.error_line = meta_line(data, "services")
        doc.note = f"Could not parse Docker Compose: {doc.error}"
        return doc

    names = [name for name in services if name not in {"__line__", "__lines__"}]
    if not names:
        doc.error = "The `services` mapping is empty; there is nothing to check."
        doc.error_line = meta_line(data, "services")
        doc.note = f"Could not parse Docker Compose: {doc.error}"
        return doc
    malformed = [name for name in names if not isinstance(services[name], dict)]
    if malformed:
        doc.error = (
            "These services are not mappings: " + ", ".join(str(item) for item in malformed)
        )
        doc.error_line = meta_line(services, str(malformed[0]))
        doc.note = f"Could not parse Docker Compose: {doc.error}"
        return doc

    doc.note = f"Parsed {len(names)} Compose service(s)."
    return doc


def parse_file(source: SourceFile) -> ParsedDocument:
    path = normalize_path(source.path)
    content = source.content
    lines = content.splitlines()
    fmt = detect_format(path, content)

    if fmt == "render":
        return parse_render(path, content, lines)
    if fmt == "compose":
        return parse_compose(path, content, lines)
    if fmt == "dotenv":
        return parse_dotenv(path, content, lines)

    return ParsedDocument(
        path=path,
        format="unknown",
        lines=lines,
        note=(
            f"Unrecognized format. Supported: Render Blueprint ({FORMAT_LABELS['render']}), "
            f"Docker Compose ({FORMAT_LABELS['compose']}), and .env "
            f"({FORMAT_LABELS['dotenv']})."
        ),
    )
