import sqlite3
import os
from pathlib import Path

DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/driver.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


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
    conn.commit()
    conn.close()
