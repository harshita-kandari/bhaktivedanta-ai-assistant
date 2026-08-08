import json
import sqlite3
from typing import Optional

CALL_LOG_COLUMNS = (
    "id, execution_id, agent_id, direction, status, recipient_phone, transcript, "
    "extracted_data, telephony_data, total_cost, conversation_duration, "
    "emergency_flag, created_at, updated_at"
)


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    if not row:
        return None
    data = dict(row)
    for key in ("extracted_data", "telephony_data"):
        if data.get(key):
            try:
                data[key] = json.loads(data[key])
            except (TypeError, json.JSONDecodeError):
                pass
    return data


def get_by_execution_id(conn: sqlite3.Connection, execution_id: str) -> Optional[dict]:
    row = conn.execute(
        f"SELECT {CALL_LOG_COLUMNS} FROM call_logs WHERE execution_id = ?", (execution_id,)
    ).fetchone()
    return _row_to_dict(row)


def create_call_log(
    conn: sqlite3.Connection,
    execution_id: str,
    agent_id: str = "",
    direction: str = "outbound",
    status: str = "queued",
    recipient_phone: str = "",
) -> int:
    cursor = conn.execute(
        """INSERT INTO call_logs (execution_id, agent_id, direction, status, recipient_phone)
           VALUES (?, ?, ?, ?, ?)""",
        (execution_id, agent_id, direction, status, recipient_phone),
    )
    conn.commit()
    return cursor.lastrowid


def upsert_call_log(conn: sqlite3.Connection, data: dict) -> int:
    existing = get_by_execution_id(conn, data["execution_id"])
    if existing:
        update_call_log(conn, existing["id"], data)
        return existing["id"]
    return create_call_log(
        conn,
        execution_id=data["execution_id"],
        agent_id=data.get("agent_id", ""),
        direction=data.get("direction", "outbound"),
        status=data.get("status", "queued"),
        recipient_phone=data.get("recipient_phone", ""),
    )


def update_call_log(conn: sqlite3.Connection, call_log_id: int, data: dict) -> bool:
    sets = []
    params: list = []
    for key in (
        "agent_id",
        "direction",
        "status",
        "recipient_phone",
        "transcript",
        "extracted_data",
        "telephony_data",
        "total_cost",
        "conversation_duration",
        "emergency_flag",
    ):
        if key in data and data[key] is not None:
            value = data[key]
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            sets.append(f"{key} = ?")
            params.append(value)
    if not sets:
        return False
    sets.append("updated_at = datetime('now')")
    cursor = conn.execute(
        f"UPDATE call_logs SET {', '.join(sets)} WHERE id = ?", (*params, call_log_id)
    )
    conn.commit()
    return cursor.rowcount > 0
