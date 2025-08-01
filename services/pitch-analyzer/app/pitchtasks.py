from celery import Celery
from uuid import uuid4
from sqlalchemy.exc import SQLAlchemyError
from app.db import SessionLocal
from app.models import PitchData
import os
import json
from datetime import datetime

# OpenAI client
from openai import OpenAI
client = OpenAI()

# Celery setup
celery_app = Celery("worker", broker='redis://redis:6379/0', backend='redis://redis:6379/0')
celery_app.conf.task_routes = {
    'pitchtasks.process_pitch': {'queue': 'pitch_tasks'}
}

# Prompt to be sent to the model (clean, structured)
PITCH_EXTRACTION_PROMPT = """
You are a startup analyst assistant. A user has uploaded a pitch deck PDF. Extract the following key details from the document:
Please return your output in **valid JSON** format using the following fields: company, industry, insight_summary, strengths (list), weaknesses (list), revenue, arr, total_turnover, revenue_yoy_growth, revenue_mom_growth, market_cap, tam, total_finance_flow, technology, operational_sector, team_size, core_team_details (list), competition (object), market_share, ip, growth_plan_5_years, extras (list).
1. Company
2. Industry
3. Insight Summary (approx. 100 words)
4. Strengths (1–3 bullet points)
5. Weaknesses (1–3 bullet points)
6. Revenue (state as-is or 'AI Estimated')
7. ARR (Annual Recurring Revenue)
8. Total Turnover
9. Financial Growth:
   - Month-over-Month (MoM) Revenue Growth
   - Year-over-Year (YoY) Revenue Growth
10. Market Insights:
    - Market Capitalization (Market Cap)
    - Total Addressable Market (TAM)
    - Total Finance Flow in the Sector
11. Technology Used
12. Broad Operational Sector
13. Team:
    - Team Size
    - Brief details of core team members (names, roles, experience if available)
14. Competition:
    - Who are the competitors?
    - What is the competitive landscape?
15. Market Share
16. Intellectual Property (IP)
17. 5-Year Growth Plan
18. Any other relevant extras found in the pitch

If any item is missing or cannot be reasonably estimated, return 'Data not found'.
"""

import re


def clean_field_name(field):
    return re.sub(r"\*\*|\*|\s+", "", field).lower()


def parse_response_text(content: str) -> dict:
    try:
        # Remove ```json and ``` if present
        clean = re.sub(r"^```json\s*|\s*```$", "", content.strip(), flags=re.DOTALL)
        return json.loads(clean)
    except json.JSONDecodeError as e:
        print("⚠️ Failed to parse JSON. Falling back to manual parsing.")
        print(f"Error: {e}")
        return {}



# Celery task
@celery_app.task(bind=True, max_retries=10, name="pitchtasks.process_pitch", queue="pitch_tasks")
def process_pitch(self, pitch_id: str, file_path: str, model: str = "gpt-4o"):
    db = SessionLocal()
    file_id = None

    try:
        # Upload file to OpenAI
        with open(file_path, "rb") as f:
            upload = client.files.create(file=f, purpose="user_data")
            file_id = upload.id

        # Request AI to analyze file with prompt
        response = client.responses.create(
            model=model,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_file", "file_id": file_id},
                    {"type": "input_text", "text": PITCH_EXTRACTION_PROMPT}
                ]
            }]
        )

        content = response.output_text.strip()
        parsed = parse_response_text(content)

        print("🔍 GPT Output:\n", content)
        print("🔍 GPT Parsed Output:\n", parsed, parsed["company"],parsed["industry"])

        pitch_data = PitchData(
            id=str(uuid4()),
            pitch_id=pitch_id,
            file_id=file_id,
            company=parsed.get("company", ""),
            industry=parsed.get("industry", ""),
            insights=parsed.get("insight_summary", ""),
            strengths="\n".join(parsed.get("strengths", [])),
            weaknesses="\n".join(parsed.get("weaknesses", [])),
            revenue=parsed.get("revenue", ""),
            arr=parsed.get("arr", ""),
            total_turnover=parsed.get("total_turnover", ""),
            revenue_yoy_growth=parsed.get("revenue_yoy_growth", ""),
            revenue_mom_growth=parsed.get("revenue_mom_growth", ""),
            market_cap=parsed.get("market_cap", ""),
            tam=parsed.get("tam", ""),
            total_finance_flow=parsed.get("total_finance_flow", ""),
            technology=parsed.get("technology", ""),
            operational_sector=parsed.get("operational_sector", ""),
            team_size=parsed.get("team_size", ""),
            core_team_details=parsed.get("core_team_details", []),  # stored as JSONB
            competition=parsed.get("competition", {}),  # stored as JSONB
            market_share=parsed.get("market_share", ""),
            ip=parsed.get("ip", ""),
            growth_plan_5_years=parsed.get("growth_plan_5_years", ""),
            extras="\n".join(parsed.get("extras", [])),
            investment_decision="pending"
        )
        db.add(pitch_data)
        db.commit()

    except Exception as e:
        db.rollback()
        raise self.retry(exc=e, countdown=10)

    finally:
        db.close()
        try:
            os.remove(file_path)
        except Exception:
            pass

