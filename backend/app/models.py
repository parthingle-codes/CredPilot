"""API request/response models and input validation."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .analysis.constants import Category, Priority, RiskLevel, Severity
from .config import MAX_FILE_BYTES, MAX_FILES, MAX_TOTAL_BYTES

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_path(value: str) -> str:
    path = value.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    path = re.sub(r"/+", "/", path)
    return path


class ConfigFile(BaseModel):
    path: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        path = clean_path(value)
        if not path:
            raise ValueError("path cannot be empty")
        if control_chars := CONTROL_CHARS_RE.search(path):
            raise ValueError(f"path contains a control character: {control_chars.group(0)!r}")
        if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
            raise ValueError("use a relative path, not an absolute filesystem path")
        if any(part in {"..", "."} for part in path.split("/")):
            raise ValueError("path cannot contain '.' or '..' segments")
        if len(path) > 120:
            raise ValueError("path is too long")
        return path

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("content cannot contain NUL bytes")
        if len(value.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError(f"file exceeds the {MAX_FILE_BYTES:,}-byte limit")
        return value


class AnalyzeRequest(BaseModel):
    files: list[ConfigFile] = Field(min_length=1, max_length=MAX_FILES)
    project_name: str = Field(default="My hackathon project", max_length=80)

    @field_validator("project_name")
    @classmethod
    def validate_project_name(cls, value: str) -> str:
        name = value.strip()
        return name or "My hackathon project"

    @model_validator(mode="after")
    def validate_bundle(self) -> "AnalyzeRequest":
        seen: set[str] = set()
        total = 0
        for file in self.files:
            key = file.path.lower()
            if key in seen:
                raise ValueError(f"duplicate file path: {file.path}")
            seen.add(key)
            total += len(file.content.encode("utf-8"))
        if total > MAX_TOTAL_BYTES:
            raise ValueError(f"bundle exceeds the {MAX_TOTAL_BYTES:,}-byte limit")
        return self


class ExplainRequest(AnalyzeRequest):
    pass


class Evidence(BaseModel):
    file: str
    line: int | None = None
    snippet: str = ""


class Finding(BaseModel):
    id: str
    rule_id: str
    title: str
    severity: Severity
    category: Category
    message: str
    why: str
    remediation: str
    evidence: Evidence
    docs_url: str | None = None
    resource: str | None = None


class CleanupTask(BaseModel):
    id: str
    title: str
    detail: str
    priority: Priority
    category: Category
    source_finding_id: str | None = None
    evidence_file: str | None = None
    evidence_line: int | None = None


class ParseNote(BaseModel):
    file: str
    format: str
    format_label: str
    ok: bool
    message: str


class EngineInfo(BaseModel):
    name: str
    version: str
    rules_version: str


class Summary(BaseModel):
    score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    counts: dict[str, int]
    findings_total: int
    checks_run: int
    files_analyzed: int
    formats: list[str]


class AnalysisResponse(BaseModel):
    project_name: str
    generated_at: str
    fingerprint: str
    engine: EngineInfo
    summary: Summary
    findings: list[Finding]
    cleanup_tasks: list[CleanupTask]
    parse_notes: list[ParseNote]
    disclaimers: list[str]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    rules_version: str
    ai_configured: bool
    gemma_model: str


class ExplainResponse(BaseModel):
    available: bool
    model: str
    explanation: str | None = None
    reason: str | None = None
    generated_at: str
    guardrail: str = (
        "AI output is generated only from the deterministic findings. Price and savings "
        "claims are withheld."
    )
