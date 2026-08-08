from fastapi import APIRouter, HTTPException

from app.api.schemas import AssistantMessage
from app.services.ai_assistant import CallContext, assistant_service

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat")
def chat(payload: AssistantMessage):
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="message is required")
    context = CallContext(
        origin=payload.origin,
        patient_id=payload.patient_id,
        phone=payload.phone,
    )
    return assistant_service.process_message(payload.message, context)
