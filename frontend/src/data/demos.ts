import type { Demo } from '../types'

/**
 * Synthetic fixtures only. Values are deliberately fake, and the UI labels
 * every demo as synthetic. Never replace these with real credentials.
 */

const sprintRender = `# Synthetic demo — not a real deployment or credential.
services:
  - type: web
    name: credpilot-demo-api
    runtime: python
    plan: starter
    region: oregon
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /api/health
    envVars:
      - key: HF_TOKEN
        value: hf_SYNTHETIC_DEMO_TOKEN_000000000000
      - key: DATABASE_URL
        value: postgres://demo:demo_password@db.internal:5432/demo
      - key: CORS_ORIGINS
        value: "*"
      - key: DEBUG
        value: "true"
    disk:
      name: uploads
      mountPath: /var/data
      sizeGB: 5

  - type: worker
    name: demo-indexer
    runtime: python
    plan: starter
    buildCommand: pip install -r requirements.txt
    startCommand: python worker.py

databases:
  - name: credpilot-demo-db
    plan: free
    ipAllowList: []

previews:
  generation: automatic
`

const sprintEnv = `# Synthetic demo values — not real credentials.
HF_TOKEN=hf_SYNTHETIC_DEMO_TOKEN_000000000000
OPENAI_API_KEY=sk-SYNTHETIC_DEMO_KEY_0000000000
DATABASE_URL=postgres://demo:demo_password@localhost:5432/demo
DEBUG=true
CORS_ORIGINS=*
VITE_API_BASE_URL=http://localhost:8000
`

const composeStack = `# Synthetic demo — not a real deployment.
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - HF_TOKEN=\${HF_TOKEN}
      - DATABASE_URL=postgres://demo:demo_password@db:5432/demo
      - DEBUG=true
    depends_on:
      - db
    restart: unless-stopped

  db:
    image: postgres:latest
    ports:
      - "5432:5432"
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: demo
    volumes:
      - demo-data:/var/lib/postgresql/data

  tools:
    image: alpine:latest
    privileged: true
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./scripts:/scripts

volumes:
  demo-data:
`

const cleanRender = `# Synthetic demo — a mostly clean free-tier configuration.
services:
  - type: web
    name: credpilot-clean-demo
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /api/health
    envVars:
      - key: HF_TOKEN
        sync: false
      - key: DATABASE_URL
        fromDatabase:
          name: credpilot-clean-db
          property: connectionString

databases:
  - name: credpilot-clean-db
    plan: free
    ipAllowList: []
`

const cleanEnv = `# Example only — replace values locally, never commit a real .env.
DEBUG=false
CORS_ORIGINS=https://credpilot-demo.onrender.com
DATABASE_URL=postgresql://demo:\${DB_PASSWORD}@db:5432/demo
`

export const demos: Demo[] = [
  {
    id: 'hackathon-sprint',
    name: 'Hackathon sprint',
    tagline: 'Paid plans, a disk, previews, and leaked demo keys.',
    projectName: 'Hackathon sprint demo',
    files: [
      { path: 'render.yaml', content: sprintRender },
      { path: '.env', content: sprintEnv },
    ],
  },
  {
    id: 'compose-stack',
    name: 'Compose stack',
    tagline: 'A database port open to the host and a mounted Docker socket.',
    projectName: 'Weekend Compose stack',
    files: [{ path: 'docker-compose.yml', content: composeStack }],
  },
  {
    id: 'clean-render',
    name: 'Free-tier clean',
    tagline: 'No paid plans. Still has free-tier limits worth knowing.',
    projectName: 'Free-tier demo',
    files: [
      { path: 'render.yaml', content: cleanRender },
      { path: '.env', content: cleanEnv },
    ],
  },
]

export const fileTemplates = {
  render: `# Render Blueprint
services:
  - type: web
    name: my-demo
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /api/health
`,
  compose: `# Docker Compose
services:
  api:
    image: nginx:1.27-alpine
    ports:
      - "8080:80"
`,
  dotenv: `# Add KEY=value pairs. Do not paste real production credentials.
DEBUG=false
`,
} as const
