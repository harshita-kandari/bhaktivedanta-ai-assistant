from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import db_session
from app.integrations.bolna import parse_webhook_payload
from app.repositories import call_logs as call_logs_repo
from app.services import emergency

logger = get_logger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])

TERMINAL_STATUSES = {"completed"}


@router.post("/bolna")
async def bolna_webhook(request: Request) -> dict:
    client_host = request.client.host if request.client else ""
    if settings.bolna_webhook_allowed_ip and client_host not in {
        settings.bolna_webhook_allowed_ip,
        "127.0.0.1",
        "localhost",
        "testclient",
    }:
        logger.warning("webhook rejected: source ip not allowed", extra={"ip": client_host})
        raise HTTPException(status_code=403, detail="Source IP not allowed")

    payload = await request.json()
    data = parse_webhook_payload(payload)
    execution_id = data["execution_id"]
    if not execution_id:
        raise HTTPException(status_code=400, detail="Missing execution id")

    emergency_flag = 0
    transcript = data.get("transcript") or ""
    if emergency.check_emergency(transcript):
        emergency_flag = 1
        logger.info("emergency flagged in call transcript", extra={"execution_id": execution_id})

    with db_session() as conn:
        call_log_id = call_logs_repo.upsert_call_log(conn, {**data, "emergency_flag": emergency_flag})
        log = call_logs_repo.get_by_execution_id(conn, execution_id)

    if data["status"] in TERMINAL_STATUSES:
        logger.info(
            "call completed",
            extra={
                "call_log_id": call_log_id,
                "execution_id": execution_id,
                "duration": data.get("conversation_duration"),
                "emergency": emergency_flag,
            },
        )

    return {"received": True, "call_log_id": call_log_id, "status": data["status"]}
