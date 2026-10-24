# CredPilot

**A pre-flight check for student cloud demos.** CredPilot reads a deployment config, finds billing traps, deployment limits, exposed credentials, and cleanup debt, then gives you an evidence-backed checklist to clear before the demo.

It is a static analyzer. It never connects to your cloud account, never deploys anything, and never deletes a resource. The optional Gemma layer only explains findings the deterministic rules already produced.

```
render.yaml / docker-compose.yml / .env
              │
              ▼
   line-aware parsers + versioned rules
              │
              ▼
   findings with file:line evidence
              │
              ├── editable cleanup checklist
              ├── Markdown report
              └── optional Gemma explanation
                  (finding metadata only, no raw config)
```

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | React 19 + Vite 8 + TypeScript |
| Backend | Python FastAPI + PyYAML |
| Optional AI | Gemma via Hugging Face Inference Providers (OpenAI-compatible router) |
| Deployment | One Render Docker web service; FastAPI serves `/api/*` and the built SPA |
| Storage | None. Checklist state lives in the browser's localStorage. |

There is no database, no auth, no queue, and no cloud SDK. The only outbound request is the optional Hugging Face call.

## What it checks

### `render.yaml` (Render Blueprint)

- Paid compute plans, paid database plans, and paid defaults when `plan` is omitted
- Persistent disks, including the free-plan/disk incompatibility
- Workers, cron jobs, private services, workflows, and autoscaling that can run without demo traffic
- Automatic preview environments and per-service PR previews
- Free web spin-down and free database expiry
- Database network exposure, read replicas, high availability, storage autoscaling
- Key Value free-tier limits and required IP allow lists
- Literal secrets in `envVars`, secret variables with no source, metered provider credentials
- Missing runtime/type/start command/health check, invalid health paths, cron schedule gaps

### `docker-compose.yml` / `compose.yaml`

- Published database/cache ports (`5432`, `3306`, `6379`, `27017`, and others)
- Literal secrets, embedded URL credentials, debug mode, wildcard CORS, localhost URLs
- Unpinned or `latest` images
- Missing CPU/memory limits
- Privileged containers, host networking, Docker socket mounts
- Persistent volumes, restart policies, replicas
- Missing image/build context

### `.env` / dotenv

- Literal credentials and token-shaped values
- Password embedded in a connection URL
- Metered provider keys (billing risk is flagged, never priced)
- Debug mode, non-production `NODE_ENV`, wildcard CORS, loopback bindings, localhost service URLs
- Ephemeral SQLite paths and duplicate keys
- `.env.example` files with real-looking values are treated as a separate, high-severity case

Every finding carries `file`, `line`, and a redacted snippet where available. Unsupported or malformed files are reported instead of silently skipped.

## Safety model

- **No account access.** CredPilot cannot see balances, usage, quotas, invoices, or current prices.
- **No invented numbers.** The 0–100 score is an exposure heuristic, not a bill or savings estimate.
- **No automatic changes.** Cleanup is a manual checklist. CredPilot never pauses, deletes, or rotates anything.
- **Secrets are redacted before display.** Evidence snippets and report text are passed through the redaction layer. Token-shaped values, URL passwords, and secret assignments are replaced.
- **The AI prompt has no raw values.** It contains finding titles, severities, resources, messages, and `file:line` locations — no file contents, env values, or evidence snippets. AI output is never parsed back into findings. Output that appears to state a price or savings claim is withheld.
- **Synthetic demos only.** The bundled demos use deliberately fake values. Never paste live production credentials into a demo or an issue.

## Risk score

The score is a capped sum of severity weights:

| Severity | Weight |
| --- | --- |
| Critical | 60 |
| High | 25 |
| Medium | 10 |
| Low | 3 |
| Info | 0 |

| Score | Level |
| --- | --- |
| 0 | Clear |
| 1–19 | Low |
| 20–44 | Elevated |
| 45–74 | High |
| 75–100 | Critical |

The UI and exported report repeat that this is not a cost estimate.

## Local development

Tested with Python 3.14.5, Node 24.19.0, and npm 11.17.0.

### 1. Backend

From the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
Copy-Item .env.example .env
```

Edit `.env` only if you want optional AI explanations. Without `HF_TOKEN`, every deterministic check still works.

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

- API docs: `http://127.0.0.1:8000/api/docs`
- Health: `http://127.0.0.1:8000/api/health`

On macOS/Linux, use `python -m venv .venv`, `source .venv/bin/activate`, and `pip install -r backend/requirements-dev.txt`.

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://127.0.0.1:8000`, so no API URL is needed in development.

### 3. Production-style local run

```powershell
cd frontend
npm run build
cd ..\backend
$env:CREDPILOT_STATIC_DIR="..\frontend\dist"
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. FastAPI serves the SPA and API from one origin.

## Environment variables

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `HF_TOKEN` | No | unset | Enables optional Gemma explanations. Use an Inference Providers token. |
| `GEMMA_MODEL` | No | `google/gemma-4-26B-A4B-it:cheapest` | Hugging Face model id. |
| `CORS_ORIGINS` | No | localhost dev origins | Comma-separated allowed browser origins. Same-origin production needs no entry. |
| `AI_REQUESTS_PER_MINUTE` | No | `10` | In-process limit for `/api/explain`. |
| `AI_TIMEOUT_SECONDS` | No | `45` | Hugging Face request timeout. |
| `CREDPILOT_STATIC_DIR` | Production only | unset | Directory containing the built SPA. Docker sets `/app/static`. |
| `VITE_API_URL` | No | empty | Only for a split frontend/backend deployment. Empty means same-origin. |
| `APP_ENV` | No | `development` | Free-form environment label. |

`HF_TOKEN` is read from the environment or a local `.env`, never logged and never returned to the browser. The health endpoint exposes only `ai_configured` and the public model id.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Version, rules version, AI configured flag |
| `POST` | `/api/analyze` | Deterministic analysis |
| `POST` | `/api/explain` | Optional Gemma explanation of the deterministic result |
| `GET` | `/api/docs` | OpenAPI UI |
| `GET` | `/api/openapi.json` | OpenAPI schema |

Input limits: 1–8 files, 120,000 bytes per file, 300,000 bytes total. Paths must be relative, with no `.`/`..` segments. Duplicate paths are rejected case-insensitively.

## Deploy to Render

The included `render.yaml` defines one free Docker web service. FastAPI serves both the API and the built Vite app, so there is no second static site and no cross-origin API URL to misconfigure.

1. Push the repository to GitHub.
2. In Render, choose **New → Blueprint** and connect the repository.
3. Render reads `render.yaml`. Optionally enter `HF_TOKEN` in the dashboard when prompted (`sync: false`).
4. Apply the Blueprint. The health check is `/api/health`.
5. Open the service URL.

Operational notes:

- Free Render web services spin down after 15 minutes without traffic and take about a minute to wake. Warm the URL before presenting.
- The app does not provision a database, so the free Render Postgres 30-day expiry does not apply to this deployment.
- The AI rate limit is in-process and resets on restart. Behind Render's proxy, callers may share a client key; it is a credit guard, not a security boundary.

## Tests and verification

Run the backend suite from `backend/`:

```powershell
..\.venv\Scripts\python.exe -m pytest
```

Run the frontend production build from `frontend/`:

```powershell
npm run build
```

### Actual results on 2026-10-24

| Check | Result |
| --- | --- |
| Backend pytest | **113 passed, 1 warning** (~0.4s) |
| Frontend build (`tsc --noEmit && vite build`) | **Passed** — 35 modules, JS 282.19 kB (86.13 kB gzip), CSS 42.62 kB (8.94 kB gzip) |
| Integration smoke (`uvicorn` + built SPA) | **Passed** — `/api/health` 200, `/` 200, SPA fallback `/dashboard` 200, hashed JS/CSS assets 200, unknown `/api/*` 404. `POST /api/analyze` on the *Free-tier clean* demo: score 20, elevated, 2 findings, 7 cleanup tasks. On the *Hackathon sprint* demo: score 100, critical, 20 findings (5 critical), 22 cleanup tasks. Neither raw demo token nor embedded DB password appeared in either JSON response. |
| AI-disabled behavior | **Verified** — `/api/explain` returns `available: false` with a clear reason when `HF_TOKEN` is unset |
| Docker image build | **Not run** — Docker is not installed in the development environment |
| Live Render deployment | **Not run** — no Render account/deploy was performed here |
| Live Gemma call | **Not run** — no `HF_TOKEN` was available; the client and guardrails are covered with mocked HTTP transports |

The one warning is Starlette's deprecation notice about using `httpx` with its test client. It does not affect test results.

## Project layout

```
CredPilot/
├─ backend/
│  ├─ app/
│  │  ├─ analysis/          # parsers, rules, engine, constants
│  │  ├─ ai/                # prompt boundary + Hugging Face client
│  │  ├─ config.py          # environment settings
│  │  ├─ main.py            # FastAPI app + static SPA serving
│  │  ├─ models.py          # request/response validation
│  │  ├─ rate_limit.py
│  │  └─ security.py        # secret detection, redaction, claim guard
│  └─ tests/
├─ frontend/
│  ├─ src/components/       # config panel, results, checklist, AI, report
│  ├─ src/hooks/            # localStorage checklist
│  ├─ src/lib/              # format helpers, Markdown report
│  └─ src/styles.css        # dark flight-deck design
├─ Dockerfile               # multi-stage frontend + backend image
├─ render.yaml              # one free Render Docker web service
└─ .env.example
```

## Honest limitations

- Only three input formats are supported. Other deployment platforms are out of scope for v1.
- Findings are deterministic heuristics. A clear result is not proof that a deployment is safe, free, or correctly configured.
- The analyzer sees only the files you submit. It cannot inspect the actual cloud account, running services, logs, or secrets.
- The score is an exposure heuristic. It is not a bill, balance, usage reading, quote, or savings estimate.
- Credential detection is pattern- and key-name-based. A real credential that matches no pattern and uses an innocuous name can be missed.
- AI explanations are optional and non-authoritative. They can be wrong; price/savings claims are withheld, but the text should still be read critically.
- Cleanup is manual by design. Nothing is paused, deleted, or rotated.
- The checklist is stored per config fingerprint in localStorage. It is not synced across devices and can be cleared by the browser.
- Docker and Render deployment were not verified in this environment.

## References

- [Render free tier](https://render.com/docs/free)
- [Render Blueprint spec](https://render.com/docs/blueprint-spec)
- [Docker Compose file reference](https://docs.docker.com/reference/compose-file/)
- [Hugging Face Inference Providers](https://huggingface.co/docs/inference-providers)
- [MDN CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS)

---

No cloud resources were created, changed, or deleted by CredPilot. Verify all billing and cleanup actions in the provider dashboard.
