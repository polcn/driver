import sqlite3
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..db import get_db_dependency, row_to_dict

router = APIRouter()

UPDATABLE_COLUMNS = frozenset(
    {
        "name",
        "metric",
        "goal_type",
        "target_value",
        "direction",
        "start_date",
        "target_date",
        "active",
        "notes",
    }
)


class GoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=160)
    metric: str = Field(min_length=1, max_length=80)
    goal_type: Literal["target", "directional"]
    target_value: Optional[float] = None
    direction: Optional[Literal["up", "down"]] = None
    start_date: date
    target_date: Optional[date] = None
    active: int = Field(default=1, ge=0, le=1)
    notes: Optional[str] = None


class GoalPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    metric: Optional[str] = Field(default=None, min_length=1, max_length=80)
    goal_type: Optional[Literal["target", "directional"]] = None
    target_value: Optional[float] = None
    direction: Optional[Literal["up", "down"]] = None
    start_date: Optional[date] = None
    target_date: Optional[date] = None
    active: Optional[int] = Field(default=None, ge=0, le=1)
    notes: Optional[str] = None


class GoalPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    plan: str = Field(min_length=1)


def _validate_goal_payload(
    *,
    goal_type: str,
    target_value: Optional[float],
    direction: Optional[str],
):
    if goal_type == "target" and target_value is None:
        raise HTTPException(
            status_code=422, detail="target_value is required for target goals"
        )
    if goal_type == "directional" and direction is None:
        raise HTTPException(
            status_code=422, detail="direction is required for directional goals"
        )


def _build_plan(goal: dict, baseline_value: Optional[float]) -> str:
    horizon = goal.get("target_date") or "open-ended"
    if goal["goal_type"] == "target":
        target_line = (
            f"Target `{goal['metric']}` to `{goal['target_value']}` by `{horizon}`."
        )
    else:
        target_line = f"Drive `{goal['metric']}` trend `{goal['direction']}` with weekly check-ins."

    baseline_text = (
        f"Current baseline for `{goal['metric']}` is `{baseline_value}`."
        if baseline_value is not None
        else f"Baseline for `{goal['metric']}` not available yet; log data for 7 days first."
    )

    return "\n".join(
        [
            f"### Goal plan: {goal['name']}",
            "",
            target_line,
            baseline_text,
            "1. Define weekly action targets and track adherence daily.",
            "2. Review trend weekly; adjust calories, training, or recovery load if off track.",
            "3. Keep one measurable behavior metric in the dashboard and agent summary.",
        ]
    )


def _latest_metric_value(conn: sqlite3.Connection, metric: str) -> Optional[float]:
    row = conn.execute(
        """SELECT value
           FROM body_metrics
           WHERE metric=?
           ORDER BY recorded_date DESC, id DESC
           LIMIT 1""",
        (metric,),
    ).fetchone()
    return row["value"] if row else None


@router.get("/")
def get_goals(
    active_only: bool = True, conn: sqlite3.Connection = Depends(get_db_dependency)
):
    if active_only:
        rows = conn.execute(
            "SELECT * FROM goals WHERE active=1 ORDER BY created_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM goals ORDER BY active DESC, created_at DESC"
        ).fetchall()
    return [row_to_dict(row) for row in rows]


@router.post("/", status_code=201)
def create_goal(
    entry: GoalCreate, conn: sqlite3.Connection = Depends(get_db_dependency)
):
    _validate_goal_payload(
        goal_type=entry.goal_type,
        target_value=entry.target_value,
        direction=entry.direction,
    )

    cur = conn.execute(
        """INSERT INTO goals
           (
             name,
             metric,
             goal_type,
             target_value,
             direction,
             start_date,
             target_date,
             active,
             notes
           )
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            entry.name,
            entry.metric,
            entry.goal_type,
            entry.target_value,
            entry.direction,
            str(entry.start_date),
            str(entry.target_date) if entry.target_date else None,
            entry.active,
            entry.notes,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM goals WHERE id=?", (cur.lastrowid,)).fetchone()
    return row_to_dict(row)


@router.patch("/{goal_id}")
def update_goal(
    goal_id: int,
    patch: GoalPatch,
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
    existing = conn.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    payload = patch.model_dump(exclude_unset=True)
    normalized = {}
    for key, value in payload.items():
        if key in {"start_date", "target_date"} and value is not None:
            normalized[key] = str(value)
        else:
            normalized[key] = value

    if not normalized:
        return row_to_dict(existing)

    safe_fields = {k: v for k, v in normalized.items() if k in UPDATABLE_COLUMNS}
    if not safe_fields:
        return row_to_dict(existing)

    merged = row_to_dict(existing)
    merged.update(safe_fields)
    _validate_goal_payload(
        goal_type=merged["goal_type"],
        target_value=merged.get("target_value"),
        direction=merged.get("direction"),
    )

    columns = ", ".join(f"{column}=?" for column in safe_fields)
    values = list(safe_fields.values()) + [goal_id]
    conn.execute(f"UPDATE goals SET {columns} WHERE id=?", values)
    conn.commit()
    row = conn.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
    return row_to_dict(row)


@router.get("/{goal_id}/plans")
def get_goal_plans(goal_id: int, conn: sqlite3.Connection = Depends(get_db_dependency)):
    goal = conn.execute("SELECT id FROM goals WHERE id=?", (goal_id,)).fetchone()
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    rows = conn.execute(
        "SELECT * FROM goal_plans WHERE goal_id=? ORDER BY version DESC, created_at DESC",
        (goal_id,),
    ).fetchall()
    return [row_to_dict(row) for row in rows]


@router.post("/{goal_id}/plans", status_code=201)
def create_goal_plan(
    goal_id: int,
    entry: GoalPlanCreate,
    conn: sqlite3.Connection = Depends(get_db_dependency),
):
    goal = conn.execute("SELECT id FROM goals WHERE id=?", (goal_id,)).fetchone()
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS max_version FROM goal_plans WHERE goal_id=?",
        (goal_id,),
    ).fetchone()
    next_version = int(row["max_version"]) + 1
    cur = conn.execute(
        "INSERT INTO goal_plans (goal_id, plan, version) VALUES (?, ?, ?)",
        (goal_id, entry.plan, next_version),
    )
    conn.commit()
    plan = conn.execute(
        "SELECT * FROM goal_plans WHERE id=?", (cur.lastrowid,)
    ).fetchone()
    return row_to_dict(plan)


@router.post("/{goal_id}/plans/generate", status_code=201)
def generate_goal_plan(
    goal_id: int, conn: sqlite3.Connection = Depends(get_db_dependency)
):
    goal_row = conn.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
    if goal_row is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    goal = row_to_dict(goal_row)

    baseline = _latest_metric_value(conn, goal["metric"])
    plan_text = _build_plan(goal, baseline)
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS max_version FROM goal_plans WHERE goal_id=?",
        (goal_id,),
    ).fetchone()
    next_version = int(row["max_version"]) + 1
    cur = conn.execute(
        "INSERT INTO goal_plans (goal_id, plan, version) VALUES (?, ?, ?)",
        (goal_id, plan_text, next_version),
    )
    conn.commit()
    plan = conn.execute(
        "SELECT * FROM goal_plans WHERE id=?", (cur.lastrowid,)
    ).fetchone()
    return row_to_dict(plan)
