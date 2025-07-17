from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from app.db import Base

class Pitch(Base):
    __tablename__ = "pitches"

    id = Column(String, primary_key=True, index=True)
    company_name = Column(String)
    industry = Column(String)
    insights = Column(Text)
    investment_decision = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
