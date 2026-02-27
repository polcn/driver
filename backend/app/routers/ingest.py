from datetime import datetime
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..db import get_db

router = APIRouter()


class IngestResponse(BaseModel):
    status: str
    processed: dict[str, int]


def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def extract_recorded_date(value: Optional[str]) -> Optional[str]:
    timestamp = parse_timestamp(value)
    return timestamp.date().isoformat() if timestamp else None


def classify_session_type(name: Optional[str]) -> str:
    label = (name or "").lower()
    if any(token in label for token in ("strength", "weight")):
        return "strength"
    if any(token in label for token in ("running", "walk", "hike")):
        return "cardio"
    if any(token in label for token in ("cycling", "bike")):
        return "cardio"
    if any(
        token in label for token in ("stair", "elliptical", "rowing", "hiit", "cardio")
    ):
        return "cardio"
    if any(token in label for token in ("yoga", "stretch", "pilates")):
        return "flexibility"
    return "strength"


def hr_zone_for_bpm(bpm: float) -> int:
    if bpm < 98:
        return 1
    if bpm < 115:
        return 2
    if bpm < 131:
        return 3
    if bpm < 148:
        return 4
    return 5


def compute_hr_zone_minutes(
    heart_rate_data: list[dict], total_duration_min: Optional[float]
) -> dict[int, float]:
    if not heart_rate_data:
        return {}

    points: list[tuple[datetime, float]] = []
    for point in heart_rate_data:
        qty = point.get("qty")
        if qty is None:
            continue
        timestamp = parse_timestamp(point.get("date"))
        if timestamp is None:
            continue
        points.append((timestamp, float(qty)))

    if not points:
        return {}

    points.sort(key=lambda item: item[0])
    session_minutes = max(float(total_duration_min or 0), 0.0)
    if session_minutes == 0:
        if len(points) < 2:
            return {}
        session_minutes = max(
            0.0, (points[-1][0] - points[0][0]).total_seconds() / 60.0
        )
        if session_minutes == 0:
            return {}

    zone_minutes: dict[int, float] = {}
    assigned_minutes = 0.0

    if len(points) == 1:
        zone = hr_zone_for_bpm(points[0][1])
        return {zone: session_minutes}

    for idx in range(1, len(points)):
        previous_time, previous_bpm = points[idx - 1]
        current_time, current_bpm = points[idx]
        delta_minutes = (current_time - previous_time).total_seconds() / 60.0
        if delta_minutes <= 0:
            continue
        interpolated_bpm = (previous_bpm + current_bpm) / 2.0
        zone = hr_zone_for_bpm(interpolated_bpm)
        zone_minutes[zone] = zone_minutes.get(zone, 0.0) + delta_minutes
        assigned_minutes += delta_minutes

    if assigned_minutes < session_minutes:
        trailing_zone = hr_zone_for_bpm(points[-1][1])
        zone_minutes[trailing_zone] = zone_minutes.get(trailing_zone, 0.0) + (
            session_minutes - assigned_minutes
        )

    return zone_minutes


@router.post("/apple-health", response_model=IngestResponse)
def ingest_apple_health(payload: dict):
    metric_name_map = {
        "resting_heart_rate": "resting_hr",
        "heart_rate_variability": "hrv",
        "weight_body_mass": "weight_lbs",
        "active_energy": "active_calories",
        "step_count": "steps",
        "basal_energy_burned": "basal_calories",
    }

    data = payload.get("data") or {}
    metrics = data.get("metrics") or []
    workouts = data.get("workouts") or []

    processed_metrics = 0
    processed_workouts = 0
    skipped = 0

    conn = get_db()
    try:
        for metric in metrics:
            metric_name = metric.get("name")
            points = metric.get("data") or []
            if not metric_name or not isinstance(points, list):
                skipped += 1
                continue

            if metric_name == "heart_rate":
                skipped += len(points)
                continue

            if metric_name == "sleep_analysis":
                for point in points:
                    recorded_date = extract_recorded_date(point.get("date"))
                    qty = point.get("qty")
                    if recorded_date is None or qty is None:
                        skipped += 1
                        continue
                    conn.execute(
                        """INSERT OR IGNORE INTO sleep_records
                           (recorded_date, duration_min, source)
                           VALUES (?, ?, 'apple_health')""",
                        (recorded_date, int(round(float(qty) * 60))),
                    )
                    processed_metrics += 1
                continue

            target_metric = metric_name_map.get(metric_name, metric_name)
            for point in points:
                recorded_date = extract_recorded_date(point.get("date"))
                qty = point.get("qty")
                if recorded_date is None or qty is None:
                    skipped += 1
                    continue
                existing_row = conn.execute(
                    """SELECT id
                       FROM body_metrics
                       WHERE recorded_date=? AND metric=? AND source='apple_health'
                       ORDER BY id DESC
                       LIMIT 1""",
                    (recorded_date, target_metric),
                ).fetchone()
                if existing_row:
                    conn.execute(
                        """UPDATE body_metrics
                           SET value=?, notes=NULL
                           WHERE id=?""",
                        (float(qty), existing_row["id"]),
                    )
                else:
                    conn.execute(
                        """INSERT INTO body_metrics (recorded_date, metric, value, source)
                           VALUES (?, ?, ?, 'apple_health')""",
                        (recorded_date, target_metric, float(qty)),
                    )
                processed_metrics += 1

        for workout in workouts:
            start_value = workout.get("start")
            recorded_date = extract_recorded_date(start_value)
            if recorded_date is None:
                skipped += 1
                continue

            external_id = (
                f"apple_health:{start_value}"
                if start_value
                else f"apple_health:{recorded_date}:{workout.get('name') or 'workout'}"
            )
            duration_seconds = workout.get("duration")
            duration_min = (
                int(round(float(duration_seconds) / 60.0))
                if duration_seconds is not None
                else None
            )
            if duration_min is None:
                start_ts = parse_timestamp(start_value)
                end_ts = parse_timestamp(workout.get("end"))
                if start_ts and end_ts:
                    duration_min = int(
                        round(max(0.0, (end_ts - start_ts).total_seconds() / 60.0))
                    )
            active_energy = workout.get("activeEnergy") or {}
            heart_rates = workout.get("heartRateData") or []
            heart_values = [
                float(p["qty"]) for p in heart_rates if p.get("qty") is not None
            ]
            avg_heart_rate = (
                int(round(sum(heart_values) / len(heart_values)))
                if heart_values
                else None
            )
            max_heart_rate = int(round(max(heart_values))) if heart_values else None

            existing_session = conn.execute(
                """SELECT id
                   FROM exercise_sessions
                   WHERE source='apple_health' AND external_id=?
                   ORDER BY id DESC
                   LIMIT 1""",
                (external_id,),
            ).fetchone()
            if existing_session:
                conn.execute(
                    """UPDATE exercise_sessions
                       SET recorded_date=?,
                           session_type=?,
                           name=?,
                           duration_min=?,
                           calories_burned=?,
                           avg_heart_rate=?,
                           max_heart_rate=?,
                           deleted_at=NULL
                       WHERE id=?""",
                    (
                        recorded_date,
                        classify_session_type(workout.get("name")),
                        workout.get("name"),
                        duration_min,
                        active_energy.get("qty"),
                        avg_heart_rate,
                        max_heart_rate,
                        existing_session["id"],
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO exercise_sessions
                       (
                         recorded_date,
                         session_type,
                         name,
                         external_id,
                         duration_min,
                         calories_burned,
                         avg_heart_rate,
                         max_heart_rate,
                         source
                       )
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'apple_health')""",
                    (
                        recorded_date,
                        classify_session_type(workout.get("name")),
                        workout.get("name"),
                        external_id,
                        duration_min,
                        active_energy.get("qty"),
                        avg_heart_rate,
                        max_heart_rate,
                    ),
                )

            session = conn.execute(
                """SELECT id
                   FROM exercise_sessions
                   WHERE source='apple_health' AND external_id=?
                   ORDER BY id DESC
                   LIMIT 1""",
                (external_id,),
            ).fetchone()

            if session is None:
                skipped += 1
                continue

            session_id = session["id"]
            conn.execute(
                "DELETE FROM exercise_hr_zones WHERE session_id=?",
                (session_id,),
            )

            zone_minutes = compute_hr_zone_minutes(heart_rates, duration_min)
            total_minutes = float(duration_min or 0)
            if total_minutes <= 0 and zone_minutes:
                total_minutes = sum(zone_minutes.values())

            if total_minutes > 0:
                for zone, minutes in sorted(zone_minutes.items()):
                    conn.execute(
                        """INSERT INTO exercise_hr_zones (session_id, zone, minutes, pct_of_session)
                           VALUES (?, ?, ?, ?)""",
                        (
                            session_id,
                            zone,
                            round(minutes, 3),
                            round((minutes / total_minutes) * 100.0, 3),
                        ),
                    )

            processed_workouts += 1

        conn.commit()
        return {
            "status": "ok",
            "processed": {
                "metrics": processed_metrics,
                "workouts": processed_workouts,
                "skipped": skipped,
            },
        }
    finally:
        conn.close()


@router.post("/oura")
def ingest_oura_stub():
    return {"status": "coming_soon"}
