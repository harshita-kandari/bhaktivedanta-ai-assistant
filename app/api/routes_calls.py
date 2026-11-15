from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import CallPlaceRequest
from app.db.database import db_session
from app.integrations.bolna import BolnaClient, BolnaError
from app.repositories import call_logs as call_logs_repo

router = APIRouter(prefix="/calls", tags=["calls"])


@router.get("")
def list_calls(limit: int = Query(default=20, ge=1, le=200)) -> list[dict]:
    """Recent calls, newest first, for the live dashboard."""
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT id, execution_id, status, direction, recipient_phone,
                   conversation_duration, total_cost, emergency_flag, created_at,
                   substr(coalesce(transcript, ''), 1, 240) AS transcript_preview
            FROM call_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


@router.post("", status_code=202)
def place_call(payload: CallPlaceRequest) -> dict:
    try:
        client = BolnaClient()
        result = client.place_call(
            recipient_phone_number=payload.recipient_phone_number,
            user_data=payload.user_data,
            retry_config=payload.retry_config,
            language=payload.language,
        )
    except BolnaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    execution_id = result.get("execution_id")
    if execution_id:
        with db_session() as conn:
            call_logs_repo.create_call_log(
                conn,
                execution_id=execution_id,
                status=result.get("status", "queued"),
                recipient_phone=payload.recipient_phone_number,
            )
    return result


@router.get("/{execution_id}")
def get_execution(execution_id: str) -> dict:
    try:
        client = BolnaClient()
        return client.get_execution(execution_id)
    except BolnaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
