"""Helpers for line-addressable evidence."""

from __future__ import annotations

import re


def find_line(
    lines: list[str],
    pattern: str,
    *,
    start: int = 1,
    skip_comments: bool = True,
) -> int | None:
    """Find a 1-based line number matching ``pattern``."""
    regex = re.compile(pattern)
    for index in range(max(1, start) - 1, len(lines)):
        line = lines[index]
        if skip_comments and line.lstrip().startswith("#"):
            continue
        if regex.search(line):
            return index + 1
    return None


def line_at(lines: list[str], line: int | None) -> str:
    if line is None or line < 1 or line > len(lines):
        return ""
    return lines[line - 1].strip()


def meta_line(mapping: object, key: str | None = None) -> int | None:
    """Return the recorded YAML line for a mapping or one of its keys."""
    if not isinstance(mapping, dict):
        return None
    if key is not None:
        lines = mapping.get("__lines__")
        if isinstance(lines, dict):
            value = lines.get(key)
            if isinstance(value, int):
                return value
    value = mapping.get("__line__")
    return value if isinstance(value, int) else None
