from celery import Celery
from uuid import uuid4
from sqlalchemy.exc import SQLAlchemyError
from app.db import SessionLocal
from app.models import Pitch, PitchData
import os
import re

# Celery setup
celery_app = Celery("worker", broker='redis://redis:6379/0', backend='redis://redis:6379/0')
celery_app.conf.task_routes = {
    'pitchtasks.process_pitch': {'queue': 'pitch_tasks'}
}

# Utility to extract structured fields from OpenAI output
def parse_response_text(content: str):
    data = {
        "company": "Data not found",
        "industry": "Data not found",
        "insight_summary": "Data not found",
        "strengths": [],
        "weaknesses": [],
        "revenue": "Data not found",
        "ARR": "Data not found",
        "total_turnover": "Data not found",
        "extras": []
    }

    for line in content.splitlines():
        line = line.strip()
        if line.lower().startswith("company"):
            data["company"] = line.split(":", 1)[-1].strip()
        elif line.lower().startswith("industry"):
            data["industry"] = line.split(":", 1)[-1].strip()
        elif line.lower().startswith("insight"):
            data["insight_summary"] = line.split(":", 1)[-1].strip()
        elif line.lower().startswith("revenue"):
            data["revenue"] = line.split(":", 1)[-1].strip()
        elif line.lower().startswith("arr"):
            data["ARR"] = line.split(":", 1)[-1].strip()
        elif line.lower().startswith("total turnover"):
            data["total_turnover"] = line.split(":", 1)[-1].strip()
        elif line.startswith("- "):
            if "strength" in line.lower():
                data["strengths"].append(line)
            elif "weakness" in line.lower():
                data["weaknesses"].append(line)
            else:
                data["extras"].append(line)

    return data

# Celery task
@celery_app.task(bind=True, max_retries=10, name="pitchtasks.process_pitch", queue="pitch_tasks")
def process_pitch(self, pitch_id: str, file_path: str, model: str = "gpt-4o"):
    from openai import OpenAI
    client = OpenAI()

    db: SessionLocal = SessionLocal()
    file_id = None

    try:
        prompt = (
            "You are a startup analyst assistant. A user uploaded a pitch deck PDF. "
            "Extract the following:\n"
            "- Company\n"
            "- Industry\n"
            "- Insight Summary (100 words)\n"
            "- Strengths (1–3 bullet points)\n"
            "- Weaknesses (1–3 bullet points)\n"
            "- Revenue (state as-is or 'AI Estimated')\n"
            "- ARR\n"
            "- Total Turnover\n"
            "- Any other relevant extras\n\n"
            "If any item is missing and cannot be reasonably estimated, return 'Data not found'."
        )

        # Upload the PDF file to OpenAI
        with open(file_path, "rb") as f:
            uploaded_file = client.files.create(file=f, purpose="user_data")
            file_id = uploaded_file.id

        # Use responses API
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_file",
                            "file_id": file_id,
                        },
                        {
                            "type": "input_text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        content = response.output_text.strip()
        print(
            'cc', content
        )
        extracted_data = parse_response_text(content)
        print(
            'ed', extracted_data
        )



        # Store structured pitch data
        pitch_data = PitchData(
            id=str(uuid4()),
            pitch_id=pitch_id,
            file_id=file_id,
            company=extracted_data["company"],
            industry=extracted_data["industry"],
            insights=extracted_data["insight_summary"],
            strengths="\n".join(extracted_data["strengths"]),
            weaknesses="\n".join(extracted_data["weaknesses"]),
            revenue=extracted_data["revenue"],
            arr=extracted_data["ARR"],
            total_turnover=extracted_data["total_turnover"],
            extras="\n".join(extracted_data["extras"]),
            investment_decision="pending"
        )

        db.add(pitch_data)
        db.commit()

    except (SQLAlchemyError, ValueError) as e:
        db.rollback()
        raise e

    finally:
        db.close()
        try:
            os.remove(file_path)
        except Exception:
            pass
