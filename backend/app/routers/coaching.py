import sqlite3
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends

from ..db import get_db_dependency
from ..services.coaching import (
    generate_daily_digest,
    generate_weekly_digest,
    get_latest_digests,
)

router = APIRouter()


@router.post("/digests/generate-daily")
def generate_daily(
    target_date: Optional[date] = None,
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
    target = target_date or date.today()
    return generate_daily_digest(conn, target=target)


@router.post("/digests/generate-weekly")
def generate_weekly(
    ending: Optional[date] = None,
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
    end = ending or date.today()
    return generate_weekly_digest(conn, ending=end)


@router.get("/digests/latest")
def latest(
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
    return get_latest_digests(conn)
