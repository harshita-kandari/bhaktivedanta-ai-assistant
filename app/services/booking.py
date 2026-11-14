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


def book_for_caller(
    full_name: str,
    phone: str,
    doctor_name: str,
    appointment_date: str,
    time_slot: str,
    department: Optional[str] = None,
    reason: str = "",
    age: Optional[int] = None,
    gender: Optional[str] = None,
) -> dict:
    """Book an appointment from a phone call using names instead of internal ids.

    Resolves (or registers) the patient by phone and matches the doctor by name,
    optionally falling back to a unique partial match inside the department.
    """
    from app.services import patients as patients_service
    from app.services.scheduling import is_working_day

    patient = patients_service.get_patient_by_phone(phone)
    if not patient:
        patient = patients_service.register_patient(full_name, phone, age, gender)

    with db_session() as conn:
        doctor = doctors_repo.get_doctor_by_name(conn, doctor_name.strip())
        if not doctor:
            candidates = doctors_repo.list_doctors(conn, department=department)
            matches = [d for d in candidates if doctor_name.strip().lower() in d["name"].lower()]
            # Seed data can contain duplicate rows for the same doctor.
            by_name = {d["name"]: d for d in matches}
            if len(by_name) != 1:
                available = ", ".join(sorted({d["name"] for d in candidates})) or "none"
                raise BookingError(
                    f"Could not find a unique doctor matching '{doctor_name}'"
                    + (f" in {department}" if department else "")
                    + f". Available doctors: {available}"
                )
            doctor = next(iter(by_name.values()))

    if department and doctor["department"].lower() != department.lower():
        raise BookingError(
            f"{doctor['name']} is in {doctor['department']}, not {department}"
        )

    try:
        target = date.fromisoformat(appointment_date)
        working = is_working_day(doctor, target)
    except ValueError as exc:
        raise BookingError(f"Invalid appointment date: {appointment_date}") from exc
    if not working:
        raise BookingError(f"{doctor['name']} is not available on {appointment_date}")

    return book_appointment(
        doctor_id=doctor["id"],
        patient_id=patient["id"],
        appointment_date=appointment_date,
        time_slot=time_slot,
        reason=reason,
        source="call",
    )


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
