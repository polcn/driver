# Driver — Personal Health Platform
## Product Requirements Document
*Version 0.15 — 2026-03-01*
*Owner: Craig | Architect: McGrupp*

---

## 1. Overview

Driver is a self-hosted personal health platform running on Craig's Mac Mini, accessible via browser (desktop + mobile via Tailscale). It consolidates food intake, exercise, body metrics, bloodwork/labs, supplements, medications, and medical history into a single queryable system with a dashboard UI and a dedicated AI agent interface.

The system is designed to be built incrementally, with each phase delivering working software. It is not a prototype — it is built to last.

---

## 2. Goals

- Single source of truth for all health data
- Queryable history with trends and charts (not just logs)
- Accessible from Mac Mini browser and iPhone via Tailscale
- Agent (McGrupp health agent) can log and query via REST API — no file-reading, no raw SQL
- Ingests data from Apple Watch (via Health Auto Export REST API push) and Oura Ring (API)
- Adaptive daily training suggestions based on Oura readiness/HRV + workout history
- HR zone analysis for cardio sessions (fat burn zone optimization)
- No reminders or push notifications (out of scope)
- Private: no cloud services, no third-party data sharing

---

## 2b. User Requirements (from interview — 2026-02-27)

### Daily Usage Pattern
- Telegram throughout the day: log food, ask questions ("what's a good alternative cardio today", "how can I get better rest", "why am I not losing weight")
- Dashboard for reviewing logs, trends, and insights
- Both input (log) and query (ask) via Telegram and dashboard

### AI Question-Answering
- **Option 2**: Data-grounded + general health knowledge context
- Cross-domain correlation: "Your sleep quality dropped the two nights after alcohol exceeded 2 drinks" — patterns Oura can't see alone
- Grounds answers in actual Driver data first, then contextualizes with health knowledge

### Goals System
- Flexible: supports both hard targets (≤3 drinks/week) and directional (trending down)
- User-adjustable at any time — no hardcoded targets
- Initial goals: weight loss, reduce alcohol, reduce sodium, reduce fat
- **Goal plans**: when a goal is set, Driver + agent generate an actionable plan (deficit targets, macro adjustments, exercise recommendations, timeline). Plan adapts if progress is off track.

### Additional Features (from interview)
- **Photo food logging** — snap a photo, agent estimates macros, logs to Driver
- **Alcohol tracking by type** — beer, wine, spirits tracked separately (different trig impact patterns)
- **Symptoms** — ingested from Oura (already tracked there), not a separate UI
- **CPAP data** — ResMed AirSense 11 AutoSet; SD card data accessible via Google Drive (`mcgrupp/resmed/`); full parser built; 282 nights of data (Feb 2025–Feb 2026); ingest into `sleep_records` with AHI, compliance hours, leak, pressure; correlate with Oura sleep quality
- **Doctor visit prep** — auto-generate summary report for appointments (April 30 primary care, Dr. Tyson sleep)
- **Body measurements** — waist circumference in addition to weight (better fat loss indicator)
- **AI question answering** — "why am I not losing weight", "how can I get better rest" — data-grounded + general health knowledge (Option 2); cross-domain correlation across all data sources

### Dashboard — Desktop
Card-based layout, not static — interactive time range selectors (7d / 30d / 90d / 6mo / all time) on all trend charts:
- **Oura-style narrative insights** (top) — cross-domain, AI-generated: sleep quality, HRV, resting HR trends, correlations
- **Sleep** — duration, phases, HRV, readiness score
- **Weight** — trend chart with selectable time range
- **Heart rate trends** — resting HR, HRV over time
- **Exercise** — sessions, calories burned, HR zone breakdown
- **Steps + Active calories**
- **Calorie consumption** — daily vs. target

### Dashboard — Phone
- Same data, responsive layout, cards stack vertically, charts scale to screen
- No separate mobile design — just works

### Insights
- Driver generates its own narrative insights by correlating across ALL data sources
- Also surfaces Oura API insights where available
- Examples: "Sleep quality below your 7-day average", "Resting HR dropped 3 bpm this week", "Alcohol correlated with poor sleep quality on 4 of 6 nights"

### Proactive Telegram Delivery (8 AM CT daily)
- **Daily morning summary**: sleep, HRV, readiness, yesterday's intake vs. targets
- **Daily training suggestion**: adaptive recommendation based on Oura readiness/HRV + schedule
- **Weekly trend report**: Sunday evening — weight trend, avg protein, cardio zone time, sleep quality, alcohol

### Exercise
- Gym equipment: free weights, machines, kettlebells, cardio machines, stair machine, short indoor track, tennis, pickleball
- Cardio preference order: stair machine → bike → rower → elliptical → track → treadmill (last resort)
- Pool: deprioritized (crowded, slow)
- Strength: logs sets/reps, tracks progression over time
- Weighs in a few times/week, consistent conditions — Driver plots trend line not noise

### Voice Capture (separate project — not Phase 1)
- mlx-whisper on Mac Mini M4 host
- Apple Watch / iPhone voice memo → transcribe → route to Driver / Clawban / notes / answer
- Questions route immediately; everything else batched
- Two iOS Shortcuts: "question" (immediate) + "capture" (batch)

## 3. Non-Goals

- Native iOS/Android app (browser PWA is sufficient)
- Multi-user support
- Third-party integrations beyond Oura + Apple Health
- Medication/supplement reminders
- Calorie goal gamification / streaks / badges
- Rigid workout programs (sets/weights prescribed at the gym)
- Complex periodization engine

---

## 4. Users

One user: Craig. The agent (McGrupp) is a non-human client of the API.

---

## 5. Architecture

```
┌─────────────────────────────────────────────┐
│              Mac Mini (native)               │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  FastAPI (uvicorn, Python 3.12)      │   │
│  │  - /api/v1/* → API routes            │   │
│  │  - /* → React PWA (static files)     │   │
│  └────────────────┬─────────────────────┘   │
│                   │                          │
│          ┌────────▼─────────┐               │
│          │  SQLite (WAL)    │               │
│          │  data/driver.db  │               │
│          └──────────────────┘               │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  Sync Jobs (GitHub Actions)          │   │
│  │  - Oura API → Driver API             │   │
│  │  - Health Auto Export → Driver API    │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
          ▲                    ▲
          │ Tailscale          │ REST API
     iPhone browser       McGrupp Agent
```

**Auth**: None. Tailscale network perimeter is sufficient for personal use.
**Port**: 8000 (API + frontend), exposed via Tailscale on :8443.

---

## 6. Data Model

### 6.1 Core Principles
- All timestamps stored as UTC ISO 8601
- `recorded_date` (DATE) used for "what day does this belong to" — distinct from `created_at`
- `source` field on every entry: `manual`, `oura`, `apple_health`, `agent`
- `is_estimated` flag on nutrition entries where macros are approximated
- Soft delete: `deleted_at` timestamp, never hard-delete rows

### 6.2 Schema — Domains

#### `food_entries`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| recorded_date | DATE | "What day" — may differ from created_at |
| meal_type | TEXT | breakfast, lunch, dinner, snack, drink |
| name | TEXT | Human-readable description |
| calories | REAL | |
| protein_g | REAL | |
| carbs_g | REAL | |
| fat_g | REAL | |
| fiber_g | REAL | |
| sodium_mg | REAL | |
| alcohol_g | REAL | nullable |
| alcohol_calories | REAL | nullable |
| alcohol_type | TEXT | nullable — beer, wine, spirits, cocktail |
| photo_url | TEXT | nullable — reference to photo for photo-based logging |
| servings | REAL | default 1.0 |
| is_estimated | INTEGER | 0/1 |
| source | TEXT | manual, agent |
| notes | TEXT | nullable |
| created_at | DATETIME | |
| deleted_at | DATETIME | nullable |

#### `exercise_sessions`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| recorded_date | DATE | |
| session_type | TEXT | strength, cardio, yoga, walk, etc. |
| name | TEXT | e.g. "Chest day", "Treadmill" |
| duration_min | INTEGER | nullable |
| calories_burned | REAL | nullable |
| avg_heart_rate | INTEGER | nullable |
| max_heart_rate | INTEGER | nullable |
| source | TEXT | manual, oura, apple_health, agent |
| notes | TEXT | nullable |
| created_at | DATETIME | |
| deleted_at | DATETIME | nullable |

#### `exercise_sets` *(strength training detail)*
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| session_id | INTEGER FK → exercise_sessions | |
| exercise_name | TEXT | e.g. "Bench Press" |
| set_number | INTEGER | |
| weight_lbs | REAL | nullable |
| reps | INTEGER | nullable |
| notes | TEXT | nullable |

#### `body_metrics`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| recorded_date | DATE | |
| metric | TEXT | weight_lbs, body_fat_pct, bmi, waist_in, etc. |
| value | REAL | |
| source | TEXT | manual, apple_health, oura |
| notes | TEXT | nullable |
| created_at | DATETIME | |

#### `lab_results`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| drawn_date | DATE | |
| panel | TEXT | e.g. "Lipid Panel", "CMP", "CBC" |
| marker | TEXT | e.g. "Triglycerides", "Glucose", "LDL" |
| value | REAL | |
| unit | TEXT | e.g. "mg/dL" |
| reference_low | REAL | nullable |
| reference_high | REAL | nullable |
| flag | TEXT | nullable — "H", "L", "HH" |
| notes | TEXT | nullable |
| created_at | DATETIME | |

#### `supplements`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| name | TEXT | e.g. "Creatine", "Vitamin D3" |
| dose | TEXT | e.g. "5g", "2000 IU" |
| frequency | TEXT | daily, post-workout, as-needed |
| active | INTEGER | 0/1 — currently taking |
| started_date | DATE | nullable |
| stopped_date | DATE | nullable |
| notes | TEXT | nullable |

#### `supplement_logs`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| supplement_id | INTEGER FK | |
| recorded_date | DATE | |
| taken | INTEGER | 0/1 |
| notes | TEXT | nullable |

#### `medications`
*(Same structure as supplements — separate table for clarity)*
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| name | TEXT | |
| dose | TEXT | |
| prescriber | TEXT | nullable |
| indication | TEXT | nullable — what it's for |
| active | INTEGER | 0/1 |
| started_date | DATE | nullable |
| stopped_date | DATE | nullable |
| notes | TEXT | nullable |

#### `sleep_records`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| recorded_date | DATE | Night of sleep (UNIQUE — one record per night, upsert on conflict) |
| bedtime | DATETIME | nullable |
| wake_time | DATETIME | nullable |
| duration_min | INTEGER | nullable |
| deep_min | INTEGER | nullable |
| rem_min | INTEGER | nullable |
| hrv | REAL | nullable |
| resting_hr | INTEGER | nullable |
| readiness_score | INTEGER | nullable — Oura |
| sleep_score | INTEGER | nullable — Oura |
| cpap_used | INTEGER | 0/1 — nullable |
| cpap_ahi | REAL | nullable — apnea-hypopnea index |
| cpap_hours | REAL | nullable — compliance hours |
| cpap_leak_95 | REAL | nullable — 95th percentile leak rate |
| cpap_pressure_avg | REAL | nullable — average pressure |
| source | TEXT | oura, apple_health, manual, cpap |
| created_at | DATETIME | |

#### `medical_history`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| category | TEXT | condition, surgery, allergy, provider, appointment |
| title | TEXT | |
| detail | TEXT | nullable — free text |
| date | DATE | nullable |
| active | INTEGER | 0/1 |
| notes | TEXT | nullable |
| created_at | DATETIME | |

#### `targets`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| metric | TEXT | calories, protein_g, sodium_mg, etc. |
| value | REAL | |
| effective_date | DATE | targets can change over time |
| notes | TEXT | nullable |

#### `goals`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| name | TEXT | e.g. "Lose weight", "Reduce alcohol" |
| metric | TEXT | weight_lbs, alcohol_calories, sodium_mg, etc. |
| goal_type | TEXT | target (hard number) or directional (up/down) |
| target_value | REAL | nullable — for hard targets |
| direction | TEXT | nullable — "down" or "up" for directional |
| start_date | DATE | |
| target_date | DATE | nullable |
| active | INTEGER | 0/1 |
| notes | TEXT | nullable |
| created_at | DATETIME | |

#### `goal_plans`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| goal_id | INTEGER FK → goals | |
| plan | TEXT | AI-generated plan in markdown |
| version | INTEGER | increments when plan is revised |
| created_at | DATETIME | |

---

## 7. API Design

Base URL: `http://driver.local/api/v1` (or Tailscale URL)

### 7.1 Food
| Method | Path | Description |
|--------|------|-------------|
| POST | `/food` | Log a food entry |
| GET | `/food?date=YYYY-MM-DD` | Get entries for a date |
| GET | `/food/summary?date=YYYY-MM-DD` | Daily totals vs. targets |
| GET | `/food/summary/week?ending=YYYY-MM-DD` | 7-day summary |
| PATCH | `/food/{id}` | Update an entry |
| DELETE | `/food/{id}` | Soft delete |

### 7.2 Exercise
| Method | Path | Description |
|--------|------|-------------|
| POST | `/exercise/sessions` | Log a session |
| POST | `/exercise/sessions/{id}/sets` | Add a set to a session |
| GET | `/exercise/sessions?date=YYYY-MM-DD` | Get sessions for a date |
| GET | `/exercise/history?exercise=Bench+Press` | History for an exercise |

### 7.3 Body Metrics
| Method | Path | Description |
|--------|------|-------------|
| POST | `/metrics` | Log a measurement |
| GET | `/metrics?metric=weight_lbs&days=90` | Trend data |

### 7.4 Labs
| Method | Path | Description |
|--------|------|-------------|
| POST | `/labs` | Log a result |
| GET | `/labs?marker=Triglycerides` | History for a marker |
| GET | `/labs?drawn_date=YYYY-MM-DD` | Full panel for a date |

### 7.5 Supplements & Medications
| Method | Path | Description |
|--------|------|-------------|
| GET | `/supplements` | Current stack (active=1) |
| POST | `/supplements` | Add a supplement |
| PATCH | `/supplements/{id}` | Update (incl. stop) |
| GET | `/medications` | Current meds |
| POST | `/medications` | Add a med |

### 7.6 Sleep
| Method | Path | Description |
|--------|------|-------------|
| POST | `/sleep` | Log a sleep record |
| GET | `/sleep?days=30` | Recent sleep trend |

### 7.7 Dashboard / Aggregate
| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard/today` | Full today snapshot (food, exercise, sleep, metrics) |
| GET | `/dashboard/week` | 7-day summary across all domains |
| GET | `/dashboard/trends?days=90` | Long-range trend data for charts |

### 7.8 Ingest (for sync jobs)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/ingest/oura` | Oura data batch |
| POST | `/ingest/apple-health` | Apple Health Export batch |

---

## 8. Frontend — Dashboard

### 8.1 Tech Stack
- React 18 + Vite
- Recharts (charts)
- Tailwind CSS (styling — compact, dark-mode-friendly)
- Mobile-responsive (works in Safari on iPhone via Tailscale)
- PWA manifest (add to home screen)

### 8.2 Pages / Views

#### Today
- Daily nutrition ring/progress bars: calories, protein, sodium, fat, fiber
- Exercise sessions logged today
- Sleep last night (score, HRV, hours)
- Quick log form (food entry by text → agent parses)

#### Food Log
- Searchable/filterable table of entries
- Daily totals at top
- Edit/delete inline

#### Exercise
- Session history
- Per-exercise strength trends (e.g. bench press 1RM over time)
- Cardio trend (duration, calories)

#### Labs & Metrics
- Marker trend charts (trigs, glucose, BP, weight)
- Lab history table grouped by panel date

#### Supplements & Meds
- Current stack (read-only grid)
- History log

#### Medical History
- Conditions, surgeries, allergies, providers (mostly static reference)

---

## 9. Agent Interface (McGrupp Health Agent)

The health agent is a persistent OpenClaw sub-agent that:
- Accepts natural language from Craig via Telegram ("just had a protein shake, 2 scoops Naked Whey")
- Parses intent and calls the Driver API
- Returns confirmation with running daily totals
- Handles date clarification ("was that today or last night?")
- Can answer queries ("what's my protein total today?" → GET /food/summary)

The agent does **not** read files or query SQLite directly — it is a REST client of the Driver API only.

**Agent triggers (examples):**
- `"log: [food]"` → parse and POST to /food
- `"log workout: [description]"` → parse and POST to /exercise/sessions
- `"weighed 198 this morning"` → POST to /metrics
- `"how am I doing today?"` → GET /dashboard/today, format summary
- `"show last week"` → GET /dashboard/week, format summary

---

## 10. Training Intelligence

### 10.1 HR Zone Definitions
Based on max HR formula: 220 - age (56) = **164 bpm**

| Zone | Name | % Max HR | BPM Range | Purpose |
|------|------|----------|-----------|---------|
| 1 | Recovery | 50-60% | 82-98 | Active recovery |
| 2 | Fat Burn | 60-70% | 98-115 | Aerobic base, fat oxidation |
| 3 | Aerobic | 70-80% | 115-131 | Cardiovascular fitness |
| 4 | Threshold | 80-90% | 131-148 | Lactate threshold |
| 5 | Max | 90-100% | 148-164 | Peak performance |

**Goal:** Cardio sessions should target Zone 2 (fat burn) for the majority of time. Apple Watch HR data feeds post-session zone breakdown.

### 10.2 HR Zone Analysis (per session)
- After each cardio session ingested from Apple Watch:
  - Calculate time-in-zone for each of the 5 zones
  - Store as `exercise_hr_zones` (session_id, zone, minutes)
  - Flag if <50% of session time was spent in Zone 2 or below (pushing too hard for fat burn goal)
- Dashboard: zone breakdown chart per session + trend over time (Zone 2 % improving = aerobic base building)

### 10.3 Adaptive Daily Routine

**Base schedule** (user-configurable):
- Mon / Wed / Fri: Strength
- Tue / Thu: Cardio
- Sat / Sun: Rest

**Daily suggestion engine** (runs each morning via cron, stores in `daily_suggestions`):
1. Pull Oura readiness score + HRV for today
2. Check what's been done this week (sessions logged)
3. Check what's scheduled today per base template
4. Apply rules:
   - Readiness < 60 or HRV significantly below 7-day avg → suggest lighter session or active recovery
   - Readiness ≥ 75 + HRV normal/high → full session, consider pushing intensity
   - Missed a scheduled session → suggest making it up today if feasible, otherwise note the gap and move on (no guilt)
   - Rest day + readiness high → optionally suggest light walk/Zone 1 activity
5. Output: one short text suggestion ("Zone 2 cardio today — 30-40 min. HRV is solid.")

**What it does NOT do:**
- Does not prescribe specific exercises, weights, or sets at the gym
- Does not reschedule the entire week when something changes
- Does not nag — one suggestion per day, Craig decides

#### `daily_suggestions` table
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| suggestion_date | DATE | |
| readiness_score | INTEGER | nullable — from Oura |
| hrv | REAL | nullable — from Oura |
| scheduled_type | TEXT | per base template |
| suggestion | TEXT | human-readable recommendation |
| intensity | TEXT | easy / moderate / full / rest |
| created_at | DATETIME | |

#### `exercise_hr_zones` table
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| session_id | INTEGER FK → exercise_sessions | |
| zone | INTEGER | 1-5 |
| minutes | REAL | |
| pct_of_session | REAL | |

---

## 11. Data Ingestion

### 11.1 Oura Ring
- Sync job runs daily via cron
- Fetches sleep, readiness, activity from Oura API
- Upserts into `sleep_records` (source=oura)
- On conflict (same date): update if source=oura (allow re-sync)

### 11.2 Apple Watch — Health Auto Export (REST API Push)
**Ongoing sync:**
- Health Auto Export (Premium) configured to POST JSON to Pulse `/ingest/apple-health` endpoint
- Interval: hourly (or daily — TBD based on battery/reliability)
- Batch Requests: ON (avoids oversized payloads)
- Metrics selected: Workouts, Heart Rate, Active Energy, Steps, Weight, Sleep, HRV, Resting HR
- Pulse endpoint parses `data.metrics` and `data.workouts`, upserts to DB

**One-time historical import:**
- In Health Auto Export: set date range to "All time", trigger manual export to REST API
- Same endpoint handles it — idempotent upserts, safe to re-run
- Alternatively: export to iCloud Drive as JSON file, run `scripts/import_apple_health.py` locally

**Data mapping:**
- `workouts` → `exercise_sessions` (source=apple_health) + HR time series → `exercise_hr_zones`
- Heart Rate, Resting HR, Weight, HRV → `body_metrics`
- Sleep (if tracked by Apple Watch) → `sleep_records` (Oura is primary; Apple Watch is fallback/cross-reference)

### 11.3 CPAP — ResMed AirSense 11 AutoSet

**Source:** Google Drive `mcgrupp/resmed/STR.edf`
**Trigger:** Manual — dashboard button "Import CPAP Data" (user uploads new SD card data to Drive first)
**Endpoint:** `POST /api/v1/ingest/cpap` — no request body; backend fetches EDF from Drive, parses, upserts

**Parser:** Already built (EDF reader, 282 nights parsed Feb 2025–Feb 2026)
**Data extracted per night:**
- `recorded_date` — date of session
- `cpap_ahi` — apnea-hypopnea index (×0.1 scale factor)
- `cpap_hours` — usage hours
- `cpap_leak_95` — 95th percentile leak rate (×0.02 L/s)
- `cpap_pressure_avg` — average mask pressure (×0.02 cmH2O)

**Storage:** Upserts CPAP columns into `sleep_records`; updates CPAP columns only on existing Oura rows — does NOT overwrite sleep quality fields. New CPAP-only rows use source=cpap.

**Response:**
```json
{ "status": "ok", "nights_imported": 282, "date_range": "2025-02-01 → 2026-02-28", "avg_ahi": 1.73, "skipped": 0 }
```

**Dashboard:** "Import CPAP Data" button on Sleep panel → shows last import date + nights on record. Spinner during import.

**Workflow:**
1. Pull SD card from AirSense 11, upload new STR.edf to Google Drive `mcgrupp/resmed/` (overwrite existing)
2. Tap "Import CPAP Data" in Driver dashboard
3. Done — new nights merged, existing data untouched

---

### 11.4 Fitbit — Historical Archive Import

**Source:** Google Drive `mcgrupp/fitbit/fitbit-raw-archive.tar.gz` (~500MB Fitbit data export)
**Trigger:** Manual — dashboard button "Import Fitbit History" (one-time historical backfill; Fitbit no longer in active use)
**Endpoint:** `POST /api/v1/ingest/fitbit` — no request body; backend downloads archive from Drive, extracts, parses, upserts

**Archive contents (data to import):**
| Data | Years | Maps To |
|------|-------|---------|
| Sleep stages + scores | 2016–2025 | `sleep_records` (source=fitbit) |
| Resting heart rate | 2016–2025 | `body_metrics` metric=resting_hr |
| HRV daily summary | 2024–2025 | `body_metrics` metric=hrv |
| Steps | 2016–2025 | `body_metrics` metric=steps |
| Active calories | 2016–2025 | `body_metrics` metric=active_calories |
| Weight | 2017–2025 | `body_metrics` metric=weight_lbs |
| Body fat % | 2017–2025 | `body_metrics` metric=body_fat_pct |
| VO2 Max (estimated) | varies | `body_metrics` metric=vo2_max |
| SpO2 daily | 2021–2025 | `body_metrics` metric=spo2 |
| Exercises | 2016–2025 | `exercise_sessions` (source=fitbit) |
| Glucose | 2007–2025 | `body_metrics` metric=glucose (flag for Dr. Smithson) |

**Idempotency:** INSERT OR IGNORE on all records — safe to re-run. Never overwrites Oura or Apple Health records for same date.

**Response:**
```json
{ "status": "ok", "processed": { "sleep": 1800, "metrics": 12400, "exercise": 620 }, "date_range": "2016-01-01 → 2025-10-01", "skipped": 0 }
```

**Dashboard:** "Import Fitbit History" button → progress indicator (large archive, may take 30–60 seconds) → summary on completion.

**AFib note:** Archive contains 8 AFib ECG readings (2021–2023). Flag these in response summary for Dr. Smithson review.

---

### 11.5 Migration
- Existing `health.db` food entries (54 rows, Feb 20–25) → migrate to Driver schema
- One-time migration script, keep old DB as archive

---

## 12. Build Phases

### Phase 1 — Foundation *(~1 week)*
- [x] Docker setup: FastAPI + SQLite
- [x] Full schema creation (`schema.sql`)
- [x] Core food API endpoints (POST, GET, summary)
- [x] Migrate existing health.db data
- [x] Basic React scaffold: Today view (food only)
- [x] Health agent v0.1: log food via API

### Phase 2 — Exercise + Sleep *(~1 week)*
- [x] Exercise API (sessions + sets + HR zones)
- [x] Sleep API
- [x] Oura sync job (sleep + readiness + HRV)
- [x] Health Auto Export REST API ingest endpoint + Apple Watch HR zone calculation
- [x] One-time historical import (all-time export via Health Auto Export)
- [x] Dashboard: Exercise view (session history + zone breakdown chart) + Sleep view
- [x] Health agent: log workouts, query sleep

### Phase 3 — Labs, Metrics, Medical *(~1 week)*
- [x] Labs API + body metrics API
- [x] Medical history API (CRUD)
- [x] Dashboard: Labs & Metrics view, trends charts
- [x] Backfill known bloodwork (Feb 2026 panel)
- [x] Supplements/medications API

### Phase 4 — Training Intelligence + Polish *(~1 week)*
- [x] Daily suggestion engine (Oura readiness + HRV + schedule → morning suggestion)
- [x] Dashboard: HR zone trend view, weekly training summary, daily suggestion card
- [x] Dashboard: Supplements/Meds view
- [x] Health agent v1.0: full query support, week summaries, relay daily suggestion
- [x] PWA manifest + mobile optimization
- [x] Week/trend views in dashboard
- [x] API error handling + validation hardening

### Phase 5 — Goals + Visit Prep + Photo Flow *(~1 week)*
- [x] Goals API + goal plans API (CRUD + generated plan scaffold)
- [x] Dashboard: Goals panel (create goal + generate plan)
- [x] Doctor visit report API (`/api/v1/reports/doctor-visit`)
- [x] Dashboard: doctor report viewer + refresh controls
- [x] Photo food logging API (`/api/v1/food/from-photo`)
- [x] Dashboard: photo food quick-log form

### Phase 6 — Photo Intelligence + Coaching Loop *(~1 week)*
- [x] Photo estimate API (`/api/v1/food/photo-estimate`) with confidence + method metadata
- [x] Photo log override flow (calories/protein edit-before-save)
- [ ] Vision-provider quality tuning and fallback thresholds
- [x] Daily + weekly coaching digest persistence and dashboard surface
- [ ] Data anomaly detection and missing-data flagging

---

## 13. Open Decisions

| # | Decision | Options | Status |
|---|----------|---------|--------|
| 1 | Strength training detail | Full sets/reps vs. session-only | **Include sets/reps** (schema ready) — Craig logs 3x/week lifting |
| 2 | Project name | Pulse, Vitals, HealthOS | Driver |
| 3 | Apple Health export delivery | REST API push (preferred) vs. iCloud file | **REST API push** — Health Auto Export Premium POSTs directly to Driver |
| 4 | CPAP data | **Google Drive** (`mcgrupp/resmed/STR.edf`) — parser built, 282 nights available | **Phase 2, solved** |
| 5 | Oura sync frequency | Daily cron vs. on-demand | Daily at 6 AM CT |

---

## 14. Success Criteria

- Craig can log a meal in Telegram in under 10 seconds
- Dashboard loads on iPhone via Tailscale in under 3 seconds
- All existing health.db data migrated without data loss
- Agent never asks about documented recurring items (smoothie, protein shake)
- Bloodwork trends visible by April 30 doctor appointment
- Daily training suggestion delivered each morning (Telegram or dashboard)
- Cardio sessions show HR zone breakdown — visible within 24h of workout
- Adaptive routine handles a missed day without manual intervention

---

*PRD status: Active v0.14 — Phase 6 in progress*
*Next step: phase-6 quality tuning (vision confidence calibration + anomaly/missing-data flags)*

---
## Changelog
| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-02-26 | Initial draft |
| 0.2 | 2026-02-26 | Added training intelligence (HR zones, adaptive routine), Health Auto Export REST API workflow, `exercise_hr_zones` + `daily_suggestions` tables, updated build phases |
| 0.3 | 2026-02-27 | User requirements interview complete — dashboard layout, insights, goals system, proactive Telegram delivery, voice capture project scoped, medical history seeded, `goals` table added |
| 0.4 | 2026-02-27 | Added photo food logging, alcohol by type, CPAP via Google Drive (parser built, 282 nights), doctor visit prep, body measurements, AI Q&A spec, symptom ingestion from Oura |
| 0.5 | 2026-02-27 | PRD review fixes: added `goals` + `goal_plans` tables to schema; added CPAP detail columns (`cpap_ahi`, `cpap_hours`, `cpap_leak_95`, `cpap_pressure_avg`) to `sleep_records`; added `alcohol_type` and `photo_url` to `food_entries`; added `max_heart_rate` to `exercise_sessions` spec; noted UNIQUE constraint on `sleep_records.recorded_date`; fixed port numbers to match docker-compose (8100/8101); fixed targets query to correctly return latest per metric; fixed PATCH handler to support field clearing |
| 0.6 | 2026-02-27 | Implemented Oura + Apple Health ingest endpoints/jobs, dashboard trends/range controls, and daily suggestion automation |
| 0.7 | 2026-02-27 | Completed Phase 3 build scope: labs API, supplements/medications APIs, medical history CRUD, labs/metrics dashboard slice, and Feb 2026 bloodwork backfill script |
| 0.8 | 2026-02-27 | Completed Phase 4: agent v1 query/week/suggestion endpoints, PWA manifest + service worker + mobile polish, and validation hardening for labs/supplements/medications/medical history APIs |
| 0.9 | 2026-02-27 | Started Phase 5: added goals + goal plans API (create/list/update, versioned plans, generated plan scaffold) with test coverage |
| 0.10 | 2026-02-27 | Added doctor-visit report API (`/api/v1/reports/doctor-visit`) with markdown output and aggregate health summary for appointment prep |
| 0.11 | 2026-02-27 | Added photo-food log flow endpoint (`/api/v1/food/from-photo`) for estimated macro capture with photo URL provenance and review notes |
| 0.12 | 2026-02-27 | Added explicit health-agent log/query endpoints for food and workouts plus sleep query (`/api/v1/agent/log-food`, `/api/v1/agent/log-workout`, `/api/v1/agent/sleep`) |
| 0.13 | 2026-02-27 | Started Phase 6 slice 1: photo estimate endpoint with method/confidence metadata, optional vision integration path, and dashboard edit-before-save overrides for photo logging |
| 0.14 | 2026-02-27 | Completed Phase 6 slice 2: persisted daily/weekly coaching digests (`coaching_digests`), generation/read APIs (`/api/v1/coaching/digests/*`), dashboard digest surface, and test coverage |
| 0.15 | 2026-03-01 | Added CPAP ingest spec (11.3 — manual button trigger, Google Drive EDF, upserts CPAP columns into sleep_records) and Fitbit historical archive import spec (11.4 — one-time backfill, 2016–2025 data, 500MB archive, glucose + AFib ECG review flag) |
