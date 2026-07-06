"""
Simple audit logging utility.

Every meaningful event in the pipeline (imports, cleaning steps, rule
execution, alert generation, exports, dashboard access) is written to
both a rotating text log and an `audit_logs` table in SQLite so the
whole thing behaves like a real internal compliance tool.
"""

import logging
import os
import sqlite3
from datetime import datetime

from src.config import settings

os.makedirs(settings.LOGS_DIR, exist_ok=True)
LOG_FILE = os.path.join(settings.LOGS_DIR, "audit_log.txt")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

_console = logging.StreamHandler()
_console.setLevel(logging.INFO)
_console.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logging.getLogger().addHandler(_console)


def log_event(event_type: str, message: str) -> None:
    """Write an event to the text log and, if the DB exists, to audit_logs."""
    logging.info(f"[{event_type}] {message}")
    try:
        if os.path.exists(settings.DB_PATH):
            conn = sqlite3.connect(settings.DB_PATH)
            conn.execute(
                "INSERT INTO audit_logs (event_type, message, event_time) VALUES (?, ?, ?)",
                (event_type, message, datetime.now().isoformat()),
            )
            conn.commit()
            conn.close()
    except sqlite3.OperationalError:
        # audit_logs table not created yet - text log still captured the event
        pass
