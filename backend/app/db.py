import sqlite3
import os
from collections.abc import Generator
from pathlib import Path

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/driver.db")


def get_db() -> sqlite3.Connection:
    # FastAPI may resolve dependency lifecycle and endpoint execution on different threads.
    # Disable SQLite thread affinity checks for request-scoped connections.
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_db_dependency() -> Generator[sqlite3.Connection, None, None]:
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


def row_to_dict(row) -> dict:
    return dict(row)


def init_db():
    schema_path = Path(__file__).parent.parent / "schema.sql"
    conn = get_db()
    with open(schema_path, "r") as f:
        conn.executescript(f.read())

    # Backfill schema for older databases created before idempotency keys existed.
    columns = conn.execute("PRAGMA table_info(exercise_sessions)").fetchall()
    has_external_id = any(column["name"] == "external_id" for column in columns)
    if not has_external_id:
        conn.execute("ALTER TABLE exercise_sessions ADD COLUMN external_id TEXT")

    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_exercise_source_external_id
           ON exercise_sessions(source, external_id)
           WHERE external_id IS NOT NULL"""
    )
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_body_metrics_recorded_metric_source
           ON body_metrics(recorded_date, metric, source)
           WHERE source = 'apple_health'"""
    )
    _migrate_food_meal_type_check(conn)
    conn.commit()
    conn.close()


def _migrate_food_meal_type_check(conn: sqlite3.Connection):
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='food_entries'"
    ).fetchone()
    if not row:
        return

    create_sql = row["sql"] or ""
    if "'meal'" in create_sql:
        return

    conn.executescript(
        """
        CREATE TABLE food_entries__new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_date   DATE NOT NULL,
            meal_type       TEXT NOT NULL CHECK(meal_type IN ('breakfast','lunch','dinner','snack','drink','meal')),
            name            TEXT NOT NULL,
            calories        REAL,
            protein_g       REAL,
            carbs_g         REAL,
            fat_g           REAL,
            fiber_g         REAL,
            sodium_mg       REAL,
            alcohol_g       REAL,
            alcohol_calories REAL,
            alcohol_type    TEXT CHECK(alcohol_type IN ('beer','wine','spirits','cocktail')),
            photo_url       TEXT,
            servings        REAL NOT NULL DEFAULT 1.0,
            is_estimated    INTEGER NOT NULL DEFAULT 0,
            source          TEXT NOT NULL DEFAULT 'manual' CHECK(source IN ('manual','agent','apple_health')),
            notes           TEXT,
            created_at      DATETIME NOT NULL DEFAULT (datetime('now')),
            deleted_at      DATETIME
        );

        INSERT INTO food_entries__new (
            id,
            recorded_date,
            meal_type,
            name,
            calories,
            protein_g,
            carbs_g,
            fat_g,
            fiber_g,
            sodium_mg,
            alcohol_g,
            alcohol_calories,
            alcohol_type,
            photo_url,
            servings,
            is_estimated,
            source,
            notes,
            created_at,
            deleted_at
        )
        SELECT
            id,
            recorded_date,
            meal_type,
            name,
            calories,
            protein_g,
            carbs_g,
            fat_g,
            fiber_g,
            sodium_mg,
            alcohol_g,
            alcohol_calories,
            alcohol_type,
            photo_url,
            servings,
            is_estimated,
            source,
            notes,
            created_at,
            deleted_at
        FROM food_entries;

        DROP TABLE food_entries;
        ALTER TABLE food_entries__new RENAME TO food_entries;
        CREATE INDEX IF NOT EXISTS idx_food_date ON food_entries(recorded_date) WHERE deleted_at IS NULL;
        """
    )
