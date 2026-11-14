from datetime import date, datetime, timedelta
from typing import Optional

from app.core.logging import get_logger
from app.db.database import db_session
from app.repositories import appointments as appointments_repo
from app.repositories import doctors as doctors_repo

logger = get_logger(__name__)

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _parse_hour_minute(value: str) -> tuple[int, int]:
    hour, minute = value.strip().split(":")
    return int(hour), int(minute)


def _generate_slots(opd_start: str, opd_end: str, slot_minutes: int) -> list[str]:
    start_h, start_m = _parse_hour_minute(opd_start)
    end_h, end_m = _parse_hour_minute(opd_end)
    cursor = datetime(2000, 1, 1, start_h, start_m)
    end = datetime(2000, 1, 1, end_h, end_m)
    slots: list[str] = []
    while cursor < end:
        slots.append(cursor.strftime("%H:%M"))
        cursor += timedelta(minutes=slot_minutes)
    return slots


def is_working_day(doctor: dict, target: date) -> bool:
    days = {d.strip() for d in doctor["days_available"].split(",") if d.strip()}
    return WEEKDAYS[target.weekday()] in days


def get_available_slots(
    doctor_id: Optional[int] = None,
    doctor_name: Optional[str] = None,
    department: Optional[str] = None,
    target_date: Optional[str] = None,
    window_days: int = 7,
) -> list[dict]:
    try:
        target = date.fromisoformat(target_date) if target_date else date.today()
    except ValueError:
        return []

    with db_session() as conn:
        doctors = []
        if doctor_id:
            doc = doctors_repo.get_doctor_by_id(conn, doctor_id)
            doctors = [doc] if doc else []
        elif doctor_name:
            doc = doctors_repo.get_doctor_by_name(conn, doctor_name)
            if doc:
                doctors = [doc]
            else:
                # Voice callers often say just a surname; match partially and
                # de-duplicate repeated seed rows by name.
                candidates = doctors_repo.list_doctors(conn, department=department)
                matches = {
                    d["name"]: d
                    for d in candidates
                    if doctor_name.strip().lower() in d["name"].lower()
                }
                doctors = list(matches.values())
        elif department:
            doctors = doctors_repo.list_doctors(conn, department=department)
        else:
            doctors = doctors_repo.list_doctors(conn)

        results = []
        for doc in doctors:
            if not is_working_day(doc, target):
                continue
            all_slots = _generate_slots(doc["opd_start"], doc["opd_end"], doc["slot_minutes"])
            booked = appointments_repo.booked_slots(conn, doc["id"], target.isoformat())
            free = [s for s in all_slots if s not in booked]
            results.append(
                {
                    "doctor_id": doc["id"],
                    "doctor_name": doc["name"],
                    "department": doc["department"],
                    "date": target.isoformat(),
                    "opd_timings": f"{doc['opd_start']} - {doc['opd_end']}",
                    "available_slots": free,
                    "consultation_fee": doc["consultation_fee"],
                    "followup_fee": doc["followup_fee"],
                    "next_7_days_slots_available": len(free) > 0,
                }
            )
        return results


def get_upcoming_slots(
    doctor_id: Optional[int] = None,
    doctor_name: Optional[str] = None,
    department: Optional[str] = None,
    window_days: int = 7,
) -> list[dict]:
    results = []
    today = date.today()
    for offset in range(window_days):
        target = today + timedelta(days=offset)
        results.extend(
            get_available_slots(
                doctor_id=doctor_id,
                doctor_name=doctor_name,
                department=department,
                target_date=target.isoformat(),
            )
        )
    return [r for r in results if r["available_slots"]]
