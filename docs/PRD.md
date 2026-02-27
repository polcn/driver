# Pulse — Personal Health Platform
## Product Requirements Document
*Version 0.4 — 2026-02-27*
*Owner: Craig | Architect: McGrupp*

---

## 1. Overview

**Pulse** is a self-hosted personal health platform running on Craig's Mac Mini, accessible via browser (desktop + mobile via Tailscale). It consolidates food intake, exercise, body metrics, bloodwork/labs, supplements, medications, and medical history into a single queryable system with a dashboard UI and a dedicated AI agent interface.

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
│              Mac Mini (Docker)               │
│                                              │
│  ┌─────────────┐    ┌──────────────────┐    │
│  │  React PWA  │◄──►│  FastAPI Backend │    │
│  │  (Vite)     │    │  (Python 3.12)   │    │
│  └─────────────┘    └────────┬─────────┘    │
│                              │               │
│                     ┌────────▼─────────┐    │
│                     │  SQLite (WAL)    │    │
│                     │  pulse.db        │    │
│                     └──────────────────┘    │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  Sync Jobs (cron)                    │   │
│  │  - Oura API → DB                     │   │
│  │  - Health Auto Export CSV → DB       │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
          ▲                    ▲
          │ Tailscale          │ REST API
     iPhone browser       McGrupp Agent
```

**Auth**: None. Tailscale network perimeter is sufficient for personal use.
**Port**: Internal Docker port (e.g. 3100), exposed via Tailscale.

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
| source | TEXT | manual, oura, apple_health |
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
| recorded_date | DATE | Night of sleep |
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
| source | TEXT | oura, apple_health, manual |
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

Base URL: `http://pulse.local/api/v1` (or Tailscale URL)

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
- Parses intent and calls the Pulse API
- Returns confirmation with running daily totals
- Handles date clarification ("was that today or last night?")
- Can answer queries ("what's my protein total today?" → GET /food/summary)

The agent does **not** read files or query SQLite directly — it is a REST client of the Pulse API only.

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

### 11.3 Migration
- Existing `health.db` food entries (54 rows, Feb 20–25) → migrate to Pulse schema
- One-time migration script, keep old DB as archive

---

## 12. Build Phases

### Phase 1 — Foundation *(~1 week)*
- [ ] Docker setup: FastAPI + SQLite
- [ ] Full schema creation (`schema.sql`)
- [ ] Core food API endpoints (POST, GET, summary)
- [ ] Migrate existing health.db data
- [ ] Basic React scaffold: Today view (food only)
- [ ] Health agent v0.1: log food via API

### Phase 2 — Exercise + Sleep *(~1 week)*
- [ ] Exercise API (sessions + sets + HR zones)
- [ ] Sleep API
- [ ] Oura sync job (sleep + readiness + HRV)
- [ ] Health Auto Export REST API ingest endpoint + Apple Watch HR zone calculation
- [ ] One-time historical import (all-time export via Health Auto Export)
- [ ] Dashboard: Exercise view (session history + zone breakdown chart) + Sleep view
- [ ] Health agent: log workouts, query sleep

### Phase 3 — Labs, Metrics, Medical *(~1 week)*
- [ ] Labs API + body metrics API
- [ ] Medical history API (CRUD)
- [ ] Dashboard: Labs & Metrics view, trends charts
- [ ] Backfill known bloodwork (Feb 2026 panel)
- [ ] Supplements/medications API

### Phase 4 — Training Intelligence + Polish *(~1 week)*
- [ ] Daily suggestion engine (Oura readiness + HRV + schedule → morning suggestion)
- [ ] Dashboard: HR zone trend view, weekly training summary, daily suggestion card
- [ ] Dashboard: Supplements/Meds view
- [ ] Health agent v1.0: full query support, week summaries, relay daily suggestion
- [ ] PWA manifest + mobile optimization
- [ ] Week/trend views in dashboard
- [ ] API error handling + validation hardening

---

## 13. Open Decisions

| # | Decision | Options | Status |
|---|----------|---------|--------|
| 1 | Strength training detail | Full sets/reps vs. session-only | **Include sets/reps** (schema ready) — Craig logs 3x/week lifting |
| 2 | Project name | Pulse, Vitals, HealthOS | Pulse (pending Craig confirmation) |
| 3 | Apple Health export delivery | REST API push (preferred) vs. iCloud file | **REST API push** — Health Auto Export Premium POSTs directly to Pulse |
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

*PRD status: DRAFT v0.2 — pending Craig review*
*Next step: Phase 1 kickoff — Docker + schema + food API*

---
## Changelog
| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-02-26 | Initial draft |
| 0.2 | 2026-02-26 | Added training intelligence (HR zones, adaptive routine), Health Auto Export REST API workflow, `exercise_hr_zones` + `daily_suggestions` tables, updated build phases |
| 0.3 | 2026-02-27 | User requirements interview complete — dashboard layout, insights, goals system, proactive Telegram delivery, voice capture project scoped, medical history seeded, `goals` table added |
| 0.4 | 2026-02-27 | Added photo food logging, alcohol by type, CPAP via Google Drive (parser built, 282 nights), doctor visit prep, body measurements, AI Q&A spec, symptom ingestion from Oura |
