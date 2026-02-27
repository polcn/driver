from __future__ import annotations

import sqlite3
from datetime import date, timedelta


SCHEDULE_BY_WEEKDAY = {
    0: "strength",  # Monday
    1: "cardio",  # Tuesday
    2: "strength",  # Wednesday
    3: "cardio",  # Thursday
    4: "strength",  # Friday
    5: "rest",  # Saturday
    6: "rest",  # Sunday
}


def _week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _expected_sessions_to_date(target: date, session_type: str) -> int:
    start = _week_start(target)
    count = 0
    cursor = start
    while cursor <= target:
        if SCHEDULE_BY_WEEKDAY[cursor.weekday()] == session_type:
            count += 1
        cursor += timedelta(days=1)
    return count


def _build_suggestion(
    *,
    scheduled_type: str,
    readiness_score: int | None,
    hrv: float | None,
    hrv_7day_avg: float | None,
    missed_sessions: int,
) -> tuple[str, str]:
    low_readiness = readiness_score is not None and readiness_score < 60
    low_hrv = (
        hrv is not None and hrv_7day_avg is not None and hrv < (hrv_7day_avg * 0.85)
    )
    high_readiness = readiness_score is not None and readiness_score >= 75
    normal_hrv = (
        hrv is not None and hrv_7day_avg is not None and hrv >= (hrv_7day_avg * 0.95)
    )

    if scheduled_type == "rest":
        if high_readiness and normal_hrv:
            return (
                "Rest day. Readiness is high, so add an optional 20-30 min Zone 1 walk and mobility.",
                "easy",
            )
        return ("Rest day. Focus on recovery, light mobility, and hydration.", "rest")

    if low_readiness or low_hrv:
        if scheduled_type == "cardio":
            base = "Cardio day. Keep it easy: 20-30 min in Zone 1-2."
        else:
            base = "Strength day. Reduce volume and keep effort moderate."
        return (base, "easy")

    if high_readiness and normal_hrv:
        if scheduled_type == "cardio":
            base = "Cardio day. Readiness is strong: target 30-45 min in Zone 2."
        else:
            base = "Strength day. Readiness is strong: run your full planned session."
        if missed_sessions > 0:
            base += f" You missed {missed_sessions} scheduled session(s) this week; consider making one up."
        return (base, "full")

    if scheduled_type == "cardio":
        base = "Cardio day. Keep a steady 25-40 min Zone 2 effort."
    else:
        base = "Strength day. Run your planned session at moderate effort."
    if missed_sessions > 0:
        base += f" You missed {missed_sessions} scheduled session(s) this week; consider a short make-up block."
    return (base, "moderate")


def generate_daily_suggestion(conn: sqlite3.Connection, *, target: date) -> dict:
    target_str = target.isoformat()
    scheduled_type = SCHEDULE_BY_WEEKDAY[target.weekday()]

    sleep_row = conn.execute(
        """SELECT readiness_score, hrv
           FROM sleep_records
           WHERE recorded_date = ?
           ORDER BY CASE source WHEN 'oura' THEN 0 ELSE 1 END, created_at DESC
           LIMIT 1""",
        (target_str,),
    ).fetchone()
    readiness_score = sleep_row["readiness_score"] if sleep_row else None
    hrv = sleep_row["hrv"] if sleep_row else None

    hrv_avg_row = conn.execute(
        """SELECT AVG(hrv) AS hrv_7day_avg
           FROM sleep_records
           WHERE recorded_date BETWEEN date(?, '-6 days') AND ?
             AND hrv IS NOT NULL""",
        (target_str, target_str),
    ).fetchone()
    hrv_7day_avg = hrv_avg_row["hrv_7day_avg"] if hrv_avg_row else None

    week_start = _week_start(target).isoformat()
    session_counts = conn.execute(
        """SELECT session_type, COUNT(*) AS count
           FROM exercise_sessions
           WHERE recorded_date BETWEEN ? AND ?
             AND deleted_at IS NULL
           GROUP BY session_type""",
        (week_start, target_str),
    ).fetchall()
    by_type = {row["session_type"]: int(row["count"]) for row in session_counts}
    expected = _expected_sessions_to_date(target, scheduled_type)
    completed = by_type.get(scheduled_type, 0)
    missed_sessions = max(expected - completed, 0) if scheduled_type != "rest" else 0

    suggestion, intensity = _build_suggestion(
        scheduled_type=scheduled_type,
        readiness_score=readiness_score,
        hrv=hrv,
        hrv_7day_avg=hrv_7day_avg,
        missed_sessions=missed_sessions,
    )

    conn.execute(
        """INSERT INTO daily_suggestions
           (
             suggestion_date,
             readiness_score,
             hrv,
             hrv_7day_avg,
             scheduled_type,
             suggestion,
             intensity
           )
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(suggestion_date) DO UPDATE SET
             readiness_score=excluded.readiness_score,
             hrv=excluded.hrv,
             hrv_7day_avg=excluded.hrv_7day_avg,
             scheduled_type=excluded.scheduled_type,
             suggestion=excluded.suggestion,
             intensity=excluded.intensity""",
        (
            target_str,
            readiness_score,
            hrv,
            hrv_7day_avg,
            scheduled_type,
            suggestion,
            intensity,
        ),
    )
    conn.commit()

    row = conn.execute(
        "SELECT * FROM daily_suggestions WHERE suggestion_date=?",
        (target_str,),
    ).fetchone()
    return dict(row)
