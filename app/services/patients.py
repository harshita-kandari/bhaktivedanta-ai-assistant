import re
from typing import Optional

from app.core.logging import get_logger
from app.db.database import db_session
from app.repositories import patients as patients_repo

logger = get_logger(__name__)


class PatientError(Exception):
    pass


PHONE_RE = re.compile(r"^\+?[0-9]{10,15}$")


def _normalise_phone(phone: str) -> str:
    cleaned = re.sub(r"[\s\-()]", "", phone.strip())
    if not PHONE_RE.match(cleaned):
        raise PatientError(f"Invalid phone number: {phone}")
    return cleaned


def register_patient(
    full_name: str, phone: str, age: Optional[int] = None, gender: Optional[str] = None
) -> dict:
    phone = _normalise_phone(phone)
    if not full_name.strip():
        raise PatientError("Patient full name is required")
    if age is not None and (age < 0 or age > 150):
        raise PatientError("Age must be between 0 and 150")
    if gender and gender.lower() not in ("male", "female", "other"):
        raise PatientError(f"Invalid gender: {gender}")

    with db_session() as conn:
        existing = patients_repo.get_patient_by_phone(conn, phone)
        if existing:
            logger.info("patient already registered", extra={"patient_id": existing["id"], "phone": phone})
            return existing
        patient_id = patients_repo.create_patient(conn, full_name.strip(), phone, age, gender)
        patient = patients_repo.get_patient_by_id(conn, patient_id)
        logger.info("patient registered", extra={"patient_id": patient_id, "phone": phone})
        return patient


def get_patient_by_phone(phone: str) -> Optional[dict]:
    phone = _normalise_phone(phone)
    with db_session() as conn:
        return patients_repo.get_patient_by_phone(conn, phone)


def get_patient_by_id(patient_id: int) -> Optional[dict]:
    with db_session() as conn:
        return patients_repo.get_patient_by_id(conn, patient_id)


def list_patients(limit: int = 100, offset: int = 0) -> list[dict]:
    with db_session() as conn:
        return patients_repo.list_patients(conn, limit=limit, offset=offset)
