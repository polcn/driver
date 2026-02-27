from datetime import date
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..db import get_db

router = APIRouter()


class SleepRecordCreate(BaseModel):
    recorded_date: date
    bedtime: Optional[str] = None
    wake_time: Optional[str] = None
    duration_min: Optional[int] = None
    deep_min: Optional[int] = None
    rem_min: Optional[int] = None
    core_min: Optional[int] = None
    awake_min: Optional[int] = None
    hrv: Optional[float] = None
    resting_hr: Optional[int] = None
    readiness_score: Optional[int] = None
    sleep_score: Optional[int] = None
    cpap_used: Optional[int] = None
    cpap_ahi: Optional[float] = None
    cpap_hours: Optional[float] = None
    cpap_leak_95: Optional[float] = None
    cpap_pressure_avg: Optional[float] = None
    source: str = "manual"


def row_to_dict(row) -> dict:
    return dict(row)


@router.post("/", status_code=201)
def create_sleep_record(entry: SleepRecordCreate):
    conn = get_db()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO sleep_records
               (
                 recorded_date,
                 bedtime,
                 wake_time,
                 duration_min,
                 deep_min,
                 rem_min,
                 core_min,
                 awake_min,
                 hrv,
                 resting_hr,
                 readiness_score,
                 sleep_score,
                 cpap_used,
                 cpap_ahi,
                 cpap_hours,
                 cpap_leak_95,
                 cpap_pressure_avg,
                 source
               )
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(entry.recorded_date),
                entry.bedtime,
                entry.wake_time,
                entry.duration_min,
                entry.deep_min,
                entry.rem_min,
                entry.core_min,
                entry.awake_min,
                entry.hrv,
                entry.resting_hr,
                entry.readiness_score,
                entry.sleep_score,
                entry.cpap_used,
                entry.cpap_ahi,
                entry.cpap_hours,
                entry.cpap_leak_95,
                entry.cpap_pressure_avg,
                entry.source,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM sleep_records WHERE recorded_date=?",
            (str(entry.recorded_date),),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


@router.get("/")
def get_sleep_records(
    recorded_date: Optional[date] = None, days: int = 14, ending: Optional[date] = None
):
    conn = get_db()
    try:
        if recorded_date is not None:
            row = conn.execute(
                """SELECT *
                   FROM sleep_records
                   WHERE recorded_date = ?
                   ORDER BY created_at DESC
                   LIMIT 1""",
                (str(recorded_date),),
            ).fetchone()
            return row_to_dict(row) if row else None

        end_date = ending or date.today()
        rows = conn.execute(
            """SELECT *
               FROM sleep_records
               WHERE recorded_date BETWEEN date(?, ?) AND ?
               ORDER BY recorded_date DESC""",
            (str(end_date), f"-{days - 1} days", str(end_date)),
        ).fetchall()
        return [row_to_dict(row) for row in rows]
    finally:
        conn.close()
