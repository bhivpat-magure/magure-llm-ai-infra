from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@postgres:5432/pitchdb")

engine = create_engine(POSTGRES_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()