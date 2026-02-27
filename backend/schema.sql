-- Driver database schema
-- SQLite with WAL mode for concurrent reads

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ─────────────────────────────────────────
-- FOOD
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS food_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_date   DATE NOT NULL,
    meal_type       TEXT NOT NULL CHECK(meal_type IN ('breakfast','lunch','dinner','snack','drink')),
    name            TEXT NOT NULL,
    calories        REAL,
    protein_g       REAL,
    carbs_g         REAL,
    fat_g           REAL,
    fiber_g         REAL,
    sodium_mg       REAL,
    alcohol_g       REAL,
    alcohol_calories REAL,
    servings        REAL NOT NULL DEFAULT 1.0,
    is_estimated    INTEGER NOT NULL DEFAULT 0,
    source          TEXT NOT NULL DEFAULT 'manual' CHECK(source IN ('manual','agent','apple_health')),
    notes           TEXT,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now')),
    deleted_at      DATETIME
);

CREATE INDEX IF NOT EXISTS idx_food_date ON food_entries(recorded_date) WHERE deleted_at IS NULL;

-- ─────────────────────────────────────────
-- EXERCISE
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exercise_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_date   DATE NOT NULL,
    session_type    TEXT NOT NULL,  -- strength, cardio, walk, yoga, etc.
    name            TEXT,
    duration_min    INTEGER,
    calories_burned REAL,
    avg_heart_rate  INTEGER,
    max_heart_rate  INTEGER,
    source          TEXT NOT NULL DEFAULT 'manual' CHECK(source IN ('manual','oura','apple_health','agent')),
    notes           TEXT,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now')),
    deleted_at      DATETIME
);

CREATE INDEX IF NOT EXISTS idx_exercise_date ON exercise_sessions(recorded_date) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS exercise_sets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES exercise_sessions(id),
    exercise_name   TEXT NOT NULL,
    set_number      INTEGER NOT NULL,
    weight_lbs      REAL,
    reps            INTEGER,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS exercise_hr_zones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES exercise_sessions(id),
    zone            INTEGER NOT NULL CHECK(zone BETWEEN 1 AND 5),
    minutes         REAL NOT NULL,
    pct_of_session  REAL NOT NULL
);

-- ─────────────────────────────────────────
-- SLEEP
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sleep_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_date   DATE NOT NULL UNIQUE,  -- night of sleep
    bedtime         DATETIME,
    wake_time       DATETIME,
    duration_min    INTEGER,
    deep_min        INTEGER,
    rem_min         INTEGER,
    core_min        INTEGER,
    awake_min       INTEGER,
    hrv             REAL,
    resting_hr      INTEGER,
    readiness_score INTEGER,
    sleep_score     INTEGER,
    cpap_used       INTEGER,  -- 0/1
    source          TEXT NOT NULL DEFAULT 'oura' CHECK(source IN ('oura','apple_health','manual')),
    created_at      DATETIME NOT NULL DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────
-- BODY METRICS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS body_metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_date   DATE NOT NULL,
    metric          TEXT NOT NULL,  -- weight_lbs, body_fat_pct, bmi, waist_in, etc.
    value           REAL NOT NULL,
    source          TEXT NOT NULL DEFAULT 'manual' CHECK(source IN ('manual','apple_health','oura')),
    notes           TEXT,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_metrics_date_metric ON body_metrics(recorded_date, metric);

-- ─────────────────────────────────────────
-- LABS / BLOODWORK
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lab_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    drawn_date      DATE NOT NULL,
    panel           TEXT NOT NULL,  -- e.g. "Lipid Panel"
    marker          TEXT NOT NULL,  -- e.g. "Triglycerides"
    value           REAL NOT NULL,
    unit            TEXT NOT NULL,  -- e.g. "mg/dL"
    reference_low   REAL,
    reference_high  REAL,
    flag            TEXT,           -- "H", "L", "HH", "LL"
    notes           TEXT,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_labs_marker ON lab_results(marker, drawn_date);

-- ─────────────────────────────────────────
-- SUPPLEMENTS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS supplements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    dose            TEXT,
    frequency       TEXT,  -- daily, post-workout, as-needed
    active          INTEGER NOT NULL DEFAULT 1,
    started_date    DATE,
    stopped_date    DATE,
    notes           TEXT,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS supplement_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    supplement_id   INTEGER NOT NULL REFERENCES supplements(id),
    recorded_date   DATE NOT NULL,
    taken           INTEGER NOT NULL DEFAULT 1,
    notes           TEXT,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────
-- MEDICATIONS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS medications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    dose            TEXT,
    prescriber      TEXT,
    indication      TEXT,
    active          INTEGER NOT NULL DEFAULT 1,
    started_date    DATE,
    stopped_date    DATE,
    notes           TEXT,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────
-- MEDICAL HISTORY
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS medical_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category        TEXT NOT NULL CHECK(category IN ('condition','surgery','allergy','provider','appointment','vaccination')),
    title           TEXT NOT NULL,
    detail          TEXT,
    date            DATE,
    active          INTEGER NOT NULL DEFAULT 1,
    notes           TEXT,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────
-- TRAINING INTELLIGENCE
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS daily_suggestions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    suggestion_date     DATE NOT NULL UNIQUE,
    readiness_score     INTEGER,
    hrv                 REAL,
    hrv_7day_avg        REAL,
    scheduled_type      TEXT,
    suggestion          TEXT NOT NULL,
    intensity           TEXT CHECK(intensity IN ('rest','easy','moderate','full')),
    created_at          DATETIME NOT NULL DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────
-- TARGETS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS targets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    metric          TEXT NOT NULL,  -- calories, protein_g, sodium_mg, etc.
    value           REAL NOT NULL,
    effective_date  DATE NOT NULL,
    notes           TEXT,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now'))
);

-- Seed current targets
INSERT OR IGNORE INTO targets (metric, value, effective_date, notes) VALUES
    ('calories',    2000, '2026-02-20', 'Daily calorie target'),
    ('protein_g',   180,  '2026-02-20', 'Daily protein goal'),
    ('sodium_mg',   2300, '2026-02-20', 'AHA general population limit'),
    ('cardio_days', 2,    '2026-02-20', 'Cardio sessions per week'),
    ('strength_days', 3,  '2026-02-20', 'Strength sessions per week');
