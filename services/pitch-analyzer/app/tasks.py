from celery import Celery
from uuid import uuid4
from sqlalchemy.exc import SQLAlchemyError
from app.db import SessionLocal
from app.models import Pitch, PitchData
from app.rag_utils import extract_text, extract_with_ocr, extract_structured_insights
import os


celery_app = Celery("worker", broker='redis://redis:6379/0', backend='redis://redis:6379/0')

@celery_app.task(name="app.tasks.process_pitch")
def process_pitch(pitch_id: str, file_path: str):
    db = SessionLocal()
    try:
        text = extract_text(file_path)
        if not text or len(text.strip()) < 30:
            text = extract_with_ocr(file_path)

        if not text.strip():
            raise ValueError("No extractable text found.")

        company_name, industry, insights = extract_structured_insights(text)

        pitch = db.query(Pitch).filter(Pitch.id == pitch_id).first()
        if pitch:
            pitch.company_name = company_name
            db.commit()

        pitch_data = PitchData(
            id=str(uuid4()),
            pitch_id=pitch_id,
            industry=industry,
            insights=insights,
            investment_decision="pending"
        )
        db.add(pitch_data)
        db.commit()

    except (SQLAlchemyError, ValueError) as e:
        db.rollback()
        raise e
    finally:
        db.close()
        try:
            os.remove(file_path)
        except Exception:
            pass