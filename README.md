# Bhaktivedanta Hospital AI Assistant — Backend

FastAPI backend for the Bhaktivedanta Hospital & Research Institute patient care
assistant ("Bhakti"). Layered architecture: **routes → services → repositories → SQLite**,
with DeepSeek for conversational intelligence and Bolna for voice calls.

## Features

- Doctor directory (ENT / Orthopedics / Cardiology) with OPD timings, days and fees
- Availability lookup with slot generation and conflict-free booking
- Patient registration and lookup by phone
- Appointment booking / cancellation with duplicate-slot protection
- Emergency triage: detects life-threatening symptoms, never books, returns helpline guidance
- Bolna integration: place outbound calls, receive end-of-call webhook with transcript,
  extracted data and costs; emergency flagging from transcripts
- DeepSeek AI assistant with OpenAI-style function calling (tool use)
- Structured JSON logging (console + rotating file `logs/app.log`)

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
copy .env.example .env            # then fill in real keys
.venv\Scripts\python -m uvicorn app.main:app --reload
```

- API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health
- Doctors are auto-seeded on first run (8 sample doctors).

## Environment (.env)

| Variable | Purpose |
|---|---|
| `BOLNA_API_KEY` | Bolna auth (Bearer token, `bn-...`) |
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `BOLNA_AGENT_ID` | Bolna agent UUID (needed for outbound calls) |
| `BOLNA_WEBHOOK_ALLOWED_IP` | Bolna webhook source IP (default `13.203.39.153`) |
| `DATABASE_PATH` | SQLite file path (default `data/hospital.db`) |
| `DEEPSEEK_MODEL` | Default `deepseek-chat` |
| `EMERGENCY_HELPLINE` / `FRONT_DESK_PHONE` | Shown in emergency / fallback replies |

## API surface (`/api/v1`)

| Endpoint | Description |
|---|---|
| `GET /doctors?department=` | List doctors |
| `GET /doctors/{id}` | Doctor details |
| `GET /doctors/availability` | Free slots (`doctor_id` / `doctor_name` / `department` + `date` or `window_days`) |
| `GET /doctors/fees` | Fees (`doctor_id` / `doctor_name` / `department`) |
| `POST /patients` | Register patient |
| `GET /patients/by-phone/{phone}` | Lookup by phone |
| `POST /appointments` | Book appointment (409 on slot conflict) |
| `POST /appointments/{id}/cancel` | Cancel appointment |
| `GET /appointments` | List (filter by doctor/patient/status) |
| `POST /emergency/check` | Triage check |
| `GET /emergency/info` | Emergency guidance |
| `POST /assistant/chat` | AI assistant (DeepSeek tool-use) |
| `POST /calls` | Place outbound Bolna call (needs `BOLNA_AGENT_ID`) |
| `POST /webhook/bolna` | Bolna end-of-call webhook (IP allowlisted) |

## Bolna webhook notes

- Bolna POSTs on every status change; only `completed` carries the full payload.
- Payloads are stored in `call_logs` (upsert by `execution_id`).
- No HMAC signature exists; requests from any IP other than
  `13.203.39.153` are rejected with 403.

## Tests

```bash
.venv\Scripts\python -m pytest tests -q
```

End-to-end test against a live server:

```bash
.venv\Scripts\python -m uvicorn app.main:app --port 8000
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\e2e_test.ps1
```

## Architecture docs

- `docs/ARCHITECTURE.md` — system design, schema, layers, build phases
- `docs/DEEPSEEK_PLAN.md` — AI integration plan (function calling vs intent JSON)
