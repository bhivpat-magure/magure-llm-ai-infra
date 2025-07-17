import os
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://user:password@localhost:5432/resumedb")
engine = create_engine(POSTGRES_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(String, primary_key=True, index=True)
    filename = Column(String)
    content = Column(Text)
    llm_output = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
