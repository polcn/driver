from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_db

router = APIRouter()


class SupplementCreate(BaseModel):
    name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    active: int = 1
    started_date: Optional[date] = None
    stopped_date: Optional[date] = None
    notes: Optional[str] = None


class SupplementPatch(BaseModel):
    name: Optional[str] = None
    dose: Optional[str] = None
    frequency: Optional[str] = None
    active: Optional[int] = None
    started_date: Optional[date] = None
    stopped_date: Optional[date] = None
    notes: Optional[str] = None


def row_to_dict(row) -> dict:
    return dict(row)


@router.get("/")
def get_supplements(active_only: int = 1):
    conn = get_db()
    try:
        if active_only:
            rows = conn.execute(
                """SELECT *
                   FROM supplements
                   WHERE active = 1
                   ORDER BY name"""
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT *
                   FROM supplements
                   ORDER BY active DESC, name"""
            ).fetchall()
        return [row_to_dict(row) for row in rows]
    finally:
        conn.close()


@router.post("/", status_code=201)
def create_supplement(entry: SupplementCreate):
    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO supplements
               (
                 name,
                 dose,
                 frequency,
                 active,
                 started_date,
                 stopped_date,
                 notes
               )
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.name,
                entry.dose,
                entry.frequency,
                entry.active,
                str(entry.started_date) if entry.started_date else None,
                str(entry.stopped_date) if entry.stopped_date else None,
                entry.notes,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM supplements WHERE id=?",
            (cur.lastrowid,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


@router.patch("/{supplement_id}")
def update_supplement(supplement_id: int, patch: SupplementPatch):
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT * FROM supplements WHERE id=?",
            (supplement_id,),
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Supplement not found")

        payload = patch.model_dump(exclude_unset=True)
        normalized = {}
        for key, value in payload.items():
            if key in {"started_date", "stopped_date"} and value is not None:
                normalized[key] = str(value)
            else:
                normalized[key] = value

        if not normalized:
            return row_to_dict(existing)

        columns = ", ".join(f"{column}=?" for column in normalized.keys())
        values = list(normalized.values()) + [supplement_id]
        conn.execute(
            f"UPDATE supplements SET {columns} WHERE id=?",
            values,
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM supplements WHERE id=?",
            (supplement_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()
