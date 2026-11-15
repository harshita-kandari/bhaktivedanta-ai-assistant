from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api import (
    routes_appointments,
    routes_assistant,
    routes_calls,
    routes_doctors,
    routes_emergency,
    routes_patients,
    routes_voice,
    routes_webhook,
)
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.database import db_session, init_db
from app.db.seed import seed_doctors

setup_logging()
logger = get_logger(__name__)

init_db()

with db_session() as conn:
    count = conn.execute("SELECT COUNT(*) AS c FROM doctors").fetchone()["c"]
if count == 0:
    seed_doctors()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI assistant backend for Bhaktivedanta Hospital & Research Institute",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def ui() -> FileResponse:
    """The booking + chat page. Same API docs stay at /docs."""
    return FileResponse(Path(__file__).resolve().parent / "static" / "index.html")

@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


for router in (
    routes_doctors.router,
    routes_patients.router,
    routes_appointments.router,
    routes_emergency.router,
    routes_calls.router,
    routes_voice.router,
    routes_webhook.router,
    routes_assistant.router,
):
    app.include_router(router, prefix=settings.api_v1_prefix)
