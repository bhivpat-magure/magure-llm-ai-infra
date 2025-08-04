import os
from uuid import uuid4
from typing import List
from fastapi import UploadFile, File, HTTPException, APIRouter, Query,Path
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename
from sqlalchemy.orm import Session
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app import app, SessionLocal, Base, engine
from app.pitchtasks import process_pitch
from fastapi.middleware.cors import CORSMiddleware

from fastapi import Path

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
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

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
        #rag_context = rag_utils.search_similar_chunks(payload.pitch_id, payload.question)

        # Combine both contexts
        #full_context = pitch_context.strip() + "\n\n---\n\n" + rag_context.strip()
        full_context = pitch_context.strip()

        # Send to LLM
        answer = rag_utils.query_llm(full_context, payload.question)
        return {"answer": answer}

    finally:
        db.close()



@router.get("/all-pitches")
async def get_all_pitches():
    db: Session = SessionLocal()
    try:
        pitches = db.query(Pitch).all()

        response = []
        for pitch in pitches:
            pitch_data = pitch.pitch_data
            response.append({
                "pitch_id": pitch.id,
                "file_name": pitch.file_name,
                "file_path": f"/uploads/{os.path.basename(pitch.file_path)}",
                "company": pitch_data.company if pitch_data else None,
                "industry": pitch_data.industry if pitch_data else None,
                "insights": pitch_data.insights if pitch_data else None,
            })

        return response
    finally:
        db.close()





@router.get("/pitch/{pitch_id}")
async def get_pitch_details(pitch_id: str):
    db: Session = SessionLocal()
    try:
        # Get Pitch with its related PitchData
        pitch = db.query(Pitch).filter(Pitch.id == pitch_id).first()

        if not pitch:
            raise HTTPException(status_code=404, detail="Pitch not found")

        pitch_data = pitch.pitch_data  # Thanks to relationship

        # Create union of both Pitch and PitchData fields
        result = {
            "pitch_id": pitch.id,
            "file_name": pitch.file_name,
            "file_path": f"/uploads/{os.path.basename(pitch.file_path)}",
            "created_at": pitch.created_at,
        }

        if pitch_data:
            result.update({
                "company": pitch_data.company,
                "industry": pitch_data.industry,
                "file_id": pitch_data.file_id,
                "insights": pitch_data.insights,
                "strengths": pitch_data.strengths,
                "weaknesses": pitch_data.weaknesses,
                "revenue": pitch_data.revenue,
                "arr": pitch_data.arr,
                "total_turnover": pitch_data.total_turnover,
                "extras": pitch_data.extras,
                "investment_decision": pitch_data.investment_decision,
            })

        return result
    finally:
        db.close()






@router.get("/download/{pitch_id}")
async def download_file(pitch_id: str = Path(...)):
    db: Session = SessionLocal()
    try:
        pitch = db.query(Pitch).filter(Pitch.id == pitch_id).first()
        if not pitch or not pitch.file_path:
            raise HTTPException(status_code=404, detail="Pitch not found or file missing")

        if not os.path.isfile(pitch.file_path):
            raise HTTPException(status_code=404, detail="File does not exist on disk")

        return FileResponse(
            path=pitch.file_path,
            media_type='application/octet-stream',
            filename=pitch.file_name  # use original uploaded name
        )
    finally:
        db.close()


# Include router
app.include_router(router)
