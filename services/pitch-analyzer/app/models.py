from sqlalchemy import Column, String, Text, DateTime,ForeignKey
from sqlalchemy.sql import func
from app.db import Base
from sqlalchemy.orm import relationship


    
    
# models.py


class Pitch(Base):
    __tablename__ = "pitches"

    id = Column(String, primary_key=True, index=True)
    file_name = Column(String)
    file_path = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # One-to-one relationship (optional: one-to-many if needed)
    pitch_data = relationship("PitchData", back_populates="pitch", uselist=False)


class PitchData(Base):
    __tablename__ = "pitch_data"

    id = Column(String, primary_key=True, index=True)
    pitch_id = Column(String, ForeignKey("pitches.id", ondelete="CASCADE"), nullable=False)

    industry = Column(String)
    insights = Column(Text)
    investment_decision = Column(String, default="pending")

    # Backward relation
    pitch = relationship("Pitch", back_populates="pitch_data")

