import sqlite3
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends

from ..db import get_db_dependency
from ..services.suggestions import generate_daily_suggestion

router = APIRouter()


@router.post("/suggestions/generate")
def generate_suggestion(
    target_date: Optional[date] = None,
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
    target = target_date or date.today()
    return generate_daily_suggestion(conn, target=target)
