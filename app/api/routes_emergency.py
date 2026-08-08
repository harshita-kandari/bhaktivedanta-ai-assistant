from fastapi import APIRouter, HTTPException

from app.services import emergency

router = APIRouter(prefix="/emergency", tags=["emergency"])


@router.post("/check")
def check_emergency(payload: dict) -> dict:
    message = payload.get("message", "")
    if not message.strip():
        raise HTTPException(status_code=400, detail="message is required")
    keyword = emergency.check_emergency(message)
    if keyword:
        return emergency.emergency_guidance() | {"matched_keyword": keyword}
    return {"emergency": False, "booking_allowed": True}


@router.get("/info")
def emergency_info() -> dict:
    return emergency.emergency_guidance()
