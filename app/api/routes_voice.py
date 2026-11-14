from fastapi import APIRouter, HTTPException

from app.api.schemas import VoiceBookRequest
from app.services import booking, patients

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/book", status_code=201)
def voice_book(payload: VoiceBookRequest) -> dict:
    """Book an appointment on a live call using spoken names instead of ids."""
    try:
        return booking.book_for_caller(
            full_name=payload.full_name,
            phone=payload.phone,
            doctor_name=payload.doctor_name,
            appointment_date=payload.appointment_date,
            time_slot=payload.time_slot,
            department=payload.department,
            reason=payload.reason,
            age=payload.age,
            gender=payload.gender,
        )
    except (booking.BookingError, patients.PatientError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
