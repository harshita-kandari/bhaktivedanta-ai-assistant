import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class BolnaError(Exception):
    pass


class BolnaClient:
    def __init__(self) -> None:
        if not settings.bolna_api_key:
            raise BolnaError("BOLNA_API_KEY is not configured")
        if not settings.bolna_agent_id:
            raise BolnaError("BOLNA_AGENT_ID is not configured (set in .env)")
        self.base_url = settings.bolna_base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {settings.bolna_api_key}",
            "Content-Type": "application/json",
        }

    def place_call(
        self,
        recipient_phone_number: str,
        user_data: dict | None = None,
        retry_config: dict | None = None,
        from_phone_number: str | None = None,
    ) -> dict:
        body = {
            "agent_id": settings.bolna_agent_id,
            "recipient_phone_number": recipient_phone_number,
        }
        if user_data:
            body["user_data"] = user_data
        if retry_config:
            body["retry_config"] = retry_config
        if from_phone_number:
            body["from_phone_number"] = from_phone_number
        try:
            response = httpx.post(f"{self.base_url}/call", json=body, headers=self.headers, timeout=30)
        except httpx.HTTPError as exc:
            logger.error("bolna place_call transport error", extra={"error": str(exc)})
            raise BolnaError(f"Bolna request failed: {exc}") from exc
        if response.status_code >= 400:
            logger.error(
                "bolna place_call error",
                extra={"status": response.status_code, "body": response.text},
            )
            raise BolnaError(f"Bolna API error {response.status_code}: {response.text}")
        data = response.json()
        logger.info("bolna call placed", extra={"execution_id": data.get("execution_id")})
        return data

    def get_execution(self, execution_id: str) -> dict:
        try:
            response = httpx.get(
                f"{self.base_url}/executions/{execution_id}", headers=self.headers, timeout=30
            )
        except httpx.HTTPError as exc:
            raise BolnaError(f"Bolna request failed: {exc}") from exc
        if response.status_code >= 400:
            raise BolnaError(f"Bolna API error {response.status_code}: {response.text}")
        return response.json()


def parse_webhook_payload(payload: dict) -> dict:
    telephony = payload.get("telephony_data") or {}
    return {
        "execution_id": payload.get("id", ""),
        "agent_id": payload.get("agent_id", ""),
        "status": payload.get("status", "unknown"),
        "direction": "inbound" if telephony.get("call_type") == "inbound" else "outbound",
        "recipient_phone": payload.get("user_number", ""),
        "transcript": payload.get("transcript"),
        "extracted_data": payload.get("extracted_data"),
        "telephony_data": payload,
        "total_cost": payload.get("total_cost", 0),
        "conversation_duration": payload.get("conversation_duration", 0)
        or telephony.get("duration", 0),
        "error_message": payload.get("error_message"),
    }
