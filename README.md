# Driver

Personal health platform. Self-hosted on Mac Mini, accessible via Tailscale.

Tracks food intake, exercise, sleep, bloodwork, body metrics, supplements, and medications. The long-term product scope also includes adaptive training suggestions powered by Oura HRV and Apple Watch HR zone data.

## Stack

- **Backend:** FastAPI (Python 3.12)
- **Database:** SQLite (WAL mode)
- **Deployment:** Docker on Mac Mini, accessible via Tailscale

## Current Status

This repository currently contains:

- A FastAPI backend
- A minimal React + Vite frontend scaffold for the Today dashboard, including weight and waist trends plus weekly intake views
- A SQLite schema covering the planned health domains
- Food endpoints, body metrics endpoints, exercise session/set endpoints, and basic dashboard aggregate endpoints
- GitHub Actions for linting, tests, dependency audit, and CodeQL

This repository does not currently contain:

- Oura sync jobs
- Apple Health ingest jobs
- Most non-food API routes from the PRD

## Structure

```
driver/
├── backend/          # FastAPI app
│   ├── app/
│   │   ├── main.py
│   │   ├── db.py
│   │   └── routers/
│   ├── schema.sql
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── Dockerfile
├── frontend/         # Minimal React + Vite dashboard scaffold
├── tests/            # Backend API tests
├── scripts/          # One-off migration and future ingest scripts
├── .github/          # CI and code scanning workflows
├── docker-compose.yml
├── .env.example
└── docs/
    ├── CI.md
    └── PRD.md
```

## Phases

- **Phase 1:** Docker setup, schema, food API, React scaffold, data migration
- **Phase 2:** Exercise + sleep, Apple Watch ingest, Oura sync, HR zone analysis
- **Phase 3:** Labs, body metrics, supplements, medications, medical history
- **Phase 4:** Training intelligence (adaptive routine + daily suggestions), polish, PWA

## Setup

See `docs/PRD.md` for full requirements.
See `docs/CI.md` for CI checks and branch protection expectations.
See `CONTRIBUTING.md` for review and validation expectations.
See `docs/DEVELOPMENT.md` for local backend commands.

```bash
cp .env.example .env
docker compose up --build
```

The current `docker-compose.yml` starts the backend on port `8100` and the minimal frontend scaffold on port `8101`.
