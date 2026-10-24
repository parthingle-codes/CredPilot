"""Deterministic configuration analysis.

The engine is imported lazily so ``app.models`` can use the shared constants
without triggering a circular import through the analysis package.
"""

from __future__ import annotations

from typing import Any

from .models import SourceFile

__all__ = ["analyze", "fingerprint", "SourceFile"]


def __getattr__(name: str) -> Any:
    if name in {"analyze", "fingerprint"}:
        from .engine import analyze, fingerprint

        return {"analyze": analyze, "fingerprint": fingerprint}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
