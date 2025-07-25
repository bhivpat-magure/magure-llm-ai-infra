from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from enum import Enum



class RoleEnum(str, Enum):
    user = "user"
    client = "assistant"

class MessageCreate(BaseModel):
    content: str    
    chat_id: UUID
    user_id:UUID
    role : RoleEnum = RoleEnum.user  

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