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
- Web app: http://127.0.0.1:8000/ — booking form, chat and microphone
- Health check: http://127.0.0.1:8000/health
- Doctors are auto-seeded on first run (8 sample doctors).

## Web app

The page at `/` uses the same API:

- **Form:** pick a doctor and date, see real free slots, book with name and phone.
  Returning phone numbers are reused, not duplicated.
- **Chat:** plain English. The browser sends recent turns as `history`, so
  follow-ups like "is she free?" keep their context.
- **Voice:** the 🎤 button uses the browser's speech recognition; replies are
  spoken with speech synthesis. Chrome and Safari support it; Firefox does not.
- **Confirmations:** the card shows the appointment id, doctor, date, time and
  fee, and the booked slot disappears from the list.

## Environment (.env)

| Variable | Purpose |
|---|---|
| `BOLNA_API_KEY` | Bolna auth (Bearer token, `bn-...`) |
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `BOLNA_AGENT_ID` | Bolna agent UUID (needed for outbound calls) |
| `BOLNA_WEBHOOK_ALLOWED_IP` | Comma-separated Bolna webhook source IPs |
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
| `POST /voice/book` | Book by doctor name + patient phone (voice agent; auto-registers patient) |
| `POST /emergency/check` | Triage check |
| `GET /emergency/info` | Emergency guidance |
| `POST /assistant/chat` | AI assistant (DeepSeek tool-use) |
| `POST /calls` | Place outbound Bolna call (needs `BOLNA_AGENT_ID`) |
| `POST /webhook/bolna` | Bolna end-of-call webhook (IP allowlisted) |

## Bolna webhook notes

- Bolna POSTs on every status change; only `completed` carries the full payload.
- Payloads are stored in `call_logs` (upsert by `execution_id`).
- No HMAC signature exists; requests from any IP other than the Bolna source IPs
  are rejected with 403. Bolna sends from `13.203.39.153`, `13.126.9.249` and
  `13.202.133.53`; configure them (comma-separated) in `BOLNA_WEBHOOK_ALLOWED_IP`.
- Behind a tunnel, the immediate peer is the loopback tunnel, so the original
  address is read from `X-Forwarded-For`.

## Voice agent wiring (Bolna)

`scripts/wire_bolna.py` connects the live phone agent to this backend:

```bash
# 1. Expose the backend publicly (the demo setup reuses an ngrok tunnel on :8000)
ngrok http 8000

# 2. Point the agent at the tunnel and install tools + prompt
.venv/bin/python scripts/wire_bolna.py --public-base-url https://<your-tunnel-host>
```

The script is idempotent. It backs up the current agent JSON to `data/`, then:

- adds five custom function tools: `list_doctors`, `check_availability`,
  `get_doctor_fee`, `book_appointment` (uses `/voice/book`) and `emergency_check`;
- sets the agent `webhook_url` to `<public-base-url>/api/v1/webhook/bolna`;
- installs the tool-driven "Bhakti" system prompt.

Use `--dry-run` to print the payload without changing the agent. Bolna blocks
private/loopback tool URLs, so the public URL must be reachable from the
internet. Re-running the script is enough after a tunnel URL changes.

## Runtime notes

- `DEEPSEEK_*` can point at any OpenAI-compatible endpoint. The demo config
  serves `deepseek-v4.1-flash-1017-fast` through Isoquant (`DEEPSEEK_BASE_URL`
  and `DEEPSEEK_API_KEY`), which supports tool calling.
- Voice agent LLM/TTS/STT stay on Bolna's managed stack (Azure GPT-4.1 mini,
  ElevenLabs, Deepgram); the tools above are what connect it to hospital data.

## Phone calls (Bolna)

The page has a **Prefer a phone call?** card: enter a number, confirm, and Bolna
rings it. The agent can check slots, quote fees and book during the call.

Same thing over the API:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/calls \
  -H 'Content-Type: application/json' \
  -d '{"recipient_phone_number":"+919876543210"}'
```

- The post-call webhook stores transcript, extracted data and cost in `call_logs`.
- Webhook source IPs are allowlisted; behind a tunnel the real IP is read from
  `X-Forwarded-For`.
- Bolna blocks private tool URLs, so the server must stay reachable through the
  tunnel. Re-run `scripts/wire_bolna.py --public-base-url <url>` if it changes.
- Outbound calls use the account's telephony caller ID; inbound calling needs a
  Bolna number assigned to the agent.

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
