import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from .db import init_db
from .routers import (
    agent,
    coaching,
    dashboard,
    exercise,
    food,
    goals,
    ingest,
    labs,
    medications,
    medical_history,
    metrics,
    reports,
    sleep,
    supplements,
    training,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Driver API",
    version="0.1.0",
    description="Personal health platform API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tailscale-only network, no external exposure
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(food.router, prefix="/api/v1/food", tags=["food"])
app.include_router(exercise.router, prefix="/api/v1/exercise", tags=["exercise"])
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["metrics"])
app.include_router(labs.router, prefix="/api/v1/labs", tags=["labs"])
app.include_router(sleep.router, prefix="/api/v1/sleep", tags=["sleep"])
app.include_router(
    supplements.router, prefix="/api/v1/supplements", tags=["supplements"]
)
app.include_router(
    medications.router, prefix="/api/v1/medications", tags=["medications"]
)
app.include_router(
    medical_history.router, prefix="/api/v1/medical-history", tags=["medical-history"]
)
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(agent.router, prefix="/api/v1/agent", tags=["agent"])
app.include_router(ingest.router, prefix="/api/v1/ingest", tags=["ingest"])
app.include_router(training.router, prefix="/api/v1/training", tags=["training"])
app.include_router(coaching.router, prefix="/api/v1/coaching", tags=["coaching"])
app.include_router(goals.router, prefix="/api/v1/goals", tags=["goals"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "driver"}


frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.is_dir() and os.getenv("TESTING") != "1":
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
