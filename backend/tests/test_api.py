"""API contract, validation, security-header, and static-serving tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

from .test_analysis import DOTENV, RENDER_FREE, RENDER_PAID


def test_health_reports_ai_disabled(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["ai_configured"] is False
    assert body["gemma_model"] == "google/gemma-test"
    assert body["rules_version"]


def test_analyze_endpoint_returns_findings_and_disclaimers(client: TestClient) -> None:
    response = client.post(
        "/api/analyze",
        json={
            "project_name": "  Demo project  ",
            "files": [
                {"path": "render.yaml", "content": RENDER_PAID},
                {"path": ".env", "content": DOTENV},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_name"] == "Demo project"
    assert body["summary"]["findings_total"] > 0
    assert body["fingerprint"]
    assert body["engine"]["name"] == "credpilot-rules"
    assert body["findings"]
    assert body["cleanup_tasks"]
    assert body["disclaimers"]
    assert body["parse_notes"][0]["ok"] is True


def test_analyze_accepts_project_name_blank_and_defaults(client: TestClient) -> None:
    response = client.post(
        "/api/analyze",
        json={
            "project_name": "   ",
            "files": [{"path": "render.yaml", "content": RENDER_FREE}],
        },
    )

    assert response.status_code == 200
    assert response.json()["project_name"] == "My hackathon project"


def test_analyze_rejects_empty_file_list(client: TestClient) -> None:
    response = client.post("/api/analyze", json={"files": []})
    assert response.status_code == 422


def test_analyze_rejects_duplicate_paths_case_insensitively(client: TestClient) -> None:
    response = client.post(
        "/api/analyze",
        json={
            "files": [
                {"path": "render.yaml", "content": RENDER_FREE},
                {"path": "RENDER.YAML", "content": RENDER_FREE},
            ]
        },
    )
    assert response.status_code == 422
    assert "duplicate file path" in response.text.lower()


def test_analyze_rejects_traversal_and_absolute_paths(client: TestClient) -> None:
    for path in ("../secrets.env", "config/../../.env", "/etc/passwd", "C:/secret.env"):
        response = client.post(
            "/api/analyze",
            json={"files": [{"path": path, "content": "DEBUG=false"}]},
        )
        assert response.status_code == 422, path


def test_analyze_rejects_nul_bytes_and_oversized_files(client: TestClient) -> None:
    nul = client.post(
        "/api/analyze",
        json={"files": [{"path": ".env", "content": "A=1\x00B=2"}]},
    )
    assert nul.status_code == 422

    oversized = client.post(
        "/api/analyze",
        json={"files": [{"path": ".env", "content": "A=" + "x" * 120_001}]},
    )
    assert oversized.status_code == 422
    assert "byte limit" in oversized.text.lower()


def test_analyze_rejects_too_many_files(client: TestClient) -> None:
    response = client.post(
        "/api/analyze",
        json={
            "files": [
                {"path": f".env.{index}", "content": "DEBUG=false"}
                for index in range(9)
            ]
        },
    )
    assert response.status_code == 422


def test_analyze_normalizes_backslash_paths(client: TestClient) -> None:
    response = client.post(
        "/api/analyze",
        json={"files": [{"path": ".\\config\\render.yaml", "content": RENDER_FREE}]},
    )

    assert response.status_code == 200
    assert response.json()["parse_notes"][0]["file"] == "config/render.yaml"


def test_explain_degrades_when_ai_is_not_configured(client: TestClient) -> None:
    response = client.post(
        "/api/explain",
        json={"files": [{"path": "render.yaml", "content": RENDER_FREE}]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["explanation"] is None
    assert "not configured" in body["reason"].lower()
    assert body["guardrail"]


def test_explain_rate_limit_returns_429(settings: Settings) -> None:
    limited = Settings(
        hf_token=None,
        gemma_model=settings.gemma_model,
        cors_origins=settings.cors_origins,
        ai_requests_per_minute=1,
        ai_timeout_seconds=settings.ai_timeout_seconds,
        static_dir=None,
        app_env="test",
        loaded_dotenv=False,
    )
    payload = {"files": [{"path": "render.yaml", "content": RENDER_FREE}]}

    with TestClient(create_app(limited)) as client:
        first = client.post("/api/explain", json=payload)
        second = client.post("/api/explain", json=payload)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["retry-after"]
    assert "deterministic checks are still available" in second.json()["detail"].lower()


def test_security_headers_are_set(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["permissions-policy"]


def test_cors_allows_configured_origin_only(client: TestClient) -> None:
    allowed = client.get(
        "/api/health", headers={"Origin": "http://localhost:5173"}
    )
    denied = client.get("/api/health", headers={"Origin": "https://evil.example"})

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers


def test_root_returns_api_metadata_without_a_frontend_build(
    client: TestClient,
) -> None:
    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "CredPilot API"
    assert body["docs"] == "/api/docs"


def test_static_spa_is_served_with_client_side_routing(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text(
        "<!doctype html><title>CredPilot SPA</title>", encoding="utf-8"
    )
    (tmp_path / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")

    settings = Settings(
        hf_token=None,
        gemma_model="google/gemma-test",
        cors_origins=("http://localhost:5173",),
        ai_requests_per_minute=10,
        ai_timeout_seconds=5.0,
        static_dir=tmp_path,
        app_env="test",
        loaded_dotenv=False,
    )

    with TestClient(create_app(settings)) as client:
        root = client.get("/")
        asset = client.get("/assets/app.js")
        route = client.get("/some/client/route")
        api_missing = client.get("/api/does-not-exist")

    assert root.status_code == 200
    assert "CredPilot SPA" in root.text
    assert asset.status_code == 200
    assert "console.log" in asset.text
    assert route.status_code == 200
    assert "CredPilot SPA" in route.text
    assert api_missing.status_code == 404


def test_openapi_docs_are_available(client: TestClient) -> None:
    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/api/docs").status_code == 200
