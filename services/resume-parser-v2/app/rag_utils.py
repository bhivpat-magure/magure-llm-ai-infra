import os
import openai
import requests
import logging
from ollama import Client as OllamaClient
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, Distance, VectorParams
from uuid import uuid4
from typing import List

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")  # Placeholder

if not OPENAI_API_KEY:
    logger.warning("OpenAI API key not provided. Skipping OpenAI support.")
if not ANTHROPIC_API_KEY:
    logger.warning("Anthropic API key not provided. Skipping Claude support.")
try:
    ollama_client = OllamaClient(host=OLLAMA_HOST)
except Exception as e:
    logger.warning(f"Local LLM (Ollama) setup failed: {e}")
    ollama_client = None

qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

COLLECTION_NAME = "resume_embeddings"
EMBEDDING_MODEL = "text-embedding-ada-002"

# Ensure Qdrant collection exists
try:
    qdrant_client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
    )
except Exception as e:
    logger.warning(f"Qdrant setup failed: {e}")

def route_to_llm(model_provider: str, model_name: str, prompt: str) -> str:
    if model_provider == "openai":
        if not OPENAI_API_KEY:
            return "OpenAI not configured"
        openai.api_key = OPENAI_API_KEY
        try:
            response = openai.ChatCompletion.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"OpenAI Error: {str(e)}"

    elif model_provider == "anthropic":
        if not ANTHROPIC_API_KEY:
            return "Anthropic not configured"
        return "Anthropic support coming soon."

    elif model_provider == "local":
        if not ollama_client:
            return "Local model not available"
        try:
            output = ollama_client.chat(model=model_name, messages=[{"role": "user", "content": prompt}])
            return output.get("message", {}).get("content", "")
        except Exception as e:
            return f"Local LLM error: {str(e)}"

    else:
        return f"Unknown model provider: {model_provider}"

def embed_and_store_resume(resume_id: str, content: str):
    if not OPENAI_API_KEY:
        logger.warning("Embedding not available - OpenAI key missing")
        return
    try:
        openai.api_key = OPENAI_API_KEY
        response = openai.Embedding.create(
            model=EMBEDDING_MODEL,
            input=content
        )
        vector = response['data'][0]['embedding']
        point = PointStruct(id=resume_id, vector=vector, payload={"resume_id": resume_id})
        qdrant_client.upsert(collection_name=COLLECTION_NAME, points=[point])
    except Exception as e:
        logger.warning(f"Embedding error: {e}")

def semantic_search(query: str, top_k: int = 3) -> List[str]:
    if not OPENAI_API_KEY:
        return ["OpenAI embedding not configured"]
    try:
        openai.api_key = OPENAI_API_KEY
        response = openai.Embedding.create(model=EMBEDDING_MODEL, input=query)
        query_vector = response['data'][0]['embedding']
        search_result = qdrant_client.search(collection_name=COLLECTION_NAME, query_vector=query_vector, limit=top_k)
        return [res.payload.get("resume_id") for res in search_result]
    except Exception as e:
        logger.warning(f"Semantic search failed: {e}")
        return ["Search error"]
