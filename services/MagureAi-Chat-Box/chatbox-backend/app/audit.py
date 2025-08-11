import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any

from sqlalchemy import (
    create_engine, Table, Column, Integer, String, JSON, MetaData,
    TIMESTAMP, text, insert
)

# Import the function that provides audit DB URL dynamically
from app.database import get_audit_db_url  # <-- Adjust import path as needed

# ThreadPoolExecutor for non-blocking DB writes
_EXECUTOR = ThreadPoolExecutor(max_workers=4)

# Lazy engine creation - create engine only when needed
_engine = None
metadata = MetaData()

audit_logs = Table(
    "audit_logs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("service_name", String(100), nullable=False),
    Column("action", String(200), nullable=False),
    Column("user_id", String(100)),
    Column("request_data", JSON),
    Column("response_data", JSON),
    Column("ip_address", String(50)),
    Column("created_at", TIMESTAMP(timezone=True), server_default=text('now()'), nullable=False)
)


def get_engine():
    global _engine
    if _engine is None:
        audit_db_url = get_audit_db_url()
        if not audit_db_url:
            raise RuntimeError("Audit DB URL could not be retrieved")
        _engine = create_engine(
            audit_db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            connect_args={
                "options": "-c timezone=utc",
            }
        )
        # Create table if not exists
        metadata.create_all(_engine, tables=[audit_logs])
    return _engine


def _write_to_db(payload: Dict[str, Any]) -> None:
    """Internal function to write audit log entry to DB."""
    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(insert(audit_logs).values(payload))
    except Exception as e:
        # Non-blocking fallback: write to local file if DB insert fails
        try:
            with open("/tmp/failed_audit_logs.jsonl", "a") as f:
                error_record = {
                    "error": str(e),
                    "payload": payload,
                    "timestamp": datetime.utcnow().isoformat()
                }
                f.write(json.dumps(error_record) + "\n")
        except Exception:
            pass  # Fail silently


def log_audit(
    service_name: str,
    action: str,
    user_id: Optional[str] = None,
    request_data: Optional[Dict[str, Any]] = None,
    response_data: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> None:
    """
    Public function to log an audit event asynchronously.

    :param service_name: Name of the service logging the event
    :param action: Description of the action performed
    :param user_id: Optional user identifier
    :param request_data: Optional request data payload
    :param response_data: Optional response data payload
    :param ip_address: Optional client IP address
    """
    payload = {
        "service_name": service_name,
        "action": action,
        "user_id": user_id,
        "request_data": request_data,
        "response_data": response_data,
        "ip_address": ip_address,
        "created_at": datetime.utcnow()
    }
    _EXECUTOR.submit(_write_to_db, payload)
