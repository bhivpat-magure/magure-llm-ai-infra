from sqlalchemy import Column, String, Text, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
import datetime

from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete")
    messages = relationship("Message", back_populates="user", cascade="all, delete")

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    messages = relationship("Message", back_populates="chat", cascade="all, delete")
    user = relationship("User", back_populates="chat_sessions")
    

class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False) 
    content = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    chat = relationship("ChatSession", back_populates="messages")
    user = relationship("User", back_populates="messages")


# New file_id column added to the Message model
# New Schema to be used
# class Message(Base):
#     __tablename__ = "messages"

#     id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
#     chat_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"))
#     role: Mapped[str] = mapped_column(String)
#     user_id: Mapped[str] = mapped_column(String, index=True)
#     content: Mapped[str] = mapped_column(String)
    
#     # Add this new column
#     file_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

#     created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

#     chat_session = relationship("ChatSession", back_populates="messages")