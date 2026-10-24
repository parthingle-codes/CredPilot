"""FastAPI entrypoint.

Production runs one origin: this app serves /api/* and the built Vite SPA.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import __version__
from .ai.gemma import explain
from .analysis import SourceFile, analyze
from .analysis.constants import RULES_VERSION
from .config import Settings
from .models import (
    AnalyzeRequest,
    AnalysisResponse,
    ExplainRequest,
    ExplainResponse,
    HealthResponse,
)
from .rate_limit import SlidingWindowLimiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("credpilot")


def _source_files(payload: AnalyzeRequest) -> list[SourceFile]:
    return [SourceFile(path=file.path, content=file.content) for file in payload.files]


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _spa_response(static_dir: Path, full_path: str) -> FileResponse:
    root = static_dir.resolve()
    candidate = (root / full_path).resolve()
    if candidate.is_file() and (candidate == root or root in candidate.parents):
        return FileResponse(candidate)
    index = root / "index.html"
    if index.is_file():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    raise HTTPException(status_code=404, detail="Frontend build not found")


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings.from_env()
    app = FastAPI(
        title="CredPilot API",
        version=__version__,
        description=(
            "Deterministic deployment-safety checks for Render Blueprints, Docker Compose, "
            "and .env files. Optional Gemma explanations are generated only from findings."
        ),
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.settings = resolved
    limiter = SlidingWindowLimiter(resolved.ai_requests_per_minute, 60.0)
    app.state.ai_limiter = limiter

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
        max_age=600,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        return response

    @app.get("/api/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            version=__version__,
            rules_version=RULES_VERSION,
            ai_configured=resolved.ai_configured,
            gemma_model=resolved.gemma_model,
        )

    @app.post("/api/analyze", response_model=AnalysisResponse, tags=["analysis"])
    def analyze_endpoint(payload: AnalyzeRequest) -> AnalysisResponse:
        try:
            return analyze(_source_files(payload), project_name=payload.project_name)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/explain", response_model=ExplainResponse, tags=["optional AI"])
    async def explain_endpoint(
        payload: ExplainRequest, request: Request
    ) -> ExplainResponse:
        allowed, retry_after = limiter.allow(_client_key(request))
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Too many AI requests. Deterministic checks are still available. "
                    f"Try again in {retry_after} seconds."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        files = _source_files(payload)
        analysis = await run_in_threadpool(
            lambda: analyze(files, project_name=payload.project_name)
        )
        return await explain(analysis, resolved)

    @app.get("/", include_in_schema=False)
    async def root():
        if resolved.static_dir and (resolved.static_dir / "index.html").is_file():
            return FileResponse(
                resolved.static_dir / "index.html", headers={"Cache-Control": "no-cache"}
            )
        return {
            "name": "CredPilot API",
            "version": __version__,
            "docs": "/api/docs",
            "health": "/api/health",
        }

    if resolved.static_dir and resolved.static_dir.is_dir():
        assets = resolved.static_dir / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found")
            return _spa_response(resolved.static_dir, full_path)

    return app


app = create_app()
