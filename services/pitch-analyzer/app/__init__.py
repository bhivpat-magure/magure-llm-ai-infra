from fastapi import FastAPI

from app.db import SessionLocal, Base, engine  # 👈 Import from db.py

from app.middleware import JWTMiddleware  # 👈 import your middleware

app = FastAPI()

app.add_middleware(JWTMiddleware)  # 👈 apply globally
# Re-export
__all__ = ["app", "SessionLocal", "Base", "engine"]
