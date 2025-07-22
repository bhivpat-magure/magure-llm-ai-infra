from fastapi import FastAPI

from app.db import SessionLocal, Base, engine  # 👈 Import from db.py

app = FastAPI()

# Re-export
__all__ = ["app", "SessionLocal", "Base", "engine"]
