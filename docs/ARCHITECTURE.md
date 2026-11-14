# Bhaktivedanta Hospital AI Assistant — Architecture Plan

**Status:** Implemented (backend, DeepSeek tool-use, Bolna voice tools)
**Stack:** FastAPI · SQLite · DeepSeek (AI) · Bolna (voice calls)

## 1. System Overview

A hospital AI assistant that patients call (or chat with) to:
- Ask about doctors (names, qualifications, OPD timings, availability)
- Get consultation fee estimates
- Get alternative doctor suggestions in the same department
- Book appointments (ENT, Orthopedics, Cardiology)
- Register new patients
- Flag emergencies (never books for life-threatening symptoms)

Voice calls are handled by **Bolna**. Bolna's agent runs the call; at the end of
the call, Bolna POSTs the execution data (transcript, extracted_data, costs) to
our **webhook endpoint**. DeepSeek powers the conversational intelligence.

## 2. High-Level Flow

```
Patient calls number (Bolna)  OR  Web chat
        │
        ▼
[Bolna agent] ──(call happens)──►  POST /api/v1/webhook/bolna  (end-of-call data)
        │                                        │
        │                                        ▼
        │                              [call_logs table]
        ▼
[Our backend /api/v1/assistant/chat] ──► [DeepSeek tool-use]
                                          │  decide: check_availability /
                                          │  get_pricing / book_appointment /
                                          │  register_patient / emergency
                                          ▼
                                   [services → repositories → SQLite]
```

- **Outbound calls:** `POST /api/v1/calls` → Bolna `POST /call` → execution_id stored.
- **Inbound calls:** Bolna agent calls our webhook after the call (config-driven; phone number needed from Bolna dashboard).

## 3. Repository Layout

```
bh-ai-assistant/
├── app/
│   ├── main.py                # FastAPI app, middleware, router registration
│   ├── core/
│   │   ├── config.py          # env-driven settings (pydantic-settings)
│   │   └── logging.py         # structured logging (console + rotating file)
│   ├── db/
│   │   ├── database.py        # SQLite connection (WAL mode), migration runner
│   │   ├── models.py          # DDL for all tables
│   │   └── seed.py            # sample doctors for ENT / Ortho / Cardiology
│   ├── repositories/          # thin SQL layer, one file per entity
│   │   ├── doctors.py
│   │   ├── patients.py
│   │   ├── appointments.py
│   │   └── call_logs.py
│   ├── services/              # business logic (no SQL, no HTTP)
│   │   ├── scheduling.py      # availability slot generation, conflict checks
│   │   ├── booking.py         # book / cancel / reschedule
│   │   ├── pricing.py         # consultation + follow-up fee estimates
│   │   ├── patients.py        # register / get / update
│   │   ├── emergency.py       # triage keywords, emergency flagging
│   │   └── ai_assistant.py    # DeepSeek orchestration (tool-use plan)
│   ├── integrations/
│   │   ├── bolna.py           # place call, fetch execution, webhook parse
│   │   └── deepseek.py        # OpenAI-compatible client (pluggable)
│   └── api/
│       ├── routes_doctors.py
│       ├── routes_patients.py
│       ├── routes_appointments.py
│       ├── routes_assistant.py
│       ├── routes_calls.py
│       └── routes_webhook.py
├── tests/                     # pytest: services + API
├── docs/
│   ├── ARCHITECTURE.md        # this file
│   └── DEEPSEEK_PLAN.md       # AI integration plan
├── .env / .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## 4. Database Schema (SQLite, 5 tables)

| Table | Key fields |
|---|---|
| `doctors` | id, name, department (ENT/Orthopedics/Cardiology), qualification, fee, followup_fee, days_available (e.g. "Mon,Wed,Fri"), opd_start, opd_end, active |
| `patients` | id, full_name, phone (UNIQUE), age, gender, created_at |
| `appointments` | id, doctor_id (FK), patient_id (FK), date, time_slot, status (booked/cancelled/completed), reason, source (call/assistant/web), created_at |
| `call_logs` | id, execution_id (UNIQUE), agent_id, status, direction (inbound/outbound), transcript, extracted_data (JSON), telephony_data (JSON), total_cost, duration, emergency_flag, created_at |
| `migrations` | version, applied_at — schema version tracking |

Notes:
- WAL mode for concurrent reads/writes; foreign keys ON.
- `call_logs.execution_id` matches Bolna's `id` field from the webhook payload.
- Emergency: `call_logs.emergency_flag` set when triage matches; appointment is never created.

## 5. Layer Responsibilities (clean separation)

| Layer | Responsibility | Must NOT do |
|---|---|---|
| `api/` (routes) | HTTP in/out, validation (Pydantic), status codes | No business logic, no SQL |
| `services/` | Business rules: availability, pricing, booking flow, triage | No SQL, no HTTP |
| `repositories/` | SQL statements, row ↔ model mapping | No business rules |
| `integrations/` | External APIs: Bolna, DeepSeek | No business rules, no SQL |
| `db/` | Connection lifecycle, schema, migrations, seed | No business logic |

## 6. Bolna Integration (verified against docs)

- **Base URL:** `https://api.bolna.ai`
- **Auth:** `Authorization: Bearer <BOLNA_API_KEY>` (key format `bn-…`, config-driven)
- **Place call:** `POST /call`
  ```json
  {
    "agent_id": "<uuid from .env>",
    "recipient_phone_number": "+91…",
    "user_data": { "patient_name": "…" },
    "retry_config": { "enabled": true, "max_retries": 2 }
  }
  ```
  Response: `{ "status": "queued", "execution_id": "…" }`
- **Track:** `GET /executions/{execution_id}`
- **Webhook:** configured at agent level in Bolna dashboard (not per call).
  - Bolna POSTs on **every status change** → our endpoint must filter and
    process only `status == "completed"` (the terminal event with full data).
  - Payload shape (verified): `id`, `agent_id`, `status`, `transcript`,
    `conversation_duration`, `total_cost`, `user_number`, `agent_number`,
    `extracted_data`, `telephony_data` (incl. `recording_url`, `call_type`,
    `hangup_reason`), `cost_breakdown`, `error_message`.
  - **No HMAC signature.** Verification = source-IP allowlist `13.203.39.153`.
  - Respond `200` fast; Bolna retries on non-2xx/timeout.

## 7. Emergency Triage (safety guardrail)

- Triage keywords: severe chest pain, shortness of breath, radiating arm/jaw
  pain, fainting, sudden paralysis, major trauma, unconsciousness.
- Flow: assistant detects → NEVER creates appointment → returns emergency
  helpline guidance → `call_logs.emergency_flag = true`.
- Exposed as service `emergency.check(message)` + flagged in call webhook processing.

## 8. Logging

- `app/core/logging.py`: structured JSON logs, console + rotating file
  (`logs/app.log`), request-id middleware, log every API call (method, path,
  status, duration) and every service-level action (booking created, etc.).
- Never log secrets (API keys, transcripts flagged sensitive).

## 9. Config (.env)

| Key | Purpose |
|---|---|
| `BOLNA_API_KEY` | Bolna auth (already in `.env`) |
| `DEEPSEEK_API_KEY` | DeepSeek auth (already in `.env`) |
| `BOLNA_AGENT_ID` | Agent UUID — fill later (blank for now) |
| `BOLNA_WEBHOOK_ALLOWED_IP` | 13.203.39.153,13.126.9.249,13.202.133.53 |
| `DATABASE_PATH` | `data/hospital.db` |
| `DEEPSEEK_MODEL` | `deepseek-chat` (default) |

`.env` is git-ignored; `.env.example` committed.

## 10. Build Phases (each = one git commit)

| Phase | Deliverable | Commit |
|---|---|---|
| 0 | Scaffolding: .gitignore, requirements.txt, .env.example, core/config, logging | `chore: scaffold project` |
| 1 | DB layer: database.py, models.py, migrations | `feat: add sqlite db layer and schema` |
| 2 | Seed data: ~8 doctors (ENT/Ortho/Cardio) | `feat: seed sample doctors` |
| 3 | Repositories (4 entities) | `feat: add repository layer` |
| 4 | Services: scheduling, booking, pricing, patients, emergency | `feat: add service layer` |
| 5 | DeepSeek integration (see DEEPSEEK_PLAN.md) | `feat: add deepseek integration` |
| 6 | REST routes: doctors/patients/appointments/emergency | `feat: add rest api routes` |
| 7 | Bolna: place call + webhook endpoint | `feat: add bolna call and webhook` |
| 8 | AI assistant orchestration (tool-use wiring) | `feat: wire ai assistant flow` |
| 9 | Tests + README + logging polish | `test: add tests and docs` |

## 11. Open Items (fill later via .env)

- Bolna `agent_id` + purchased phone number (inbound calls)
- Final decision on DeepSeek integration style (function-calling vs intent JSON) — see DEEPSEEK_PLAN.md
- Actual doctor roster, OPD timings, fee structure
- Emergency helpline number + front-desk fallback number
