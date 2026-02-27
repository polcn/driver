from datetime import date
from typing import Optional

from fastapi import APIRouter

from ..db import get_db
from ..services.suggestions import generate_daily_suggestion

router = APIRouter()


@router.post("/suggestions/generate")
def generate_suggestion(target_date: Optional[date] = None):
    target = target_date or date.today()
    conn = get_db()
    try:
        return generate_daily_suggestion(conn, target=target)
    finally:
        conn.close()
