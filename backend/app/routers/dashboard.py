from fastapi import APIRouter, Query
from datetime import date, timedelta

from ..db import get_db

router = APIRouter()


@router.get("/today")
def get_today(target_date: str = None):
    today = target_date or str(date.today())
    conn = get_db()
    try:
        # Food summary
        food = conn.execute(
            """SELECT
                ROUND(SUM(calories), 1) as calories,
                ROUND(SUM(protein_g), 1) as protein_g,
                ROUND(SUM(sodium_mg), 0) as sodium_mg,
                ROUND(SUM(carbs_g), 1) as carbs_g,
                ROUND(SUM(fat_g), 1) as fat_g,
                ROUND(SUM(fiber_g), 1) as fiber_g,
                ROUND(SUM(alcohol_calories), 0) as alcohol_calories,
                COUNT(*) as entry_count
               FROM food_entries WHERE recorded_date=? AND deleted_at IS NULL""",
            (today,),
        ).fetchone()

        # Targets
        targets_rows = conn.execute(
            """SELECT t1.metric, t1.value FROM targets t1
               WHERE t1.effective_date = (
                   SELECT MAX(t2.effective_date) FROM targets t2
                   WHERE t2.metric = t1.metric AND t2.effective_date <= ?
               )""",
            (today,),
        ).fetchall()
        targets = {r["metric"]: r["value"] for r in targets_rows}

        # Exercise
        exercise = conn.execute(
            """SELECT *
               FROM exercise_sessions
               WHERE recorded_date=?
                 AND deleted_at IS NULL
               ORDER BY created_at""",
            (today,),
        ).fetchall()

        # Sleep (last night)
        sleep = conn.execute(
            """SELECT *
               FROM sleep_records
               WHERE recorded_date=?
               ORDER BY created_at DESC
               LIMIT 1""",
            (today,),
        ).fetchone()

        # Daily suggestion
        suggestion = conn.execute(
            "SELECT * FROM daily_suggestions WHERE suggestion_date=?", (today,)
        ).fetchone()

        return {
            "date": today,
            "food": dict(food) if food else {},
            "targets": targets,
            "exercise": [dict(e) for e in exercise],
            "sleep": dict(sleep) if sleep else None,
            "suggestion": dict(suggestion) if suggestion else None,
        }
    finally:
        conn.close()


@router.get("/week")
def get_week_summary(ending: str = None):
    end = date.fromisoformat(ending) if ending else date.today()
    start = end - timedelta(days=6)
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT recorded_date,
                ROUND(SUM(calories), 0) as calories,
                ROUND(SUM(protein_g), 1) as protein_g,
                ROUND(SUM(sodium_mg), 0) as sodium_mg,
                ROUND(SUM(alcohol_calories), 0) as alcohol_calories
               FROM food_entries
               WHERE recorded_date BETWEEN ? AND ? AND deleted_at IS NULL
               GROUP BY recorded_date ORDER BY recorded_date""",
            (str(start), str(end)),
        ).fetchall()

        exercise_rows = conn.execute(
            """SELECT recorded_date, session_type, COUNT(*) as sessions
               FROM exercise_sessions
               WHERE recorded_date BETWEEN ? AND ? AND deleted_at IS NULL
               GROUP BY recorded_date, session_type""",
            (str(start), str(end)),
        ).fetchall()

        return {
            "start": str(start),
            "end": str(end),
            "food_by_day": [dict(r) for r in rows],
            "exercise_by_day": [dict(r) for r in exercise_rows],
        }
    finally:
        conn.close()


@router.get("/trends")
def get_trends(days: int = Query(default=90, ge=1, le=3650), ending: str = None):
    end = date.fromisoformat(ending) if ending else date.today()
    start = end - timedelta(days=days - 1)
    conn = get_db()
    try:
        food_rows = conn.execute(
            """SELECT recorded_date,
                      ROUND(SUM(calories), 0) as calories,
                      ROUND(SUM(protein_g), 1) as protein_g,
                      ROUND(SUM(sodium_mg), 0) as sodium_mg,
                      ROUND(SUM(alcohol_calories), 0) as alcohol_calories
               FROM food_entries
               WHERE recorded_date BETWEEN ? AND ?
                 AND deleted_at IS NULL
               GROUP BY recorded_date
               ORDER BY recorded_date""",
            (str(start), str(end)),
        ).fetchall()

        exercise_rows = conn.execute(
            """SELECT recorded_date,
                      COUNT(*) as sessions,
                      COALESCE(SUM(duration_min), 0) as duration_min,
                      ROUND(SUM(calories_burned), 1) as calories_burned
               FROM exercise_sessions
               WHERE recorded_date BETWEEN ? AND ?
                 AND deleted_at IS NULL
               GROUP BY recorded_date
               ORDER BY recorded_date""",
            (str(start), str(end)),
        ).fetchall()

        sleep_rows = conn.execute(
            """SELECT recorded_date,
                      duration_min,
                      sleep_score,
                      hrv,
                      resting_hr,
                      readiness_score
               FROM sleep_records
               WHERE recorded_date BETWEEN ? AND ?
               ORDER BY recorded_date""",
            (str(start), str(end)),
        ).fetchall()

        metrics_rows = conn.execute(
            """SELECT bm.recorded_date, bm.metric, bm.value
               FROM body_metrics bm
               JOIN (
                    SELECT recorded_date, metric, MAX(created_at) as max_created_at
                    FROM body_metrics
                    WHERE metric IN ('weight_lbs', 'waist_in')
                      AND recorded_date BETWEEN ? AND ?
                    GROUP BY recorded_date, metric
               ) latest
                 ON bm.recorded_date = latest.recorded_date
                AND bm.metric = latest.metric
                AND bm.created_at = latest.max_created_at
               ORDER BY bm.recorded_date""",
            (str(start), str(end)),
        ).fetchall()

        weight = [
            {"recorded_date": row["recorded_date"], "value": row["value"]}
            for row in metrics_rows
            if row["metric"] == "weight_lbs"
        ]
        waist = [
            {"recorded_date": row["recorded_date"], "value": row["value"]}
            for row in metrics_rows
            if row["metric"] == "waist_in"
        ]

        return {
            "start": str(start),
            "end": str(end),
            "days": days,
            "food_by_day": [dict(r) for r in food_rows],
            "exercise_by_day": [dict(r) for r in exercise_rows],
            "sleep_by_day": [dict(r) for r in sleep_rows],
            "weight_by_day": weight,
            "waist_by_day": waist,
        }
    finally:
        conn.close()
