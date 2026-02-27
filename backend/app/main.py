from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .db import init_db
from .routers import dashboard, exercise, food, ingest, metrics, sleep


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
app.include_router(sleep.router, prefix="/api/v1/sleep", tags=["sleep"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(ingest.router, prefix="/api/v1/ingest", tags=["ingest"])


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "driver"}
