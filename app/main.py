from fastapi import FastAPI

from app.api import (
    routes_appointments,
    routes_assistant,
    routes_calls,
    routes_doctors,
    routes_emergency,
    routes_patients,
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


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


for router in (
    routes_doctors.router,
    routes_patients.router,
    routes_appointments.router,
    routes_emergency.router,
    routes_calls.router,
    routes_webhook.router,
    routes_assistant.router,
):
    app.include_router(router, prefix=settings.api_v1_prefix)
