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

    # Basic Info
    company = Column(String)
    industry = Column(String)
    file_id = Column(String)
    insights = Column(Text)  # 100-word summary
    strengths = Column(Text)  # Can store bullet points as newline-separated
    weaknesses = Column(Text)
    revenue = Column(String)
    arr = Column(String)
    total_turnover = Column(String)

    # Financial Growth
    revenue_yoy_growth = Column(String)
    revenue_mom_growth = Column(String)

    # Market Insights
    market_cap = Column(String)
    tam = Column(String)  # Total Addressable Market
    total_finance_flow = Column(String)

    # Team & Operations
    technology = Column(String)
    operational_sector = Column(String)
    team_size = Column(String)
    core_team_details = Column(Text)

    # Competition & Positioning
    competition = Column(Text)
    market_share = Column(String)

    # IP & Vision
    ip = Column(Text)  # Intellectual Property
    growth_plan_5_years = Column(Text)

    # Extras & System Fields
    extras = Column(Text)
    investment_decision = Column(String, default="pending")

    # Relationship
    pitch = relationship("Pitch", back_populates="pitch_data")
