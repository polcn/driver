# Pulse

Personal health platform. Self-hosted on Mac Mini, accessible via Tailscale.

Tracks food intake, exercise, sleep, bloodwork, body metrics, supplements, and medications — with adaptive training suggestions powered by Oura HRV and Apple Watch HR zone data.

## Stack

- **Backend:** FastAPI (Python 3.12)
- **Database:** SQLite (WAL mode)
- **Frontend:** React 18 + Vite + Recharts + Tailwind CSS
- **Ingestion:** Oura API sync + Health Auto Export REST API push
- **Deployment:** Docker on Mac Mini, accessible via Tailscale

## Structure

```
driver/
├── backend/          # FastAPI app
│   ├── app/
│   │   ├── main.py
│   │   ├── db.py
│   │   ├── models/
│   │   ├── routers/
│   │   └── schemas/
│   ├── schema.sql
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/         # React + Vite app
│   ├── src/
│   ├── index.html
│   ├── package.json
│   └── Dockerfile
├── scripts/          # Sync jobs, migration, import tools
├── docker-compose.yml
├── .env.example
└── docs/
    └── PRD.md
```

## Phases

- **Phase 1:** Docker setup, schema, food API, React scaffold, data migration
- **Phase 2:** Exercise + sleep, Apple Watch ingest, Oura sync, HR zone analysis
- **Phase 3:** Labs, body metrics, supplements, medications, medical history
- **Phase 4:** Training intelligence (adaptive routine + daily suggestions), polish, PWA

## Setup

See `docs/PRD.md` for full requirements.

```bash
cp .env.example .env
docker compose up --build
```
