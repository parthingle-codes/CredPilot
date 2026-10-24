"""PyYAML loader that records 1-based line numbers for mappings and keys."""

from __future__ import annotations

from typing import Any

import yaml

LINE_KEY = "__line__"
LINES_KEY = "__lines__"


class LineLoader(yaml.SafeLoader):
    pass


def _construct_mapping(
    loader: LineLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[str, Any]:
    loader.flatten_mapping(node)
    mapping: dict[str, Any] = {}
    key_lines: dict[str, int] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str):
            key = str(key)
        value = loader.construct_object(value_node, deep=True)
        mapping[key] = value
        key_lines[key] = key_node.start_mark.line + 1
    mapping[LINE_KEY] = node.start_mark.line + 1
    mapping[LINES_KEY] = key_lines
    return mapping


LineLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


class DocumentParseError(Exception):
    def __init__(self, message: str, line: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.line = line


def load_yaml_with_lines(content: str) -> Any:
    try:
        return yaml.load(content, Loader=LineLoader)  # noqa: S506 - SafeLoader subclass
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        problem = getattr(exc, "problem", None) or "invalid YAML syntax"
        line = mark.line + 1 if mark is not None else None
        raise DocumentParseError(problem, line) from None


def strip_meta(value: Any) -> Any:
    """Remove line metadata (used for compact AI/finding payloads, not rules)."""
    if isinstance(value, dict):
        return {
            key: strip_meta(item)
            for key, item in value.items()
            if key not in (LINE_KEY, LINES_KEY)
        }
    if isinstance(value, list):
        return [strip_meta(item) for item in value]
    return value
