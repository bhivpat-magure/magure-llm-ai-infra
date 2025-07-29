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

    company = Column(String)
    industry = Column(String)
    file_id = Column(String)
    insights = Column(Text)  # 100-word summary
    strengths = Column(Text)  # Store as newline-separated string or use JSONB
    weaknesses = Column(Text)
    revenue = Column(String)
    arr = Column(String)
    total_turnover = Column(String)
    extras = Column(Text)

    investment_decision = Column(String, default="pending")

    # Relationship
    pitch = relationship("Pitch", back_populates="pitch_data")

