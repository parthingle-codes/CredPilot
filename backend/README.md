# CredPilot backend

FastAPI service that performs the deterministic deployment-config analysis and
optionally calls Gemma through Hugging Face Inference Providers for a plain-English
explanation of findings.

See the [root README](../README.md) for architecture, environment variables, the
rule set, and deployment instructions.

## Run locally

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Serve the built frontend from the same origin by setting `CREDPILOT_STATIC_DIR`
to `..\frontend\dist`.

## Test

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
```

Current result: 113 passed (one Starlette `httpx` deprecation warning).
