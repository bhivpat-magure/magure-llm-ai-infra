import os
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func
from PyPDF2 import PdfReader

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

def extract_text_from_pdf_or_txt(path: str) -> str:
    if path.lower().endswith(".txt"):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    elif path.lower().endswith(".pdf"):
        try:
            reader = PdfReader(path)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            return f"Error extracting text from PDF: {str(e)}"
    else:
        return "Unsupported file format"
