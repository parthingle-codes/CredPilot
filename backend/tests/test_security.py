"""Unit tests for secret detection, redaction, and claim guardrails."""

from __future__ import annotations

import pytest

from app.security import (
    contains_embedded_credentials,
    detect_token_kinds,
    has_price_or_savings_claim,
    is_placeholder,
    is_public_client_key,
    is_weak_secret,
    looks_secret_key,
    redact_assignment,
    redact_text,
    redact_url_credentials,
    unique_provider_for_key,
)

HF_TOKEN = "hf_SYNTHETIC_DEMO_TOKEN_000000000000"
OPENAI_KEY = "sk-SYNTHETIC_DEMO_KEY_0000000000"
DB_URL = "postgres://demo:demo_password@db.internal:5432/demo"


@pytest.mark.parametrize(
    "name",
    [
        "HF_TOKEN",
        "OPENAI_API_KEY",
        "DATABASE_PASSWORD",
        "JWT_SECRET",
        "SOME_SERVICE_TOKEN",
        "MY_PRIVATE_KEY",
    ],
)
def test_secret_key_names_are_detected(name: str) -> None:
    assert looks_secret_key(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "VITE_FIREBASE_API_KEY",
        "SUPABASE_ANON_KEY",
        "TOKEN_BUDGET",
        "TOKEN_LIMIT",
        "SECRET_NAME",
        "DATABASE_URL",
        "API_KEY_HEADER",
        "PASSWORD_POLICY",
        "",
    ],
)
def test_public_or_descriptive_names_are_not_secrets(name: str) -> None:
    assert looks_secret_key(name) is False


def test_public_client_prefixes() -> None:
    assert is_public_client_key("VITE_OPENAI_API_KEY") is True
    assert is_public_client_key("NEXT_PUBLIC_STRIPE_KEY") is True
    assert is_public_client_key("OPENAI_API_KEY") is False


@pytest.mark.parametrize(
    "value",
    [
        "",
        "your-api-key",
        "${HF_TOKEN}",
        "$HF_TOKEN",
        "<your-token>",
        "replace_me",
        "example",
        "xxxxxx",
        "000000",
        None,
    ],
)
def test_placeholder_values(value: object) -> None:
    assert is_placeholder(value) is True


@pytest.mark.parametrize("value", [HF_TOKEN, OPENAI_KEY, "hunter2!", DB_URL])
def test_real_looking_values_are_not_placeholders(value: str) -> None:
    assert is_placeholder(value) is False


def test_weak_secret_detection() -> None:
    assert is_weak_secret("postgres") is True
    assert is_weak_secret("admin") is True
    assert is_weak_secret("short") is True
    assert is_weak_secret("a-strong-enough-demo-password") is False


def test_token_patterns() -> None:
    realistic_hf = "hf_" + "A" * 30
    assert detect_token_kinds(realistic_hf) == ["Hugging Face token"]
    assert detect_token_kinds(OPENAI_KEY) == ["OpenAI-style key"]
    assert "AWS access key" in detect_token_kinds("AKIAIOSFODNN7EXAMPLE")
    assert "private key block" in detect_token_kinds(
        "-----BEGIN RSA PRIVATE KEY-----"
    )
    assert detect_token_kinds("plain text") == []


def test_embedded_credentials() -> None:
    assert contains_embedded_credentials(DB_URL) is True
    assert contains_embedded_credentials(
        "postgresql://demo:${DB_PASSWORD}@db:5432/demo"
    ) is False
    assert contains_embedded_credentials("postgresql://db:5432/demo") is False


def test_url_credential_redaction() -> None:
    redacted = redact_url_credentials(DB_URL)
    assert "demo_password" not in redacted
    assert "[redacted]" in redacted
    assert redacted.startswith("postgres://demo:[redacted]@")


def test_redact_text_removes_tokens_urls_and_assignments() -> None:
    raw = (
        f"HF_TOKEN={HF_TOKEN}\n"
        f"OPENAI_API_KEY={OPENAI_KEY}\n"
        f"DATABASE_URL={DB_URL}\n"
    )
    redacted = redact_text(raw)
    assert HF_TOKEN not in redacted
    assert OPENAI_KEY not in redacted
    assert "demo_password" not in redacted
    assert redacted.count("[redacted]") >= 3


def test_redact_text_truncates() -> None:
    redacted = redact_text("abcdefghij", max_length=6)
    assert len(redacted) <= 6
    assert redacted.endswith("…")


def test_redact_assignment_keeps_only_key_names() -> None:
    assert redact_assignment("HF_TOKEN", HF_TOKEN) == "HF_TOKEN=[redacted]"
    assert "demo_password" not in redact_assignment("DATABASE_URL", DB_URL)
    assert "demo:[redacted]@" in redact_assignment("DATABASE_URL", DB_URL)


def test_provider_lookup() -> None:
    assert unique_provider_for_key("HF_TOKEN") == "Hugging Face Inference Providers"
    assert unique_provider_for_key("OPENAI_API_KEY") == "OpenAI"
    assert unique_provider_for_key("UNKNOWN_KEY") is None


@pytest.mark.parametrize(
    "text",
    [
        "This will cost $50 per month.",
        "Only 5 dollars per month.",
        "USD 12.50",
        "You will save money with this plan.",
        "Guaranteed savings!",
        "It will save you $20.",
    ],
)
def test_price_and_savings_claims_are_detected(text: str) -> None:
    assert has_price_or_savings_claim(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Confirm the current price in the dashboard.",
        "The free plan has a 25 MB limit.",
        "0.5c-512mb is a plan identifier, not a rate.",
        "No dollar amount appears here.",
    ],
)
def test_non_claims_are_allowed(text: str) -> None:
    assert has_price_or_savings_claim(text) is False
