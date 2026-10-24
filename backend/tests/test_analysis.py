"""End-to-end tests for the deterministic analysis engine."""

from __future__ import annotations

import json
import re

import pytest

from app.analysis import SourceFile, analyze, fingerprint
from app.analysis import engine

HF_TOKEN = "hf_SYNTHETIC_DEMO_TOKEN_000000000000"
OPENAI_KEY = "sk-SYNTHETIC_DEMO_KEY_0000000000"

RENDER_PAID = """services:
  - type: web
    name: demo-api
    runtime: python
    plan: starter
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /api/health
    envVars:
      - key: HF_TOKEN
        value: hf_SYNTHETIC_DEMO_TOKEN_000000000000
"""

RENDER_FREE = """services:
  - type: web
    name: demo-web
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /api/health
    envVars:
      - key: HF_TOKEN
        sync: false
databases:
  - name: demo-db
    plan: free
    ipAllowList: []
"""

RENDER_DEFAULTS = """services:
  - type: web
    name: default-api
    runtime: python
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /api/health
databases:
  - name: default-db
"""

COMPOSE_STACK = """services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      HF_TOKEN: hf_SYNTHETIC_DEMO_TOKEN_000000000000
      DATABASE_URL: postgres://demo:demo_password@db:5432/demo
      DEBUG: "true"
    depends_on:
      - db

  db:
    image: postgres:latest
    ports:
      - "5432:5432"
    environment:
      POSTGRES_PASSWORD: postgres
    volumes:
      - demo-data:/var/lib/postgresql/data

  tools:
    image: alpine:latest
    privileged: true
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

volumes:
  demo-data:
"""

DOTENV = f"""# synthetic values only
HF_TOKEN={HF_TOKEN}
OPENAI_API_KEY={OPENAI_KEY}
DATABASE_URL=postgres://demo:demo_password@localhost:5432/demo
DEBUG=true
CORS_ORIGINS=*
VITE_API_BASE_URL=http://localhost:8000
DUPLICATE=one
DUPLICATE=two
"""


def rule_ids(result) -> set[str]:
    return {finding.rule_id for finding in result.findings}


def dump(result) -> str:
    return json.dumps(result.model_dump(), default=str)


def test_render_paid_plan_has_evidence_and_secret_is_redacted() -> None:
    result = analyze([SourceFile("render.yaml", RENDER_PAID)])

    assert "render-plan-paid" in rule_ids(result)
    paid = next(f for f in result.findings if f.rule_id == "render-plan-paid")
    assert paid.severity == "high"
    assert paid.category == "billing"
    assert paid.evidence.file == "render.yaml"
    assert paid.evidence.line == 5
    assert paid.evidence.snippet == "plan: starter"
    assert paid.resource == "demo-api"

    assert "render-secret-value" in rule_ids(result)
    secret = next(f for f in result.findings if f.rule_id == "render-secret-value")
    assert secret.severity == "critical"
    assert secret.evidence.line == 10
    assert "HF_TOKEN=[redacted]" == secret.evidence.snippet

    assert "env-metered-provider" in rule_ids(result)
    assert result.summary.score == 88
    assert result.summary.risk_level == "critical"
    assert result.summary.files_analyzed == 1
    assert result.summary.formats == ["Render Blueprint"]
    assert result.summary.checks_run > 0

    serialized = dump(result)
    assert HF_TOKEN not in serialized
    assert "demo_password" not in serialized


def test_render_free_tier_is_not_treated_as_paid() -> None:
    result = analyze([SourceFile("render.yaml", RENDER_FREE)])
    ids = rule_ids(result)

    assert "render-plan-paid" not in ids
    assert "render-secret-value" not in ids
    assert "render-free-spindown" in ids
    assert "render-database-free-expiry" in ids
    assert result.summary.risk_level == "elevated"
    assert all(f.severity not in {"critical", "high"} for f in result.findings)

    spindown = next(f for f in result.findings if f.rule_id == "render-free-spindown")
    assert "15 minutes" in spindown.message
    assert "about a minute" in spindown.message


def test_render_missing_plans_default_to_paid() -> None:
    result = analyze([SourceFile("render.yaml", RENDER_DEFAULTS)])
    ids = rule_ids(result)

    assert "render-plan-default" in ids
    assert "render-database-plan-default" in ids
    assert "render-database-public-network" in ids
    assert result.summary.counts["high"] >= 2


def test_render_parse_error_is_reported_and_not_silently_skipped() -> None:
    broken = "services:\n  - type: web\n    name: [unclosed\n"
    result = analyze([SourceFile("render.yaml", broken)])

    assert result.parse_notes[0].ok is False
    assert "Could not parse YAML" in result.parse_notes[0].message
    assert rule_ids(result) == {"parse-error"}
    finding = result.findings[0]
    assert finding.severity == "high"
    assert finding.evidence.line is not None


def test_unknown_format_is_flagged() -> None:
    result = analyze([SourceFile("notes.txt", "hello, this is not config")])

    assert result.summary.formats == ["Unrecognized"]
    assert result.parse_notes[0].ok is False
    assert rule_ids(result) == {"unsupported-format"}
    assert result.findings[0].severity == "medium"


def test_content_based_detection_for_renamed_render_file() -> None:
    result = analyze([SourceFile("deploy.yaml", RENDER_FREE)])

    assert result.summary.formats == ["Render Blueprint"]
    assert result.parse_notes[0].ok is True
    assert "render-free-spindown" in rule_ids(result)


def test_compose_stack_finds_host_exposure_and_cleanup_hazards() -> None:
    result = analyze([SourceFile("docker-compose.yml", COMPOSE_STACK)])
    ids = rule_ids(result)
    lines = COMPOSE_STACK.splitlines()

    for expected in {
        "compose-published-datastore",
        "compose-secret-value",
        "env-embedded-credentials",
        "env-debug-enabled",
        "compose-image-unpinned",
        "compose-no-resource-limits",
        "compose-privileged",
        "compose-docker-socket",
        "compose-persistent-volumes",
    }:
        assert expected in ids, f"missing {expected}"

    published = next(
        f for f in result.findings if f.rule_id == "compose-published-datastore"
    )
    assert published.severity == "high"
    assert published.evidence.line == lines.index('      - "5432:5432"') + 1
    assert "PostgreSQL" in published.title

    socket = next(f for f in result.findings if f.rule_id == "compose-docker-socket")
    assert socket.severity == "critical"
    assert socket.evidence.line == (
        lines.index("      - /var/run/docker.sock:/var/run/docker.sock") + 1
    )

    serialized = dump(result)
    assert HF_TOKEN not in serialized
    assert "demo_password" not in serialized
    assert "POSTGRES_PASSWORD=[redacted]" in serialized


def test_dotenv_findings_cover_secrets_billing_and_cleanup_inputs() -> None:
    result = analyze([SourceFile(".env", DOTENV)])
    ids = rule_ids(result)

    for expected in {
        "dotenv-secret-value",
        "env-embedded-credentials",
        "env-debug-enabled",
        "env-cors-wildcard",
        "env-localhost-url",
        "env-metered-provider",
        "dotenv-duplicate-key",
    }:
        assert expected in ids, f"missing {expected}"

    assert result.summary.counts["critical"] >= 3
    serialized = dump(result)
    assert HF_TOKEN not in serialized
    assert OPENAI_KEY not in serialized
    assert "demo_password" not in serialized

    duplicate = next(f for f in result.findings if f.rule_id == "dotenv-duplicate-key")
    assert duplicate.evidence.line == 9
    assert duplicate.evidence.snippet == "DUPLICATE=two"


def test_example_env_file_is_high_not_critical() -> None:
    content = f"HF_TOKEN={HF_TOKEN}\n"
    result = analyze([SourceFile(".env.example", content)])

    assert "dotenv-secret-value" in rule_ids(result)
    finding = next(f for f in result.findings if f.rule_id == "dotenv-secret-value")
    assert finding.severity == "high"
    assert "Example env file" in finding.title
    assert "env-metered-provider" not in rule_ids(result)
    assert HF_TOKEN not in dump(result)


def test_multiple_files_are_combined_and_parse_notes_recorded() -> None:
    result = analyze(
        [
            SourceFile("render.yaml", RENDER_FREE),
            SourceFile(".env", "DEBUG=false\n"),
            SourceFile("README.md", "# docs\n"),
        ]
    )

    assert result.summary.files_analyzed == 3
    assert "Render Blueprint" in result.summary.formats
    assert "Dotenv (.env)" in result.summary.formats
    assert "Unrecognized" in result.summary.formats
    assert [note.ok for note in result.parse_notes] == [True, True, False]


def test_analysis_is_deterministic() -> None:
    files = [
        SourceFile("render.yaml", RENDER_FREE),
        SourceFile(".env", DOTENV),
    ]
    first = analyze(files, project_name="Demo")
    second = analyze(files, project_name="Demo")

    assert first.fingerprint == second.fingerprint
    assert [f.rule_id for f in first.findings] == [f.rule_id for f in second.findings]
    assert [f.evidence.line for f in first.findings] == [
        f.evidence.line for f in second.findings
    ]
    assert first.summary == second.summary


def test_fingerprint_changes_with_content_and_rules_version(monkeypatch) -> None:
    files = [SourceFile("render.yaml", RENDER_FREE)]
    baseline = fingerprint(files)

    assert fingerprint([SourceFile("render.yaml", RENDER_FREE + "\n")]) != baseline
    assert fingerprint([SourceFile("other.yaml", RENDER_FREE)]) != baseline

    monkeypatch.setattr(engine, "RULES_VERSION", "9999.99.9")
    assert fingerprint(files) != baseline


def test_cleanup_tasks_always_include_manual_verification() -> None:
    result = analyze([SourceFile("render.yaml", RENDER_PAID)])
    tasks = {task.title: task for task in result.cleanup_tasks}

    assert "Set provider budget or spend alerts" in tasks
    assert "Confirm secret files are gitignored" in tasks
    assert "Delete or pause demo services after judging" in tasks
    assert "Remove demo data and shared credentials" in tasks
    assert "Re-run CredPilot after cleanup" in tasks
    assert tasks["Set provider budget or spend alerts"].priority == "before-demo"
    assert tasks["Delete or pause demo services after judging"].priority == "after-demo"
    assert any(
        task.title.startswith("Rotate exposed credential")
        and task.priority == "now"
        for task in result.cleanup_tasks
    )
    assert any(
        task.title.startswith("Confirm billing exposure")
        and task.priority == "before-demo"
        for task in result.cleanup_tasks
    )


def test_cleanup_tasks_are_sorted_by_priority() -> None:
    result = analyze([SourceFile("docker-compose.yml", COMPOSE_STACK)])
    order = {"now": 0, "before-demo": 1, "after-demo": 2}
    ranks = [order[task.priority] for task in result.cleanup_tasks]
    assert ranks == sorted(ranks)


def test_output_never_states_a_dollar_amount() -> None:
    result = analyze(
        [
            SourceFile("render.yaml", RENDER_PAID),
            SourceFile("docker-compose.yml", COMPOSE_STACK),
            SourceFile(".env", DOTENV),
        ]
    )
    text = dump(result)
    assert re.search(r"\$\s?\d", text) is None


def test_project_name_and_disclaimers_are_present() -> None:
    result = analyze(
        [SourceFile("render.yaml", RENDER_FREE)], project_name="My demo"
    )
    assert result.project_name == "My demo"
    assert result.engine.name == "credpilot-rules"
    assert result.disclaimers
    assert any("not a prediction of charges" in item for item in result.disclaimers)
