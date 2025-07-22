import os
from uuid import uuid4
from typing import List
from fastapi import UploadFile, File, HTTPException, APIRouter
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app import app, SessionLocal, Base, engine

from app.models import Pitch
from app import rag_utils
from celery_app import make_celery
celery = make_celery()

router = APIRouter()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Ensure DB is initialized on startup
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

# Pydantic schema for query
class PitchQuery(BaseModel):
    pitch_id: str
    question: str

@router.post("/analyze-pitches")
async def analyze_pitches(files: List[UploadFile] = File(...)):
    results = []
    db: Session = SessionLocal()

    for file in files:
        pitch_id = f"pitch_{uuid4()}"
        filename = secure_filename(file.filename)
        saved_path = os.path.join(UPLOAD_DIR, f"{uuid4()}_{filename}")

        try:
            with open(saved_path, "wb") as f:
                f.write(await file.read())

            pitch = Pitch(id=pitch_id, file_name=filename, file_path=saved_path)
            db.add(pitch)
            db.commit()

            celery.send_task("app.tasks.process_pitch", args=[pitch_id, saved_path])
            results.append({"filename": filename, "pitch_id": pitch_id, "status": "queued"})

        except SQLAlchemyError as e:
            db.rollback()
            results.append({"filename": filename, "status": "error", "detail": str(e)})

        except Exception as e:
            results.append({"filename": filename, "status": "error", "detail": f"Unexpected error: {str(e)}"})

    db.close()
    return {"results": results}


@router.post("/query-pitch")
async def ask_about_pitch(payload: PitchQuery):
    if not payload.pitch_id or not payload.question:
        raise HTTPException(status_code=400, detail="pitch_id and question required")

    context = rag_utils.search_similar_chunks(payload.pitch_id, payload.question)
    answer = rag_utils.query_llm(context, payload.question)
    return {"answer": answer}


# Include router
app.include_router(router)
