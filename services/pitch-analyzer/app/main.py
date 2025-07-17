from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from uuid import uuid4
import os

from app.db import SessionLocal, engine
from app.models import Pitch
from app import rag_utils

from sqlalchemy.exc import SQLAlchemyError

app = FastAPI()

# Auto-create tables
from app.db import Base
Base.metadata.create_all(bind=engine)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/analyze-pitch")
async def analyze_pitch(file: UploadFile = File(...)):
    temp_path = os.path.join(UPLOAD_DIR, f"{uuid4()}_{file.filename}")
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    text = rag_utils.extract_text(temp_path)
    if not text or len(text.strip()) < 30:
        text = rag_utils.extract_with_ocr(temp_path)

    if not text.strip():
        raise HTTPException(status_code=400, detail="No extractable text found.")

    pitch_id = f"pitch_{uuid4()}"
    company_name, industry, insights = rag_utils.extract_structured_insights(text)

    db = SessionLocal()
    try:
        db_pitch = Pitch(
            id=pitch_id,
            company_name=company_name,
            industry=industry,
            insights=insights
        )
        db.add(db_pitch)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

    rag_utils.embed_and_store(pitch_id, text)
    return {"pitch_id": pitch_id, "message": "Pitch analyzed and stored."}

@app.post("/query-pitch")
async def ask_about_pitch(payload: dict):
    pitch_id = payload.get("pitch_id")
    question = payload.get("question")
    if not pitch_id or not question:
        raise HTTPException(status_code=400, detail="pitch_id and question required")

    context = rag_utils.search_similar_chunks(pitch_id, question)
    answer = rag_utils.query_llm(context, question)
    return {"answer": answer}
