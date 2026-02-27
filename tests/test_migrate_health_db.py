import importlib.util
import sqlite3
from pathlib import Path


def load_migration_module():
    module_path = (
        Path(__file__).resolve().parent.parent / "scripts" / "migrate_health_db.py"
    )
    spec = importlib.util.spec_from_file_location("migrate_health_db", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def create_target_db(path: Path):
    schema = (
        Path(__file__).resolve().parent.parent / "backend" / "schema.sql"
    ).read_text()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


def test_migrate_health_db_imports_food_entries_and_is_idempotent(tmp_path: Path):
    migration = load_migration_module()
    source_db = tmp_path / "health.db"
    target_db = tmp_path / "driver.db"

    source_conn = sqlite3.connect(source_db)
    try:
        source_conn.execute(
            """CREATE TABLE food_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                meal_type TEXT,
                name TEXT NOT NULL,
                calories REAL,
                protein REAL,
                notes TEXT,
                created_at TEXT
            )"""
        )
        source_conn.execute(
            """INSERT INTO food_entries
               (date, meal_type, name, calories, protein, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                "2026-02-25",
                "Lunch",
                "Turkey sandwich",
                540,
                38,
                "legacy import",
                "2026-02-25 18:30:00",
            ),
        )
        source_conn.commit()
    finally:
        source_conn.close()

    create_target_db(target_db)

    inserted, skipped = migration.migrate_food_entries(str(source_db), str(target_db))
    assert inserted == 1
    assert skipped == 0

    second_inserted, second_skipped = migration.migrate_food_entries(
        str(source_db), str(target_db)
    )
    assert second_inserted == 0
    assert second_skipped == 1

    target_conn = sqlite3.connect(target_db)
    target_conn.row_factory = sqlite3.Row
    try:
        row = target_conn.execute(
            """SELECT recorded_date, meal_type, name, calories, protein_g, notes
               FROM food_entries"""
        ).fetchone()
    finally:
        target_conn.close()

    assert dict(row) == {
        "recorded_date": "2026-02-25",
        "meal_type": "lunch",
        "name": "Turkey sandwich",
        "calories": 540.0,
        "protein_g": 38.0,
        "notes": "legacy import",
    }
