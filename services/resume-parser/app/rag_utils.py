import os
import hashlib
from typing import List
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
qdrant = QdrantClient(host="qdrant", port=6333)

def get_embedding(text: str):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

def init_qdrant():
    if "resumes" not in [c.name for c in qdrant.get_collections().collections]:
        qdrant.recreate_collection(
            collection_name="resumes",
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
        )

def store_resume_chunks(resume_id: str, chunks: List[str]):
    init_qdrant()
    points = []
    for chunk in chunks:
        vector = get_embedding(chunk)
        uid = int(hashlib.md5(f"{resume_id}-{chunk}".encode()).hexdigest(), 16) % 1_000_000_000
        points.append(PointStruct(
            id=uid,
            vector=vector,
            payload={
                "text": chunk,
                "resume_id": resume_id
            }
        ))
    qdrant.upsert(collection_name="resumes", points=points)

def search_chunks_by_resume(resume_id: str, query: str, top_k=5):
    embedding = get_embedding(query)
    results = qdrant.search(
        collection_name="resumes",
        query_vector=embedding,
        query_filter=Filter(
            must=[FieldCondition(key="resume_id", match=MatchValue(value=resume_id))]
        ),
        limit=top_k
    )
    return [r.payload["text"] for r in results]
