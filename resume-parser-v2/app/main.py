from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from typing import List
import uuid
import json
import logging
import fitz  # PyMuPDF
import docx
from io import BytesIO
from app.llm_router import route_to_llm, embed_and_store_resume, semantic_search
from app.minio_utils import upload_file_to_minio

app = FastAPI()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

@app.post("/resume/parse")
async def parse_resumes(
    files: List[UploadFile] = File(...),
    model_provider: str = Form(...),
    model_name: str = Form(...)
):
    # Read all files into memory first to avoid I/O closed errors
    file_contents = []
    for file in files:
        contents = await file.read()
        file_contents.append((file.filename, contents))

    async def result_stream():
        for filename, contents in file_contents:
            try:
                lower_filename = filename.lower()

                if lower_filename.endswith(".pdf"):
                    text = extract_text_from_pdf(contents)
                elif lower_filename.endswith(".txt"):
                    text = contents.decode("utf-8")
                elif lower_filename.endswith(".docx"):
                    text = extract_text_from_docx(contents)
                else:
                    yield json.dumps({
                        "filename": filename,
                        "error": "Unsupported file format. Only .pdf, .txt, and .docx allowed."
                    }) + "\n"
                    continue

                # Upload to MinIO
                minio_path = upload_file_to_minio(contents, filename)
                logger.info(f"Uploaded {filename} to MinIO at: {minio_path}")

                resume_id = str(uuid.uuid4())
                embed_and_store_resume(resume_id, text)

                prompt = f"Analyze this resume:\n{text}"
                result = route_to_llm(model_provider, model_name, prompt)

                yield json.dumps({
                    "resume_id": resume_id,
                    "filename": filename,
                    "minio_path": minio_path,
                    "analysis": result
                }) + "\n"

            except Exception as e:
                logger.exception(f"Error processing {filename}")
                yield json.dumps({
                    "filename": filename,
                    "error": str(e)
                }) + "\n"

    return StreamingResponse(result_stream(), media_type="application/jsonlines")

@app.post("/resume/query")
async def query_resume(
    query: str = Form(...),
    model_provider: str = Form(...),
    model_name: str = Form(...)
):
    try:
        ids = semantic_search(query)
        results = []
        for resume_id in ids:
            prompt = f"Answer this question based on resume with ID {resume_id}:\n{query}"
            answer = route_to_llm(model_provider, model_name, prompt)
            results.append({"resume_id": resume_id, "answer": answer})
        return {"results": results}
    except Exception as e:
        logger.exception("Query failed")
        raise HTTPException(status_code=500, detail=str(e))

def extract_text_from_pdf(data: bytes) -> str:
    doc = fitz.open(stream=data, filetype="pdf")
    return "\n".join([page.get_text() for page in doc])

def extract_text_from_docx(data: bytes) -> str:
    doc = docx.Document(BytesIO(data))
    return "\n".join([para.text for para in doc.paragraphs])

@app.post("/resume/parse-single")
async def parse_single_resume(
    file: UploadFile = File(...),
    model_provider: str = Form(...),
    model_name: str = Form(...)
):
    try:
        contents = await file.read()
        filename = file.filename.lower()

        if filename.endswith(".pdf"):
            text = extract_text_from_pdf(contents)
        elif filename.endswith(".txt"):
            text = contents.decode("utf-8")
        elif filename.endswith(".docx"):
            text = extract_text_from_docx(contents)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Only .pdf, .txt, and .docx allowed.")

        minio_path = upload_file_to_minio(contents, file.filename)
        logger.info(f"Uploaded {filename} to MinIO at: {minio_path}")

        resume_id = str(uuid.uuid4())
        embed_and_store_resume(resume_id, text)

        prompt = f"Analyze this resume:\n{text}"
        result = route_to_llm(model_provider, model_name, prompt)

        return JSONResponse({
            "resume_id": resume_id,
            "filename": file.filename,
            "minio_path": minio_path,
            "analysis": result
        })

    except Exception as e:
        logger.exception("Single resume parsing failed")
        raise HTTPException(status_code=500, detail=str(e))
