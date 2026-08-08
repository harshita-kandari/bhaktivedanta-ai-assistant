from typing import Optional

from app.core.logging import get_logger
from app.db.database import db_session
from app.repositories import doctors as doctors_repo

logger = get_logger(__name__)


def get_consultation_fee(
    doctor_id: Optional[int] = None, doctor_name: Optional[str] = None
) -> Optional[dict]:
    with db_session() as conn:
        if doctor_id:
            doctor = doctors_repo.get_doctor_by_id(conn, doctor_id)
        elif doctor_name:
            doctor = doctors_repo.get_doctor_by_name(conn, doctor_name)
        else:
            return None
        if not doctor:
            return None
        return {
            "doctor_id": doctor["id"],
            "doctor_name": doctor["name"],
            "department": doctor["department"],
            "qualification": doctor["qualification"],
            "consultation_fee": doctor["consultation_fee"],
            "followup_fee": doctor["followup_fee"],
            "note": "Consultation fee covers the OPD visit only; diagnostic tests, "
            "X-rays, ECGs and blood work are billed separately.",
        }


def get_department_fee_range(department: str) -> Optional[dict]:
    with db_session() as conn:
        doctors = doctors_repo.list_doctors(conn, department=department)
        if not doctors:
            return None
        fees = [d["consultation_fee"] for d in doctors]
        return {
            "department": department,
            "min_fee": min(fees),
            "max_fee": max(fees),
            "doctor_count": len(doctors),
        }
