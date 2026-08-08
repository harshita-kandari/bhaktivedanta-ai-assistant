SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS doctors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    department TEXT NOT NULL CHECK (department IN ('ENT', 'Orthopedics', 'Cardiology')),
    qualification TEXT NOT NULL DEFAULT '',
    consultation_fee REAL NOT NULL DEFAULT 0,
    followup_fee REAL NOT NULL DEFAULT 0,
    days_available TEXT NOT NULL DEFAULT 'Mon,Tue,Wed,Thu,Fri,Sat',
    opd_start TEXT NOT NULL DEFAULT '09:00',
    opd_end TEXT NOT NULL DEFAULT '20:00',
    slot_minutes INTEGER NOT NULL DEFAULT 30,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    age INTEGER,
    gender TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE RESTRICT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    appointment_date TEXT NOT NULL,
    time_slot TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'booked'
        CHECK (status IN ('booked', 'cancelled', 'completed')),
    reason TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'assistant'
        CHECK (source IN ('assistant', 'call', 'web')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (doctor_id, appointment_date, time_slot)
);

CREATE TABLE IF NOT EXISTS call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT UNIQUE,
    agent_id TEXT NOT NULL DEFAULT '',
    direction TEXT NOT NULL DEFAULT 'outbound'
        CHECK (direction IN ('inbound', 'outbound')),
    status TEXT NOT NULL DEFAULT 'queued',
    recipient_phone TEXT NOT NULL DEFAULT '',
    transcript TEXT,
    extracted_data TEXT,
    telephony_data TEXT,
    total_cost REAL DEFAULT 0,
    conversation_duration REAL DEFAULT 0,
    emergency_flag INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(appointment_date);
CREATE INDEX IF NOT EXISTS idx_appointments_doctor ON appointments(doctor_id);
CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_doctors_department ON doctors(department);
CREATE INDEX IF NOT EXISTS idx_call_logs_execution ON call_logs(execution_id);

INSERT OR IGNORE INTO migrations (version) VALUES (1);
"""

MIGRATION_V2_SQL = """
ALTER TABLE appointments RENAME TO appointments_old;

CREATE TABLE appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE RESTRICT,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    appointment_date TEXT NOT NULL,
    time_slot TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'booked'
        CHECK (status IN ('booked', 'cancelled', 'completed')),
    reason TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'assistant'
        CHECK (source IN ('assistant', 'call', 'web')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (doctor_id, appointment_date, time_slot)
);

INSERT INTO appointments (id, doctor_id, patient_id, appointment_date, time_slot, status, reason, source, created_at)
SELECT id, doctor_id, patient_id, appointment_date, time_slot, status, reason, source, created_at
FROM appointments_old
WHERE id IN (
    SELECT MAX(id) FROM appointments_old GROUP BY doctor_id, appointment_date, time_slot
);

DROP TABLE appointments_old;

INSERT INTO migrations (version) VALUES (2);
"""
