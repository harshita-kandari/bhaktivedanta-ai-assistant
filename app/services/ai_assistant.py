from dataclasses import dataclass
from typing import Any, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import db_session
from app.integrations.deepseek import (
    DeepSeekClient,
    DeepSeekError,
    SYSTEM_PROMPT,
    build_tool_schemas,
)
from app.repositories import doctors as doctors_repo
from app.services import booking, emergency, patients as patients_service, pricing, scheduling

logger = get_logger(__name__)


class AssistantError(Exception):
    pass


@dataclass
class CallContext:
    origin: str = "chat"
    patient_id: Optional[int] = None
    phone: Optional[str] = None


@dataclass
class AssistantResponse:
    reply: str
    tool_calls: int = 0
    booking_id: Optional[int] = None
    patient_id: Optional[int] = None
    emergency: bool = False
    emergency_guidance: Optional[dict] = None


def _format_slots(result: list[dict]) -> str:
    if not result:
        return "No availability found for the requested doctor or date."
    lines = []
    for item in result:
        slots = ", ".join(item["available_slots"]) if item["available_slots"] else "none"
        lines.append(
            f"{item['doctor_name']} ({item['department']}) on {item['date']} "
            f"[{item['opd_timings']}]: {slots}"
        )
    return "\n".join(lines)


def _format_fee(result: dict) -> str:
    return (
        f"{result['doctor_name']}: consultation fee Rs.{result['consultation_fee']}, "
        f"follow-up Rs.{result['followup_fee']}. {result['note']}"
    )


class ToolExecutor:
    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        logger.info("tool called", extra={"tool": name, "arguments": arguments})
        if name == "list_doctors":
            with db_session() as conn:
                doctors = doctors_repo.list_doctors(conn, department=arguments.get("department"))
            return {
                "doctors": [
                    {
                        "id": d["id"],
                        "name": d["name"],
                        "department": d["department"],
                        "qualification": d["qualification"],
                        "days": d["days_available"],
                        "opd": f"{d['opd_start']} - {d['opd_end']}",
                        "consultation_fee": d["consultation_fee"],
                    }
                    for d in doctors
                ]
            }
        if name == "check_doctor_availability":
            return {
                "result": _format_slots(
                    scheduling.get_upcoming_slots(
                        doctor_name=arguments.get("doctor_name"),
                        department=arguments.get("department"),
                        window_days=7,
                    )
                )
            }
        if name == "get_consultation_fee":
            result = pricing.get_consultation_fee(
                doctor_id=arguments.get("doctor_id"),
                doctor_name=arguments.get("doctor_name"),
            )
            if not result:
                return {"result": "Doctor not found. Please ask the patient for the exact name."}
            return {"result": _format_fee(result)}
        if name == "suggest_alternative_doctor":
            exclude = arguments.get("exclude_doctor_name", "")
            doctors = scheduling.get_upcoming_slots(department=arguments["department"], window_days=7)
            unique = {}
            for d in doctors:
                if d["doctor_name"].lower() == (exclude or "").lower():
                    continue
                unique[d["doctor_name"]] = d
            if not unique:
                return {"result": f"No alternative doctors found in {arguments['department']}."}
            return {
                "result": "\n".join(
                    f"{d['doctor_name']} - next slots: {', '.join(d['available_slots'][:3]) or 'check schedule'}"
                    for d in unique.values()
                )
            }
        if name == "register_patient":
            try:
                patient = patients_service.register_patient(
                    full_name=arguments["full_name"],
                    phone=arguments["phone"],
                    age=arguments.get("age"),
                    gender=arguments.get("gender"),
                )
                self._last_patient_id = patient["id"]
                return {
                    "result": f"Patient registered successfully. Patient ID {patient['id']}, "
                    f"name {patient['full_name']}, phone {patient['phone']}."
                }
            except patients_service.PatientError as exc:
                return {"error": str(exc)}
        if name == "get_patient":
            try:
                patient = patients_service.get_patient_by_phone(arguments["phone"])
            except patients_service.PatientError as exc:
                return {"error": str(exc)}
            if not patient:
                return {"result": "No patient found with that phone number."}
            return {
                "result": f"Patient found: ID {patient['id']}, {patient['full_name']}, "
                f"age {patient['age']}, gender {patient['gender'] or 'unknown'}."
            }
        if name == "book_appointment":
            try:
                appointment = booking.book_appointment(
                    doctor_id=arguments["doctor_id"],
                    patient_id=arguments["patient_id"],
                    appointment_date=arguments["appointment_date"],
                    time_slot=arguments["time_slot"],
                    reason=arguments.get("reason", ""),
                    source="assistant",
                )
                self._last_booking_id = appointment["id"]
                return {
                    "result": (
                        f"Appointment booked successfully. Booking ID {appointment['id']} "
                        f"with {appointment['doctor_name']} on {appointment['appointment_date']} "
                        f"at {appointment['time_slot']}. Consultation fee "
                        f"Rs.{appointment['consultation_fee']}."
                    )
                }
            except booking.BookingError as exc:
                return {"error": str(exc)}
        if name == "flag_emergency":
            return {"result": emergency.emergency_guidance()["message"]}
        return {"error": f"Unknown tool: {name}"}


class AIAssistantService:
    def __init__(self) -> None:
        self.tools = build_tool_schemas()
        self.executor = ToolExecutor()
        self._client: Optional[DeepSeekClient] = None

    def _get_client(self) -> DeepSeekClient:
        if self._client is None:
            self._client = DeepSeekClient()
        return self._client

    def process_message(self, message: str, context: CallContext) -> AssistantResponse:
        pre_emergency = emergency.check_emergency(message)
        if pre_emergency:
            return self._emergency_response(pre_emergency)

        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if context.patient_id:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        f"The current patient has ID {context.patient_id} on the call."
                    ),
                }
            )
        elif context.phone:
            patient = patients_service.get_patient_by_phone(context.phone) if context.phone else None
            if patient:
                messages.append(
                    {
                        "role": "system",
                        "content": (
                            f"The caller is a registered patient: ID {patient['id']}, "
                            f"{patient['full_name']}. Use this patient ID when booking."
                        ),
                    }
                )
        messages.append({"role": "user", "content": message})

        tool_rounds = 0
        booking_id: Optional[int] = None
        patient_id: Optional[int] = context.patient_id
        try:
            client = self._get_client()
            while tool_rounds < settings.max_tool_rounds:
                result = client.chat(messages, tools=self.tools)
                if result["tool_calls"]:
                    for call in result["tool_calls"]:
                        tool_result = self.executor.execute(call["name"], call["arguments"])
                        messages.append(
                            {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": call["id"],
                                        "type": "function",
                                        "function": {
                                            "name": call["name"],
                                            "arguments": json_dumps(call["arguments"]),
                                        },
                                    }
                                ],
                            }
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call["id"],
                                "content": json_dumps(tool_result),
                            }
                        )
                        if tool_result.get("error"):
                            messages.append(
                                {
                                    "role": "user",
                                    "content": (
                                        "Inform the patient of the issue politely and offer the "
                                        "front desk helpline."
                                    ),
                                }
                            )
                        tool_rounds += 1
                        continue
                if result["content"]:
                    final = result["content"]
                    break
                messages.append(
                    {"role": "user", "content": "Please provide a natural language response."}
                )
            else:
                final = (
                    "I'm having trouble processing that right now. Please hold while I "
                    "connect you to our front desk helpline."
                )
        except DeepSeekError as exc:
            logger.error("assistant deepseek failure", extra={"error": str(exc)})
            return AssistantResponse(
                reply=(
                    "I am having trouble retrieving the latest schedule right now. Let me "
                    "connect you directly to our front desk helpline so our staff can assist "
                    "you immediately."
                ),
                emergency=False,
            )

        booking_id = getattr(self.executor, "_last_booking_id", None)
        patient_id = patient_id or getattr(self.executor, "_last_patient_id", None)
        return AssistantResponse(
            reply=final,
            tool_calls=tool_rounds,
            booking_id=booking_id,
            patient_id=patient_id,
            emergency=False,
        )

    def _emergency_response(self, keyword: str) -> AssistantResponse:
        guidance = emergency.emergency_guidance()
        guidance["matched_keyword"] = keyword
        return AssistantResponse(
            reply=guidance["message"],
            emergency=True,
            emergency_guidance=guidance,
        )


def json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, default=str)


assistant_service = AIAssistantService()
