import sqlite3
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..db import get_db_dependency, row_to_dict

router = APIRouter()

UPDATABLE_COLUMNS = frozenset(
    {
        "name",
        "dose",
        "prescriber",
        "indication",
        "active",
        "started_date",
        "stopped_date",
        "notes",
    }
)


class MedicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    dose: Optional[str] = None
    prescriber: Optional[str] = None
    indication: Optional[str] = None
    active: int = Field(default=1, ge=0, le=1)
    started_date: Optional[date] = None
    stopped_date: Optional[date] = None
    notes: Optional[str] = None


class MedicationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Optional[str] = None
    dose: Optional[str] = None
    prescriber: Optional[str] = None
    indication: Optional[str] = None
    active: Optional[int] = Field(default=None, ge=0, le=1)
    started_date: Optional[date] = None
    stopped_date: Optional[date] = None
    notes: Optional[str] = None


@router.get("/")
def get_medications(
    active_only: bool = True, conn: sqlite3.Connection = Depends(get_db_dependency)
):
    if active_only:
        rows = conn.execute(
            """SELECT *
               FROM medications
               WHERE active = 1
               ORDER BY name"""
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT *
               FROM medications
               ORDER BY active DESC, name"""
        ).fetchall()
    return [row_to_dict(row) for row in rows]


@router.post("/", status_code=201)
def create_medication(
    entry: MedicationCreate, conn: sqlite3.Connection = Depends(get_db_dependency)
):
    if entry.stopped_date and not entry.started_date:
        raise HTTPException(
            status_code=422, detail="started_date is required when stopped_date is set"
        )

    cur = conn.execute(
        """INSERT INTO medications
           (
             name,
             dose,
             prescriber,
             indication,
             active,
             started_date,
             stopped_date,
             notes
           )
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            entry.name,
            entry.dose,
            entry.prescriber,
            entry.indication,
            entry.active,
            str(entry.started_date) if entry.started_date else None,
            str(entry.stopped_date) if entry.stopped_date else None,
            entry.notes,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM medications WHERE id=?",
        (cur.lastrowid,),
    ).fetchone()
    return row_to_dict(row)


@router.patch("/{medication_id}")
def update_medication(
    medication_id: int,
    patch: MedicationPatch,
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
    existing = conn.execute(
        "SELECT * FROM medications WHERE id=?",
        (medication_id,),
    ).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="Medication not found")

    payload = patch.model_dump(exclude_unset=True)
    normalized = {}
    for key, value in payload.items():
        if key in {"started_date", "stopped_date"} and value is not None:
            normalized[key] = str(value)
        else:
            normalized[key] = value

    if not normalized:
        return row_to_dict(existing)

    safe_fields = {k: v for k, v in normalized.items() if k in UPDATABLE_COLUMNS}
    if not safe_fields:
        return row_to_dict(existing)

    columns = ", ".join(f"{column}=?" for column in safe_fields)
    values = list(safe_fields.values()) + [medication_id]
    conn.execute(
        f"UPDATE medications SET {columns} WHERE id=?",
        values,
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM medications WHERE id=?",
        (medication_id,),
    ).fetchone()
    return row_to_dict(row)
