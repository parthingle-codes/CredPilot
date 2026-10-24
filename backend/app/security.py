"""Secret detection and redaction.

This module is deliberately conservative:

* Evidence shown in the UI/report is redacted before it leaves the analysis
  engine.
* AI prompts never contain environment-variable values or evidence snippets.
* Nothing here attempts to validate a credential against a provider.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# ---------------------------------------------------------------------------
# Key-name heuristics
# ---------------------------------------------------------------------------

KNOWN_SECRET_KEYS = {
    "HF_TOKEN",
    "HUGGINGFACEHUB_API_TOKEN",
    "HUGGING_FACE_HUB_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "REPLICATE_API_TOKEN",
    "TOGETHER_API_KEY",
    "GROQ_API_KEY",
    "MISTRAL_API_KEY",
    "COHERE_API_KEY",
    "FIREWORKS_API_KEY",
    "OPENROUTER_API_KEY",
    "DEEPSEEK_API_KEY",
    "PERPLEXITY_API_KEY",
    "XAI_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AZURE_OPENAI_API_KEY",
    "STRIPE_SECRET_KEY",
    "STRIPE_API_KEY",
    "TWILIO_AUTH_TOKEN",
    "SENDGRID_API_KEY",
    "RESEND_API_KEY",
    "MAILGUN_API_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "CLERK_SECRET_KEY",
    "FIREBASE_PRIVATE_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GITLAB_TOKEN",
    "DISCORD_TOKEN",
    "SLACK_BOT_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "DATABASE_PASSWORD",
    "POSTGRES_PASSWORD",
    "MYSQL_ROOT_PASSWORD",
    "MYSQL_PASSWORD",
    "MONGO_INITDB_ROOT_PASSWORD",
    "REDIS_PASSWORD",
    "MINIO_ROOT_PASSWORD",
    "JWT_SECRET",
    "SESSION_SECRET",
    "APP_SECRET",
    "SECRET_KEY",
    "SMTP_PASSWORD",
    "MAIL_PASSWORD",
    "PRIVATE_KEY",
    "API_KEY",
    "API_SECRET",
    "AUTH_TOKEN",
    "ACCESS_TOKEN",
    "REFRESH_TOKEN",
}

# Public by design, or names that merely contain a sensitive-sounding word.
SAFE_KEY_NAMES = {
    "FIREBASE_API_KEY",
    "NEXT_PUBLIC_FIREBASE_API_KEY",
    "VITE_FIREBASE_API_KEY",
    "SUPABASE_ANON_KEY",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "VITE_SUPABASE_ANON_KEY",
    "STRIPE_PUBLISHABLE_KEY",
    "NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY",
    "VITE_STRIPE_PUBLISHABLE_KEY",
    "PUBLISHABLE_KEY",
    "PUBLIC_KEY",
    "TOKEN_BUDGET",
    "TOKEN_LIMIT",
    "TOKEN_COUNT",
    "TOKEN_TTL",
    "PASSWORD_POLICY",
    "SECRET_NAME",
    "KEY_NAME",
    "KEY_ID",
    "KEY_VERSION",
}

SECRET_WORD_RE = re.compile(
    r"(?:API[_-]?KEY|APIKEY|ACCESS[_-]?KEY|PRIVATE[_-]?KEY|CLIENT[_-]?SECRET"
    r"|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIALS?)",
    re.IGNORECASE,
)
SAFE_SUFFIXES = (
    "_URL",
    "_URI",
    "_ENDPOINT",
    "_LIMIT",
    "_BUDGET",
    "_COUNT",
    "_NAME",
    "_POLICY",
    "_LENGTH",
    "_TTL",
    "_HEADER",
    "_TIMEOUT",
    "_PATH",
)

PUBLIC_CLIENT_PREFIXES = (
    "VITE_",
    "NEXT_PUBLIC_",
    "REACT_APP_",
    "EXPO_PUBLIC_",
    "PUBLIC_",
    "NUXT_PUBLIC_",
)

METERED_PROVIDERS = {
    "OPENAI_API_KEY": "OpenAI",
    "ANTHROPIC_API_KEY": "Anthropic",
    "GEMINI_API_KEY": "Google Gemini",
    "GOOGLE_API_KEY": "Google AI",
    "HF_TOKEN": "Hugging Face Inference Providers",
    "HUGGINGFACEHUB_API_TOKEN": "Hugging Face",
    "REPLICATE_API_TOKEN": "Replicate",
    "TOGETHER_API_KEY": "Together AI",
    "GROQ_API_KEY": "Groq",
    "MISTRAL_API_KEY": "Mistral",
    "COHERE_API_KEY": "Cohere",
    "FIREWORKS_API_KEY": "Fireworks AI",
    "OPENROUTER_API_KEY": "OpenRouter",
    "DEEPSEEK_API_KEY": "DeepSeek",
    "PERPLEXITY_API_KEY": "Perplexity",
    "XAI_API_KEY": "xAI",
    "AWS_ACCESS_KEY_ID": "AWS",
    "STRIPE_SECRET_KEY": "Stripe",
    "TWILIO_AUTH_TOKEN": "Twilio",
    "SENDGRID_API_KEY": "SendGrid",
    "RESEND_API_KEY": "Resend",
    "MAILGUN_API_KEY": "Mailgun",
}

WEAK_SECRET_VALUES = {
    "password",
    "passw0rd",
    "postgres",
    "postgresql",
    "mysql",
    "root",
    "admin",
    "administrator",
    "changeme",
    "change_me",
    "change-me",
    "secret",
    "letmein",
    "minioadmin",
    "guest",
    "test",
    "demo",
    "dev",
    "123456",
    "12345678",
    "123456789",
    "qwerty",
    "abc123",
}

PLACEHOLDER_VALUES = {
    "",
    "todo",
    "none",
    "null",
    "undefined",
    "example",
    "placeholder",
    "your-key",
    "your_key",
    "your-api-key",
    "your_api_key",
    "your-token",
    "your_token",
    "your-token-here",
    "your_token_here",
    "your-api-key-here",
    "your_api_key_here",
    "replace-me",
    "replace_me",
    "replace-with-key",
    "insert-key-here",
    "insert_key_here",
    "not-set",
    "not_set",
    "redacted",
}

# ---------------------------------------------------------------------------
# Value patterns
# ---------------------------------------------------------------------------

VALUE_TOKEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{20,}\b")),
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("Stripe key", re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{10,}\b")),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    (
        "JWT",
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    ),
)

URL_CREDENTIALS_RE = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)"
    r"(?P<user>[^/\s:@]+):(?P<password>[^@\s/]+)@"
)

ASSIGNMENT_SECRET_RE = re.compile(
    r"(?P<key>[A-Za-z_][A-Za-z0-9_.-]*(?:API_KEY|APIKEY|SECRET|TOKEN|PASSWORD|PASSWD"
    r"|ACCESS_KEY|PRIVATE_KEY)[A-Za-z0-9_.-]*)"
    r"(?P<sep>\s*[:=]\s*)"
    r"(?P<quote>[\"']?)(?P<value>[^\s\"',#]+)"
)

PRICE_CLAIM_RE = re.compile(
    r"(?i)(?:\$\s?\d[\d,.]*|\d[\d,.]*\s*(?:usd|dollars?)|usd\s*\d[\d,.]*)"
)
SAVINGS_CLAIM_RE = re.compile(
    r"(?i)\b(?:guaranteed?\s+savings?|you(?:'|’| wi)ll\s+save"
    r"|save\s+you\s+(?:money|\$)|guaranteed?\s+to\s+save)\b"
)


def looks_secret_key(name: str) -> bool:
    """Return True when an environment variable name likely holds a credential."""
    key = name.strip().upper()
    if not key:
        return False
    if key in SAFE_KEY_NAMES:
        return False
    if key in KNOWN_SECRET_KEYS:
        return True
    if key.endswith(SAFE_SUFFIXES):
        return False
    return bool(SECRET_WORD_RE.search(key))


def is_public_client_key(name: str) -> bool:
    return name.strip().upper().startswith(PUBLIC_CLIENT_PREFIXES)


def is_placeholder(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip().strip("\"'").strip()
    lower = text.lower()
    if lower in PLACEHOLDER_VALUES:
        return True
    if re.fullmatch(r"<[^>]{0,120}>", text):
        return True
    if re.fullmatch(r"\$\{[^}]{1,120}\}", text):
        return True
    if re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]{0,80}", text):
        return True
    if lower.startswith(
        (
            "your_",
            "your-",
            "replace_",
            "replace-",
            "insert_",
            "insert-",
            "example",
            "placeholder",
            "dummy",
            "fake_",
            "fake-",
            "***",
            "xxx",
        )
    ):
        return True
    if len(text) >= 6 and set(text) <= {"x", "X", "*", "0", "."}:
        return True
    return False


def is_weak_secret(value: object) -> bool:
    text = str(value).strip().strip("\"'")
    return text.lower() in WEAK_SECRET_VALUES or (0 < len(text) < 8)


def detect_token_kinds(value: str) -> list[str]:
    return [label for label, pattern in VALUE_TOKEN_PATTERNS if pattern.search(value)]


def contains_embedded_credentials(value: str) -> bool:
    match = URL_CREDENTIALS_RE.search(value)
    if not match:
        return False
    # `${DB_PASSWORD}` and similar references are not literal secrets.
    return not is_placeholder(match.group("password"))


def has_price_or_savings_claim(text: str) -> bool:
    return bool(PRICE_CLAIM_RE.search(text) or SAVINGS_CLAIM_RE.search(text))


def redact_url_credentials(text: str) -> str:
    return URL_CREDENTIALS_RE.sub(
        lambda m: f"{m.group('scheme')}{m.group('user')}:[redacted]@", text
    )


def redact_text(text: object, *, max_length: int | None = None) -> str:
    """Best-effort redaction for arbitrary evidence text."""
    if text is None:
        return ""
    result = str(text)
    result = redact_url_credentials(result)
    for _, pattern in VALUE_TOKEN_PATTERNS:
        result = pattern.sub("[redacted]", result)
    result = ASSIGNMENT_SECRET_RE.sub(
        lambda m: f"{m.group('key')}{m.group('sep')}[redacted]", result
    )
    if max_length is not None and len(result) > max_length:
        result = result[: max_length - 1].rstrip() + "…"
    return result


def redact_assignment(key: str, value: object) -> str:
    """Render a safe ``KEY=value`` style evidence line for a secret."""
    if contains_embedded_credentials(str(value)):
        return redact_url_credentials(f"{key}={value}")
    return f"{key}=[redacted]"


def secret_evidence_label(key: str) -> str:
    """Key name is safe to show; the value never is."""
    return f"{key} (value redacted)"


def unique_provider_for_key(name: str) -> str | None:
    return METERED_PROVIDERS.get(name.strip().upper())


def truncate_lines(text: str, limit: int = 12) -> Iterable[str]:
    for index, line in enumerate(text.splitlines(), start=1):
        if index > limit:
            break
        yield line
