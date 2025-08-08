from sqlalchemy import Column, String, Text, DateTime , ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from .utils import get_current_time

from .database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=True)
    user_id = Column(UUID(as_uuid=True), nullable=False)

    created_at = Column(DateTime(timezone=True), default=get_current_time)
    updated_at = Column(DateTime(timezone=True), default=get_current_time, onupdate=get_current_time)

    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    files = relationship("File", back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    role = Column(String, nullable=False) 
    content = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), default=get_current_time)
    updated_at = Column(DateTime(timezone=True), default=get_current_time, onupdate=get_current_time)

    chat = relationship("ChatSession", back_populates="messages")


class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    file_url = Column(String, nullable=False)
    file_name = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), default=get_current_time)
    updated_at = Column(DateTime(timezone=True), default=get_current_time, onupdate=get_current_time)

    chat = relationship("ChatSession", back_populates="files")

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