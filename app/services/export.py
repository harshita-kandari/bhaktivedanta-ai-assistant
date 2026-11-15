"""Build an Excel workbook from the hospital database.

Used by the `/api/v1/export/calls.xlsx` download and by
`scripts/export_call_data.py`.

Excel is a report, not the live store: SQLite remains the source of truth.
"""

import json
from datetime import datetime
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.core.config import settings
from app.db.database import db_session

EXCEL_CELL_LIMIT = 32_000
HEADER_FILL = PatternFill("solid", fgColor="0F766E")
HEADER_FONT = Font(color="FFFFFF", bold=True)


def _clip(value, limit: int = EXCEL_CELL_LIMIT):
    if value is None:
        return ""
    text = str(value)
    return text if len(text) <= limit else text[:limit] + " …[truncated]"


def _call_type(telephony_data) -> str:
    if not telephony_data:
        return ""
    try:
        data = json.loads(telephony_data) if isinstance(telephony_data, str) else telephony_data
        return str(data.get("call_type", ""))
    except (ValueError, AttributeError):
        return ""


def _as_json(value):
    if not value:
        return {}
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return {}


def _search(data, keys: set[str], depth: int = 0) -> str:
    """Find the first non-empty value for any of these key names, nested or not."""
    if depth > 6:
        return ""
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in keys and isinstance(value, (str, int, float)):
                text = str(value).strip()
                if text:
                    return text
        for value in data.values():
            found = _search(value, keys, depth + 1)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _search(item, keys, depth + 1)
            if found:
                return found
    return ""


NAME_KEYS = {"patient_name", "patient", "full_name", "name", "caller_name"}
DOCTOR_KEYS = {"doctor", "doctor_name", "preferred_doctor", "specialist"}
REASON_KEYS = {"reason", "requirement", "symptoms", "purpose", "concern", "issue"}
DATE_KEYS = {"appointment_date", "date", "preferred_date"}
TIME_KEYS = {"time_slot", "time", "preferred_time"}
LINK_WINDOW_SECONDS = 900


def _parse_datetime(value):
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _match_by_time(call, candidates, used):
    """Fallback link: a call booking made within 15 minutes of the call.

    The caller often gives a different phone number than the one dialled, so
    matching on phone alone misses real bookings.
    """
    call_time = _parse_datetime(call.get("created_at"))
    if call_time is None:
        return {}
    best, best_delta = None, None
    for appointment in candidates:
        if appointment["id"] in used:
            continue
        appointment_time = _parse_datetime(appointment.get("created_at"))
        if appointment_time is None:
            continue
        delta = abs((appointment_time - call_time).total_seconds())
        if delta <= LINK_WINDOW_SECONDS and (best_delta is None or delta < best_delta):
            best, best_delta = appointment, delta
    if best is not None:
        used.add(best["id"])
    return best or {}


def _add_sheet(workbook, title, headers, rows, widths, wrap_columns=()):
    sheet = workbook.create_sheet(title)
    sheet.append(headers)
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center")
    for row in rows:
        sheet.append(row)
    sheet.freeze_panes = "A2"
    if rows:
        sheet.auto_filter.ref = sheet.dimensions
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column in wrap_columns)
    return sheet


def build_workbook() -> Workbook:
    with db_session() as conn:
        calls = [dict(row) for row in conn.execute("SELECT * FROM call_logs ORDER BY id DESC")]
        appointments = [
            dict(row)
            for row in conn.execute(
                """
                SELECT a.id, d.name AS doctor, d.department, p.full_name AS patient,
                       p.phone, a.appointment_date, a.time_slot, a.status, a.source,
                       a.reason, d.consultation_fee, a.created_at
                FROM appointments a
                JOIN doctors d ON d.id = a.doctor_id
                JOIN patients p ON p.id = a.patient_id
                ORDER BY a.id DESC
                """
            )
        ]
        doctors = [dict(row) for row in conn.execute("SELECT * FROM doctors ORDER BY name")]
        patients = [dict(row) for row in conn.execute("SELECT * FROM patients ORDER BY id DESC")]

    workbook = Workbook()
    summary = workbook.active
    summary.title = "Summary"

    completed = [call for call in calls if call["status"] == "completed"]
    talk_seconds = sum(float(call.get("conversation_duration") or 0) for call in calls)
    total_cost = sum(float(call.get("total_cost") or 0) for call in calls)
    emergencies = sum(1 for call in calls if call.get("emergency_flag"))

    summary_rows = [
        ("Generated at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("Total calls", len(calls)),
        ("Completed calls", len(completed)),
        ("Total talk time (minutes)", round(talk_seconds / 60, 1)),
        ("Total call cost (INR)", round(total_cost, 2)),
        ("Emergency flagged calls", emergencies),
        ("Appointments", len(appointments)),
        ("Patients", len(patients)),
        ("Doctors", len(doctors)),
    ]
    summary.append(["Metric", "Value"])
    for cell in summary[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
    for row in summary_rows:
        summary.append(list(row))
    summary.column_dimensions["A"].width = 32
    summary.column_dimensions["B"].width = 24
    summary.freeze_panes = "A2"

    by_phone = {}
    for appointment in appointments:  # newest first
        if appointment.get("source") == "call":
            by_phone.setdefault(appointment["phone"], appointment)

    call_bookings = [item for item in appointments if item.get("source") == "call"]
    used_bookings: set[int] = set()

    call_rows = []
    for call in calls:
        appointment = {}
        if call["status"] == "completed":
            # Prefer a booking made within 15 minutes of the call; the caller
            # often gives a number different from the one dialled.
            appointment = _match_by_time(call, call_bookings, used_bookings)
            if not appointment:
                candidate = by_phone.get(call["recipient_phone"])
                if candidate and candidate["id"] not in used_bookings:
                    used_bookings.add(candidate["id"])
                    appointment = candidate
        extracted = _as_json(call.get("extracted_data"))
        call_rows.append(
            [
                call["id"],
                call["execution_id"],
                call["status"],
                call["direction"],
                call["recipient_phone"],
                appointment.get("patient") or _search(extracted, NAME_KEYS),
                appointment.get("doctor") or _search(extracted, DOCTOR_KEYS),
                appointment.get("reason") or _search(extracted, REASON_KEYS),
                appointment.get("appointment_date") or _search(extracted, DATE_KEYS),
                appointment.get("time_slot") or _search(extracted, TIME_KEYS),
                float(call.get("conversation_duration") or 0),
                float(call.get("total_cost") or 0),
                "YES" if call.get("emergency_flag") else "",
                call["created_at"],
                _clip(call.get("transcript")),
                _clip(call.get("extracted_data")),
            ]
        )

    _add_sheet(
        workbook,
        "Calls",
        [
            "ID",
            "Execution ID",
            "Status",
            "Direction",
            "Phone",
            "Patient",
            "Doctor",
            "Requirement",
            "Appointment date",
            "Time",
            "Duration (s)",
            "Cost (INR)",
            "Emergency",
            "Created",
            "Transcript",
            "Extracted data",
        ],
        call_rows,
        [6, 38, 11, 10, 16, 22, 22, 30, 14, 8, 10, 10, 10, 20, 70, 50],
        wrap_columns=(8, 15, 16),
    )

    _add_sheet(
        workbook,
        "Appointments",
        [
            "ID",
            "Doctor",
            "Department",
            "Patient",
            "Phone",
            "Date",
            "Time",
            "Status",
            "Source",
            "Reason",
            "Fee (INR)",
            "Created",
        ],
        [
            [
                item["id"],
                item["doctor"],
                item["department"],
                item["patient"],
                item["phone"],
                item["appointment_date"],
                item["time_slot"],
                item["status"],
                item["source"],
                item.get("reason") or "",
                float(item.get("consultation_fee") or 0),
                item["created_at"],
            ]
            for item in appointments
        ],
        [6, 22, 14, 22, 16, 13, 8, 10, 10, 28, 11, 20],
    )

    _add_sheet(
        workbook,
        "Doctors",
        [
            "ID",
            "Name",
            "Department",
            "Qualification",
            "Consultation fee",
            "Follow-up fee",
            "Days",
            "OPD start",
            "OPD end",
            "Slot minutes",
            "Active",
        ],
        [
            [
                doctor["id"],
                doctor["name"],
                doctor["department"],
                doctor["qualification"],
                float(doctor["consultation_fee"]),
                float(doctor["followup_fee"]),
                doctor["days_available"],
                doctor["opd_start"],
                doctor["opd_end"],
                doctor["slot_minutes"],
                "yes" if doctor["active"] else "no",
            ]
            for doctor in doctors
        ],
        [6, 22, 14, 26, 15, 13, 24, 10, 10, 12, 8],
    )

    _add_sheet(
        workbook,
        "Patients",
        ["ID", "Name", "Phone", "Age", "Gender", "Created"],
        [
            [
                patient["id"],
                patient["full_name"],
                patient["phone"],
                patient["age"],
                patient["gender"],
                patient["created_at"],
            ]
            for patient in patients
        ],
        [6, 24, 16, 6, 10, 20],
    )

    return workbook


def workbook_bytes() -> bytes:
    buffer = BytesIO()
    build_workbook().save(buffer)
    return buffer.getvalue()


def write_latest_files() -> list[Path]:
    """Rewrite the on-disk workbook, so it reflects the newest call.

    Excel cannot watch a database; the file is refreshed after each webhook and
    the user reopens it. Failures are ignored so a report never breaks a call.
    """
    content = workbook_bytes()
    targets = [settings.database_file.parent / "hospital_call_data_latest.xlsx"]
    desktop = Path.home() / "Desktop"
    if desktop.is_dir():
        targets.append(desktop / "hospital_call_data.xlsx")

    written: list[Path] = []
    for target in targets:
        try:
            target.write_bytes(content)
            written.append(target)
        except OSError:
            continue
    return written


def database_path():
    return settings.database_file
