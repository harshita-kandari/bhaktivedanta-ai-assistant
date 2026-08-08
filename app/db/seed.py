from app.core.logging import get_logger
from app.db.database import db_session

logger = get_logger(__name__)

SAMPLE_DOCTORS = [
    {
        "name": "Dr. Rajesh Sharma",
        "department": "ENT",
        "qualification": "MS (ENT)",
        "consultation_fee": 600.0,
        "followup_fee": 300.0,
        "days_available": "Mon,Tue,Wed,Thu,Fri,Sat",
        "opd_start": "09:00",
        "opd_end": "17:00",
        "slot_minutes": 30,
    },
    {
        "name": "Dr. Anita Desai",
        "department": "ENT",
        "qualification": "MS (ENT), DLO",
        "consultation_fee": 800.0,
        "followup_fee": 400.0,
        "days_available": "Mon,Wed,Fri",
        "opd_start": "10:00",
        "opd_end": "14:00",
        "slot_minutes": 30,
    },
    {
        "name": "Dr. Sanjay Verma",
        "department": "Orthopedics",
        "qualification": "MS (Ortho), Fellowship Joint Replacement",
        "consultation_fee": 1000.0,
        "followup_fee": 500.0,
        "days_available": "Tue,Thu,Sat",
        "opd_start": "11:00",
        "opd_end": "16:00",
        "slot_minutes": 30,
    },
    {
        "name": "Dr. Meera Krishnan",
        "department": "Orthopedics",
        "qualification": "MS (Ortho), Spine Fellow",
        "consultation_fee": 900.0,
        "followup_fee": 450.0,
        "days_available": "Mon,Tue,Wed,Thu,Fri",
        "opd_start": "09:00",
        "opd_end": "15:00",
        "slot_minutes": 30,
    },
    {
        "name": "Dr. Vikram Kulkarni",
        "department": "Orthopedics",
        "qualification": "MBBS, D.Ortho",
        "consultation_fee": 500.0,
        "followup_fee": 250.0,
        "days_available": "Mon,Tue,Wed,Thu,Fri,Sat",
        "opd_start": "14:00",
        "opd_end": "20:00",
        "slot_minutes": 30,
    },
    {
        "name": "Dr. Arvind Nair",
        "department": "Cardiology",
        "qualification": "DM (Cardiology)",
        "consultation_fee": 1200.0,
        "followup_fee": 600.0,
        "days_available": "Mon,Wed,Fri",
        "opd_start": "10:00",
        "opd_end": "14:00",
        "slot_minutes": 45,
    },
    {
        "name": "Dr. Sunita Rao",
        "department": "Cardiology",
        "qualification": "MD, DNB (Cardiology)",
        "consultation_fee": 1000.0,
        "followup_fee": 500.0,
        "days_available": "Tue,Thu,Sat",
        "opd_start": "09:00",
        "opd_end": "13:00",
        "slot_minutes": 45,
    },
    {
        "name": "Dr. Ramesh Iyer",
        "department": "Cardiology",
        "qualification": "DM (Cardiology), FACC",
        "consultation_fee": 1500.0,
        "followup_fee": 750.0,
        "days_available": "Mon,Tue,Thu,Fri",
        "opd_start": "16:00",
        "opd_end": "19:00",
        "slot_minutes": 45,
    },
]

INSERT_DOCTOR_SQL = """
INSERT OR REPLACE INTO doctors (
    name, department, qualification, consultation_fee, followup_fee,
    days_available, opd_start, opd_end, slot_minutes, active
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
"""


def seed_doctors() -> int:
    count = 0
    with db_session() as conn:
        for doc in SAMPLE_DOCTORS:
            conn.execute(
                INSERT_DOCTOR_SQL,
                (
                    doc["name"],
                    doc["department"],
                    doc["qualification"],
                    doc["consultation_fee"],
                    doc["followup_fee"],
                    doc["days_available"],
                    doc["opd_start"],
                    doc["opd_end"],
                    doc["slot_minutes"],
                ),
            )
            count += 1
    logger.info("seeded doctors", extra={"count": count})
    return count


def seed_all() -> None:
    seed_doctors()
