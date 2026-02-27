#!/usr/bin/env python3

from __future__ import annotations

import os
import sqlite3


DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/driver.db")

# Known Feb 2026 panel values used for initial backfill.
FEB_2026_LABS = [
    {
        "drawn_date": "2026-02-14",
        "panel": "Lipid Panel",
        "marker": "Total Cholesterol",
        "value": 219.0,
        "unit": "mg/dL",
        "reference_low": None,
        "reference_high": 199.0,
        "flag": "H",
        "notes": "Initial backfill",
    },
    {
        "drawn_date": "2026-02-14",
        "panel": "Lipid Panel",
        "marker": "LDL",
        "value": 131.0,
        "unit": "mg/dL",
        "reference_low": None,
        "reference_high": 99.0,
        "flag": "H",
        "notes": "Initial backfill",
    },
    {
        "drawn_date": "2026-02-14",
        "panel": "Lipid Panel",
        "marker": "HDL",
        "value": 39.0,
        "unit": "mg/dL",
        "reference_low": 40.0,
        "reference_high": None,
        "flag": "L",
        "notes": "Initial backfill",
    },
    {
        "drawn_date": "2026-02-14",
        "panel": "Lipid Panel",
        "marker": "Triglycerides",
        "value": 244.0,
        "unit": "mg/dL",
        "reference_low": None,
        "reference_high": 149.0,
        "flag": "H",
        "notes": "Initial backfill",
    },
    {
        "drawn_date": "2026-02-14",
        "panel": "CMP",
        "marker": "Glucose",
        "value": 102.0,
        "unit": "mg/dL",
        "reference_low": 70.0,
        "reference_high": 99.0,
        "flag": "H",
        "notes": "Initial backfill",
    },
]


def run_backfill(conn: sqlite3.Connection) -> int:
    inserted = 0
    for row in FEB_2026_LABS:
        exists = conn.execute(
            """SELECT id
               FROM lab_results
               WHERE drawn_date = ?
                 AND panel = ?
                 AND marker = ?""",
            (row["drawn_date"], row["panel"], row["marker"]),
        ).fetchone()
        if exists:
            continue
        conn.execute(
            """INSERT INTO lab_results
               (
                 drawn_date,
                 panel,
                 marker,
                 value,
                 unit,
                 reference_low,
                 reference_high,
                 flag,
                 notes
               )
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["drawn_date"],
                row["panel"],
                row["marker"],
                row["value"],
                row["unit"],
                row["reference_low"],
                row["reference_high"],
                row["flag"],
                row["notes"],
            ),
        )
        inserted += 1
    conn.commit()
    return inserted


def main() -> int:
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        inserted = run_backfill(conn)
        print(f"Inserted {inserted} lab result rows.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
