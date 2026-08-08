import sqlite3
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

DOCTOR_COLUMNS = (
    "id, name, department, qualification, consultation_fee, followup_fee, "
    "days_available, opd_start, opd_end, slot_minutes, active, created_at"
)


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    return dict(row) if row else None


def get_doctor_by_id(conn: sqlite3.Connection, doctor_id: int) -> Optional[dict]:
    row = conn.execute(
        f"SELECT {DOCTOR_COLUMNS} FROM doctors WHERE id = ?", (doctor_id,)
    ).fetchone()
    return _row_to_dict(row)


def get_doctor_by_name(conn: sqlite3.Connection, name: str) -> Optional[dict]:
    row = conn.execute(
        f"SELECT {DOCTOR_COLUMNS} FROM doctors WHERE name = ? COLLATE NOCASE LIMIT 1",
        (name,),
    ).fetchone()
    return _row_to_dict(row)


def list_doctors(
    conn: sqlite3.Connection, department: Optional[str] = None, active_only: bool = True
) -> list[dict]:
    query = f"SELECT {DOCTOR_COLUMNS} FROM doctors"
    params: list = []
    conditions = []
    if department:
        conditions.append("department = ?")
        params.append(department)
    if active_only:
        conditions.append("active = 1")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY department, name"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def create_doctor(conn: sqlite3.Connection, data: dict) -> int:
    cursor = conn.execute(
        """INSERT INTO doctors (
               name, department, qualification, consultation_fee, followup_fee,
               days_available, opd_start, opd_end, slot_minutes, active
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["name"],
            data["department"],
            data.get("qualification", ""),
            data.get("consultation_fee", 0),
            data.get("followup_fee", 0),
            data.get("days_available", "Mon,Tue,Wed,Thu,Fri,Sat"),
            data.get("opd_start", "09:00"),
            data.get("opd_end", "20:00"),
            data.get("slot_minutes", 30),
            data.get("active", 1),
        ),
    )
    conn.commit()
    return cursor.lastrowid
