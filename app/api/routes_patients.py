from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import PatientRegister
from app.services import patients as patients_service

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", status_code=201)
def register_patient(payload: PatientRegister):
    try:
        return patients_service.register_patient(
            full_name=payload.full_name,
            phone=payload.phone,
            age=payload.age,
            gender=payload.gender,
        )
    except patients_service.PatientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
def list_patients(limit: int = Query(default=100, ge=1, le=500), offset: int = 0):
    return patients_service.list_patients(limit=limit, offset=offset)


@router.get("/{patient_id}")
def get_patient(patient_id: int):
    patient = patients_service.get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("/by-phone/{phone}")
def get_patient_by_phone(phone: str):
    try:
        patient = patients_service.get_patient_by_phone(phone)
    except patients_service.PatientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient
