from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import db_session
from app.integrations.bolna import parse_webhook_payload
from app.repositories import call_logs as call_logs_repo
from app.services import emergency, export

logger = get_logger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])

TERMINAL_STATUSES = {"completed"}
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _client_ip(request: Request) -> str:
    """Real caller IP, accounting for the local tunnel in front of the server.

    Bolna posts from a fixed set of public IPs, but behind ngrok/cloudflared the
    immediate peer is the loopback tunnel. In that case the original address is
    only available in ``X-Forwarded-For``.
    """
    host = request.client.host if request.client else ""
    if host in LOOPBACK_HOSTS:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return host


@router.post("/bolna")
async def bolna_webhook(request: Request) -> dict:
    client_host = _client_ip(request)
    allowed_ips = settings.bolna_webhook_allowed_ips
    if allowed_ips and client_host not in allowed_ips | LOOPBACK_HOSTS | {"testclient"}:
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

    # Refresh the Excel report as soon as the call data lands.
    try:
        written = export.write_latest_files()
        logger.info("export refreshed", extra={"files": [str(path) for path in written]})
    except Exception as exc:  # noqa: BLE001 - reporting must never fail the webhook
        logger.warning("export refresh failed", extra={"error": str(exc)})

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
