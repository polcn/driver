# Driver

Personal health platform. Self-hosted on Mac Mini, accessible via Tailscale.

Tracks food intake, exercise, sleep, bloodwork, body metrics, supplements, and medications. The long-term product scope also includes adaptive training suggestions powered by Oura HRV and Apple Watch HR zone data.

## Stack

- **Backend:** FastAPI (Python 3.12)
- **Database:** SQLite (WAL mode)
- **Deployment:** Native macOS (launchd), accessible via Tailscale

## Current Status

This repository currently contains:

- A FastAPI backend serving both the API and built frontend static files
- A React + Vite frontend for the Today dashboard, including weight and waist trends plus weekly intake views
- A SQLite schema covering the planned health domains
- Food endpoints, body metrics endpoints, exercise session/set endpoints, sleep endpoints, and basic dashboard aggregate endpoints
- GitHub Actions for linting, tests, dependency audit, and CodeQL
- Oura ingest endpoint and scheduled sync workflow (`.github/workflows/oura-sync.yml`)

## Structure

```
driver/
├── backend/          # FastAPI app
│   ├── app/
│   │   ├── main.py   # API + StaticFiles mount for frontend
│   │   ├── db.py
│   │   └── routers/
│   ├── schema.sql
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── Dockerfile     # Docker setup (for CI reference)
├── frontend/         # React + Vite dashboard
├── tests/            # Backend API tests
├── scripts/          # Sync and migration scripts
├── data/             # SQLite database (not in git)
├── logs/             # Service logs (not in git)
├── start.sh          # Service launcher script
├── docker-compose.yml # Docker setup (for CI reference)
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
- **Phase 5:** Goals, doctor visit reports, photo food logging
- **Phase 6:** Photo intelligence, coaching digests

## Setup

See `docs/PRD.md` for full requirements.
See `docs/CI.md` for CI checks and branch protection expectations.
See `docs/DEVELOPMENT.md` for local development commands.
See `CONTRIBUTING.md` for review and validation expectations.

```bash
# Native setup
cp .env.example .env          # edit DATABASE_PATH and tokens
pyenv install 3.12
python3.12 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install && npm run build && cd ..
make run                      # starts on port 8000
```

The backend serves both the API (`/api/v1/...`) and the built frontend on port 8000.
