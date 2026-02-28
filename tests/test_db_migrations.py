import sqlite3
from pathlib import Path

from app import db as db_module


def test_init_db_migrates_food_entries_check_to_allow_meal(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE food_entries (
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
                alcohol_type    TEXT CHECK(alcohol_type IN ('beer','wine','spirits','cocktail')),
                photo_url       TEXT,
                servings        REAL NOT NULL DEFAULT 1.0,
                is_estimated    INTEGER NOT NULL DEFAULT 0,
                source          TEXT NOT NULL DEFAULT 'manual' CHECK(source IN ('manual','agent','apple_health')),
                notes           TEXT,
                created_at      DATETIME NOT NULL DEFAULT (datetime('now')),
                deleted_at      DATETIME
            );
            CREATE INDEX idx_food_date ON food_entries(recorded_date) WHERE deleted_at IS NULL;
            """
        )
        conn.execute(
            """INSERT INTO food_entries (recorded_date, meal_type, name, source)
               VALUES ('2026-02-20', 'breakfast', 'Legacy row', 'manual')"""
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(db_module, "DATABASE_PATH", str(db_path))
    db_module.init_db()

    conn = sqlite3.connect(db_path)
    try:
        table_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='food_entries'"
        ).fetchone()[0]
        assert "'meal'" in table_sql

        conn.execute(
            """INSERT INTO food_entries (recorded_date, meal_type, name, source)
               VALUES ('2026-02-21', 'meal', 'New meal row', 'agent')"""
        )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM food_entries").fetchone()[0]
        assert count == 2
    finally:
        conn.close()
