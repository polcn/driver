from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from typing import Literal


DigestType = Literal["daily", "weekly"]


def _safe_number(value: float | None, digits: int = 0) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _load_targets(conn: sqlite3.Connection, target: date) -> dict[str, float]:
    rows = conn.execute(
        """SELECT t1.metric, t1.value
           FROM targets t1
           WHERE t1.effective_date = (
             SELECT MAX(t2.effective_date)
             FROM targets t2
             WHERE t2.metric = t1.metric
               AND t2.effective_date <= ?
           )""",
        (target.isoformat(),),
    ).fetchall()
    return {row["metric"]: float(row["value"]) for row in rows}


def _persist_digest(
    conn: sqlite3.Connection,
    *,
    digest_date: date,
    digest_type: DigestType,
    summary: str,
    highlights: list[str],
) -> dict:
    conn.execute(
        """INSERT INTO coaching_digests (digest_date, digest_type, summary, highlights)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(digest_date, digest_type) DO UPDATE SET
             summary=excluded.summary,
             highlights=excluded.highlights""",
        (
            digest_date.isoformat(),
            digest_type,
            summary,
            json.dumps(highlights),
        ),
    )
    conn.commit()

    row = conn.execute(
        """SELECT *
           FROM coaching_digests
           WHERE digest_date = ?
             AND digest_type = ?""",
        (digest_date.isoformat(), digest_type),
    ).fetchone()

    return {
        "id": row["id"],
        "digest_date": row["digest_date"],
        "digest_type": row["digest_type"],
        "summary": row["summary"],
        "highlights": json.loads(row["highlights"] or "[]"),
        "created_at": row["created_at"],
    }


def generate_daily_digest(conn: sqlite3.Connection, *, target: date) -> dict:
    day = target.isoformat()
    targets = _load_targets(conn, target)

    food = conn.execute(
        """SELECT
             ROUND(SUM(calories), 0) AS calories,
             ROUND(SUM(protein_g), 1) AS protein_g,
             ROUND(SUM(sodium_mg), 0) AS sodium_mg,
             ROUND(SUM(alcohol_calories), 0) AS alcohol_calories,
             COUNT(*) AS entry_count
           FROM food_entries
           WHERE recorded_date = ?
             AND deleted_at IS NULL""",
        (day,),
    ).fetchone()

    sleep = conn.execute(
        """SELECT duration_min, sleep_score, readiness_score
           FROM sleep_records
           WHERE recorded_date = ?
           ORDER BY CASE source WHEN 'oura' THEN 0 ELSE 1 END, created_at DESC
           LIMIT 1""",
        (day,),
    ).fetchone()

    exercise = conn.execute(
        """SELECT
             COUNT(*) AS session_count,
             ROUND(SUM(duration_min), 0) AS duration_min
           FROM exercise_sessions
           WHERE recorded_date = ?
             AND deleted_at IS NULL""",
        (day,),
    ).fetchone()

    highlights: list[str] = []
    calories = food["calories"]
    protein = food["protein_g"]
    sodium = food["sodium_mg"]
    alcohol = food["alcohol_calories"]
    entry_count = int(food["entry_count"] or 0)

    if entry_count > 0:
        calories_target = targets.get("calories")
        protein_target = targets.get("protein_g")
        sodium_target = targets.get("sodium_mg")
        calorie_line = f"{int(calories or 0)} kcal"
        if calories_target:
            delta = int((calories or 0) - calories_target)
            calorie_line += f" ({delta:+} vs target)"
        highlights.append(f"Intake: {entry_count} entries, {calorie_line}.")

        if protein is not None and protein_target:
            protein_gap = _safe_number(float(protein) - protein_target, 1)
            highlights.append(
                f"Protein: {protein} g ({protein_gap:+} vs {protein_target:g} g target)."
            )
        if sodium is not None and sodium_target:
            sodium_gap = int(float(sodium) - sodium_target)
            highlights.append(
                f"Sodium: {int(sodium)} mg ({sodium_gap:+} vs {int(sodium_target)} mg target)."
            )
        if alcohol and alcohol > 0:
            highlights.append(f"Alcohol intake logged: {int(alcohol)} kcal.")
    else:
        highlights.append("No nutrition entries logged today.")

    if sleep:
        sleep_duration = sleep["duration_min"]
        sleep_score = sleep["sleep_score"]
        readiness = sleep["readiness_score"]
        if sleep_duration is not None:
            highlights.append(
                f"Sleep: {round(float(sleep_duration) / 60, 1)} h"
                + (f", score {sleep_score}" if sleep_score is not None else "")
                + (f", readiness {readiness}" if readiness is not None else "")
                + "."
            )
    else:
        highlights.append("No sleep record for this date.")

    session_count = int(exercise["session_count"] or 0)
    if session_count > 0:
        duration = int(exercise["duration_min"] or 0)
        highlights.append(f"Training: {session_count} session(s), {duration} total minutes.")
    else:
        highlights.append("No workouts logged today.")

    summary = (
        f"Daily digest for {day}: "
        f"{entry_count} food entries, {session_count} workouts, "
        + (
            f"sleep score {sleep['sleep_score']}."
            if sleep and sleep["sleep_score"] is not None
            else "sleep score unavailable."
        )
    )
    return _persist_digest(
        conn,
        digest_date=target,
        digest_type="daily",
        summary=summary,
        highlights=highlights[:6],
    )


def generate_weekly_digest(conn: sqlite3.Connection, *, ending: date) -> dict:
    start = ending - timedelta(days=6)
    start_s = start.isoformat()
    end_s = ending.isoformat()
    targets = _load_targets(conn, ending)

    food = conn.execute(
        """SELECT
             ROUND(AVG(day_calories), 0) AS avg_calories,
             ROUND(AVG(day_protein), 1) AS avg_protein_g,
             ROUND(AVG(day_sodium), 0) AS avg_sodium_mg,
             ROUND(SUM(day_alcohol), 0) AS alcohol_calories_total,
             COUNT(*) AS days_with_food
           FROM (
             SELECT
               recorded_date,
               SUM(calories) AS day_calories,
               SUM(protein_g) AS day_protein,
               SUM(sodium_mg) AS day_sodium,
               SUM(alcohol_calories) AS day_alcohol
             FROM food_entries
             WHERE recorded_date BETWEEN ? AND ?
               AND deleted_at IS NULL
             GROUP BY recorded_date
           )""",
        (start_s, end_s),
    ).fetchone()

    exercise = conn.execute(
        """SELECT
             COUNT(*) AS session_count,
             ROUND(SUM(duration_min), 0) AS total_duration_min,
             ROUND(SUM(calories_burned), 0) AS total_calories_burned
           FROM exercise_sessions
           WHERE recorded_date BETWEEN ? AND ?
             AND deleted_at IS NULL""",
        (start_s, end_s),
    ).fetchone()

    sleep = conn.execute(
        """SELECT
             ROUND(AVG(duration_min), 1) AS avg_sleep_min,
             ROUND(AVG(sleep_score), 1) AS avg_sleep_score,
             ROUND(AVG(readiness_score), 1) AS avg_readiness
           FROM sleep_records
           WHERE recorded_date BETWEEN ? AND ?""",
        (start_s, end_s),
    ).fetchone()

    highlights: list[str] = []
    avg_calories = food["avg_calories"]
    avg_protein = food["avg_protein_g"]
    avg_sodium = food["avg_sodium_mg"]
    if avg_calories is not None:
        calories_target = targets.get("calories")
        calorie_line = f"Average calories/day: {int(avg_calories)}"
        if calories_target:
            delta = int(float(avg_calories) - calories_target)
            calorie_line += f" ({delta:+} vs target)"
        highlights.append(calorie_line + ".")
    else:
        highlights.append("No food intake logged in this 7-day window.")

    if avg_protein is not None and "protein_g" in targets:
        gap = _safe_number(float(avg_protein) - targets["protein_g"], 1)
        highlights.append(
            f"Average protein/day: {avg_protein} g ({gap:+} vs {targets['protein_g']:g} g target)."
        )
    if avg_sodium is not None and "sodium_mg" in targets:
        gap = int(float(avg_sodium) - targets["sodium_mg"])
        highlights.append(
            f"Average sodium/day: {int(avg_sodium)} mg ({gap:+} vs {int(targets['sodium_mg'])} mg target)."
        )

    session_count = int(exercise["session_count"] or 0)
    if session_count > 0:
        total_duration = int(exercise["total_duration_min"] or 0)
        highlights.append(
            f"Training volume: {session_count} sessions and {total_duration} minutes."
        )
    else:
        highlights.append("No training sessions logged this week.")

    avg_sleep_min = sleep["avg_sleep_min"]
    if avg_sleep_min is not None:
        highlights.append(
            f"Average sleep: {round(float(avg_sleep_min) / 60, 1)} h/night"
            + (
                f", score {sleep['avg_sleep_score']}"
                if sleep["avg_sleep_score"] is not None
                else ""
            )
            + "."
        )
    else:
        highlights.append("No sleep records logged this week.")

    summary = (
        f"Weekly digest for {start_s} to {end_s}: "
        f"{session_count} workouts and "
        + (
            f"{int(avg_calories)} avg kcal/day."
            if avg_calories is not None
            else "no nutrition averages yet."
        )
    )
    return _persist_digest(
        conn,
        digest_date=ending,
        digest_type="weekly",
        summary=summary,
        highlights=highlights[:6],
    )


def get_latest_digests(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        """SELECT id, digest_date, digest_type, summary, highlights, created_at
           FROM coaching_digests
           ORDER BY digest_type, digest_date DESC, id DESC"""
    ).fetchall()

    latest = {"daily": None, "weekly": None}
    for row in rows:
        digest_type = row["digest_type"]
        if latest.get(digest_type) is not None:
            continue
        latest[digest_type] = {
            "id": row["id"],
            "digest_date": row["digest_date"],
            "digest_type": digest_type,
            "summary": row["summary"],
            "highlights": json.loads(row["highlights"] or "[]"),
            "created_at": row["created_at"],
        }

        if latest["daily"] is not None and latest["weekly"] is not None:
            break

    return latest
