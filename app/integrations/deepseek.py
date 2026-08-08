import json
from typing import Any, Optional

from openai import OpenAI

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

ToolSchema = dict[str, Any]
ToolResult = dict[str, Any]


class DeepSeekError(Exception):
    pass


class DeepSeekClient:
    def __init__(self) -> None:
        if not settings.deepseek_api_key:
            raise DeepSeekError("DEEPSEEK_API_KEY is not configured")
        self._client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        self.model = settings.deepseek_model

    def chat(
        self,
        messages: list[dict[str, str]],
        tools: Optional[list[ToolSchema]] = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            response = self._client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            return {
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments or "{}"),
                    }
                    for tc in (message.tool_calls or [])
                ],
            }
        except Exception as exc:
            logger.error("deepseek api error", extra={"error": str(exc)})
            raise DeepSeekError(f"DeepSeek API error: {exc}") from exc


def build_tool_schemas() -> list[ToolSchema]:
    return [
        {
            "type": "function",
            "function": {
                "name": "list_doctors",
                "description": "List doctors in a department (ENT, Orthopedics, Cardiology).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "department": {"type": "string", "enum": ["ENT", "Orthopedics", "Cardiology"]}
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "check_doctor_availability",
                "description": "Check a doctor's available slots on a given date.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "doctor_name": {"type": "string"},
                        "department": {"type": "string", "enum": ["ENT", "Orthopedics", "Cardiology"]},
                        "date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_consultation_fee",
                "description": "Get consultation and follow-up fees for a doctor.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "doctor_name": {"type": "string"},
                        "doctor_id": {"type": "integer"},
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "suggest_alternative_doctor",
                "description": "Suggest alternative doctors in the same department.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "department": {"type": "string", "enum": ["ENT", "Orthopedics", "Cardiology"]},
                        "exclude_doctor_name": {"type": "string"},
                    },
                    "required": ["department"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "register_patient",
                "description": "Register a new patient. Call this before booking if the patient is unknown.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "full_name": {"type": "string"},
                        "phone": {"type": "string"},
                        "age": {"type": "integer"},
                        "gender": {"type": "string", "enum": ["male", "female", "other"]},
                    },
                    "required": ["full_name", "phone"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_patient",
                "description": "Look up an existing patient by phone number.",
                "parameters": {
                    "type": "object",
                    "properties": {"phone": {"type": "string"}},
                    "required": ["phone"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "book_appointment",
                "description": "Book an appointment for a patient with a doctor. Confirm details with the patient first.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "doctor_id": {"type": "integer"},
                        "patient_id": {"type": "integer"},
                        "appointment_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                        "time_slot": {"type": "string", "description": "HH:MM"},
                        "reason": {"type": "string"},
                    },
                    "required": ["doctor_id", "patient_id", "appointment_date", "time_slot"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "flag_emergency",
                "description": "Use when the patient describes life-threatening symptoms. Never book appointments in this case.",
                "parameters": {
                    "type": "object",
                    "properties": {"symptoms": {"type": "string"}},
                    "required": ["symptoms"],
                },
            },
        },
    ]


SYSTEM_PROMPT = """You are "Bhakti", the virtual patient care assistant for Bhaktivedanta Hospital & Research Institute.

Your responsibilities:
1. Answer questions about doctors: names, qualifications, departments, OPD timings and availability.
2. Suggest alternative doctors in the same department when a preferred doctor is unavailable.
3. Provide consultation fee estimates. Fees cover the OPD visit only; tests are billed separately.
4. Book appointments for ENT, Orthopedics and Cardiology, and register new patients.
5. Never diagnose, prescribe, or interpret lab results. Always advise consulting a qualified physician.

Booking flow:
- If the patient is unknown, register them first (full name + phone; ask for age and gender too).
- Confirm the appointment details with the patient before booking.
- If a preferred doctor is unavailable, proactively suggest an alternative with a specific time slot.

Emergency safety rule (STRICT):
- If the patient reports severe chest pain, shortness of breath, radiating pain to arm or jaw,
  fainting, unconsciousness, sudden paralysis, or major trauma: call flag_emergency and DO NOT
  book an appointment. Direct them to the 24/7 Emergency / Casualty department.

Use only data returned by tools. Never invent doctor names, fees, or availability.
If a lookup returns nothing, say you are unable to find the details and offer the front desk helpline."""

DEFAULT_HISTORY_CONTEXT = 10


def build_system_messages(extra_context: Optional[dict] = None) -> list[dict[str, str]]:
    return [{"role": "system", "content": SYSTEM_PROMPT}]
