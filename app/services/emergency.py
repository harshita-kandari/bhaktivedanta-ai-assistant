from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

EMERGENCY_KEYWORDS = [
    "severe chest pain",
    "chest pain",
    "heart attack",
    "shortness of breath",
    "difficulty breathing",
    "breathless",
    "radiating pain",
    "pain in the arm",
    "pain in the jaw",
    "fainting",
    "unconscious",
    "unconsciousness",
    "sudden paralysis",
    "stroke",
    "major trauma",
    "severe bleeding",
    "heavy bleeding",
    "not breathing",
    "suicidal",
    "severe allergic reaction",
    "anaphylaxis",
    "seizure",
    "convulsing",
]


def caller_text(transcript: str) -> str:
    """Only the caller's lines, so the agent's own words cannot trigger triage.

    Bolna transcripts are formatted as ``role: text`` per line.
    """
    lines = []
    for line in (transcript or "").splitlines():
        if line.lower().startswith("user:"):
            lines.append(line.split(":", 1)[1])
    return " ".join(lines) if lines else (transcript or "")


def check_emergency(message: str) -> Optional[str]:
    lowered = (message or "").lower()
    for keyword in EMERGENCY_KEYWORDS:
        if keyword in lowered:
            logger.info("emergency detected", extra={"keyword": keyword})
            return keyword
    return None


def emergency_guidance() -> dict:
    return {
        "emergency": True,
        "message": (
            "If you or the patient are experiencing severe chest pain, extreme "
            "breathlessness, or any medical emergency, please do not wait for an "
            "OPD booking. Proceed immediately to our 24/7 Emergency / Casualty "
            "Department, or call our emergency helpline."
        ),
        "emergency_helpline": settings.emergency_helpline,
        "front_desk_phone": settings.front_desk_phone,
        "booking_allowed": False,
    }
