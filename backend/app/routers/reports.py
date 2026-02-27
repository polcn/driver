import sqlite3
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query

from ..db import get_db_dependency, row_to_dict

router = APIRouter()


def _safe_delta(latest: Optional[float], earliest: Optional[float]) -> Optional[float]:
    if latest is None or earliest is None:
        return None
    return round(float(latest) - float(earliest), 2)


@router.get("/doctor-visit")
def get_doctor_visit_report(
    ending: Optional[date] = None,
    days: int = Query(default=30, ge=7, le=365),
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
    end = ending or date.today()
    start = end - timedelta(days=days - 1)

    food_row = conn.execute(
        """SELECT
            ROUND(AVG(calories), 1) as avg_calories,
            ROUND(AVG(protein_g), 1) as avg_protein_g,
            ROUND(AVG(sodium_mg), 0) as avg_sodium_mg,
            ROUND(SUM(alcohol_calories), 0) as alcohol_calories_total
           FROM (
             SELECT recorded_date,
                    SUM(calories) as calories,
                    SUM(protein_g) as protein_g,
                    SUM(sodium_mg) as sodium_mg,
                    SUM(alcohol_calories) as alcohol_calories
             FROM food_entries
             WHERE recorded_date BETWEEN ? AND ?
               AND deleted_at IS NULL
             GROUP BY recorded_date
           )""",
        (str(start), str(end)),
    ).fetchone()

    exercise_row = conn.execute(
        """SELECT
            COUNT(*) as session_count,
            ROUND(SUM(duration_min), 1) as total_duration_min,
            ROUND(SUM(calories_burned), 1) as total_calories_burned
           FROM exercise_sessions
           WHERE recorded_date BETWEEN ? AND ?
             AND deleted_at IS NULL""",
        (str(start), str(end)),
    ).fetchone()

    sleep_row = conn.execute(
        """SELECT
            ROUND(AVG(duration_min), 1) as avg_sleep_min,
            ROUND(AVG(sleep_score), 1) as avg_sleep_score,
            ROUND(AVG(readiness_score), 1) as avg_readiness
           FROM sleep_records
           WHERE recorded_date BETWEEN ? AND ?""",
        (str(start), str(end)),
    ).fetchone()

    weight_rows = conn.execute(
        """SELECT recorded_date, value
           FROM body_metrics
           WHERE metric='weight_lbs'
             AND recorded_date BETWEEN ? AND ?
           ORDER BY recorded_date""",
        (str(start), str(end)),
    ).fetchall()
    latest_weight = weight_rows[-1]["value"] if weight_rows else None
    earliest_weight = weight_rows[0]["value"] if weight_rows else None
    weight_delta = _safe_delta(latest_weight, earliest_weight)

    waist_rows = conn.execute(
        """SELECT recorded_date, value
           FROM body_metrics
           WHERE metric='waist_in'
             AND recorded_date BETWEEN ? AND ?
           ORDER BY recorded_date""",
        (str(start), str(end)),
    ).fetchall()
    latest_waist = waist_rows[-1]["value"] if waist_rows else None
    earliest_waist = waist_rows[0]["value"] if waist_rows else None
    waist_delta = _safe_delta(latest_waist, earliest_waist)

    active_supplements = conn.execute(
        "SELECT name, dose, frequency FROM supplements WHERE active=1 ORDER BY name"
    ).fetchall()
    active_medications = conn.execute(
        "SELECT name, dose, indication FROM medications WHERE active=1 ORDER BY name"
    ).fetchall()

    latest_labs = conn.execute(
        """SELECT *
           FROM lab_results
           WHERE drawn_date = (
             SELECT MAX(drawn_date) FROM lab_results
           )
           ORDER BY panel, marker"""
    ).fetchall()
    medical_items = conn.execute(
        """SELECT category, title, detail, date, notes
           FROM medical_history
           WHERE active=1
           ORDER BY date DESC, created_at DESC
           LIMIT 20"""
    ).fetchall()

    food = row_to_dict(food_row)
    exercise = row_to_dict(exercise_row)
    sleep = row_to_dict(sleep_row)
    supplements_payload = [row_to_dict(row) for row in active_supplements]
    medications_payload = [row_to_dict(row) for row in active_medications]
    labs_payload = [row_to_dict(row) for row in latest_labs]
    history_payload = [row_to_dict(row) for row in medical_items]

    markdown_lines = [
        f"# Doctor Visit Report ({start} to {end})",
        "",
        "## Intake and Recovery",
        f"- Avg calories/day: {food.get('avg_calories') or 'n/a'}",
        f"- Avg protein/day: {food.get('avg_protein_g') or 'n/a'} g",
        f"- Avg sodium/day: {food.get('avg_sodium_mg') or 'n/a'} mg",
        f"- Alcohol calories total: {food.get('alcohol_calories_total') or 0}",
        f"- Avg sleep: {sleep.get('avg_sleep_min') or 'n/a'} min",
        f"- Avg sleep score: {sleep.get('avg_sleep_score') or 'n/a'}",
        f"- Avg readiness: {sleep.get('avg_readiness') or 'n/a'}",
        "",
        "## Training",
        f"- Sessions: {exercise.get('session_count') or 0}",
        f"- Total duration: {exercise.get('total_duration_min') or 0} min",
        f"- Total calories burned: {exercise.get('total_calories_burned') or 0}",
        "",
        "## Body Metrics",
        f"- Weight: {latest_weight if latest_weight is not None else 'n/a'}"
        + (f" ({weight_delta:+} vs period start)" if weight_delta is not None else ""),
        f"- Waist: {latest_waist if latest_waist is not None else 'n/a'}"
        + (f" ({waist_delta:+} vs period start)" if waist_delta is not None else ""),
        "",
        "## Active Medications",
    ]

    if medications_payload:
        markdown_lines.extend(
            [
                f"- {item['name']} {item.get('dose') or ''} ({item.get('indication') or 'no indication'})".strip()
                for item in medications_payload
            ]
        )
    else:
        markdown_lines.append("- none")

    markdown_lines.append("")
    markdown_lines.append("## Active Supplements")
    if supplements_payload:
        markdown_lines.extend(
            [
                f"- {item['name']} {item.get('dose') or ''} ({item.get('frequency') or 'no frequency'})".strip()
                for item in supplements_payload
            ]
        )
    else:
        markdown_lines.append("- none")

    markdown_lines.append("")
    markdown_lines.append("## Latest Labs")
    if labs_payload:
        for row in labs_payload:
            flag = f" ({row['flag']})" if row.get("flag") else ""
            markdown_lines.append(
                f"- {row['panel']}: {row['marker']} {row['value']} {row['unit']}{flag}"
            )
    else:
        markdown_lines.append("- no labs available")

    markdown_lines.append("")
    markdown_lines.append("## Active Medical History Notes")
    if history_payload:
        for row in history_payload:
            when = f" [{row['date']}]" if row.get("date") else ""
            detail = f": {row['detail']}" if row.get("detail") else ""
            markdown_lines.append(f"- {row['category']} - {row['title']}{when}{detail}")
    else:
        markdown_lines.append("- none")

    return {
        "start": str(start),
        "end": str(end),
        "food": food,
        "exercise": exercise,
        "sleep": sleep,
        "body_metrics": {
            "latest_weight": latest_weight,
            "weight_delta": weight_delta,
            "latest_waist": latest_waist,
            "waist_delta": waist_delta,
        },
        "active_medications": medications_payload,
        "active_supplements": supplements_payload,
        "latest_labs": labs_payload,
        "medical_history": history_payload,
        "report_markdown": "\n".join(markdown_lines),
    }
