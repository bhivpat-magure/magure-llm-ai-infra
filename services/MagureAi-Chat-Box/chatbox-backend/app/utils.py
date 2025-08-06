from fastapi import HTTPException
from typing import Union
from .schemas import RoleEnum
from jose import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from .config import settings
from .models import ChatSession
from zoneinfo import ZoneInfo

BASE_URL_OLLAMA  = "http://ollama:11434/api/generate" if settings.ENVIRONMENT == 'production' else "http://localhost:11434/api/generate"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def get_password_hash(password):
    return pwd_context.hash(password)

def normalize_role(role):
    return role.value if isinstance(role,RoleEnum) else role


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def build_context(model_type: str, past_messages: list):
    if model_type == "ollama":
        context = "\n".join([f"{normalize_role(msg.role)}: {msg.content}" for msg in past_messages])
        context += "\nassistant:"
        return context

    elif model_type == "openai":
        context = [
            {
                "role": normalize_role(msg.role),
                "content": msg.content
            }
            for msg in past_messages
        ]
        context.insert(0, {
            "role": "system",
            "content": "You are a helpful assistant."
        })
        return context

    elif model_type == "anthropic":
        trimmed_message = past_messages[-3:]
        context = [
            {
                "role": normalize_role(msg.role),
                "content": msg.content
            }
            for msg in trimmed_message
        ]
        return context 

    else:
        raise HTTPException(status_code=422, detail=f"Unsupported model type: {model_type}")

def build_query(model_type: str, context: Union[str, list]) -> dict:
    if model_type == "ollama":
        return {
            "url": BASE_URL_OLLAMA,
            "json": {
                "model": "gemma3:1b",
                "prompt": context,
                "stream": False
            },
            "headers": {}
        }

    elif model_type == "openai":
        return {
            "url": "https://api.openai.com/v1/chat/completions",
            "json": {
                "model": "gpt-4",
                "messages": context,
                "temperature": 0.7,
                "stream": False
            },
            "headers": {
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
        }

    elif model_type == "anthropic":
        return {
            "url": "https://api.anthropic.com/v1/messages",
            "json": {
                "model": "claude-3-haiku-20240307",
                "messages": context,
                "max_tokens": 1024,
                "temperature": 0.7,
            },
            "headers": {
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }
        }

    else:
        raise HTTPException(status_code=422, detail=f"Unsupported model type: {model_type}")

def get_chat_by_id(chat_id: str, db):
    chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
    return chat

def get_current_time():
    return datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kolkata"))