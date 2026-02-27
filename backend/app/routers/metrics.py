import sqlite3
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..db import get_db_dependency, row_to_dict

router = APIRouter()


class BodyMetricCreate(BaseModel):
    recorded_date: date
    metric: str
    value: float
    source: str = "manual"
    notes: Optional[str] = None


@router.post("/", status_code=201)
def create_body_metric(
    entry: BodyMetricCreate, conn: sqlite3.Connection = Depends(get_db_dependency)
):
    cur = conn.execute(
        """INSERT INTO body_metrics
           (recorded_date, metric, value, source, notes)
           VALUES (?, ?, ?, ?, ?)""",
        (
            str(entry.recorded_date),
            entry.metric,
            entry.value,
            entry.source,
            entry.notes,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM body_metrics WHERE id=?",
        (cur.lastrowid,),
    ).fetchone()
    return row_to_dict(row)


@router.get("/")
def get_body_metrics(
    metric: str,
    days: int = 30,
    ending: Optional[date] = None,
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
    end_date = ending or date.today()
    rows = conn.execute(
        """SELECT recorded_date, metric, value, source, notes, created_at
           FROM body_metrics
           WHERE metric = ?
             AND recorded_date BETWEEN date(?, ?) AND ?
           ORDER BY recorded_date""",
        (metric, str(end_date), f"-{days - 1} days", str(end_date)),
    ).fetchall()
    return [row_to_dict(row) for row in rows]
