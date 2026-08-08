from typing import Any

from fastapi.testclient import TestClient


class TestDoctorsApi:
    def test_list_doctors(self, client: TestClient) -> None:
        response = client.get("/api/v1/doctors")
        assert response.status_code == 200
        doctors: list[dict[str, Any]] = response.json()
        assert len(doctors) >= 8
        departments = {d["department"] for d in doctors}
        assert departments == {"ENT", "Orthopedics", "Cardiology"}

    def test_filter_by_department(self, client: TestClient) -> None:
        response = client.get("/api/v1/doctors", params={"department": "ENT"})
        assert response.status_code == 200
        doctors: list[dict[str, Any]] = response.json()
        assert doctors
        assert all(d["department"] == "ENT" for d in doctors)

    def test_get_doctor_by_id_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/doctors/999999")
        assert response.status_code == 404

    def test_availability(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/doctors/availability", params={"department": "ENT", "window_days": 3}
        )
        assert response.status_code == 200
        slots: list[dict[str, Any]] = response.json()
        assert slots
        assert all("available_slots" in s for s in slots)

    def test_fees_by_department(self, client: TestClient) -> None:
        response = client.get("/api/v1/doctors/fees", params={"department": "Cardiology"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["department"] == "Cardiology"
        assert payload["min_fee"] > 0


class TestPatientsApi:
    def test_register_and_get(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/patients",
            json={"full_name": "API Patient", "phone": "+919123456789", "age": 40, "gender": "female"},
        )
        assert response.status_code == 201
        patient = response.json()
        assert patient["full_name"] == "API Patient"

        fetched = client.get(f"/api/v1/patients/{patient['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["phone"] == "+919123456789"

    def test_register_invalid_phone(self, client: TestClient) -> None:
        response = client.post("/api/v1/patients", json={"full_name": "X", "phone": "abc"})
        assert response.status_code == 400


class TestAppointmentsApi:
    def _free_slot(self, client: TestClient, department: str) -> dict[str, Any]:
        availability = client.get(
            "/api/v1/doctors/availability", params={"department": department, "window_days": 7}
        ).json()
        for entry in availability:
            if entry["available_slots"]:
                return {
                    "doctor_id": entry["doctor_id"],
                    "appointment_date": entry["date"],
                    "time_slot": entry["available_slots"][0],
                }
        raise AssertionError("No free slot found")

    def test_create_list_cancel(self, client: TestClient) -> None:
        slot = self._free_slot(client, "ENT")
        patient = client.post(
            "/api/v1/patients",
            json={"full_name": "Appt Patient", "phone": "+919234567890", "age": 25, "gender": "male"},
        ).json()

        created = client.post(
            "/api/v1/appointments",
            json={
                "doctor_id": slot["doctor_id"],
                "patient_id": patient["id"],
                "appointment_date": slot["appointment_date"],
                "time_slot": slot["time_slot"],
                "reason": "sinusitis",
            },
        )
        assert created.status_code == 201
        appointment = created.json()
        assert appointment["status"] == "booked"

        listing = client.get("/api/v1/appointments", params={"patient_id": patient["id"]})
        assert listing.status_code == 200
        assert any(a["id"] == appointment["id"] for a in listing.json())

        cancelled = client.post(f"/api/v1/appointments/{appointment['id']}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"

    def test_duplicate_slot_conflict(self, client: TestClient) -> None:
        slot = self._free_slot(client, "ENT")
        patient = client.post(
            "/api/v1/patients",
            json={"full_name": "Conflict Patient", "phone": "+919345678901", "age": 22, "gender": "other"},
        ).json()
        body = {
            "doctor_id": slot["doctor_id"],
            "patient_id": patient["id"],
            "appointment_date": slot["appointment_date"],
            "time_slot": slot["time_slot"],
        }
        first = client.post("/api/v1/appointments", json=body)
        assert first.status_code == 201
        second = client.post("/api/v1/appointments", json=body)
        assert second.status_code == 409


class TestEmergencyApi:
    def test_check_emergency(self, client: TestClient) -> None:
        response = client.post("/api/v1/emergency/check", json={"message": "severe chest pain"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["emergency"] is True
        assert payload["booking_allowed"] is False

    def test_check_non_emergency(self, client: TestClient) -> None:
        response = client.post("/api/v1/emergency/check", json={"message": "need ENT checkup"})
        assert response.status_code == 200
        assert response.json()["emergency"] is False


class TestSystemApi:
    def test_health(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestCallLogsWebhook:
    def test_webhook_completed(self, client: TestClient) -> None:
        payload = {
            "id": "test-exec-001",
            "agent_id": "agent-1",
            "status": "completed",
            "transcript": "assistant: Hello\nuser: I have severe chest pain",
            "conversation_duration": 42,
            "total_cost": 12.5,
            "user_number": "+919999999999",
            "telephony_data": {"call_type": "inbound", "recording_url": "https://x/rec"},
            "extracted_data": {"General": {"Call Summary": {"subjective": "Booked"}}},
        }
        response = client.post("/api/v1/webhook/bolna", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["received"] is True
        assert body["status"] == "completed"
        assert body["call_log_id"] > 0

        replay = client.post("/api/v1/webhook/bolna", json=payload)
        assert replay.status_code == 200
        assert replay.json()["call_log_id"] == body["call_log_id"]

    def test_webhook_marks_emergency(self, client: TestClient) -> None:
        payload = {
            "id": "test-exec-002",
            "agent_id": "agent-1",
            "status": "completed",
            "transcript": "assistant: Are you okay?\nuser: severe chest pain and shortness of breath",
            "conversation_duration": 10,
            "user_number": "+919888888888",
        }
        response = client.post("/api/v1/webhook/bolna", json=payload)
        assert response.status_code == 200
        from app.db.database import db_session
        from app.repositories import call_logs as call_logs_repo

        with db_session() as conn:
            log = call_logs_repo.get_by_execution_id(conn, "test-exec-002")
        assert log is not None
        assert log["emergency_flag"] == 1
