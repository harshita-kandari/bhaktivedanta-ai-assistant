# DeepSeek Integration Plan

**Status:** Design decided, implementation deferred (user: "will be determined later, just create a plan to use it")
**Model default:** `deepseek-chat` (OpenAI-compatible API at `https://api.deepseek.com`)

## 1. Decision

Two candidate designs were proposed; the recommended one is **OpenAI-style
function calling (tool_use)** because it lets the model itself decide when to
query the DB, making the flow robust and extensible.

> User decision: **not determined yet** — this doc captures the recommended
> plan and the swap path so the interface is approach-agnostic.

## 2. Interface (approach-agnostic)

The assistant service exposes ONE entry point regardless of internals:

```python
# services/ai_assistant.py
class AIAssistantService:
    def process_message(self, message: str, context: CallContext) -> AssistantResponse:
        ...
```

`CallContext`: patient identity (or none), department preference, origin
(call/chat). `AssistantResponse`: natural-language reply + side effects
(booking created?, patient registered?, emergency flag?).

Implementations behind this interface:
- `FunctionCallingAssistant` (recommended — §3)
- `IntentJsonAssistant` (fallback — §4)

The choice is a config flag `DEEPSEEK_MODE=function_calling|intent_json`.

## 3. Recommended: Function Calling (tool_use)

### 3.1 Tools exposed to the model

| Tool | Purpose | Returns |
|---|---|---|
| `check_doctor_availability(doctor_name?, department?, date)` | Schedules & next slots | doctor, day, free slots |
| `list_doctors(department)` | Roster incl. qualifications & days | doctor list |
| `get_consultation_fee(doctor_id)` | Consult + follow-up fee | fee, followup_fee |
| `suggest_alternative(doctor_name, department, date)` | Same-department alternatives | doctor list |
| `book_appointment(doctor_id, patient_id, date, time_slot, reason)` | Creates booking | appointment id + confirmation |
| `register_patient(name, phone, age, gender)` | New patient | patient id |
| `get_patient(phone)` | Lookup existing patient | patient or none |
| `flag_emergency(symptoms)` | Never books; returns helpline info | emergency message + flag |

### 3.2 Message loop (single turn, max 4 iterations)

1. Send `system_prompt` + user message + tool schemas to
   `chat/completions` (`tool_choice: "auto"`).
2. If response is a tool call → execute tool via service layer, append
   `tool` message with result, re-send.
3. If plain text → that's the final reply. Stop.
4. Guard: max 4 tool rounds, then force a natural-language reply.

### 3.3 Safety rules baked into the system prompt

- If `flag_emergency` matches → do **not** call `book_appointment`; reply with
  emergency guidance.
- Patient identity: if no patient found for phone, assistant must call
  `register_patient` before `book_appointment`.
- Confirm booking with patient before finalizing (assistant-side confirmation
  question).
- Never invent doctor names/fees — only use tool results; if lookup returns
  empty, give front-desk fallback message.

## 4. Fallback: Intent JSON

Single prompt asks for JSON:

```json
{ "intent": "book", "doctor": "Dr. Sharma", "dept": "ortho",
  "date": "2026-08-10", "patient": { "name": "...", "phone": "..." } }
```

Server maps intent → service call. Brittle for multi-step (needs booking
confirmation flow), hence the fallback role.

## 5. Config

```env
DEEPSEEK_API_KEY=sk-...            # already in .env
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODE=function_calling     # or intent_json
MAX_TOOL_ROUNDS=4
```

## 6. Dependencies

- `openai` Python SDK (DeepSeek is OpenAI-compatible) or plain `httpx` client.
  Choice: `openai` SDK with `base_url` override — less code, standard tool-use
  support.

## 7. Swap path

Because everything sits behind `AIAssistantService.process_message`, swapping
function-calling ↔ intent-JSON (or a future hosted agent like Bolna's LLM) is a
one-file change + config flip. No route/service changes required.

## 8. Testing plan (when implemented)

- Unit: fake tool executor, canned model responses (both modes).
- Integration: real DeepSeek call with a scripted booking conversation.
- Assert: booking created, patient registered, emergency never books.
