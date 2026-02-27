import sqlite3
from datetime import date as dt_date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from ..db import get_db_dependency, row_to_dict

router = APIRouter()


class MedicalHistoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    category: Literal[
        "condition",
        "surgery",
        "allergy",
        "provider",
        "appointment",
        "vaccination",
    ]
    title: str = Field(min_length=1, max_length=200)
    detail: Optional[str] = None
    date: Optional[dt_date] = None
    active: int = Field(default=1, ge=0, le=1)
    notes: Optional[str] = None


class MedicalHistoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    category: Optional[
        Literal[
            "condition",
            "surgery",
            "allergy",
            "provider",
            "appointment",
            "vaccination",
        ]
    ] = None
    title: Optional[str] = None
    detail: Optional[str] = None
    date: Optional[dt_date] = None
    active: Optional[int] = Field(default=None, ge=0, le=1)
    notes: Optional[str] = None


@router.get("/")
def get_medical_history(
    category: Optional[
        Literal[
            "condition",
            "surgery",
            "allergy",
            "provider",
            "appointment",
            "vaccination",
        ]
    ] = Query(default=None),
    active_only: bool = False,
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
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


@router.post("/", status_code=201)
def create_medical_history(
    entry: MedicalHistoryCreate, conn: sqlite3.Connection = Depends(get_db_dependency)
):
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


@router.patch("/{entry_id}")
def update_medical_history(
    entry_id: int,
    patch: MedicalHistoryPatch,
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
    existing = conn.execute(
        "SELECT * FROM medical_history WHERE id=?",
        (entry_id,),
    ).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="Medical history entry not found")

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


@router.delete("/{entry_id}", status_code=204)
def archive_medical_history(
    entry_id: int, conn: sqlite3.Connection = Depends(get_db_dependency)
):
    row = conn.execute(
        "SELECT id FROM medical_history WHERE id=?",
        (entry_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Medical history entry not found")
    conn.execute(
        "UPDATE medical_history SET active=0 WHERE id=?",
        (entry_id,),
    )
    conn.commit()
    return Response(status_code=204)
