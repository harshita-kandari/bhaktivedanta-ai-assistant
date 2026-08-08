from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import DoctorCreate
from app.db.database import db_session
from app.repositories import doctors as doctors_repo
from app.services import pricing, scheduling

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("")
def list_doctors(
    department: Optional[str] = Query(default=None),
    active_only: bool = True,
) -> list[dict]:
    with db_session() as conn:
        return doctors_repo.list_doctors(conn, department=department, active_only=active_only)


@router.get("/availability")
def availability(
    doctor_id: Optional[int] = None,
    doctor_name: Optional[str] = None,
    department: Optional[str] = None,
    date: Optional[str] = None,
    window_days: int = Query(default=7, ge=1, le=30),
) -> list[dict]:
    if not doctor_id and not doctor_name and not department:
        raise HTTPException(status_code=400, detail="Provide doctor_id, doctor_name or department")
    if date and window_days != 7:
        raise HTTPException(status_code=400, detail="date and window_days cannot be combined")
    if date:
        slots = scheduling.get_available_slots(
            doctor_id=doctor_id,
            doctor_name=doctor_name,
            department=department,
            target_date=date,
        )
        return slots
    return scheduling.get_upcoming_slots(
        doctor_id=doctor_id, doctor_name=doctor_name, department=department, window_days=window_days
    )


@router.get("/fees")
def fees(
    doctor_id: Optional[int] = None,
    doctor_name: Optional[str] = None,
    department: Optional[str] = None,
) -> dict:
    if department:
        result = pricing.get_department_fee_range(department)
        if not result:
            raise HTTPException(status_code=404, detail=f"No doctors in department {department}")
        return result
    result = pricing.get_consultation_fee(doctor_id=doctor_id, doctor_name=doctor_name)
    if not result:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return result


@router.get("/{doctor_id}")
def get_doctor(doctor_id: int) -> dict:
    with db_session() as conn:
        doctor = doctors_repo.get_doctor_by_id(conn, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


@router.post("", status_code=201)
def create_doctor(payload: DoctorCreate) -> dict:
    with db_session() as conn:
        doctor_id = doctors_repo.create_doctor(conn, payload.model_dump())
        doctor = doctors_repo.get_doctor_by_id(conn, doctor_id)
    return doctor
