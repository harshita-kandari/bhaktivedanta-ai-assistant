from typing import Any

from fastapi.testclient import TestClient

from app.core.config import Settings


def _first_free_slot(client: TestClient) -> tuple[str, str, str]:
    response = client.get(
        "/api/v1/doctors/availability", params={"department": "ENT", "window_days": 7}
    )
    assert response.status_code == 200
    for entry in response.json():
        if entry["available_slots"]:
            return entry["doctor_name"], entry["date"], entry["available_slots"][-1]
    raise AssertionError("seed data has no free ENT slots")


class TestVoiceBookingApi:
    def test_books_by_doctor_name_and_registers_patient(self, client: TestClient) -> None:
        doctor_name, date, slot = _first_free_slot(client)
        response = client.post(
            "/api/v1/voice/book",
            json={
                "full_name": "Voice Caller",
                "phone": "+919800000001",
                "doctor_name": doctor_name,
                "department": "ENT",
                "appointment_date": date,
                "time_slot": slot,
                "reason": "ear pain",
            },
        )
        assert response.status_code == 201, response.text
        appointment = response.json()
        assert appointment["doctor_name"] == doctor_name
        assert appointment["time_slot"] == slot
        assert appointment["source"] == "call"

        patient = client.get("/api/v1/patients/by-phone/+919800000001")
        assert patient.status_code == 200
        assert patient.json()["full_name"] == "Voice Caller"

    def test_partial_doctor_name_resolves(self, client: TestClient) -> None:
        doctor_name, date, slot = _first_free_slot(client)
        surname = doctor_name.split()[-1]
        response = client.post(
            "/api/v1/voice/book",
            json={
                "full_name": "Partial Name Caller",
                "phone": "+919800000002",
                "doctor_name": surname,
                "department": "ENT",
                "appointment_date": date,
                "time_slot": slot,
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["doctor_name"] == doctor_name

    def test_duplicate_slot_conflicts(self, client: TestClient) -> None:
        doctor_name, date, slot = _first_free_slot(client)
        payload = {
            "full_name": "Duplicate Caller",
            "phone": "+919800000003",
            "doctor_name": doctor_name,
            "department": "ENT",
            "appointment_date": date,
            "time_slot": slot,
        }
        assert client.post("/api/v1/voice/book", json=payload).status_code == 201
        conflict = client.post("/api/v1/voice/book", json=payload)
        assert conflict.status_code == 409
        assert "already booked" in conflict.json()["detail"]

    def test_unknown_doctor_returns_409(self, client: TestClient) -> None:
        _, date, slot = _first_free_slot(client)
        response = client.post(
            "/api/v1/voice/book",
            json={
                "full_name": "Unknown Doctor Caller",
                "phone": "+919800000004",
                "doctor_name": "Dr. Nobody",
                "department": "ENT",
                "appointment_date": date,
                "time_slot": slot,
            },
        )
        assert response.status_code == 409


class TestVoiceAvailabilityLookup:
    def test_partial_name_matches_doctor(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/doctors/availability",
            params={"doctor_name": "Desai", "window_days": 7},
        )
        assert response.status_code == 200
        names = {entry["doctor_name"] for entry in response.json()}
        assert names
        assert all("Desai" in name for name in names)


class TestWebhookIpAllowlist:
    def test_parses_comma_separated_ips(self, monkeypatch: Any) -> None:
        monkeypatch.setenv(
            "BOLNA_WEBHOOK_ALLOWED_IP", "13.203.39.153, 13.126.9.249 ,13.202.133.53"
        )
        settings = Settings()
        assert settings.bolna_webhook_allowed_ips == {
            "13.203.39.153",
            "13.126.9.249",
            "13.202.133.53",
        }

    def test_empty_value_disables_allowlist(self, monkeypatch: Any) -> None:
        monkeypatch.setenv("BOLNA_WEBHOOK_ALLOWED_IP", "")
        settings = Settings()
        assert settings.bolna_webhook_allowed_ips == set()
