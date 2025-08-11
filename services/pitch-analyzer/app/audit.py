# audit.py  (drop into each service)
import os
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import create_engine, Table, Column, Integer, String, JSON, MetaData, TIMESTAMP, text
from sqlalchemy.sql import insert

# ThreadPool to offload DB writes so main request thread is not blocked
_EXECUTOR = ThreadPoolExecutor(max_workers=4)

AUDIT_DB_URL = os.getenv("AUDIT_DB_URL")  # e.g. postgresql://audit_user:pass@audit_postgres:5432/audit_logs_db
if not AUDIT_DB_URL:
    raise RuntimeError("AUDIT_DB_URL not set in environment")

# create_engine with pooling; tune pool_size/max_overflow as needed
_engine = create_engine(
    AUDIT_DB_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    connect_args={"options": "-c timezone=utc"}  # optional
)

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
    Column("created_at", TIMESTAMP(timezone=True), server_default=text('now()'))
)

# Ensure table exists (safe to call repeatedly)
def ensure_table():
    metadata.create_all(_engine, tables=[audit_logs])

ensure_table()

def _write_to_db(payload: dict):
    try:
        with _engine.begin() as conn:
            conn.execute(insert(audit_logs).values(payload))
    except Exception as e:
        # NON-BLOCKING fallback: write failed logs to a local file for later replay
        # (avoid raising; do not break the main app)
        try:
            with open("/tmp/failed_audit_logs.jsonl", "a") as f:
                f.write(json.dumps({"error": str(e), "payload": payload, "ts": datetime.utcnow().isoformat()}) + "\n")
        except Exception:
            # last resort: swallow
            pass

def log_audit(service_name: str, action: str, user_id: str | None = None,
              request_data: dict | None = None, response_data: dict | None = None, ip_address: str | None = None):
    payload = {
        "service_name": service_name,
        "action": action,
        "user_id": user_id,
        "request_data": request_data,
        "response_data": response_data,
        "ip_address": ip_address,
        "created_at": datetime.utcnow()
    }
    # schedule background write and return immediately
    _EXECUTOR.submit(_write_to_db, payload)
