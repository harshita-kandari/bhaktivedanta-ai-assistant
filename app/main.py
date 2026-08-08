from fastapi import FastAPI

from app.api import routes_appointments, routes_doctors, routes_emergency, routes_patients
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.database import init_db

setup_logging()
logger = get_logger(__name__)

init_db()

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
):
    app.include_router(router, prefix=settings.api_v1_prefix)
