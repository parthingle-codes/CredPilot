"""Tests for the optional Gemma layer, its prompt boundary, and guardrails."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.ai.gemma import MAX_OUTPUT_CHARS, explain
from app.ai.prompts import SYSTEM_PROMPT, build_user_prompt
from app.analysis import SourceFile, analyze
from app.config import Settings

from .test_analysis import DOTENV, HF_TOKEN, OPENAI_KEY, RENDER_PAID


def make_settings(token: str | None = "hf_test_token") -> Settings:
    return Settings(
        hf_token=token,
        gemma_model="google/gemma-test",
        cors_origins=("http://localhost:5173",),
        ai_requests_per_minute=10,
        ai_timeout_seconds=5.0,
        static_dir=None,
        app_env="test",
        loaded_dotenv=False,
    )


@pytest.fixture
def analysis():
    return analyze(
        [
            SourceFile("render.yaml", RENDER_PAID),
            SourceFile(".env", DOTENV),
        ],
        project_name="Synthetic demo",
    )


def run_explain(analysis, settings, transport):
    return asyncio.run(explain(analysis, settings, transport=transport))


def test_prompt_contains_findings_but_no_raw_values(analysis) -> None:
    prompt = build_user_prompt(analysis)

    assert "PROJECT: Synthetic demo" in prompt
    assert "FINDINGS" in prompt
    assert "evidence snippets intentionally omitted" in prompt
    assert "render-plan-paid" not in prompt  # rule ids are not sent
    assert "plan: starter" in prompt  # safe finding text
    assert "render.yaml" in prompt

    assert HF_TOKEN not in prompt
    assert OPENAI_KEY not in prompt
    assert "demo_password" not in prompt
    assert "hf_SYNTHETIC" not in prompt
    assert "sk-SYNTHETIC" not in prompt
    assert "# synthetic values only" not in prompt
    assert "DATABASE_URL=" not in prompt
    assert "POSTGRES_PASSWORD" not in prompt


def test_system_prompt_forbids_prices_and_new_findings() -> None:
    assert "Never state or estimate prices" in SYSTEM_PROMPT
    assert "not a second scanner" in SYSTEM_PROMPT
    assert "Never ask for, infer, guess, or repeat credentials" in SYSTEM_PROMPT


def test_explain_returns_model_text_and_never_leaks_token(analysis) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                "Fix the exposed credential first, then confirm the paid "
                                "plan in the dashboard. Re-run the checks after cleanup."
                            )
                        }
                    }
                ]
            },
        )

    result = run_explain(analysis, make_settings(), httpx.MockTransport(handler))

    assert result.available is True
    assert result.explanation
    assert "Fix the exposed credential first" in result.explanation
    assert result.model == "google/gemma-test"
    assert result.guardrail
    assert captured["authorization"] == "Bearer hf_test_token"

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["stream"] is False
    assert payload["temperature"] == 0.2
    assert payload["messages"][0]["role"] == "system"
    user_prompt = payload["messages"][1]["content"]
    assert HF_TOKEN not in user_prompt
    assert "demo_password" not in user_prompt


def test_price_claim_is_withheld(analysis) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "This setup will cost about $50 per month."
                        }
                    }
                ]
            },
        )

    result = run_explain(analysis, make_settings(), httpx.MockTransport(handler))

    assert result.available is False
    assert result.explanation is None
    assert "withheld" in result.reason.lower()
    assert "does not estimate costs" in result.reason


def test_savings_claim_is_withheld(analysis) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "Follow this and you will save money."
                        }
                    }
                ]
            },
        )

    result = run_explain(analysis, make_settings(), httpx.MockTransport(handler))
    assert result.available is False
    assert "withheld" in result.reason.lower()


def test_missing_token_returns_unavailable_without_network(analysis) -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("network must not be called")

    result = run_explain(
        analysis, make_settings(token=None), httpx.MockTransport(handler)
    )
    assert result.available is False
    assert "not configured" in result.reason.lower()


def test_blank_token_is_not_configured(analysis) -> None:
    settings = make_settings(token="   ")
    assert settings.ai_configured is False

    result = asyncio.run(explain(analysis, settings))
    assert result.available is False
    assert "not configured" in result.reason.lower()


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "rejected the token"),
        (403, "rejected the token"),
        (429, "rate-limiting"),
        (500, "returned an error"),
    ],
)
def test_upstream_errors_degrade_gracefully(analysis, status, expected) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "upstream"})

    result = run_explain(analysis, make_settings(), httpx.MockTransport(handler))
    assert result.available is False
    assert expected in result.reason.lower()
    assert "deterministic findings are unaffected" in result.reason.lower()


def test_timeout_degrades_gracefully(analysis) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("simulated timeout")

    result = run_explain(analysis, make_settings(), httpx.MockTransport(handler))
    assert result.available is False
    assert "timed out" in result.reason.lower()


def test_empty_output_degrades_gracefully(analysis) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "   "}}]}
        )

    result = run_explain(analysis, make_settings(), httpx.MockTransport(handler))
    assert result.available is False
    assert "no usable text" in result.reason.lower()


def test_unexpected_shape_degrades_gracefully(analysis) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    result = run_explain(analysis, make_settings(), httpx.MockTransport(handler))
    assert result.available is False
    assert "no usable text" in result.reason.lower()


def test_output_is_truncated(analysis) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "a" * (MAX_OUTPUT_CHARS + 500)}}
                ]
            },
        )

    result = run_explain(analysis, make_settings(), httpx.MockTransport(handler))
    assert result.available is True
    assert len(result.explanation) == MAX_OUTPUT_CHARS + 1
    assert result.explanation.endswith("…")


def test_list_content_parts_are_supported(analysis) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": "First part. "},
                                {"type": "text", "text": "Second part."},
                            ]
                        }
                    }
                ]
            },
        )

    result = run_explain(analysis, make_settings(), httpx.MockTransport(handler))
    assert result.available is True
    assert result.explanation == "First part. Second part."
