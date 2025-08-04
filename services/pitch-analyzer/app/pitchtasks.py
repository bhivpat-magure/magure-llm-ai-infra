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

PITCH_EXTRACTION_PROMPT = """
You are a startup analyst assistant. A user has uploaded a pitch deck PDF. Extract the following key details from the document:
Please return your output in **valid JSON** format using the following fields: company, industry, insight_summary, strengths (list), weaknesses (list), revenue, arr, total_turnover, technology, team_size, team_details, competition (object), market_share, ip_assets, growth_plan_5_years, extras (list).

1. Company
2. Industry
3. Insight Summary (approx. 100 words)
4. Strengths (1–3 bullet points)
5. Weaknesses (1–3 bullet points)
6. Revenue (state as-is or 'AI Estimated')
7. ARR (Annual Recurring Revenue)
8. Total Turnover
9. Technology Used
10. Team:
    - Team Size
    - Brief details of core team members (names, roles, experience if available)
11. Competition:
    - Who are the competitors?
    - What is the competitive landscape?
12. Market Share
13. Intellectual Property (IP Assets)
14. 5-Year Growth Plan
15. Any other relevant extras found in the pitch

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

            strengths="\n".join(parsed.get("strengths", [])) if isinstance(parsed.get("strengths"), list) else str(
                parsed.get("strengths", "")),
            weaknesses="\n".join(parsed.get("weaknesses", [])) if isinstance(parsed.get("weaknesses"), list) else str(
                parsed.get("weaknesses", "")),
            extras="\n".join(parsed.get("extras", [])) if isinstance(parsed.get("extras"), list) else str(
                parsed.get("extras", "")),
            competition=json.dumps(parsed.get("competition", {})) if isinstance(parsed.get("competition"),
                                                                                dict) else str(
                parsed.get("competition", "")),

            revenue=parsed.get("revenue", ""),
            arr=parsed.get("arr", ""),
            total_turnover=parsed.get("total_turnover", ""),
            technology=parsed.get("technology", ""),
            team_size=parsed.get("team_size", ""),
            team_details=json.dumps(parsed.get("team_details", [])) if isinstance(parsed.get("team_details"), (list, dict)) else str(parsed.get("team_details", "")),


            market_share=parsed.get("market_share", ""),
            ip_assets=parsed.get("ip_assets", ""),
            growth_plan_5_years=parsed.get("growth_plan_5_years", ""),

            investment_decision="pending"
        )

        db.add(pitch_data)
        db.commit()



    except Exception as e:
        db.rollback()
        print("error", e);
        raise self.retry(exc=e, countdown=10)

    finally:
        db.close()
        try:
            os.remove(file_path)
        except Exception:
            pass

