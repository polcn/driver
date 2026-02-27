import sqlite3
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import get_db_dependency, row_to_dict

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


class ExerciseSetCreate(BaseModel):
    exercise_name: str
    set_number: int
    weight_lbs: Optional[float] = None
    reps: Optional[int] = None
    notes: Optional[str] = None


EXERCISE_SESSION_SELECT = """SELECT
                               id,
                               recorded_date,
                               session_type,
                               name,
                               duration_min,
                               calories_burned,
                               avg_heart_rate,
                               max_heart_rate,
                               source,
                               notes,
                               created_at,
                               deleted_at
                             FROM exercise_sessions"""


@router.post("/sessions", status_code=201)
def create_exercise_session(
    entry: ExerciseSessionCreate, conn: sqlite3.Connection = Depends(get_db_dependency)
):
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
        f"{EXERCISE_SESSION_SELECT} WHERE id=?",
        (cur.lastrowid,),
    ).fetchone()
    return row_to_dict(row)


@router.get("/sessions")
def get_exercise_sessions(
    date: Optional[date] = None, conn: sqlite3.Connection = Depends(get_db_dependency)
):
    if date is None:
        rows = conn.execute(
            f"""{EXERCISE_SESSION_SELECT}
                WHERE deleted_at IS NULL
                ORDER BY recorded_date DESC, created_at DESC
                LIMIT 100"""
        ).fetchall()
    else:
        rows = conn.execute(
            f"""{EXERCISE_SESSION_SELECT}
                WHERE recorded_date = ?
                  AND deleted_at IS NULL
                ORDER BY created_at""",
            (str(date),),
        ).fetchall()

    return [row_to_dict(row) for row in rows]


@router.post("/sessions/{session_id}/sets", status_code=201)
def create_exercise_set(
    session_id: int,
    entry: ExerciseSetCreate,
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
    session = conn.execute(
        """SELECT id
           FROM exercise_sessions
           WHERE id = ?
             AND deleted_at IS NULL""",
        (session_id,),
    ).fetchone()
    if session is None:
        raise HTTPException(status_code=404, detail="Exercise session not found")

    cur = conn.execute(
        """INSERT INTO exercise_sets
           (
             session_id,
             exercise_name,
             set_number,
             weight_lbs,
             reps,
             notes
           )
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            entry.exercise_name,
            entry.set_number,
            entry.weight_lbs,
            entry.reps,
            entry.notes,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM exercise_sets WHERE id=?",
        (cur.lastrowid,),
    ).fetchone()
    return row_to_dict(row)


@router.get("/sessions/{session_id}/sets")
def get_exercise_sets(
    session_id: int, conn: sqlite3.Connection = Depends(get_db_dependency)
):
    session = conn.execute(
        """SELECT id
           FROM exercise_sessions
           WHERE id = ?
             AND deleted_at IS NULL""",
        (session_id,),
    ).fetchone()
    if session is None:
        raise HTTPException(status_code=404, detail="Exercise session not found")

    rows = conn.execute(
        """SELECT *
           FROM exercise_sets
           WHERE session_id = ?
           ORDER BY exercise_name, set_number, id""",
        (session_id,),
    ).fetchall()
    return [row_to_dict(row) for row in rows]
