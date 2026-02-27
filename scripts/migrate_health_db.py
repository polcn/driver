#!/usr/bin/env python3

import argparse
import sqlite3
from pathlib import Path


SOURCE_TABLE_CANDIDATES = (
    "food_entries",
    "foods",
    "food_log",
    "meal_entries",
)

MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack", "drink"}
SOURCE_VALUES = {"manual", "agent", "apple_health"}


def get_table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [row[1] for row in rows]


def discover_source_table(conn: sqlite3.Connection, explicit_table: str | None) -> str:
    if explicit_table:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if explicit_table not in tables:
            raise ValueError(f"Source table '{explicit_table}' was not found")
        return explicit_table

    for candidate in SOURCE_TABLE_CANDIDATES:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (candidate,),
        ).fetchone()
        if row:
            return candidate

    raise ValueError(
        "Could not find a source food table. Pass --table to specify it explicitly."
    )


def pick_first(record: sqlite3.Row, columns: set[str], *names: str):
    for name in names:
        if name in columns:
            return record[name]
    return None


def normalize_meal_type(value) -> str:
    if not value:
        return "snack"
    normalized = str(value).strip().lower()
    if normalized in MEAL_TYPES:
        return normalized
    return "snack"


def normalize_source(value) -> str:
    if not value:
        return "manual"
    normalized = str(value).strip().lower()
    if normalized in SOURCE_VALUES:
        return normalized
    return "manual"


def normalize_record(record: sqlite3.Row, columns: set[str]) -> dict:
    recorded_date = pick_first(
        record,
        columns,
        "recorded_date",
        "date",
        "entry_date",
        "logged_date",
    )
    if recorded_date is None:
        created_at = pick_first(record, columns, "created_at", "logged_at", "timestamp")
        if created_at is None:
            raise ValueError("Source row is missing both a date and created timestamp")
        recorded_date = str(created_at)[:10]

    return {
        "recorded_date": str(recorded_date)[:10],
        "meal_type": normalize_meal_type(
            pick_first(record, columns, "meal_type", "category", "meal")
        ),
        "name": str(
            pick_first(record, columns, "name", "description", "title") or "Imported entry"
        ),
        "calories": pick_first(record, columns, "calories"),
        "protein_g": pick_first(record, columns, "protein_g", "protein"),
        "carbs_g": pick_first(record, columns, "carbs_g", "carbs"),
        "fat_g": pick_first(record, columns, "fat_g", "fat"),
        "fiber_g": pick_first(record, columns, "fiber_g", "fiber"),
        "sodium_mg": pick_first(record, columns, "sodium_mg", "sodium"),
        "alcohol_g": pick_first(record, columns, "alcohol_g"),
        "alcohol_calories": pick_first(record, columns, "alcohol_calories"),
        "servings": pick_first(record, columns, "servings", "serving_count") or 1.0,
        "is_estimated": int(
            bool(pick_first(record, columns, "is_estimated", "estimated", "is_approximate"))
        ),
        "source": normalize_source(pick_first(record, columns, "source")),
        "notes": pick_first(record, columns, "notes"),
        "created_at": pick_first(record, columns, "created_at", "logged_at", "timestamp"),
    }


def target_row_exists(conn: sqlite3.Connection, normalized: dict) -> bool:
    row = conn.execute(
        """SELECT 1
           FROM food_entries
           WHERE recorded_date = ?
             AND meal_type = ?
             AND name = ?
             AND COALESCE(calories, -1) = COALESCE(?, -1)
             AND COALESCE(protein_g, -1) = COALESCE(?, -1)
             AND COALESCE(carbs_g, -1) = COALESCE(?, -1)
             AND COALESCE(fat_g, -1) = COALESCE(?, -1)
             AND COALESCE(fiber_g, -1) = COALESCE(?, -1)
             AND COALESCE(sodium_mg, -1) = COALESCE(?, -1)
             AND COALESCE(alcohol_g, -1) = COALESCE(?, -1)
             AND COALESCE(alcohol_calories, -1) = COALESCE(?, -1)
             AND COALESCE(servings, -1) = COALESCE(?, -1)
             AND COALESCE(notes, '') = COALESCE(?, '')
             AND deleted_at IS NULL
           LIMIT 1""",
        (
            normalized["recorded_date"],
            normalized["meal_type"],
            normalized["name"],
            normalized["calories"],
            normalized["protein_g"],
            normalized["carbs_g"],
            normalized["fat_g"],
            normalized["fiber_g"],
            normalized["sodium_mg"],
            normalized["alcohol_g"],
            normalized["alcohol_calories"],
            normalized["servings"],
            normalized["notes"],
        ),
    ).fetchone()
    return row is not None


def migrate_food_entries(
    source_db_path: str, target_db_path: str, source_table: str | None = None, dry_run: bool = False
) -> tuple[int, int]:
    source_conn = sqlite3.connect(source_db_path)
    target_conn = sqlite3.connect(target_db_path)
    source_conn.row_factory = sqlite3.Row
    target_conn.row_factory = sqlite3.Row

    try:
        resolved_table = discover_source_table(source_conn, source_table)
        columns = set(get_table_columns(source_conn, resolved_table))
        rows = source_conn.execute(
            f"SELECT * FROM {resolved_table} ORDER BY ROWID"
        ).fetchall()

        inserted = 0
        skipped = 0

        for row in rows:
            normalized = normalize_record(row, columns)
            if target_row_exists(target_conn, normalized):
                skipped += 1
                continue

            inserted += 1
            if dry_run:
                continue

            target_conn.execute(
                """INSERT INTO food_entries (
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
                    servings,
                    is_estimated,
                    source,
                    notes,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, datetime('now')))""",
                (
                    normalized["recorded_date"],
                    normalized["meal_type"],
                    normalized["name"],
                    normalized["calories"],
                    normalized["protein_g"],
                    normalized["carbs_g"],
                    normalized["fat_g"],
                    normalized["fiber_g"],
                    normalized["sodium_mg"],
                    normalized["alcohol_g"],
                    normalized["alcohol_calories"],
                    normalized["servings"],
                    normalized["is_estimated"],
                    normalized["source"],
                    normalized["notes"],
                    normalized["created_at"],
                ),
            )

        if not dry_run:
            target_conn.commit()

        return inserted, skipped
    finally:
        source_conn.close()
        target_conn.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate legacy health.db food entries into Driver")
    parser.add_argument("source_db", help="Path to the legacy health.db SQLite database")
    parser.add_argument("target_db", help="Path to the Driver SQLite database")
    parser.add_argument("--table", help="Explicit source table name", default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect and count rows without inserting anything into the target database",
    )
    args = parser.parse_args()

    source_path = Path(args.source_db)
    target_path = Path(args.target_db)

    if not source_path.exists():
        raise SystemExit(f"Source database not found: {source_path}")
    if not target_path.exists():
        raise SystemExit(f"Target database not found: {target_path}")

    inserted, skipped = migrate_food_entries(
        str(source_path),
        str(target_path),
        source_table=args.table,
        dry_run=args.dry_run,
    )
    mode = "dry run" if args.dry_run else "migration"
    print(f"{mode} complete: inserted={inserted} skipped={skipped}")


if __name__ == "__main__":
    main()
