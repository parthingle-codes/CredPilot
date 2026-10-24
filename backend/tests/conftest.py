"""Shared pytest fixtures for the CredPilot backend."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        hf_token=None,
        gemma_model="google/gemma-test",
        cors_origins=("http://localhost:5173",),
        ai_requests_per_minute=10,
        ai_timeout_seconds=5.0,
        static_dir=None,
        app_env="test",
        loaded_dotenv=False,
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
