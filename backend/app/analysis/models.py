"""Internal analysis data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .constants import Category, Format, Severity


@dataclass(frozen=True)
class SourceFile:
    path: str
    content: str


@dataclass(frozen=True)
class EnvEntry:
    key: str
    value: str
    line: int
    raw: str


@dataclass
class ParsedDocument:
    path: str
    format: Format
    lines: list[str]
    data: dict[str, Any] | None = None
    env_entries: list[EnvEntry] = field(default_factory=list)
    error: str | None = None
    error_line: int | None = None
    note: str = ""


@dataclass(frozen=True)
class FindingDraft:
    rule_id: str
    title: str
    severity: Severity
    category: Category
    message: str
    why: str
    remediation: str
    file: str
    line: int | None
    snippet: str
    docs_url: str | None = None
    resource: str | None = None


@dataclass
class AnalysisContext:
    checks: int = 0
    file_paths: set[str] = field(default_factory=set)
    metered_seen: set[tuple[str, str]] = field(default_factory=set)

    def tick(self, count: int = 1) -> None:
        self.checks += count
