import sqlite3
from typing import Optional

APPOINTMENT_COLUMNS = (
    "id, doctor_id, patient_id, appointment_date, time_slot, status, reason, source, created_at"
)


def get_appointment_by_id(conn: sqlite3.Connection, appointment_id: int) -> Optional[dict]:
    row = conn.execute(
        f"SELECT {APPOINTMENT_COLUMNS} FROM appointments WHERE id = ?", (appointment_id,)
    ).fetchone()
    return dict(row) if row else None


def list_appointments(
    conn: sqlite3.Connection,
    doctor_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    query = f"SELECT {APPOINTMENT_COLUMNS} FROM appointments"
    params: list = []
    conditions = []
    if doctor_id:
        conditions.append("doctor_id = ?")
        params.append(doctor_id)
    if patient_id:
        conditions.append("patient_id = ?")
        params.append(patient_id)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY appointment_date, time_slot LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def booked_slots(
    conn: sqlite3.Connection, doctor_id: int, appointment_date: str
) -> set[str]:
    rows = conn.execute(
        """SELECT time_slot FROM appointments
           WHERE doctor_id = ? AND appointment_date = ? AND status = 'booked'""",
        (doctor_id, appointment_date),
    ).fetchall()
    return {r["time_slot"] for r in rows}


def create_appointment(
    conn: sqlite3.Connection,
    doctor_id: int,
    patient_id: int,
    appointment_date: str,
    time_slot: str,
    reason: str = "",
    source: str = "assistant",
) -> int:
    cursor = conn.execute(
        """INSERT INTO appointments (doctor_id, patient_id, appointment_date, time_slot, reason, source)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (doctor_id, patient_id, appointment_date, time_slot, reason, source),
    )
    conn.commit()
    return cursor.lastrowid


def update_appointment_status(
    conn: sqlite3.Connection, appointment_id: int, status: str
) -> bool:
    cursor = conn.execute(
        "UPDATE appointments SET status = ? WHERE id = ?", (status, appointment_id)
    )
    conn.commit()
    return cursor.rowcount > 0
