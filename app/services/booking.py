from datetime import date
from typing import Optional

from app.core.logging import get_logger
from app.db.database import db_session
from app.repositories import appointments as appointments_repo
from app.repositories import doctors as doctors_repo
from app.repositories import patients as patients_repo

logger = get_logger(__name__)


class BookingError(Exception):
    pass


def book_appointment(
    doctor_id: int,
    patient_id: int,
    appointment_date: str,
    time_slot: str,
    reason: str = "",
    source: str = "assistant",
) -> dict:
    with db_session() as conn:
        doctor = doctors_repo.get_doctor_by_id(conn, doctor_id)
        if not doctor or not doctor["active"]:
            raise BookingError("Doctor not found or inactive")
        patient = patients_repo.get_patient_by_id(conn, patient_id)
        if not patient:
            raise BookingError("Patient not found")

        from app.services.scheduling import is_working_day

        target = date.fromisoformat(appointment_date)
        if not is_working_day(doctor, target):
            raise BookingError(f"Doctor is not available on {appointment_date}")

        booked = appointments_repo.booked_slots(conn, doctor_id, appointment_date)
        if time_slot in booked:
            raise BookingError(
                f"Slot {time_slot} on {appointment_date} is already booked for {doctor['name']}"
            )

        appointment_id = appointments_repo.create_appointment(
            conn,
            doctor_id=doctor_id,
            patient_id=patient_id,
            appointment_date=appointment_date,
            time_slot=time_slot,
            reason=reason,
            source=source,
        )
        appointment = appointments_repo.get_appointment_by_id(conn, appointment_id)
        appointment["doctor_name"] = doctor["name"]
        appointment["patient_name"] = patient["full_name"]
        appointment["consultation_fee"] = doctor["consultation_fee"]
        logger.info(
            "appointment booked",
            extra={
                "appointment_id": appointment_id,
                "doctor_id": doctor_id,
                "patient_id": patient_id,
                "date": appointment_date,
                "slot": time_slot,
            },
        )
        return appointment


def cancel_appointment(appointment_id: int) -> dict:
    with db_session() as conn:
        appointment = appointments_repo.get_appointment_by_id(conn, appointment_id)
        if not appointment:
            raise BookingError("Appointment not found")
        if appointment["status"] != "booked":
            raise BookingError(f"Cannot cancel appointment in status '{appointment['status']}'")
        appointments_repo.update_appointment_status(conn, appointment_id, "cancelled")
        appointment = appointments_repo.get_appointment_by_id(conn, appointment_id)
        logger.info("appointment cancelled", extra={"appointment_id": appointment_id})
        return appointment


def get_appointments(
    doctor_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    with db_session() as conn:
        appointments = appointments_repo.list_appointments(
            conn, doctor_id=doctor_id, patient_id=patient_id, status=status, limit=limit, offset=offset
        )
        for appointment in appointments:
            doctor = doctors_repo.get_doctor_by_id(conn, appointment["doctor_id"])
            patient = patients_repo.get_patient_by_id(conn, appointment["patient_id"])
            appointment["doctor_name"] = doctor["name"] if doctor else None
            appointment["doctor_department"] = doctor["department"] if doctor else None
            appointment["patient_name"] = patient["full_name"] if patient else None
        return appointments
