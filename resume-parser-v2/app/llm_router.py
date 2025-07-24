import os
import logging
from typing import List
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance
from uuid import uuid4
import hashlib
import requests
import anthropic

logger = logging.getLogger(__name__)

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
COLLECTION_NAME = "resumes"

# Create collection if it doesn't exist
try:
    client.get_collection(collection_name=COLLECTION_NAME)
except:
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
    )

def get_embedding(text: str, model_provider: str, model_name: str) -> List[float]:
    if model_provider == "openai":
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not set.")
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {openai_api_key}"
            },
            json={
                "input": text,
                "model": model_name  # e.g. text-embedding-ada-002
            }
        )
        return response.json()["data"][0]["embedding"]

    elif model_provider == "local":
        response = requests.post(
            "http://host.docker.internal:11434/api/embeddings",
            json={"model": model_name, "prompt": text}
        )
        return response.json()["embedding"]

    raise ValueError(f"Unsupported model provider for embedding: {model_provider}")

def embed_and_store_resume(resume_id: str, text: str, model_provider: str = "openai", model_name: str = "text-embedding-ada-002"):
    embedding = get_embedding(text, model_provider, model_name)
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=resume_id,
                vector=embedding,
                payload={"text": text}
            )
        ]
    )
    logger.info(f"Stored resume {resume_id} in Qdrant.")

def semantic_search(query: str, top_k: int = 5) -> List[str]:
    query_vector = get_embedding(query, model_provider="openai", model_name="text-embedding-ada-002")
    search_result = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k
    )
    return [point.id for point in search_result]

def route_to_llm(provider: str, model: str, prompt: str) -> str:
    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            return "OpenAI API key not found."
        res = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        return res.json()["choices"][0]["message"]["content"]

    elif provider == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            return "Anthropic API key not found."
        client = anthropic.Anthropic(api_key=key)
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            temperature=0.7,
            system="You are a helpful assistant analyzing resumes.",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text if response.content else ""

    elif provider == "local":
        res = requests.post(
            "http://host.docker.internal:11434/api/generate",
            json={"model": model, "prompt": prompt}
        )
        return res.json().get("response", "")

    return f"LLM provider '{provider}' not supported."

import os
import requests
import httpx
import asyncio

async def route_to_llm_stream(provider: str, model: str, prompt: str):
    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            yield "[OpenAI API key missing]"
            return

        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST", "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "stream": True,
                    "messages": [{"role": "user", "content": prompt}]
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            yield eval(data)["choices"][0]["delta"].get("content", "")
                        except Exception:
                            continue

    elif provider == "local":
        yield "Streaming from local models not yet implemented.\n"

    elif provider == "anthropic":
        # Optional: Add streaming for Claude
        yield "Anthropic streaming not implemented yet.\n"

    else:
        yield f"Unsupported provider '{provider}'"

