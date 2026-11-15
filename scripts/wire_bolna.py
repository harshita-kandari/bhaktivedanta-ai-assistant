#!/usr/bin/env python
"""Wire the Bolna voice agent to this backend.

Adds custom function tools (doctors, availability, fees, booking, emergency),
points the agent's post-call webhook at this service, and installs a
tool-driven system prompt for "Bhakti".

Usage:
    .venv/bin/python scripts/wire_bolna.py --public-base-url https://<tunnel-host>
    .venv/bin/python scripts/wire_bolna.py --dry-run     # print config only

The public base URL must be reachable from the internet: Bolna validates the
tool URLs and blocks private/loopback addresses before calling them.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings  # noqa: E402

DEPARTMENTS = ["ENT", "Orthopedics", "Cardiology"]
TIMEOUT = 30.0


def build_prompt() -> str:
    helpline = settings.emergency_helpline or "108"
    front_desk = settings.front_desk_phone or "the hospital front desk"
    return f"""# ROLE
You are "Bhakti", the patient care assistant for Bhaktivedanta Hospital & Research Institute,
speaking on a live phone call. Your tone is warm, calm, polite and reassuring.

# VOICE STYLE (STRICT)
- Speak in short, natural sentences. One idea per sentence, at most two sentences per turn.
- Never read out lists, tables, markdown, brackets or symbols. Say fees as "six hundred rupees".
- Never spell out dates in digits when speaking; say "Monday, the sixteenth of November".
- Ask one question at a time and wait for the answer.
- The current date and time are given to you below; use them to resolve "today" and "tomorrow".

# TOOLS - ALWAYS USE THEM, NEVER INVENT DATA
- list_doctors(department): doctors, their OPD days/timings and consultation fee.
- check_availability(doctor_name, appointment_date): free slots for one doctor on one date.
- get_doctor_fee(doctor_name): consultation and follow-up fee for one doctor.
- book_appointment(full_name, phone, doctor_name, appointment_date, time_slot): creates the booking.
- emergency_check(symptoms): emergency triage. Use it before saying anything else when the caller
  describes a possible emergency.

Only state facts that came back from a tool. Never invent doctor names, fees, slots or booking ids.

# BOOKING FLOW
1. Ask which department and the reason for the visit (ENT, Orthopedics or Cardiology).
2. Offer a doctor from list_doctors, or use the doctor the caller names.
3. Ask for the date. Call check_availability and offer one or two specific free slots.
4. Collect the patient's full name, age, gender and phone number, one question at a time
   (read the phone number back digit by digit).
5. Call get_doctor_fee if the caller asks about cost, otherwise quote the fee returned by the tool.
6. Read back doctor, date, time and fee, and get an explicit "yes".
7. Call book_appointment. Only after it succeeds, confirm the appointment id, doctor, date and time.
If a tool returns an error, apologise once, offer another slot or doctor, and never claim success.

# EMERGENCY (STRICT SAFETY RULE)
If the caller mentions severe chest pain, shortness of breath, fainting, unconsciousness,
sudden paralysis, stroke, heavy bleeding, major trauma or a seizure:
1. Call emergency_check(symptoms) immediately.
2. Tell them to go to the 24/7 Emergency / Casualty department right away, or call {helpline}.
3. Do NOT book an OPD appointment and do not continue the booking flow.

# BOUNDARIES
- Never diagnose, prescribe, or interpret reports. Advise seeing a doctor for medical advice.
- Fees cover the OPD consultation only; tests and procedures are billed separately.
- If you cannot help, offer {front_desk} instead of guessing.
"""


def _function(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    # Bolna's API expects the flat (legacy) OpenAI tool description shape here.
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def _text(description: str) -> dict[str, str]:
    return {"type": "string", "description": description}


def build_api_tools(public_base_url: str) -> dict[str, Any]:
    base = public_base_url.rstrip("/")
    api = f"{base}/api/v1"

    tools = [
        _function(
            "custom_task_list_doctors",
            "Look up the hospital's doctors in a department, including OPD days, timings and "
            "consultation fee. Use when the caller asks which doctors are available, wants a "
            "specialist, or asks about a doctor's schedule.",
            {
                "department": {
                    "type": "string",
                    "enum": DEPARTMENTS,
                    "description": "Department: ENT, Orthopedics or Cardiology",
                }
            },
            ["department"],
        ),
        _function(
            "custom_task_check_availability",
            "Check free appointment slots for one doctor on one date. Use before offering or "
            "confirming any appointment time.",
            {
                "doctor_name": _text("Doctor's name, for example 'Dr. Anita Desai'"),
                "appointment_date": _text("Date in YYYY-MM-DD format"),
            },
            ["doctor_name", "appointment_date"],
        ),
        _function(
            "custom_task_get_doctor_fee",
            "Get the consultation and follow-up fee for one doctor. Use when the caller asks what "
            "a visit costs.",
            {"doctor_name": _text("Doctor's name")},
            ["doctor_name"],
        ),
        _function(
            "custom_task_book_appointment",
            "Create an appointment for the caller. Only call after the caller has confirmed the "
            "doctor, date and time. Requires the patient's full name, age, gender and phone number.",
            {
                "full_name": _text("Patient's full name"),
                "age": {
                    "type": "integer",
                    "description": "Patient's age in years",
                },
                "gender": {
                    "type": "string",
                    "enum": ["male", "female", "other"],
                    "description": "Patient's gender",
                },
                "phone": _text("Patient's phone number with country code if possible"),
                "doctor_name": _text("Doctor's name"),
                "appointment_date": _text("Date in YYYY-MM-DD format"),
                "time_slot": _text("Time in 24-hour HH:MM format, for example 10:30"),
            },
            [
                "full_name",
                "age",
                "gender",
                "phone",
                "doctor_name",
                "appointment_date",
                "time_slot",
            ],
        ),
        _function(
            "custom_task_emergency_check",
            "Emergency triage for life-threatening symptoms such as severe chest pain, breathing "
            "difficulty, fainting or heavy bleeding. Call it first and never book an OPD slot.",
            {"symptoms": _text("What the caller said, in their own words")},
            ["symptoms"],
        ),
    ]

    tools_params = {
        "custom_task_list_doctors": {
            "method": "GET",
            "url": f"{api}/doctors",
            "param": {"department": "%(department)s"},
            "headers": {},
            "pre_call_message": "Let me check our doctors for you.",
        },
        "custom_task_check_availability": {
            "method": "GET",
            "url": f"{api}/doctors/availability",
            "param": {
                "doctor_name": "%(doctor_name)s",
                "date": "%(appointment_date)s",
            },
            "headers": {},
            "pre_call_message": "Let me look at the schedule for you.",
        },
        "custom_task_get_doctor_fee": {
            "method": "GET",
            "url": f"{api}/doctors/fees",
            "param": {"doctor_name": "%(doctor_name)s"},
            "headers": {},
            "pre_call_message": "Let me check the consultation fee.",
        },
        "custom_task_book_appointment": {
            "method": "POST",
            "url": f"{api}/voice/book",
            "param": {
                "full_name": "%(full_name)s",
                "age": "%(age)s",
                "gender": "%(gender)s",
                "phone": "%(phone)s",
                "doctor_name": "%(doctor_name)s",
                "appointment_date": "%(appointment_date)s",
                "time_slot": "%(time_slot)s",
            },
            "headers": {},
            "pre_call_message": "I am booking that appointment for you now.",
        },
        "custom_task_emergency_check": {
            "method": "POST",
            "url": f"{api}/emergency/check",
            "param": {"message": "%(symptoms)s"},
            "headers": {},
            "pre_call_message": "This sounds serious, let me guide you right away.",
        },
    }
    return {"tools": tools, "tools_params": tools_params}


def build_agent_config(current: dict[str, Any], public_base_url: str) -> dict[str, Any]:
    base = public_base_url.rstrip("/")
    config: dict[str, Any] = {
        "agent_name": current.get("agent_name") or "Hospital appointment",
        "agent_welcome_message": current.get(
            "agent_welcome_message",
            "Hello and welcome to Bhaktivedanta Hospital. How may I help you today?",
        ),
        "agent_type": current.get("agent_type") or "other",
        "webhook_url": f"{base}/api/v1/webhook/bolna",
        "tasks": [],
    }
    for task in current.get("tasks", []):
        tasks_config = task.get("tools_config") or {}
        tasks_config["api_tools"] = build_api_tools(base)
        config["tasks"].append(
            {
                "task_type": task.get("task_type", "conversation"),
                "toolchain": task.get("toolchain"),
                "task_config": task.get("task_config"),
                "tools_config": tasks_config,
            }
        )
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--public-base-url",
        required=True,
        help="Public https URL that tunnels to this backend, e.g. https://abc.ngrok-free.dev",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the payload without sending")
    args = parser.parse_args()

    if not settings.bolna_api_key or not settings.bolna_agent_id:
        print("BOLNA_API_KEY and BOLNA_AGENT_ID must be set in .env", file=sys.stderr)
        return 1

    base_url = args.public_base_url.rstrip("/")
    headers = {
        "Authorization": f"Bearer {settings.bolna_api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=TIMEOUT) as client:
        agent_resp = client.get(
            f"{settings.bolna_base_url}/agent/{settings.bolna_agent_id}", headers=headers
        )
        agent_resp.raise_for_status()
        current = agent_resp.json()

        payload = {
            "agent_config": build_agent_config(current, base_url),
            "agent_prompts": {"task_1": {"system_prompt": build_prompt()}},
        }

        backup_dir = BASE_DIR / "data"
        backup_dir.mkdir(exist_ok=True)
        backup = backup_dir / (
            f"bolna_agent_{settings.bolna_agent_id}_{datetime.now():%Y%m%d_%H%M%S}.json"
        )
        backup.write_text(json.dumps(current, indent=2))
        print(f"Backed up current agent config to {backup}")

        if args.dry_run:
            print(json.dumps(payload, indent=2))
            return 0

        update = client.put(
            f"{settings.bolna_base_url}/v2/agent/{settings.bolna_agent_id}",
            headers=headers,
            json=payload,
        )
        if update.status_code >= 400:
            print(f"Bolna rejected the update ({update.status_code}): {update.text}", file=sys.stderr)
            return 1
        print(f"Bolna update accepted: {update.text}")

        verify_resp = client.get(
            f"{settings.bolna_base_url}/agent/{settings.bolna_agent_id}", headers=headers
        )
        verify_resp.raise_for_status()
        updated = verify_resp.json()

    tools_config = (updated.get("tasks") or [{}])[0].get("tools_config") or {}
    api_tools = tools_config.get("api_tools") or {}
    tool_names = sorted((api_tools.get("tools_params") or {}).keys())
    webhook = updated.get("webhook_url")

    print(f"Webhook: {webhook}")
    print(f"Tools: {', '.join(tool_names) or 'none'}")

    ok = webhook == f"{base_url}/api/v1/webhook/bolna" and len(tool_names) == 5
    if not ok:
        print("Verification failed: agent config does not match what was sent", file=sys.stderr)
        return 1
    print("Agent wired successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
