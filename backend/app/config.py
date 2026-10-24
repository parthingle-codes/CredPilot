"""Application configuration.

Secrets are read from the environment only. Nothing here is logged or returned
to the browser except ``ai_configured`` (a boolean) and the public model id.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_GEMMA_MODEL = "google/gemma-4-26B-A4B-it:cheapest"
DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)

MAX_FILES = 8
MAX_FILE_BYTES = 120_000
MAX_TOTAL_BYTES = 300_000


def _load_local_env() -> None:
    """Load .env for local development without overriding real environment vars."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dependency is installed in normal use
        return

    candidates = (
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    )
    for candidate in candidates:
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return


def _int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def _float_env(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def _origins_from_env() -> tuple[str, ...]:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if not raw:
        return DEFAULT_CORS_ORIGINS
    origins = tuple(item.strip().rstrip("/") for item in raw.split(",") if item.strip())
    return origins or DEFAULT_CORS_ORIGINS


@dataclass(frozen=True)
class Settings:
    hf_token: str | None = None
    gemma_model: str = DEFAULT_GEMMA_MODEL
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    ai_requests_per_minute: int = 10
    ai_timeout_seconds: float = 45.0
    static_dir: Path | None = None
    app_env: str = "development"
    loaded_dotenv: bool = field(default=False, compare=False)

    @property
    def ai_configured(self) -> bool:
        return bool(self.hf_token and self.hf_token.strip())

    @classmethod
    def from_env(cls, *, load_dotenv: bool = True) -> "Settings":
        if load_dotenv:
            _load_local_env()

        token = os.getenv("HF_TOKEN", "").strip()
        model = os.getenv("GEMMA_MODEL", "").strip() or DEFAULT_GEMMA_MODEL
        static_raw = os.getenv("CREDPILOT_STATIC_DIR", "").strip()
        static_dir = Path(static_raw) if static_raw else None
        if static_dir is not None and not static_dir.is_dir():
            static_dir = None

        return cls(
            hf_token=token or None,
            gemma_model=model,
            cors_origins=_origins_from_env(),
            ai_requests_per_minute=_int_env(
                "AI_REQUESTS_PER_MINUTE", 10, minimum=1, maximum=100
            ),
            ai_timeout_seconds=_float_env(
                "AI_TIMEOUT_SECONDS", 45.0, minimum=5.0, maximum=120.0
            ),
            static_dir=static_dir,
            app_env=os.getenv("APP_ENV", "development").strip() or "development",
            loaded_dotenv=load_dotenv,
        )
