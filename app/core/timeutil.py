"""Timestamp helpers.

SQLite stores UTC (`CURRENT_TIMESTAMP`). Everything shown to a human should be
in the machine's local timezone.
"""

from datetime import datetime, timezone


def to_local(value) -> str:
    """Convert a stored UTC timestamp to a local 'YYYY-MM-DD HH:MM:SS' string."""
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S")
