#!/usr/bin/env python3
"""Import CPAP data from local STR.edf into Driver.

Usage:
    cd ~/proj/driver
    source venv/bin/activate
    python scripts/import_cpap.py [--edf-path data/cpap/STR.edf] [--dry-run]

Reads the ResMed STR.edf file and upserts nightly CPAP data into sleep_records.
Safe to re-run — uses ON CONFLICT upsert so existing sleep data is preserved.
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

# Add backend to path for parser import
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.parsers.cpap_edf import parse_cpap_edf

DEFAULT_EDF_PATH = "data/cpap/STR.edf"
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/driver.db")


def main():
    parser = argparse.ArgumentParser(description="Import CPAP data from STR.edf into Driver")
    parser.add_argument("--edf-path", default=DEFAULT_EDF_PATH, help="Path to STR.edf file")
    parser.add_argument("--dry-run", action="store_true", help="Parse and count without inserting")
    args = parser.parse_args()

    edf_path = Path(args.edf_path).resolve()
    db_path = Path(DATABASE_PATH).resolve()

    print("CPAP Import")
    print(f"  EDF file: {edf_path}")
    print(f"  Database: {db_path}")
    print(f"  Dry run:  {args.dry_run}")

    if not edf_path.is_file():
        print(f"\nERROR: EDF file not found: {edf_path}")
        print("Copy STR.edf from your ResMed SD card to data/cpap/")
        sys.exit(1)

    print("\n── Parsing EDF ──")
    nights = parse_cpap_edf(edf_path)
    print(f"  Parsed {len(nights)} nights")

    if not nights:
        print("  No data found in EDF file.")
        return

    dates = sorted(n["recorded_date"] for n in nights)
    print(f"  Date range: {dates[0]} → {dates[-1]}")

    if args.dry_run:
        ahi_vals = [n["cpap_ahi"] for n in nights if n["cpap_ahi"] is not None]
        avg_ahi = round(sum(ahi_vals) / len(ahi_vals), 2) if ahi_vals else None
        print(f"  Avg AHI: {avg_ahi}")
        print("\n  ** DRY RUN — no data was written **")
        return

    print("\n── Importing ──")
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    for night in nights:
        conn.execute(
            """INSERT INTO sleep_records
               (recorded_date, cpap_used, cpap_ahi, cpap_hours,
                cpap_leak_95, cpap_pressure_avg, source)
               VALUES (?, ?, ?, ?, ?, ?, 'cpap')
               ON CONFLICT(recorded_date) DO UPDATE SET
                 cpap_used=excluded.cpap_used,
                 cpap_ahi=excluded.cpap_ahi,
                 cpap_hours=excluded.cpap_hours,
                 cpap_leak_95=excluded.cpap_leak_95,
                 cpap_pressure_avg=excluded.cpap_pressure_avg""",
            (
                night["recorded_date"],
                night["cpap_used"],
                night["cpap_ahi"],
                night["cpap_hours"],
                night["cpap_leak_95"],
                night["cpap_pressure_avg"],
            ),
        )

    conn.commit()
    conn.close()

    ahi_vals = [n["cpap_ahi"] for n in nights if n["cpap_ahi"] is not None]
    avg_ahi = round(sum(ahi_vals) / len(ahi_vals), 2) if ahi_vals else None

    print(f"  Imported {len(nights)} nights")
    print(f"  Date range: {dates[0]} → {dates[-1]}")
    print(f"  Avg AHI: {avg_ahi}")
    print(f"\n  Done. Data committed to {db_path}")


if __name__ == "__main__":
    main()
