from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from enum import Enum



class RoleEnum(str, Enum):
    user = "user"
    client = "assistant"
    
class ModelType(str, Enum):
    OLLAMA = "ollama"
    OPENAI  = "openai"
    ANTHROPIC = "anthropic"

class MessageCreate(BaseModel):
    content: str    
    chat_id: UUID
    user_id:UUID
    role : RoleEnum = RoleEnum.user
    modelType : ModelType = ModelType.OLLAMA 

class MessageOut(BaseModel):
    id: UUID
    created_at: datetime
    content: str
    role : RoleEnum = RoleEnum.user
    class Config:
        from_attributes = True  # ✅ Fixed

class ChatSessionCreate(BaseModel):
    title: Optional[str] = None
    user_id: UUID

class ChatSessionOut(BaseModel):
    id: UUID
    title: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: UUID
    username: str

    class Config:
        from_attributes = True 


class UserLogin(BaseModel):
    username : str
    password : str
    
class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    username: str

# Updated Schema for File Based Message
# File_id is optional

class MessageBase(BaseModel):
    chat_id: str
    user_id: str
    role: RoleEnum
    content: str
    modelType: ModelType

class MessageCreate(MessageBase):
    pass

class MessageOut(BaseModel):
    id: str
    chat_id: str
    role: str
    user_id: str
    content: str
    created_at: datetime
    
    # Add this field to the output model
    file_id: Optional[str] = None

    class Config:
        from_attributes = True # Or orm_mode = True for Pydantic v1