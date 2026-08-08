import sqlite3
from typing import Optional

PATIENT_COLUMNS = "id, full_name, phone, age, gender, created_at"


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    return dict(row) if row else None


def get_patient_by_id(conn: sqlite3.Connection, patient_id: int) -> Optional[dict]:
    row = conn.execute(
        f"SELECT {PATIENT_COLUMNS} FROM patients WHERE id = ?", (patient_id,)
    ).fetchone()
    return _row_to_dict(row)


def get_patient_by_phone(conn: sqlite3.Connection, phone: str) -> Optional[dict]:
    row = conn.execute(
        f"SELECT {PATIENT_COLUMNS} FROM patients WHERE phone = ?", (phone,)
    ).fetchone()
    return _row_to_dict(row)


def list_patients(conn: sqlite3.Connection, limit: int = 100, offset: int = 0) -> list[dict]:
    rows = conn.execute(
        f"SELECT {PATIENT_COLUMNS} FROM patients ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def create_patient(
    conn: sqlite3.Connection, full_name: str, phone: str, age: Optional[int], gender: Optional[str]
) -> int:
    cursor = conn.execute(
        """INSERT INTO patients (full_name, phone, age, gender) VALUES (?, ?, ?, ?)""",
        (full_name, phone, age, gender),
    )
    conn.commit()
    return cursor.lastrowid
