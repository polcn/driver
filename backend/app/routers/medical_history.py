from datetime import date as dt_date
from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from ..db import get_db

router = APIRouter()


class MedicalHistoryCreate(BaseModel):
    category: str
    title: str
    detail: Optional[str] = None
    date: Optional[dt_date] = None
    active: int = 1
    notes: Optional[str] = None


class MedicalHistoryPatch(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    detail: Optional[str] = None
    date: Optional[dt_date] = None
    active: Optional[int] = None
    notes: Optional[str] = None


def row_to_dict(row) -> dict:
    return dict(row)


@router.get("/")
def get_medical_history(category: Optional[str] = None, active_only: int = 0):
    conn = get_db()
    try:
        query = "SELECT * FROM medical_history"
        params = []
        clauses = []

        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if active_only:
            clauses.append("active = 1")

        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY date DESC, created_at DESC"

        rows = conn.execute(query, params).fetchall()
        return [row_to_dict(row) for row in rows]
    finally:
        conn.close()


@router.post("/", status_code=201)
def create_medical_history(entry: MedicalHistoryCreate):
    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO medical_history
               (category, title, detail, date, active, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                entry.category,
                entry.title,
                entry.detail,
                str(entry.date) if entry.date else None,
                entry.active,
                entry.notes,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM medical_history WHERE id=?",
            (cur.lastrowid,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


@router.patch("/{entry_id}")
def update_medical_history(entry_id: int, patch: MedicalHistoryPatch):
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT * FROM medical_history WHERE id=?",
            (entry_id,),
        ).fetchone()
        if existing is None:
            raise HTTPException(
                status_code=404, detail="Medical history entry not found"
            )

        payload = patch.model_dump(exclude_unset=True)
        normalized = {}
        for key, value in payload.items():
            if key == "date" and value is not None:
                normalized[key] = str(value)
            else:
                normalized[key] = value

        if not normalized:
            return row_to_dict(existing)

        columns = ", ".join(f"{column}=?" for column in normalized.keys())
        values = list(normalized.values()) + [entry_id]
        conn.execute(
            f"UPDATE medical_history SET {columns} WHERE id=?",
            values,
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM medical_history WHERE id=?",
            (entry_id,),
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


@router.delete("/{entry_id}", status_code=204)
def archive_medical_history(entry_id: int):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM medical_history WHERE id=?",
            (entry_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404, detail="Medical history entry not found"
            )
        conn.execute(
            "UPDATE medical_history SET active=0 WHERE id=?",
            (entry_id,),
        )
        conn.commit()
        return Response(status_code=204)
    finally:
        conn.close()
