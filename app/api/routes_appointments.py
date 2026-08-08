from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import AppointmentCreate
from app.services import booking

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("")
def list_appointments(
    doctor_id: int | None = None,
    patient_id: int | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = 0,
):
    return booking.get_appointments(
        doctor_id=doctor_id, patient_id=patient_id, status=status, limit=limit, offset=offset
    )


@router.post("", status_code=201)
def create_appointment(payload: AppointmentCreate):
    try:
        return booking.book_appointment(
            doctor_id=payload.doctor_id,
            patient_id=payload.patient_id,
            appointment_date=payload.appointment_date,
            time_slot=payload.time_slot,
            reason=payload.reason,
            source=payload.source,
        )
    except booking.BookingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{appointment_id}")
def get_appointment(appointment_id: int):
    appointments = booking.get_appointments(limit=500)
    for appointment in appointments:
        if appointment["id"] == appointment_id:
            return appointment
    raise HTTPException(status_code=404, detail="Appointment not found")


@router.post("/{appointment_id}/cancel")
def cancel_appointment(appointment_id: int):
    try:
        return booking.cancel_appointment(appointment_id)
    except booking.BookingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
