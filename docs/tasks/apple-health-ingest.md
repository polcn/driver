# Task: Build Apple Health Auto Export Ingest Endpoint

## Overview
Build `POST /api/v1/ingest/apple-health` — receives JSON from Health Auto Export (iOS app) and loads it into the Driver SQLite database. All upserts must be idempotent (safe to POST same data multiple times).

---

## Health Auto Export JSON Payload Format

```json
{
  "data": {
    "metrics": [
      {
        "name": "resting_heart_rate",
        "units": "count/min",
        "data": [{ "date": "2026-02-27 08:00:00", "qty": 58 }]
      },
      {
        "name": "heart_rate_variability",
        "units": "ms",
        "data": [{ "date": "2026-02-27", "qty": 38.2 }]
      },
      {
        "name": "weight_body_mass",
        "units": "lb",
        "data": [{ "date": "2026-02-27 07:00:00", "qty": 198.4 }]
      },
      {
        "name": "active_energy",
        "units": "kcal",
        "data": [{ "date": "2026-02-27", "qty": 450 }]
      },
      {
        "name": "step_count",
        "units": "count",
        "data": [{ "date": "2026-02-27", "qty": 8234 }]
      },
      {
        "name": "sleep_analysis",
        "units": "hr",
        "data": [{ "date": "2026-02-27", "qty": 6.5 }]
      }
    ],
    "workouts": [
      {
        "name": "Traditional Strength Training",
        "start": "2026-02-27 09:00:00",
        "end": "2026-02-27 10:00:00",
        "duration": 3600,
        "activeEnergy": { "qty": 320, "units": "kcal" },
        "totalEnergy": { "qty": 380, "units": "kcal" },
        "heartRateData": [
          { "date": "2026-02-27 09:00:00", "qty": 95 },
          { "date": "2026-02-27 09:15:00", "qty": 128 },
          { "date": "2026-02-27 09:30:00", "qty": 142 },
          { "date": "2026-02-27 09:45:00", "qty": 115 }
        ]
      }
    ]
  }
}
```

Batch Requests is enabled in the app — the same endpoint receives multiple POSTs for a historical import. Must be fully idempotent.

---

## Files to Create

### `backend/app/routers/ingest.py`

#### Metrics mapping (metric name → body_metrics.metric):
| Health Auto Export name | body_metrics.metric |
|------------------------|---------------------|
| `resting_heart_rate` | `resting_hr` |
| `heart_rate_variability` | `hrv` |
| `weight_body_mass` | `weight_lbs` |
| `active_energy` | `active_calories` |
| `step_count` | `steps` |
| `basal_energy_burned` | `basal_calories` |
| anything else | use name as-is |

- Skip `heart_rate` (raw HR — too granular, used in workouts only)
- Handle `sleep_analysis` separately (see below)

#### Sleep mapping:
- `sleep_analysis` → `sleep_records` with `source='apple_health'`
- `duration_min` = qty * 60
- INSERT OR IGNORE — never overwrite existing Oura record for same date

#### Workout mapping (workouts[] → exercise_sessions):
Session type mapping:
| Workout name contains | session_type |
|-----------------------|--------------|
| Strength, Weight | strength |
| Running, Walk, Hike | cardio |
| Cycling, Bike | cardio |
| Stair, Elliptical, Rowing, HIIT, Cardio | cardio |
| Yoga, Stretch, Pilates | flexibility |
| anything else | strength |

Fields:
- `recorded_date` = date portion of `start`
- `external_id` = `apple_health:{start}` (unique idempotency key for Apple workout events)
- `duration_min` = duration / 60
- `calories_burned` = activeEnergy.qty
- `avg_heart_rate` = mean of heartRateData[].qty (if present)
- `max_heart_rate` = max of heartRateData[].qty (if present)
- `source` = "apple_health"

Dedupe: INSERT OR IGNORE on `(source, external_id)`.

#### HR Zone calculation (after inserting exercise_session):
Max HR = 164 bpm (220 - 56)

| Zone | BPM Range |
|------|-----------|
| 1 | < 98 |
| 2 | 98 <= bpm < 115 |
| 3 | 115 <= bpm < 131 |
| 4 | 131 <= bpm < 148 |
| 5 | >= 148 |

From heartRateData time series:
- Sort by date, interpolate time between consecutive readings
- Calculate minutes spent in each zone
- pct_of_session = zone_minutes / total_session_minutes * 100
- Insert into exercise_hr_zones (session_id, zone, minutes, pct_of_session)
- DELETE existing zones for session before re-inserting (idempotent)

#### Idempotency:
- `body_metrics`: INSERT OR REPLACE on (recorded_date, metric, source)
- `sleep_records`: INSERT OR IGNORE
- `exercise_sessions`: INSERT OR IGNORE on (source, external_id)

#### Response:
```json
{ "status": "ok", "processed": { "metrics": 42, "workouts": 3, "skipped": 1 } }
```

---

## Files to Modify

### `backend/app/main.py`
Register ingest router:
```python
from .routers import ingest
app.include_router(ingest.router, prefix="/api/v1/ingest", tags=["ingest"])
```

Add Oura stub: `POST /api/v1/ingest/oura` → `{"status": "coming_soon"}`

### `backend/schema.sql`
Add schema support required for true idempotency:

1. `body_metrics` unique index:
```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_body_metrics_recorded_metric_source
ON body_metrics(recorded_date, metric, source);
```

2. `exercise_sessions` idempotency key:
```sql
-- add `external_id TEXT` to exercise_sessions table definition
-- for existing databases, run:
ALTER TABLE exercise_sessions ADD COLUMN external_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS uq_exercise_source_external_id
ON exercise_sessions(source, external_id)
WHERE external_id IS NOT NULL;
```

---

## Tests: `tests/test_ingest.py`

1. POST metrics → body_metrics rows created correctly
2. POST workouts with heartRateData → exercise_session + hr_zones created
3. POST same data twice → no duplicates
4. POST sleep_analysis → sleep_records created
5. POST sleep_analysis when oura record exists → oura NOT overwritten
6. POST sleep_analysis first, then Oura sleep record POST/upsert → Oura wins (record replaced with source=`oura`)
7. POST workout with no heartRateData → session created, no hr_zones, no crash
8. HR zone calc: all HR in Zone 2 → 100% Zone 2
9. Two same-day workouts with same name but different `start` values both persist (no false dedupe)

---

## Schema Reference

```sql
body_metrics (id, recorded_date DATE, metric TEXT, value REAL, source TEXT, notes TEXT, created_at)
exercise_sessions (id, recorded_date DATE, session_type TEXT, name TEXT, duration_min INTEGER,
                   calories_burned REAL, avg_heart_rate INTEGER, max_heart_rate INTEGER,
                   source TEXT, external_id TEXT, notes TEXT, created_at, deleted_at)
exercise_hr_zones (id, session_id INTEGER FK, zone INTEGER 1-5, minutes REAL, pct_of_session REAL)
sleep_records (id, recorded_date DATE UNIQUE, duration_min INTEGER, hrv REAL, resting_hr INTEGER,
               readiness_score INTEGER, sleep_score INTEGER, cpap_ahi REAL, cpap_hours REAL,
               cpap_pressure_avg REAL, source TEXT, created_at)
```

## Constraints
- No new dependencies
- Use get_db() from app/db.py
- Timestamps are local time "YYYY-MM-DD HH:MM:SS" — store recorded_date as "YYYY-MM-DD"
- Handle missing/null fields gracefully throughout
