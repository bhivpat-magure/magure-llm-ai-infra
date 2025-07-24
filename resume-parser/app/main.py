from fastapi import FastAPI, UploadFile, File, Depends
from sqlalchemy.orm import Session
from app.db import SessionLocal, engine
from app.models import Resume, Base
from app.rag_utils import store_resume_chunks, search_chunks_by_resume
from openai import OpenAI
from pydantic import BaseModel
import uuid
import os
import fitz  # PyMuPDF

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

Base.metadata.create_all(bind=engine)
app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def extract_text_from_pdf(content: bytes) -> str:
    with open("/tmp/temp.pdf", "wb") as f:
        f.write(content)

    doc = fitz.open("/tmp/temp.pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

@app.post("/parse-resume/")
async def parse_resume(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()

    if file.filename.endswith(".pdf"):
        text = extract_text_from_pdf(content)
    else:
        text = content.decode(errors="ignore")

    text = text[:1500]
    chunks = [text[i:i+500] for i in range(0, len(text), 500)]
    resume_id = str(uuid.uuid4())
    store_resume_chunks(resume_id, chunks)

    prompt = f"""Extract the following from the text:
- Full Name
- Email
- Phone
- Key Skills
- Experience (Title, Company, Years)

Text:
{text}
"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    result = response.choices[0].message.content

    resume = Resume(name="Unknown", email="Unknown", phone="Unknown", skills="Parsed", experience=result)
    db.add(resume)
    db.commit()

    return {
        "message": "Resume parsed successfully",
        "resume_id": resume_id,
        "parsed": result
    }

class ResumeQuery(BaseModel):
    resume_id: str
    question: str

@app.post("/ask-about-resume/")
def ask_about_resume(query: ResumeQuery):
    context_chunks = search_chunks_by_resume(query.resume_id, query.question)
    context = "\n".join(context_chunks)

    prompt = f"""
You are answering a question about a candidate's resume.
Use only the following context extracted from the resume.

Resume context:
{context}

Question:
{query.question}
"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    return {"response": response.choices[0].message.content}
