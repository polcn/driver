from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db

router = APIRouter()


class LabResultCreate(BaseModel):
    drawn_date: date
    panel: str
    marker: str
    value: float
    unit: str
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None
    flag: Optional[str] = None
    notes: Optional[str] = None


def row_to_dict(row) -> dict:
    return dict(row)


@router.post("/", status_code=201)
def create_lab_result(entry: LabResultCreate):
    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO lab_results
               (
                 drawn_date,
                 panel,
                 marker,
                 value,
                 unit,
                 reference_low,
                 reference_high,
                 flag,
                 notes
               )
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(entry.drawn_date),
                entry.panel,
                entry.marker,
                entry.value,
                entry.unit,
                entry.reference_low,
                entry.reference_high,
                entry.flag,
                entry.notes,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM lab_results WHERE id=?",
            (cur.lastrowid,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


@router.get("/")
def get_lab_results(marker: Optional[str] = None, drawn_date: Optional[date] = None):
    conn = get_db()
    try:
        if marker is not None:
            rows = conn.execute(
                """SELECT *
                   FROM lab_results
                   WHERE marker = ?
                   ORDER BY drawn_date DESC, created_at DESC""",
                (marker,),
            ).fetchall()
            return [row_to_dict(row) for row in rows]

        if drawn_date is not None:
            rows = conn.execute(
                """SELECT *
                   FROM lab_results
                   WHERE drawn_date = ?
                   ORDER BY panel, marker""",
                (str(drawn_date),),
            ).fetchall()
            return [row_to_dict(row) for row in rows]

        rows = conn.execute(
            """SELECT *
               FROM lab_results
               ORDER BY drawn_date DESC, panel, marker
               LIMIT 200"""
        ).fetchall()
        return [row_to_dict(row) for row in rows]
    finally:
        conn.close()


@router.patch("/{result_id}")
def update_lab_result(result_id: int, entry: LabResultCreate):
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM lab_results WHERE id=?",
            (result_id,),
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Lab result not found")

        conn.execute(
            """UPDATE lab_results
               SET drawn_date=?,
                   panel=?,
                   marker=?,
                   value=?,
                   unit=?,
                   reference_low=?,
                   reference_high=?,
                   flag=?,
                   notes=?
               WHERE id=?""",
            (
                str(entry.drawn_date),
                entry.panel,
                entry.marker,
                entry.value,
                entry.unit,
                entry.reference_low,
                entry.reference_high,
                entry.flag,
                entry.notes,
                result_id,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM lab_results WHERE id=?",
            (result_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()
