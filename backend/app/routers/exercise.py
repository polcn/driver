from datetime import date
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..db import get_db

router = APIRouter()


class ExerciseSessionCreate(BaseModel):
    recorded_date: date
    session_type: str
    name: Optional[str] = None
    duration_min: Optional[int] = None
    calories_burned: Optional[float] = None
    avg_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None
    source: str = "manual"
    notes: Optional[str] = None


def row_to_dict(row) -> dict:
    return dict(row)


@router.post("/sessions", status_code=201)
def create_exercise_session(entry: ExerciseSessionCreate):
    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO exercise_sessions
               (
                 recorded_date,
                 session_type,
                 name,
                 duration_min,
                 calories_burned,
                 avg_heart_rate,
                 max_heart_rate,
                 source,
                 notes
               )
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(entry.recorded_date),
                entry.session_type,
                entry.name,
                entry.duration_min,
                entry.calories_burned,
                entry.avg_heart_rate,
                entry.max_heart_rate,
                entry.source,
                entry.notes,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM exercise_sessions WHERE id=?",
            (cur.lastrowid,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


@router.get("/sessions")
def get_exercise_sessions(date: Optional[date] = None):
    conn = get_db()
    try:
        if date is None:
            rows = conn.execute(
                """SELECT *
                   FROM exercise_sessions
                   WHERE deleted_at IS NULL
                   ORDER BY recorded_date DESC, created_at DESC
                   LIMIT 100"""
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT *
                   FROM exercise_sessions
                   WHERE recorded_date = ?
                     AND deleted_at IS NULL
                   ORDER BY created_at""",
                (str(date),),
            ).fetchall()

        return [row_to_dict(row) for row in rows]
    finally:
        conn.close()
