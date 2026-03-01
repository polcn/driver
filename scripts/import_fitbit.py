#!/usr/bin/env python3
"""One-time Fitbit historical data import into Driver.

Usage:
    cd ~/proj/driver
    source venv/bin/activate
    python scripts/import_fitbit.py [--data-dir data/fitbit/fitbit-data] [--dry-run]

Reads the extracted Fitbit data export and inserts into the Driver SQLite DB.
Uses INSERT OR IGNORE / pre-check logic so existing Oura and Apple Health
records are never overwritten. Safe to re-run.
"""

import argparse
import csv
import glob
import json
import os
import sqlite3
import sys
from datetime import datetime

# ── Config ──────────────────────────────────────────────────────────────────

DEFAULT_DATA_DIR = "data/fitbit/fitbit-data"
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/driver.db")

# Exercise type mapping: Fitbit activityName → Driver session_type
EXERCISE_TYPE_MAP = {
    "walk": "walk",
    "walking": "walk",
    "run": "cardio",
    "running": "cardio",
    "treadmill": "cardio",
    "bike": "cardio",
    "biking": "cardio",
    "cycling": "cardio",
    "spinning": "cardio",
    "outdoor bike": "cardio",
    "sport": "cardio",
    "swim": "cardio",
    "swimming": "cardio",
    "elliptical": "cardio",
    "stairmaster": "cardio",
    "weights": "strength",
    "weight training": "strength",
    "workout": "strength",
    "yoga": "yoga",
    "hike": "walk",
    "hiking": "walk",
    "tennis": "cardio",
    "pickleball": "cardio",
    "aerobic workout": "cardio",
    "circuit training": "strength",
    "bootcamp": "strength",
    "interval workout": "cardio",
}


# ── Schema migration ───────────────────────────────────────────────────────

def migrate_add_fitbit_source(conn: sqlite3.Connection):
    """Add 'fitbit' to source CHECK constraints on tables that need it."""
    _migrate_table_source(
        conn,
        "exercise_sessions",
        "('manual','oura','apple_health','agent')",
        "('manual','oura','apple_health','agent','fitbit')",
    )
    _migrate_table_source(
        conn,
        "sleep_records",
        "('oura','apple_health','manual','cpap')",
        "('oura','apple_health','manual','cpap','fitbit')",
    )
    _migrate_table_source(
        conn,
        "body_metrics",
        "('manual','apple_health','oura')",
        "('manual','apple_health','oura','fitbit')",
    )
    conn.commit()


def _migrate_table_source(conn, table, old_check, new_check):
    """Recreate a table to update a CHECK constraint on the source column."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not row:
        return
    create_sql = row[0] or ""
    if "'fitbit'" in create_sql:
        return  # already migrated

    new_sql = create_sql.replace(old_check, new_check)
    if new_sql == create_sql:
        print(f"  WARNING: Could not find CHECK constraint to update in {table}")
        return

    # Replace original table name with temp name
    new_sql = new_sql.replace(f"CREATE TABLE {table}", f"CREATE TABLE {table}__new", 1)
    # Handle IF NOT EXISTS variant
    new_sql = new_sql.replace(
        f"CREATE TABLE IF NOT EXISTS {table}", f"CREATE TABLE {table}__new", 1
    )

    # Get column list
    cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    col_list = ", ".join(cols)

    index_rows = conn.execute(
        """SELECT sql
           FROM sqlite_master
           WHERE type='index'
             AND tbl_name=?
             AND sql IS NOT NULL""",
        (table,),
    ).fetchall()
    index_sql = [row[0] for row in index_rows if row[0]]

    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.executescript(f"""
            DROP TABLE IF EXISTS {table}__new;
            {new_sql};
            INSERT INTO {table}__new ({col_list}) SELECT {col_list} FROM {table};
            DROP TABLE {table};
            ALTER TABLE {table}__new RENAME TO {table};
        """)
        for statement in index_sql:
            conn.execute(statement)
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
    print(f"  Migrated {table}: added 'fitbit' to source CHECK")


# ── Parsers ─────────────────────────────────────────────────────────────────

def parse_fitbit_date(date_str: str) -> str | None:
    """Parse various Fitbit date formats to YYYY-MM-DD."""
    for fmt in ("%m/%d/%y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_fitbit_datetime(dt_str: str) -> str | None:
    """Parse Fitbit datetime to ISO format."""
    for fmt in (
        "%m/%d/%y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%m/%d/%y %H:%M",
    ):
        try:
            return datetime.strptime(dt_str.strip(), fmt).strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    return None


def import_sleep(conn, data_dir, dry_run=False):
    """Import sleep records from Global Export Data/sleep-*.json and Sleep Score CSV."""
    print("\n── Sleep ──")
    sleep_dir = os.path.join(data_dir, "Global Export Data")
    files = sorted(glob.glob(os.path.join(sleep_dir, "sleep-*.json")))
    print(f"  Found {len(files)} sleep JSON files")

    # Load sleep scores into a lookup
    scores = {}
    score_file = os.path.join(data_dir, "Sleep Score", "sleep_score.csv")
    if os.path.exists(score_file):
        with open(score_file) as f:
            for row in csv.DictReader(f):
                ts = row.get("timestamp", "")
                date = ts[:10] if len(ts) >= 10 else None
                if date and row.get("overall_score"):
                    try:
                        scores[date] = int(float(row["overall_score"]))
                    except (ValueError, TypeError):
                        pass
        print(f"  Loaded {len(scores)} sleep scores")

    imported = 0
    skipped = 0
    for filepath in files:
        with open(filepath) as f:
            records = json.load(f)
        for rec in records:
            if not rec.get("mainSleep"):
                continue  # skip naps, only import main sleep
            date = rec.get("dateOfSleep")
            if not date:
                continue

            existing = conn.execute(
                "SELECT source FROM sleep_records WHERE recorded_date = ?", (date,)
            ).fetchone()
            # Preserve Oura/Apple as authoritative for overlapping sleep dates.
            if existing and existing["source"] in ("oura", "apple_health"):
                skipped += 1
                continue

            start_time = rec.get("startTime")
            end_time = rec.get("endTime")
            duration_ms = rec.get("duration", 0)
            duration_min = int(duration_ms / 60000) if duration_ms else None
            minutes_asleep = rec.get("minutesAsleep")
            minutes_awake = rec.get("minutesAwake")

            # Extract stage minutes (newer "stages" format)
            deep_min = None
            rem_min = None
            core_min = None
            awake_min = minutes_awake

            levels = rec.get("levels", {})
            summary = levels.get("summary", {})
            if rec.get("type") == "stages":
                deep_min = summary.get("deep", {}).get("minutes")
                rem_min = summary.get("rem", {}).get("minutes")
                core_min = summary.get("light", {}).get("minutes")  # Fitbit "light" = core
                awake_min = summary.get("wake", {}).get("minutes")

            sleep_score = scores.get(date)

            if not dry_run:
                if existing:
                    conn.execute(
                        """UPDATE sleep_records
                           SET bedtime=COALESCE(bedtime, ?),
                               wake_time=COALESCE(wake_time, ?),
                               duration_min=COALESCE(duration_min, ?),
                               deep_min=COALESCE(deep_min, ?),
                               rem_min=COALESCE(rem_min, ?),
                               core_min=COALESCE(core_min, ?),
                               awake_min=COALESCE(awake_min, ?),
                               sleep_score=COALESCE(sleep_score, ?)
                           WHERE recorded_date=?""",
                        (
                            start_time,
                            end_time,
                            duration_min or minutes_asleep,
                            deep_min,
                            rem_min,
                            core_min,
                            awake_min,
                            sleep_score,
                            date,
                        ),
                    )
                else:
                    conn.execute(
                        """INSERT OR IGNORE INTO sleep_records
                           (recorded_date, bedtime, wake_time, duration_min,
                            deep_min, rem_min, core_min, awake_min,
                            sleep_score, source)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'fitbit')""",
                        (
                            date,
                            start_time,
                            end_time,
                            duration_min or minutes_asleep,
                            deep_min,
                            rem_min,
                            core_min,
                            awake_min,
                            sleep_score,
                        ),
                    )
            imported += 1

    print(f"  Imported: {imported}, Skipped (existing): {skipped}")
    return imported


def import_resting_hr(conn, data_dir, dry_run=False):
    """Import resting heart rate from Global Export Data/resting_heart_rate-*.json."""
    print("\n── Resting Heart Rate ──")
    gdir = os.path.join(data_dir, "Global Export Data")
    files = sorted(glob.glob(os.path.join(gdir, "resting_heart_rate-*.json")))
    print(f"  Found {len(files)} resting HR files")

    imported = 0
    skipped = 0
    for filepath in files:
        with open(filepath) as f:
            records = json.load(f)
        for rec in records:
            val = rec.get("value", {})
            date_str = val.get("date")
            hr_value = val.get("value")
            if not date_str or not hr_value:
                continue
            date = parse_fitbit_date(date_str)
            if not date:
                continue

            existing = conn.execute(
                "SELECT 1 FROM body_metrics WHERE recorded_date = ? AND metric = 'resting_hr'",
                (date,),
            ).fetchone()
            if existing:
                skipped += 1
                continue

                if not dry_run:
                    conn.execute(
                        """INSERT INTO body_metrics (recorded_date, metric, value, source)
                           VALUES (?, 'resting_hr', ?, 'fitbit')""",
                        (date, round(hr_value, 1)),
                    )
                    conn.execute(
                        """UPDATE sleep_records
                           SET resting_hr=COALESCE(resting_hr, ?)
                           WHERE recorded_date=?
                             AND source='fitbit'""",
                        (round(hr_value, 1), date),
                    )
                imported += 1

    print(f"  Imported: {imported}, Skipped (existing): {skipped}")
    return imported


def import_hrv(conn, data_dir, dry_run=False):
    """Import HRV from Heart Rate Variability/Daily Heart Rate Variability Summary CSVs."""
    print("\n── Heart Rate Variability ──")
    hrv_dir = os.path.join(data_dir, "Heart Rate Variability")
    files = sorted(glob.glob(os.path.join(hrv_dir, "Daily Heart Rate Variability Summary*.csv")))
    print(f"  Found {len(files)} HRV CSV files")

    imported = 0
    skipped = 0
    for filepath in files:
        with open(filepath) as f:
            for row in csv.DictReader(f):
                ts = row.get("timestamp", "")
                date = ts[:10] if len(ts) >= 10 else None
                rmssd = row.get("rmssd")
                if not date or not rmssd:
                    continue
                try:
                    rmssd_val = float(rmssd)
                except (ValueError, TypeError):
                    continue

                existing = conn.execute(
                    "SELECT 1 FROM body_metrics WHERE recorded_date = ? AND metric = 'hrv'",
                    (date,),
                ).fetchone()
                if existing:
                    skipped += 1
                    continue

                if not dry_run:
                    conn.execute(
                        """INSERT INTO body_metrics (recorded_date, metric, value, source)
                           VALUES (?, 'hrv', ?, 'fitbit')""",
                        (date, round(rmssd_val, 1)),
                    )
                    conn.execute(
                        """UPDATE sleep_records
                           SET hrv=COALESCE(hrv, ?)
                           WHERE recorded_date=?
                             AND source='fitbit'""",
                        (round(rmssd_val, 1), date),
                    )
                imported += 1

    print(f"  Imported: {imported}, Skipped (existing): {skipped}")
    return imported


def import_steps(conn, data_dir, dry_run=False):
    """Import daily step totals from Global Export Data/steps-*.json.

    Steps files contain per-minute data; we sum to daily totals.
    """
    print("\n── Steps ──")
    gdir = os.path.join(data_dir, "Global Export Data")
    files = sorted(glob.glob(os.path.join(gdir, "steps-*.json")))
    print(f"  Found {len(files)} steps files")

    # Accumulate daily totals across all files
    daily_steps: dict[str, int] = {}
    for filepath in files:
        with open(filepath) as f:
            records = json.load(f)
        for rec in records:
            dt_str = rec.get("dateTime", "")
            val = rec.get("value", "0")
            parsed = parse_fitbit_datetime(dt_str)
            if not parsed:
                continue
            date = parsed[:10]
            try:
                steps = int(val)
            except (ValueError, TypeError):
                continue
            daily_steps[date] = daily_steps.get(date, 0) + steps

    imported = 0
    skipped = 0
    for date in sorted(daily_steps):
        if daily_steps[date] == 0:
            continue
        existing = conn.execute(
            "SELECT 1 FROM body_metrics WHERE recorded_date = ? AND metric = 'steps'",
            (date,),
        ).fetchone()
        if existing:
            skipped += 1
            continue

        if not dry_run:
            conn.execute(
                """INSERT INTO body_metrics (recorded_date, metric, value, source)
                   VALUES (?, 'steps', ?, 'fitbit')""",
                (date, daily_steps[date]),
            )
        imported += 1

    print(f"  Imported: {imported}, Skipped (existing): {skipped}")
    return imported


def import_calories(conn, data_dir, dry_run=False):
    """Import daily active calorie totals from Global Export Data/calories-*.json."""
    print("\n── Active Calories ──")
    gdir = os.path.join(data_dir, "Global Export Data")
    files = sorted(glob.glob(os.path.join(gdir, "calories-*.json")))
    print(f"  Found {len(files)} calories files")

    daily_cals: dict[str, float] = {}
    for filepath in files:
        with open(filepath) as f:
            records = json.load(f)
        for rec in records:
            dt_str = rec.get("dateTime", "")
            val = rec.get("value", "0")
            parsed = parse_fitbit_datetime(dt_str)
            if not parsed:
                continue
            date = parsed[:10]
            try:
                cals = float(val)
            except (ValueError, TypeError):
                continue
            daily_cals[date] = daily_cals.get(date, 0) + cals

    imported = 0
    skipped = 0
    for date in sorted(daily_cals):
        if daily_cals[date] == 0:
            continue
        existing = conn.execute(
            "SELECT 1 FROM body_metrics WHERE recorded_date = ? AND metric = 'active_calories'",
            (date,),
        ).fetchone()
        if existing:
            skipped += 1
            continue

        if not dry_run:
            conn.execute(
                """INSERT INTO body_metrics (recorded_date, metric, value, source)
                   VALUES (?, 'active_calories', ?, 'fitbit')""",
                (date, round(daily_cals[date], 1)),
            )
        imported += 1

    print(f"  Imported: {imported}, Skipped (existing): {skipped}")
    return imported


def import_weight(conn, data_dir, dry_run=False):
    """Import weight from Global Export Data/weight-*.json."""
    print("\n── Weight ──")
    gdir = os.path.join(data_dir, "Global Export Data")
    files = sorted(glob.glob(os.path.join(gdir, "weight-*.json")))
    print(f"  Found {len(files)} weight files")

    imported = 0
    skipped = 0
    for filepath in files:
        with open(filepath) as f:
            records = json.load(f)
        for rec in records:
            date_str = rec.get("date")
            weight = rec.get("weight")
            if not date_str or not weight:
                continue
            date = parse_fitbit_date(date_str)
            if not date:
                continue

            existing = conn.execute(
                "SELECT 1 FROM body_metrics WHERE recorded_date = ? AND metric = 'weight_lbs'",
                (date,),
            ).fetchone()
            if existing:
                skipped += 1
                continue

            if not dry_run:
                conn.execute(
                    """INSERT INTO body_metrics (recorded_date, metric, value, source)
                       VALUES (?, 'weight_lbs', ?, 'fitbit')""",
                    (date, round(weight, 1)),
                )
            imported += 1

            # Also import BMI if present
            bmi = rec.get("bmi")
            if bmi and not dry_run:
                conn.execute(
                    """INSERT OR IGNORE INTO body_metrics (recorded_date, metric, value, source)
                       VALUES (?, 'bmi', ?, 'fitbit')""",
                    (date, round(bmi, 1)),
                )

    print(f"  Imported: {imported}, Skipped (existing): {skipped}")
    return imported


def import_spo2(conn, data_dir, dry_run=False):
    """Import SpO2 from Oxygen Saturation (SpO2)/Daily SpO2 CSVs."""
    print("\n── SpO2 ──")
    spo2_dir = os.path.join(data_dir, "Oxygen Saturation (SpO2)")
    files = sorted(glob.glob(os.path.join(spo2_dir, "Daily SpO2*.csv")))
    print(f"  Found {len(files)} SpO2 CSV files")

    imported = 0
    skipped = 0
    for filepath in files:
        with open(filepath) as f:
            for row in csv.DictReader(f):
                ts = row.get("timestamp", "")
                date = ts[:10] if len(ts) >= 10 else None
                avg_val = row.get("average_value")
                if not date or not avg_val:
                    continue
                try:
                    spo2 = float(avg_val)
                except (ValueError, TypeError):
                    continue

                existing = conn.execute(
                    "SELECT 1 FROM body_metrics WHERE recorded_date = ? AND metric = 'spo2'",
                    (date,),
                ).fetchone()
                if existing:
                    skipped += 1
                    continue

                if not dry_run:
                    conn.execute(
                        """INSERT INTO body_metrics (recorded_date, metric, value, source)
                           VALUES (?, 'spo2', ?, 'fitbit')""",
                        (date, round(spo2, 1)),
                    )
                imported += 1

    print(f"  Imported: {imported}, Skipped (existing): {skipped}")
    return imported


def import_exercise(conn, data_dir, dry_run=False):
    """Import exercises from Global Export Data/exercise-*.json."""
    print("\n── Exercise Sessions ──")
    gdir = os.path.join(data_dir, "Global Export Data")
    files = sorted(glob.glob(os.path.join(gdir, "exercise-*.json")))
    print(f"  Found {len(files)} exercise files")

    imported = 0
    skipped = 0
    for filepath in files:
        with open(filepath) as f:
            records = json.load(f)
        for rec in records:
            log_id = str(rec.get("logId", ""))
            start_str = rec.get("startTime", "")
            if not start_str:
                continue
            start_dt = parse_fitbit_datetime(start_str)
            if not start_dt:
                continue
            date = start_dt[:10]

            # Map activity name to session_type
            activity = (rec.get("activityName") or "Workout").lower()
            session_type = EXERCISE_TYPE_MAP.get(activity, "cardio")

            duration_ms = rec.get("activeDuration") or rec.get("duration", 0)
            duration_min = int(duration_ms / 60000) if duration_ms else None
            calories = rec.get("calories")
            avg_hr = rec.get("averageHeartRate")

            # Use logId as external_id for dedup
            existing = conn.execute(
                "SELECT 1 FROM exercise_sessions WHERE source = 'fitbit' AND external_id = ?",
                (log_id,),
            ).fetchone()
            if existing:
                skipped += 1
                continue

            if not dry_run:
                conn.execute(
                    """INSERT INTO exercise_sessions
                       (recorded_date, session_type, name, external_id,
                        duration_min, calories_burned, avg_heart_rate, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'fitbit')""",
                    (date, session_type, rec.get("activityName", "Workout"),
                     log_id, duration_min, calories, avg_hr),
                )
            imported += 1

    print(f"  Imported: {imported}, Skipped (existing): {skipped}")
    return imported


def scan_afib_ecg(data_dir):
    """Scan AFib ECG readings and report findings."""
    print("\n── AFib ECG Readings ──")
    ecg_dir = os.path.join(data_dir, "Atrial Fibrillation ECG")
    files = sorted(glob.glob(os.path.join(ecg_dir, "afib_ecg_reading_*.csv")))
    print(f"  Found {len(files)} ECG reading files")

    readings = []
    for filepath in files:
        with open(filepath) as f:
            r = csv.DictReader(f)
            for row in r:
                readings.append({
                    "date": row.get("reading_time", ""),
                    "classification": row.get("result_classification", ""),
                    "heart_rate": row.get("heart_rate", ""),
                })

    afib_count = sum(1 for r in readings if r["classification"] == "AFIB")
    nsr_count = sum(1 for r in readings if r["classification"] == "NSR")
    unreadable_count = sum(1 for r in readings if r["classification"] == "UNREADABLE")

    print(f"  Total readings: {len(readings)}")
    print(f"  NSR (normal): {nsr_count}")
    print(f"  UNREADABLE: {unreadable_count}")
    print(f"  AFib detected: {afib_count}")
    if afib_count > 0:
        print("  ⚠️  AFib readings found — flag for Dr. Smithson review:")
        for r in readings:
            if r["classification"] == "AFIB":
                print(f"    {r['date']} — HR {r['heart_rate']} bpm")
    else:
        print("  No AFib detected in any readings.")

    for r in readings:
        print(f"    {r['date']} — {r['classification']} (HR {r['heart_rate']})")

    return {"total": len(readings), "afib": afib_count, "nsr": nsr_count, "unreadable": unreadable_count}


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Import Fitbit historical data into Driver")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help="Path to extracted fitbit-data directory")
    parser.add_argument("--dry-run", action="store_true", help="Parse and count without inserting")
    args = parser.parse_args()

    data_dir = os.path.abspath(args.data_dir)
    if not os.path.isdir(data_dir):
        print(f"ERROR: Data directory not found: {data_dir}")
        sys.exit(1)

    db_path = os.path.abspath(DATABASE_PATH)
    print("Fitbit Historical Import")
    print(f"  Data dir: {data_dir}")
    print(f"  Database: {db_path}")
    print(f"  Dry run:  {args.dry_run}")

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Migrate schema to accept source='fitbit'
    print("\n── Schema Migration ──")
    migrate_add_fitbit_source(conn)

    totals = {}
    totals["sleep"] = import_sleep(conn, data_dir, args.dry_run)
    totals["resting_hr"] = import_resting_hr(conn, data_dir, args.dry_run)
    totals["hrv"] = import_hrv(conn, data_dir, args.dry_run)
    totals["steps"] = import_steps(conn, data_dir, args.dry_run)
    totals["calories"] = import_calories(conn, data_dir, args.dry_run)
    totals["weight"] = import_weight(conn, data_dir, args.dry_run)
    totals["spo2"] = import_spo2(conn, data_dir, args.dry_run)
    totals["exercise"] = import_exercise(conn, data_dir, args.dry_run)
    ecg = scan_afib_ecg(data_dir)

    if not args.dry_run:
        conn.commit()
    conn.close()

    # Summary
    total_records = sum(totals.values())
    print("\n" + "=" * 50)
    print("IMPORT SUMMARY")
    print("=" * 50)
    for category, count in totals.items():
        print(f"  {category:20s} {count:>6}")
    print(f"  {'TOTAL':20s} {total_records:>6}")
    print(f"\n  ECG readings: {ecg['total']} ({ecg['nsr']} NSR, {ecg['unreadable']} unreadable, {ecg['afib']} AFib)")
    if args.dry_run:
        print("\n  ** DRY RUN — no data was written **")
    else:
        print(f"\n  Done. Data committed to {db_path}")


if __name__ == "__main__":
    main()
