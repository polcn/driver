import sqlite3
from datetime import date, timedelta
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import get_db_dependency, row_to_dict
from ..services.suggestions import generate_daily_suggestion

router = APIRouter()


class AgentQueryType(str, Enum):
    today_summary = "today_summary"
    week_summary = "week_summary"
    daily_suggestion = "daily_suggestion"
    food_summary = "food_summary"
    sleep_summary = "sleep_summary"
    metric_trend = "metric_trend"


def _get_food_summary(conn: sqlite3.Connection, target: date) -> dict:
    summary = conn.execute(
        """SELECT
            COUNT(*) as entry_count,
            ROUND(SUM(calories), 1) as calories,
            ROUND(SUM(protein_g), 1) as protein_g,
            ROUND(SUM(sodium_mg), 0) as sodium_mg
           FROM food_entries
           WHERE recorded_date=? AND deleted_at IS NULL""",
        (str(target),),
    ).fetchone()
    return row_to_dict(summary)


def _get_sleep_summary(conn: sqlite3.Connection, target: date) -> Optional[dict]:
    sleep = conn.execute(
        """SELECT *
           FROM sleep_records
           WHERE recorded_date=?
           ORDER BY created_at DESC
           LIMIT 1""",
        (str(target),),
    ).fetchone()
    return row_to_dict(sleep) if sleep else None


def _get_daily_suggestion(
    conn: sqlite3.Connection, target: date, *, autocreate: bool
) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM daily_suggestions WHERE suggestion_date=?",
        (str(target),),
    ).fetchone()
    if row:
        return row_to_dict(row)
    if not autocreate:
        return None
    return generate_daily_suggestion(conn, target=target)


@router.get("/today-summary")
def get_today_summary(
    target_date: Optional[date] = None,
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
    target = target_date or date.today()
    food = _get_food_summary(conn, target)
    sleep = _get_sleep_summary(conn, target)
    suggestion = _get_daily_suggestion(conn, target, autocreate=False)
    activity_rows = conn.execute(
        """SELECT metric, value
           FROM body_metrics
           WHERE recorded_date=?
             AND metric IN ('steps', 'active_calories')
           ORDER BY id DESC""",
        (str(target),),
    ).fetchall()
    activity = {}
    for row in activity_rows:
        if row["metric"] not in activity:
            activity[row["metric"]] = row["value"]

    text = (
        f"{target}: calories {food.get('calories') or 0}, "
        f"protein {food.get('protein_g') or 0}g, "
        f"steps {activity.get('steps') or 0}, "
        f"active calories {activity.get('active_calories') or 0}."
    )
    return {
        "date": str(target),
        "food": food,
        "sleep": sleep,
        "activity": activity,
        "daily_suggestion": suggestion,
        "summary_text": text,
    }


@router.get("/week-summary")
def get_week_summary(
    ending: Optional[date] = None,
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
    end = ending or date.today()
    start = end - timedelta(days=6)
    food = conn.execute(
        """SELECT
            ROUND(SUM(calories), 1) as calories,
            ROUND(SUM(protein_g), 1) as protein_g,
            ROUND(SUM(sodium_mg), 0) as sodium_mg,
            ROUND(SUM(alcohol_calories), 0) as alcohol_calories,
            COUNT(DISTINCT recorded_date) as food_days
           FROM food_entries
           WHERE recorded_date BETWEEN ? AND ?
             AND deleted_at IS NULL""",
        (str(start), str(end)),
    ).fetchone()
    exercise = conn.execute(
        """SELECT
            COUNT(*) as session_count,
            ROUND(SUM(duration_min), 1) as total_duration_min,
            ROUND(SUM(calories_burned), 1) as calories_burned
           FROM exercise_sessions
           WHERE recorded_date BETWEEN ? AND ?
             AND deleted_at IS NULL""",
        (str(start), str(end)),
    ).fetchone()
    sleep = conn.execute(
        """SELECT
            ROUND(AVG(duration_min), 1) as avg_sleep_min,
            ROUND(AVG(sleep_score), 1) as avg_sleep_score
           FROM sleep_records
           WHERE recorded_date BETWEEN ? AND ?""",
        (str(start), str(end)),
    ).fetchone()

    food_payload = row_to_dict(food)
    exercise_payload = row_to_dict(exercise)
    sleep_payload = row_to_dict(sleep)
    text = (
        f"Week {start} to {end}: "
        f"{food_payload.get('calories') or 0} cals, "
        f"{food_payload.get('protein_g') or 0}g protein, "
        f"{exercise_payload.get('session_count') or 0} workouts, "
        f"avg sleep {sleep_payload.get('avg_sleep_min') or 0} min."
    )
    return {
        "start": str(start),
        "end": str(end),
        "food": food_payload,
        "exercise": exercise_payload,
        "sleep": sleep_payload,
        "summary_text": text,
    }


@router.get("/daily-suggestion")
def get_daily_suggestion(
    target_date: Optional[date] = None,
    create_if_missing: bool = True,
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
    target = target_date or date.today()
    suggestion = _get_daily_suggestion(
        conn,
        target,
        autocreate=create_if_missing,
    )
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Daily suggestion not found")
    return suggestion


@router.get("/query")
def query(
    query_type: AgentQueryType,
    target_date: Optional[date] = None,
    metric: Optional[str] = None,
    days: int = Query(default=7, ge=1, le=90),
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
    target = target_date or date.today()

    if query_type == AgentQueryType.today_summary:
        return get_today_summary(target, conn)

    if query_type == AgentQueryType.week_summary:
        return get_week_summary(target, conn)

    if query_type == AgentQueryType.daily_suggestion:
        return get_daily_suggestion(target, True, conn)

    if query_type == AgentQueryType.food_summary:
        food = _get_food_summary(conn, target)
        return {"date": str(target), "food": food}

    if query_type == AgentQueryType.sleep_summary:
        sleep = _get_sleep_summary(conn, target)
        return {"date": str(target), "sleep": sleep}

    if query_type == AgentQueryType.metric_trend:
        if not metric:
            raise HTTPException(
                status_code=422,
                detail="metric query parameter is required for metric_trend",
            )
        rows = conn.execute(
            """SELECT recorded_date, metric, value, source, notes, created_at
               FROM body_metrics
               WHERE metric = ?
                 AND recorded_date BETWEEN date(?, ?) AND ?
               ORDER BY recorded_date""",
            (metric, str(target), f"-{days - 1} days", str(target)),
        ).fetchall()
        return {
            "metric": metric,
            "ending": str(target),
            "days": days,
            "values": [row_to_dict(row) for row in rows],
        }

    raise HTTPException(status_code=400, detail="Unsupported query type")
