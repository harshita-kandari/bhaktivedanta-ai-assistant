from typing import Literal, Optional

from pydantic import BaseModel, Field

Department = Literal["ENT", "Orthopedics", "Cardiology"]


class DoctorCreate(BaseModel):
    name: str
    department: Department
    qualification: str = ""
    consultation_fee: float = 0
    followup_fee: float = 0
    days_available: str = "Mon,Tue,Wed,Thu,Fri,Sat"
    opd_start: str = "09:00"
    opd_end: str = "20:00"
    slot_minutes: int = 30


class PatientRegister(BaseModel):
    full_name: str
    phone: str
    age: Optional[int] = Field(default=None, ge=0, le=150)
    gender: Optional[Literal["male", "female", "other"]] = None


class AppointmentCreate(BaseModel):
    doctor_id: int
    patient_id: int
    appointment_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    time_slot: str = Field(pattern=r"^\d{2}:\d{2}$")
    reason: str = ""
    source: Literal["assistant", "call", "web"] = "assistant"


class AvailabilityQuery(BaseModel):
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    department: Optional[Department] = None
    date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    window_days: int = Field(default=7, ge=1, le=30)


class FeeQuery(BaseModel):
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    department: Optional[Department] = None


class CallPlaceRequest(BaseModel):
    recipient_phone_number: str
    user_data: dict = {}
    retry_config: dict = {}


class VoiceBookRequest(BaseModel):
    """Single-call booking payload used by the Bolna voice agent.

    The voice agent only has the caller's spoken name, phone, doctor and slot,
    so patient lookup/registration and doctor name resolution happen server-side.
    """

    full_name: str
    phone: str
    doctor_name: str
    appointment_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    time_slot: str = Field(pattern=r"^\d{2}:\d{2}$")
    department: Optional[Department] = None
    reason: str = ""
    age: Optional[int] = Field(default=None, ge=0, le=150)
    gender: Optional[Literal["male", "female", "other"]] = None


class AssistantMessage(BaseModel):
    message: str
    patient_id: Optional[int] = None
    phone: Optional[str] = None
    origin: Literal["call", "chat"] = "chat"
    history: list[dict] = []
