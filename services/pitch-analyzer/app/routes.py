import os
from uuid import uuid4
from typing import List
from fastapi import UploadFile, File, HTTPException, APIRouter, Query
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename
from sqlalchemy.orm import Session
from pydantic import BaseModel


from app import app, SessionLocal, Base, engine
from app.pitchtasks import process_pitch
from fastapi.middleware.cors import CORSMiddleware



from app.models import Pitch, PitchData
from app import rag_utils
from celery_app import make_celery
celery = make_celery()
# Add this right after you define `app`
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specify ["http://localhost:3000", "http://yourdomain.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


router = APIRouter(prefix="/api3")

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
async def analyze_pitches(
    files: List[UploadFile] = File(...),
    model: str = Query(default="gpt-4o")
):
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

            # Enqueue task with model
            process_pitch.delay(pitch_id, saved_path, model)

            results.append({
                "filename": filename,
                "pitch_id": pitch_id,
                "status": "processing"
            })

        except SQLAlchemyError as e:
            db.rollback()
            results.append({
                "filename": filename,
                "status": "error",
                "detail": str(e)
            })

        except Exception as e:
            results.append({
                "filename": filename,
                "status": "error",
                "detail": f"Unexpected error: {str(e)}"
            })

    db.close()
    return {"results": results}


@router.post("/query-pitch")
async def ask_about_pitch(payload: PitchQuery):
    if not payload.pitch_id or not payload.question:
        raise HTTPException(status_code=400, detail="pitch_id and question required")

    db: Session = SessionLocal()

    try:
        pitch_data = db.query(PitchData).filter(PitchData.pitch_id == payload.pitch_id).first()
        if not pitch_data:
            raise HTTPException(status_code=404, detail="Pitch data not found")

        # Convert pitch_data fields to a structured string
        pitch_context = f"""
Company Name: {pitch_data.company or "N/A"}
Industry: {pitch_data.industry or "N/A"}
Insight Summary: {pitch_data.insights or "N/A"}

Strengths:
{pitch_data.strengths or "N/A"}

Weaknesses:
{pitch_data.weaknesses or "N/A"}

Revenue: {pitch_data.revenue or "N/A"}
ARR: {pitch_data.arr or "N/A"}
Total Turnover: {pitch_data.total_turnover or "N/A"}

Extras:
{pitch_data.extras or "N/A"}

Investment Decision: {pitch_data.investment_decision or "N/A"}
"""

        # Also fetch similar chunks from RAG
        rag_context = rag_utils.search_similar_chunks(payload.pitch_id, payload.question)

        # Combine both contexts
        full_context = pitch_context.strip() + "\n\n---\n\n" + rag_context.strip()

        # Send to LLM
        answer = rag_utils.query_llm(full_context, payload.question)
        return {"answer": answer}

    finally:
        db.close()

# Include router
app.include_router(router)
