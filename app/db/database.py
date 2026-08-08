import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

SCHEMA_VERSION = 1


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_connection() -> sqlite3.Connection:
    return _connect(settings.database_file)


@contextmanager
def db_session():
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    from app.db.models import SCHEMA_SQL

    conn = _connect(settings.database_file)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        logger.info("database initialised", extra={"path": str(settings.database_file)})
    finally:
        conn.close()


def get_schema_version() -> int:
    conn = _connect(settings.database_file)
    try:
        row = conn.execute("SELECT version FROM migrations ORDER BY version DESC LIMIT 1").fetchone()
        return int(row["version"]) if row else 0
    finally:
        conn.close()
