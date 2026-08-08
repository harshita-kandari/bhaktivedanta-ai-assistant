from datetime import date, timedelta
from typing import Any, Optional

import pytest

from app.db.database import db_session
from app.repositories import appointments as appointments_repo
from app.services import booking, emergency, patients as patients_service, pricing, scheduling
from app.services.patients import PatientError


def _future_date(days: int = 3) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _working_doctor_and_slot() -> tuple[dict[str, Any], str, str]:
    with db_session() as conn:
        from app.repositories import doctors as doctors_repo

        for doctor in doctors_repo.list_doctors(conn):
            for offset in range(1, 8):
                target = (date.today() + timedelta(days=offset)).isoformat()
                result = scheduling.get_available_slots(doctor_id=doctor["id"], target_date=target)
                if result and result[0]["available_slots"]:
                    return doctor, target, result[0]["available_slots"][0]
    raise AssertionError("No working doctor found within window")


class TestScheduling:
    def test_available_slots_for_department(self) -> None:
        results: list[dict[str, Any]] = scheduling.get_upcoming_slots(
            department="Cardiology", window_days=7
        )
        assert results
        for entry in results:
            assert entry["department"] == "Cardiology"
            assert "available_slots" in entry

    def test_available_slots_for_doctor_name(self) -> None:
        results: list[dict[str, Any]] = scheduling.get_upcoming_slots(
            doctor_name="Dr. Anita Desai", window_days=7
        )
        assert results
        assert all(r["doctor_name"] == "Dr. Anita Desai" for r in results)

    def test_invalid_date_returns_empty(self) -> None:
        results: list[dict[str, Any]] = scheduling.get_available_slots(
            department="ENT", target_date="not-a-date"
        )
        assert results == []


class TestPatients:
    def test_register_and_lookup(self) -> None:
        patient: dict[str, Any] = patients_service.register_patient(
            full_name="Test Patient", phone="+919876543210", age=30, gender="male"
        )
        assert patient["id"] > 0
        found = patients_service.get_patient_by_phone("+919876543210")
        assert found is not None
        assert found["full_name"] == "Test Patient"

    def test_register_duplicate_returns_existing(self) -> None:
        first = patients_service.register_patient("Dup Patient", "+919000000001", None, None)
        second = patients_service.register_patient("Dup Patient", "+919000000001", None, None)
        assert first["id"] == second["id"]

    def test_invalid_phone_raises(self) -> None:
        with pytest.raises(PatientError):
            patients_service.register_patient("Bad Phone", "123", None, None)


class TestBooking:
    def test_book_cancel_flow(self) -> None:
        doctor, appointment_date, time_slot = _working_doctor_and_slot()
        patient = patients_service.register_patient("Booking Patient", "+919000000002", None, None)
        appointment = booking.book_appointment(
            doctor_id=doctor["id"],
            patient_id=patient["id"],
            appointment_date=appointment_date,
            time_slot=time_slot,
            reason="test",
        )
        assert appointment["status"] == "booked"

        with pytest.raises(booking.BookingError):
            booking.book_appointment(
                doctor_id=doctor["id"],
                patient_id=patient["id"],
                appointment_date=appointment_date,
                time_slot=time_slot,
            )

        cancelled = booking.cancel_appointment(appointment["id"])
        assert cancelled["status"] == "cancelled"

    def test_cancelled_slot_can_be_rebooked(self) -> None:
        doctor, appointment_date, time_slot = _working_doctor_and_slot()
        patient = patients_service.register_patient("Rebook Patient", "+919000000005", None, None)
        first = booking.book_appointment(
            doctor_id=doctor["id"],
            patient_id=patient["id"],
            appointment_date=appointment_date,
            time_slot=time_slot,
        )
        booking.cancel_appointment(first["id"])
        second = booking.book_appointment(
            doctor_id=doctor["id"],
            patient_id=patient["id"],
            appointment_date=appointment_date,
            time_slot=time_slot,
        )
        assert second["id"] == first["id"]
        assert second["status"] == "booked"

    def test_book_unknown_doctor_raises(self) -> None:
        patient = patients_service.register_patient("X Patient", "+919000000003", None, None)
        with pytest.raises(booking.BookingError):
            booking.book_appointment(
                doctor_id=99999,
                patient_id=patient["id"],
                appointment_date=_future_date(),
                time_slot="10:00",
            )

    def test_booked_slot_hidden_from_availability(self) -> None:
        doctor, target, chosen = _working_doctor_and_slot()
        patient = patients_service.register_patient("Avail Patient", "+919000000004", None, None)
        booking.book_appointment(
            doctor_id=doctor["id"],
            patient_id=patient["id"],
            appointment_date=target,
            time_slot=chosen,
        )
        slots_after = scheduling.get_available_slots(doctor_id=doctor["id"], target_date=target)
        assert chosen not in slots_after[0]["available_slots"]


class TestPricing:
    def test_fee_for_doctor(self) -> None:
        result = pricing.get_consultation_fee(doctor_name="Dr. Sanjay Verma")
        assert result is not None
        assert result["doctor_name"] == "Dr. Sanjay Verma"
        assert result["consultation_fee"] > 0
        assert result["followup_fee"] > 0

    def test_department_fee_range(self) -> None:
        result = pricing.get_department_fee_range("Orthopedics")
        assert result is not None
        assert result["min_fee"] <= result["max_fee"]

    def test_unknown_doctor_returns_none(self) -> None:
        assert pricing.get_consultation_fee(doctor_name="Dr. Missing") is None


class TestEmergency:
    def test_emergency_detection(self) -> None:
        assert emergency.check_emergency("I have severe chest pain") is not None
        assert emergency.check_emergency("I have a headache") is None

    def test_emergency_guidance_blocks_booking(self) -> None:
        guidance = emergency.emergency_guidance()
        assert guidance["emergency"] is True
        assert guidance["booking_allowed"] is False
