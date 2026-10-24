"""Rule registry for each supported format."""

from __future__ import annotations

from collections.abc import Callable

from ..constants import Format
from ..models import AnalysisContext, FindingDraft, ParsedDocument
from . import compose, dotenv, render

Rule = Callable[[ParsedDocument, AnalysisContext], list[FindingDraft]]

RULES: dict[Format, tuple[Rule, ...]] = {
    "render": render.RULES,
    "compose": compose.RULES,
    "dotenv": dotenv.RULES,
    "unknown": (),
}
