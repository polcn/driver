import sqlite3
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..db import get_db_dependency, row_to_dict

router = APIRouter()

UPDATABLE_COLUMNS = frozenset(
    {
        "meal_type",
        "name",
        "calories",
        "protein_g",
        "carbs_g",
        "fat_g",
        "fiber_g",
        "sodium_mg",
        "alcohol_g",
        "alcohol_calories",
        "alcohol_type",
        "photo_url",
        "servings",
        "is_estimated",
        "notes",
    }
)


class FoodEntryCreate(BaseModel):
    recorded_date: date
    meal_type: str
    name: str
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    alcohol_g: Optional[float] = None
    alcohol_calories: Optional[float] = None
    alcohol_type: Optional[str] = None
    photo_url: Optional[str] = None
    servings: float = 1.0
    is_estimated: bool = False
    source: str = "manual"
    notes: Optional[str] = None


class FoodEntryUpdate(BaseModel):
    meal_type: Optional[str] = None
    name: Optional[str] = None
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    alcohol_g: Optional[float] = None
    alcohol_calories: Optional[float] = None
    alcohol_type: Optional[str] = None
    photo_url: Optional[str] = None
    servings: Optional[float] = None
    is_estimated: Optional[bool] = None
    notes: Optional[str] = None


class PhotoFoodCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    recorded_date: date
    meal_type: str = "meal"
    description: str = Field(min_length=1, max_length=300)
    photo_url: str = Field(min_length=1, max_length=800)
    servings: float = Field(default=1.0, gt=0, le=10)
    source: str = "agent"


def _estimate_from_description(description: str, servings: float) -> dict:
    text = description.lower()
    base = {
        "name": description,
        "calories": 450.0,
        "protein_g": 28.0,
        "carbs_g": 35.0,
        "fat_g": 18.0,
        "fiber_g": 5.0,
        "sodium_mg": 700.0,
        "alcohol_g": 0.0,
        "alcohol_calories": 0.0,
        "alcohol_type": None,
    }

    if "shake" in text or "protein" in text:
        base.update(
            {
                "calories": 260.0,
                "protein_g": 35.0,
                "carbs_g": 12.0,
                "fat_g": 6.0,
                "fiber_g": 2.0,
                "sodium_mg": 220.0,
            }
        )
    elif "salad" in text:
        base.update(
            {
                "calories": 320.0,
                "protein_g": 18.0,
                "carbs_g": 20.0,
                "fat_g": 16.0,
                "fiber_g": 7.0,
                "sodium_mg": 460.0,
            }
        )
    elif "beer" in text:
        base.update(
            {
                "calories": 150.0,
                "protein_g": 1.5,
                "carbs_g": 13.0,
                "fat_g": 0.0,
                "fiber_g": 0.0,
                "sodium_mg": 15.0,
                "alcohol_g": 14.0,
                "alcohol_calories": 98.0,
                "alcohol_type": "beer",
            }
        )
    elif "wine" in text:
        base.update(
            {
                "calories": 125.0,
                "protein_g": 0.2,
                "carbs_g": 4.0,
                "fat_g": 0.0,
                "fiber_g": 0.0,
                "sodium_mg": 10.0,
                "alcohol_g": 14.0,
                "alcohol_calories": 98.0,
                "alcohol_type": "wine",
            }
        )

    factor = float(servings)
    return {
        key: round(value * factor, 2) if isinstance(value, float) else value
        for key, value in base.items()
    }


@router.post("/", status_code=201)
def create_food_entry(
    entry: FoodEntryCreate, conn: sqlite3.Connection = Depends(get_db_dependency)
):
    cur = conn.execute(
        """INSERT INTO food_entries
           (recorded_date, meal_type, name, calories, protein_g, carbs_g, fat_g,
            fiber_g, sodium_mg, alcohol_g, alcohol_calories, alcohol_type,
            photo_url, servings, is_estimated, source, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            str(entry.recorded_date),
            entry.meal_type,
            entry.name,
            entry.calories,
            entry.protein_g,
            entry.carbs_g,
            entry.fat_g,
            entry.fiber_g,
            entry.sodium_mg,
            entry.alcohol_g,
            entry.alcohol_calories,
            entry.alcohol_type,
            entry.photo_url,
            entry.servings,
            int(entry.is_estimated),
            entry.source,
            entry.notes,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM food_entries WHERE id=?",
        (cur.lastrowid,),
    ).fetchone()
    return row_to_dict(row)


@router.post("/from-photo", status_code=201)
def create_photo_food_entry(
    entry: PhotoFoodCreate, conn: sqlite3.Connection = Depends(get_db_dependency)
):
    estimated = _estimate_from_description(entry.description, entry.servings)
    notes = (
        f"Estimated from photo input. Description: {entry.description}. "
        "Review and patch if needed."
    )

    cur = conn.execute(
        """INSERT INTO food_entries
           (recorded_date, meal_type, name, calories, protein_g, carbs_g, fat_g,
            fiber_g, sodium_mg, alcohol_g, alcohol_calories, alcohol_type,
            photo_url, servings, is_estimated, source, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            str(entry.recorded_date),
            entry.meal_type,
            estimated["name"],
            estimated["calories"],
            estimated["protein_g"],
            estimated["carbs_g"],
            estimated["fat_g"],
            estimated["fiber_g"],
            estimated["sodium_mg"],
            estimated["alcohol_g"],
            estimated["alcohol_calories"],
            estimated["alcohol_type"],
            entry.photo_url,
            entry.servings,
            1,
            entry.source,
            notes,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM food_entries WHERE id=?",
        (cur.lastrowid,),
    ).fetchone()
    return row_to_dict(row)


@router.get("/")
def get_food_entries(
    date: Optional[str] = None, conn: sqlite3.Connection = Depends(get_db_dependency)
):
    if date:
        rows = conn.execute(
            """SELECT *
               FROM food_entries
               WHERE recorded_date=?
                 AND deleted_at IS NULL
               ORDER BY created_at""",
            (date,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT *
               FROM food_entries
               WHERE deleted_at IS NULL
               ORDER BY recorded_date DESC, created_at DESC
               LIMIT 100"""
        ).fetchall()
    return [row_to_dict(r) for r in rows]


@router.get("/summary")
def get_daily_summary(date: str, conn: sqlite3.Connection = Depends(get_db_dependency)):
    totals = conn.execute(
        """SELECT
            COUNT(*) as entry_count,
            ROUND(SUM(calories), 1) as calories,
            ROUND(SUM(protein_g), 1) as protein_g,
            ROUND(SUM(carbs_g), 1) as carbs_g,
            ROUND(SUM(fat_g), 1) as fat_g,
            ROUND(SUM(fiber_g), 1) as fiber_g,
            ROUND(SUM(sodium_mg), 0) as sodium_mg,
            ROUND(SUM(alcohol_calories), 0) as alcohol_calories
           FROM food_entries
           WHERE recorded_date=? AND deleted_at IS NULL""",
        (date,),
    ).fetchone()

    targets = conn.execute(
        """SELECT t1.metric, t1.value FROM targets t1
           WHERE t1.effective_date = (
               SELECT MAX(t2.effective_date) FROM targets t2
               WHERE t2.metric = t1.metric AND t2.effective_date <= ?
           )""",
        (date,),
    ).fetchall()
    target_map = {r["metric"]: r["value"] for r in targets}

    result = dict(totals)
    result["date"] = date
    result["targets"] = {
        "calories": target_map.get("calories"),
        "protein_g": target_map.get("protein_g"),
        "sodium_mg": target_map.get("sodium_mg"),
    }
    return result


@router.get("/summary/week")
def get_weekly_summary(
    ending: str, conn: sqlite3.Connection = Depends(get_db_dependency)
):
    rows = conn.execute(
        """SELECT
            recorded_date,
            COUNT(*) as entry_count,
            ROUND(SUM(calories), 1) as calories,
            ROUND(SUM(protein_g), 1) as protein_g,
            ROUND(SUM(carbs_g), 1) as carbs_g,
            ROUND(SUM(fat_g), 1) as fat_g,
            ROUND(SUM(fiber_g), 1) as fiber_g,
            ROUND(SUM(sodium_mg), 0) as sodium_mg,
            ROUND(SUM(alcohol_calories), 0) as alcohol_calories
           FROM food_entries
           WHERE recorded_date BETWEEN date(?, '-6 days') AND ?
             AND deleted_at IS NULL
           GROUP BY recorded_date
           ORDER BY recorded_date""",
        (ending, ending),
    ).fetchall()

    return {
        "ending": ending,
        "days": [row_to_dict(row) for row in rows],
    }


@router.patch("/{entry_id}")
def update_food_entry(
    entry_id: int,
    update: FoodEntryUpdate,
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
    row = conn.execute(
        "SELECT * FROM food_entries WHERE id=? AND deleted_at IS NULL", (entry_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Entry not found")

    fields = update.model_dump(exclude_unset=True)
    if not fields:
        return row_to_dict(row)

    safe_fields = {k: v for k, v in fields.items() if k in UPDATABLE_COLUMNS}
    if not safe_fields:
        return row_to_dict(row)

    set_clause = ", ".join(f"{k}=?" for k in safe_fields)
    values = list(safe_fields.values()) + [entry_id]
    conn.execute(f"UPDATE food_entries SET {set_clause} WHERE id=?", values)
    conn.commit()
    row = conn.execute(
        "SELECT * FROM food_entries WHERE id=?",
        (entry_id,),
    ).fetchone()
    return row_to_dict(row)


@router.delete("/{entry_id}", status_code=204)
def delete_food_entry(
    entry_id: int, conn: sqlite3.Connection = Depends(get_db_dependency)
):
    row = conn.execute(
        "SELECT id FROM food_entries WHERE id=? AND deleted_at IS NULL", (entry_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Entry not found")
    conn.execute(
        "UPDATE food_entries SET deleted_at=datetime('now') WHERE id=?", (entry_id,)
    )
    conn.commit()
