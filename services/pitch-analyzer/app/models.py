from sqlalchemy import Column, String, Text, DateTime,ForeignKey,  Float, Boolean, Integer
from sqlalchemy.sql import func
from app.db import Base
from sqlalchemy.orm import relationship
from datetime import datetime

from sqlalchemy.dialects.postgresql import JSONB


# models.py


class Pitch(Base):
    __tablename__ = "pitches"

    id = Column(String, primary_key=True, index=True)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to PitchData
    pitch_data = relationship("PitchData", back_populates="pitch", uselist=False)



class PitchData(Base):
    __tablename__ = "pitch_data"

    id = Column(String, primary_key=True, index=True)
    pitch_id = Column(String, ForeignKey("pitches.id"), nullable=False)
    file_id = Column(String, nullable=True)

    company = Column(String)
    industry = Column(String)
    insights = Column(Text)
    strengths = Column(Text)
    weaknesses = Column(Text)
    revenue = Column(String)
    arr = Column(String)
    total_turnover = Column(String)
    extras = Column(Text)
    investment_decision = Column(String, default="pending")

    parsed = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)

    # New fields from your follow-up request
    technology = Column(Text, nullable=True)
    team_size = Column(String, nullable=True)
    team_details = Column(Text, nullable=True)
    competition = Column(Text, nullable=True)
    market_share = Column(String, nullable=True)
    ip_assets = Column(Text, nullable=True)
    growth_plan_5_years = Column(Text, nullable=True)

    # Back relation
    pitch = relationship("Pitch", back_populates="pitch_data")
