import os
import uuid
from PyPDF2 import PdfReader
#from pptx import Presentation
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from openai import OpenAI

openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

qdrant = QdrantClient(host="qdrant", port=6333)

def extract_text(path: str) -> str:
    if path.endswith(".pdf"):
        reader = PdfReader(path)
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    '''
    elif path.endswith(".pptx"):
        prs = Presentation(path)
        return "\n".join([shape.text for slide in prs.slides for shape in slide.shapes if hasattr(shape, "text")])
        '''
    return ""

def extract_with_ocr(path: str) -> str:
    images = convert_from_path(path)
    extracted = ""
    for i, img in enumerate(images):
        text = pytesseract.image_to_string(img)
        extracted += f"\n\n--- Page {i + 1} ---\n{text.strip()}"
    return extracted.strip()

def extract_structured_insights(text: str):
    messages = [
        {"role": "system", "content": "Extract company name, industry, and a 100-word insight summary from the pitch deck content."},
        {"role": "user", "content": text}
    ]
    response = client.chat.completions.create(model="gpt-4", messages=messages)
    content = response.choices[0].message.content.strip()

    # Very naive parsing
    lines = content.split("\n")
    company = next((l.split(":")[1].strip() for l in lines if "Company" in l), "Unknown")
    industry = next((l.split(":")[1].strip() for l in lines if "Industry" in l), "Unknown")
    insight_lines = [l for l in lines if "Insight" in l or len(l.split()) > 5]
    insights = "\n".join(insight_lines).strip()

    return company, industry, insights

def embed_and_store(pitch_id: str, text: str):
    chunks = [text[i:i+500] for i in range(0, len(text), 500)]
    embeddings = client.embeddings.create(model="text-embedding-ada-002", input=chunks).data
    qdrant.recreate_collection(
        collection_name=pitch_id,
        vectors_config=VectorParams(size=len(embeddings[0].embedding), distance=Distance.COSINE)
    )
    qdrant.upload_points(
        collection_name=pitch_id,
        points=[
            PointStruct(id=str(uuid.uuid4()), vector=e.embedding, payload={"text": c})
            for e, c in zip(embeddings, chunks)
        ]
    )

def search_similar_chunks(pitch_id: str, query: str) -> str:
    query_vec = client.embeddings.create(model="text-embedding-ada-002", input=[query]).data[0].embedding
    hits = qdrant.search(collection_name=pitch_id, query_vector=query_vec, limit=5)
    return "\n".join([hit.payload["text"] for hit in hits])

def query_llm(context: str, question: str) -> str:
    messages = [
        {"role": "system", "content": f"Answer based on pitch deck content:\n{context}"},
        {"role": "user", "content": question}
    ]
    completion = client.chat.completions.create(model="gpt-4", messages=messages)
    return completion.choices[0].message.content.strip()
