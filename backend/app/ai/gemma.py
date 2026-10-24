"""Gemma via Hugging Face Inference Providers (OpenAI-compatible router)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import Settings
from ..models import AnalysisResponse, ExplainResponse
from ..security import has_price_or_savings_claim
from .prompts import SYSTEM_PROMPT, build_user_prompt

HF_ROUTER_URL = "https://router.huggingface.co/v1/chat/completions"
MAX_OUTPUT_CHARS = 4_500
logger = logging.getLogger("credpilot.ai")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _unavailable(settings: Settings, reason: str) -> ExplainResponse:
    return ExplainResponse(
        available=False,
        model=settings.gemma_model,
        explanation=None,
        reason=reason,
        generated_at=_iso_now(),
    )


def _extract_content(payload: dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("unexpected response shape") from exc

    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "".join(parts).strip()
    return ""


async def _request(
    settings: Settings,
    analysis: AnalysisResponse,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[str, int]:
    if not settings.hf_token:
        raise ValueError("missing token")

    payload = {
        "model": settings.gemma_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(analysis)},
        ],
        "temperature": 0.2,
        "max_tokens": 500,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.hf_token}",
        "Content-Type": "application/json",
        "User-Agent": "CredPilot/0.1",
    }

    timeout = httpx.Timeout(settings.ai_timeout_seconds, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        response = await client.post(HF_ROUTER_URL, json=payload, headers=headers)

    if response.status_code != 200:
        return "", response.status_code
    try:
        data = response.json()
    except ValueError:
        return "", 502
    content = _extract_content(data)
    return content, response.status_code


async def explain(
    analysis: AnalysisResponse,
    settings: Settings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ExplainResponse:
    if not settings.ai_configured:
        return _unavailable(
            settings,
            "Gemma is not configured on this server. The deterministic findings above are "
            "complete; add HF_TOKEN to enable optional AI explanations.",
        )

    try:
        content, status = await _request(settings, analysis, transport=transport)
    except ValueError:
        return _unavailable(
            settings,
            "Gemma returned no usable text. The deterministic findings are unaffected.",
        )
    except httpx.TimeoutException:
        logger.warning("Gemma request timed out")
        return _unavailable(
            settings,
            "Gemma timed out. The deterministic findings are unaffected; try again later.",
        )
    except httpx.HTTPError as exc:
        logger.warning("Gemma upstream error: %s", type(exc).__name__)
        return _unavailable(
            settings,
            "Could not reach Hugging Face. The deterministic findings are unaffected.",
        )
    except Exception as exc:  # pragma: no cover - defensive boundary
        logger.warning("Gemma unexpected error: %s", type(exc).__name__)
        return _unavailable(
            settings,
            "The AI explanation is temporarily unavailable. The deterministic findings are unaffected.",
        )

    if status in {401, 403}:
        logger.warning("Gemma authentication rejected (status=%s)", status)
        return _unavailable(
            settings,
            "Hugging Face rejected the token. Confirm it has the Inference Providers "
            "permission. The deterministic findings are unaffected.",
        )
    if status == 429:
        return _unavailable(
            settings,
            "Hugging Face is rate-limiting this account. Try again later; checks still "
            "work. The deterministic findings are unaffected.",
        )
    if status != 200:
        logger.warning("Gemma request failed (status=%s)", status)
        return _unavailable(
            settings,
            f"Hugging Face returned an error (status {status}). The deterministic findings are unaffected.",
        )

    if not content:
        return _unavailable(
            settings,
            "Gemma returned no usable text. The deterministic findings are unaffected.",
        )
    if len(content) > MAX_OUTPUT_CHARS:
        content = content[:MAX_OUTPUT_CHARS].rstrip() + "…"

    # Product guardrail: the UI must never present an invented price or savings claim.
    if has_price_or_savings_claim(content):
        logger.warning("Gemma output withheld by price/savings guardrail")
        return _unavailable(
            settings,
            "The generated explanation was withheld because it appeared to state a price or "
            "savings claim. CredPilot does not estimate costs; use the deterministic findings.",
        )

    return ExplainResponse(
        available=True,
        model=settings.gemma_model,
        explanation=content,
        generated_at=_iso_now(),
    )
