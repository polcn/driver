# Task: CPAP Ingest (PRD 11.3)

## Overview
Implement `POST /api/v1/ingest/cpap` — fetches ResMed AirSense 11 STR.edf from Google Drive, parses nightly CPAP data, upserts into `sleep_records`.

## Spec
See `docs/PRD.md` section 11.3 for full spec. Key points below.

## Backend

### Dependencies (add to `backend/requirements.txt`)
- `google-auth` — service account auth
- `google-api-python-client` — Drive API file download
- `pyedflib` — EDF file parsing

### Google Drive download
- Credentials path from env var `GOOGLE_SERVICE_ACCOUNT_PATH` (see `.env.example`)
- Service account email: shared with OpenClaw (already has access to `mcgrupp/resmed/` folder)
- Download `STR.edf` to a temp file, parse, delete temp file
- If file not found: return `{"status": "error", "detail": "STR.edf not found in mcgrupp/resmed/"}`

### EDF Parser (`backend/app/parsers/cpap_edf.py`)
- ResMed STR.edf is a multi-signal EDF containing nightly summary data
- Extract per-night records with these fields:
  - `recorded_date` — date of the CPAP session
  - `cpap_used` — always `1`
  - `cpap_ahi` — apnea-hypopnea index (raw value × 0.1)
  - `cpap_hours` — usage hours
  - `cpap_leak_95` — 95th percentile leak rate (raw value × 0.02, units: L/s)
  - `cpap_pressure_avg` — average mask pressure (raw value × 0.02, units: cmH2O)
- Scale factors are critical — raw EDF values must be multiplied by the factors above

### Endpoint (`backend/app/routers/ingest.py`)
- `POST /api/v1/ingest/cpap` — no request body
- Follow existing patterns in `ingest_apple_health()` and `ingest_oura()`
- Upsert logic:
  - `INSERT INTO sleep_records ... ON CONFLICT(recorded_date) DO UPDATE SET cpap_used=1, cpap_ahi=?, cpap_hours=?, cpap_leak_95=?, cpap_pressure_avg=?`
  - The ON CONFLICT UPDATE must ONLY set CPAP columns — do NOT overwrite `bedtime`, `wake_time`, `duration_min`, `deep_min`, `rem_min`, `hrv`, `resting_hr`, `readiness_score`, `sleep_score`, or `source`
  - For new rows (no existing Oura data for that date): set `source='cpap'`
- Full re-import each time (not incremental) — safe due to upsert
- Response: `{"status": "ok", "nights_imported": N, "date_range": "YYYY-MM-DD → YYYY-MM-DD", "avg_ahi": X.XX, "skipped": 0}`
- Error responses: `{"status": "error", "detail": "..."}`

### Schema
Already in place — `sleep_records` table has all CPAP columns and `source` CHECK includes `'cpap'`. No migrations needed.

### Tests (`tests/test_ingest_cpap.py`)
- Test EDF parser with a small synthetic EDF fixture (or mock)
- Test endpoint with mocked Drive download + mocked EDF data
- Test upsert: CPAP data merges onto existing Oura row without overwriting sleep fields
- Test upsert: CPAP data creates new row with source=cpap when no Oura row exists
- Test error: Drive file not found returns proper error response
- Test error: corrupt EDF returns proper error response

## Frontend (`frontend/src/App.jsx`)

### Sleep panel changes
- Add "Import CPAP Data" button below existing sleep content
- On click: POST to `/api/v1/ingest/cpap`, show spinner during request
- On success: display summary (nights imported, date range, avg AHI)
- On error: display error message
- Show last import date and total CPAP nights on record (query from existing sleep data)
- Display CPAP metrics when available: AHI, compliance hours, leak, pressure

## Notes
- The `GOOGLE_SERVICE_ACCOUNT_PATH` env var is already in `.env.example`
- The ingest router is already mounted at `/api/v1/ingest` in `main.py`
- Keep the parser in its own module (`backend/app/parsers/cpap_edf.py`) — it will be reusable
- Do NOT hardcode any credential paths — always read from env
