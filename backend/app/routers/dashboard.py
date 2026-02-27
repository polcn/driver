from fastapi import APIRouter
from datetime import date, timedelta

from ..db import get_db

router = APIRouter()


def _build_narrative_insights(conn, today: date) -> list[str]:
    insights: list[str] = []
    today_str = str(today)

    sleep_rows = conn.execute(
        """SELECT recorded_date, sleep_score, hrv, resting_hr
           FROM sleep_records
           WHERE recorded_date BETWEEN date(?, '-6 days') AND ?
           ORDER BY recorded_date""",
        (today_str, today_str),
    ).fetchall()

    today_sleep = next(
        (row for row in sleep_rows if row["recorded_date"] == today_str), None
    )
    prior_sleep = [row for row in sleep_rows if row["recorded_date"] != today_str]

    if today_sleep and prior_sleep:
        prior_scores = [
            row["sleep_score"] for row in prior_sleep if row["sleep_score"] is not None
        ]
        if today_sleep["sleep_score"] is not None and prior_scores:
            avg_score = sum(prior_scores) / len(prior_scores)
            delta = round(today_sleep["sleep_score"] - avg_score, 1)
            if delta <= -2:
                insights.append(
                    f"Sleep score is {today_sleep['sleep_score']}, {abs(delta):g} below your recent average ({avg_score:.1f})."
                )
            elif delta >= 2:
                insights.append(
                    f"Sleep score is {today_sleep['sleep_score']}, {delta:g} above your recent average ({avg_score:.1f})."
                )

        prior_resting_hr = [
            row["resting_hr"] for row in prior_sleep if row["resting_hr"] is not None
        ]
        if today_sleep["resting_hr"] is not None and prior_resting_hr:
            avg_rhr = sum(prior_resting_hr) / len(prior_resting_hr)
            delta_rhr = round(today_sleep["resting_hr"] - avg_rhr, 1)
            if delta_rhr <= -1:
                insights.append(
                    f"Resting HR is {today_sleep['resting_hr']} bpm, down {abs(delta_rhr):g} vs your recent average."
                )
            elif delta_rhr >= 1:
                insights.append(
                    f"Resting HR is {today_sleep['resting_hr']} bpm, up {delta_rhr:g} vs your recent average."
                )

    alcohol_sleep_rows = conn.execute(
        """SELECT s.recorded_date, s.sleep_score, COALESCE(f.alcohol_calories, 0) AS alcohol_calories
           FROM sleep_records s
           LEFT JOIN (
               SELECT recorded_date, SUM(alcohol_calories) AS alcohol_calories
               FROM food_entries
               WHERE recorded_date BETWEEN date(?, '-13 days') AND ?
                 AND deleted_at IS NULL
               GROUP BY recorded_date
           ) f ON f.recorded_date = s.recorded_date
           WHERE s.recorded_date BETWEEN date(?, '-13 days') AND ?
           ORDER BY s.recorded_date""",
        (today_str, today_str, today_str, today_str),
    ).fetchall()

    alcohol_nights = 0
    low_sleep_after_alcohol = 0
    for row in alcohol_sleep_rows:
        if (row["alcohol_calories"] or 0) > 0:
            alcohol_nights += 1
            if row["sleep_score"] is not None and row["sleep_score"] < 70:
                low_sleep_after_alcohol += 1

    if alcohol_nights >= 2 and low_sleep_after_alcohol >= 2:
        insights.append(
            f"Alcohol intake coincided with lower sleep quality on {low_sleep_after_alcohol} of the last {alcohol_nights} drinking nights."
        )

    cardio_zone_rows = conn.execute(
        """SELECT
               s.id,
               s.recorded_date,
               COALESCE(SUM(CASE WHEN z.zone IN (1, 2) THEN z.minutes ELSE 0 END), 0) AS zone12_minutes,
               COALESCE(SUM(z.minutes), 0) AS total_minutes
           FROM exercise_sessions s
           LEFT JOIN exercise_hr_zones z
             ON z.session_id = s.id
           WHERE s.recorded_date BETWEEN date(?, '-13 days') AND ?
             AND s.deleted_at IS NULL
             AND s.session_type = 'cardio'
           GROUP BY s.id, s.recorded_date
           HAVING COALESCE(SUM(z.minutes), 0) > 0
           ORDER BY s.recorded_date""",
        (today_str, today_str),
    ).fetchall()

    zone12_pcts = [
        (row["zone12_minutes"] / row["total_minutes"]) * 100.0
        for row in cardio_zone_rows
    ]
    if zone12_pcts:
        recent = zone12_pcts[-3:]
        recent_avg = sum(recent) / len(recent)
        prior = zone12_pcts[:-3]
        prior_avg = (sum(prior[-3:]) / len(prior[-3:])) if prior else None

        if recent_avg < 50:
            insights.append(
                f"Recent cardio sessions averaged {recent_avg:.0f}% in Zone 1-2; target at least 50% for aerobic base/fat-burn work."
            )
        elif prior_avg is not None and recent_avg >= prior_avg + 10:
            insights.append(
                f"Zone 1-2 cardio time is improving ({prior_avg:.0f}% → {recent_avg:.0f}% across recent sessions)."
            )

    return insights[:3]


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
        activity_rows = conn.execute(
            """SELECT bm.metric, bm.value
               FROM body_metrics bm
               JOIN (
                    SELECT metric, MAX(id) AS max_id
                    FROM body_metrics
                    WHERE recorded_date = ?
                      AND metric IN ('steps', 'active_calories')
                    GROUP BY metric
               ) latest
                 ON bm.id = latest.max_id""",
            (today,),
        ).fetchall()
        activity = {row["metric"]: row["value"] for row in activity_rows}
        insights = _build_narrative_insights(conn, date.fromisoformat(today))

        return {
            "date": today,
            "food": dict(food) if food else {},
            "activity": activity,
            "targets": targets,
            "exercise": [dict(e) for e in exercise],
            "sleep": dict(sleep) if sleep else None,
            "suggestion": dict(suggestion) if suggestion else None,
            "insights": insights,
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
