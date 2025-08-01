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
            "You are a startup analyst assistant. A user has uploaded a pitch deck PDF. "
            "Extract the following key details from the document:\n\n"

            "1. Company\n"
            "2. Industry\n"
            "3. Insight Summary (approx. 100 words)\n"
            "4. Strengths (1–3 bullet points)\n"
            "5. Weaknesses (1–3 bullet points)\n"
            "6. Revenue (state as-is or 'AI Estimated')\n"
            "7. ARR (Annual Recurring Revenue)\n"
            "8. Total Turnover\n"
            "9. Financial Growth:\n"
            "   - Month-over-Month (MoM) Revenue Growth\n"
            "   - Year-over-Year (YoY) Revenue Growth\n"
            "10. Market Insights:\n"
            "   - Market Capitalization (Market Cap)\n"
            "   - Total Addressable Market (TAM)\n"
            "   - Total Finance Flow in the Sector\n"
            "11. Technology Used\n"
            "12. Broad Operational Sector\n"
            "13. Team:\n"
            "   - Team Size\n"
            "   - Brief details of core team members (names, roles, experience if available)\n"
            "14. Competition:\n"
            "   - Who are the competitors?\n"
            "   - What is the competitive landscape?\n"
            "15. Market Share:\n"
            "   - What is this company's market share within its sector?\n"
            "16. Intellectual Property (IP):\n"
            "   - Any patents, trademarks, or proprietary technologies?\n"
            "17. 5-Year Growth Plan:\n"
            "   - What are the company’s stated or implied goals for the next five years?\n"
            "18. Any other relevant extras found in the pitch\n\n"

            "If any item is missing or cannot be reasonably estimated, return 'Data not found'."
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
        extracted_data = parse_response_text(content)




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

            # New financial growth fields
            revenue_yoy_growth=extracted_data["revenue_yoy_growth"],
            revenue_mom_growth=extracted_data["revenue_mom_growth"],

            # New market insight fields
            market_cap=extracted_data["market_cap"],
            tam=extracted_data["TAM"],
            total_finance_flow=extracted_data["total_finance_flow"],

            # Technology and sector
            technology=extracted_data["technology"],
            operational_sector=extracted_data["operational_sector"],

            # Team details
            team_size=extracted_data["team_size"],
            core_team_details=extracted_data["core_team_details"],

            # Competitive landscape
            competition=extracted_data["competition"],
            market_share=extracted_data["market_share"],

            # Intellectual property and growth plan
            ip=extracted_data["IP"],
            growth_plan_5_years=extracted_data["growth_plan_5_years"],

            # Extras and default
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


'''
#step 1 install 

#step2
from pdf2image import convert_from_path
from io import BytesIO
import base64

def get_pdf_page_images(file_path: str, start: int, end: int):
    images = convert_from_path(file_path, dpi=150, first_page=start, last_page=end)
    image_base64_list = []
    for img in images:
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        image_base64_list.append(img_base64)
    return image_base64_list
    
    
    #step3
    import openai

openai.api_key = "sk-..."  # your API key

def extract_insights_from_images(images_base64: list[str]) -> str:
    messages = [{"role": "user", "content": "Please extract pitch insights from the following pages of a pitch deck."}]
    
    for img_b64 in images_base64:
        messages.append({
            "role": "user",
            "content": [{
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_b64}",
                    "detail": "low"
                }
            }]
        })

    response = openai.ChatCompletion.create(
        model="gpt-4-vision-preview",
        messages=messages,
        max_tokens=800
    )

    return response.choices[0].message.content.strip()
    
#step4 
    from math import ceil
from PyPDF2 import PdfReader
from app.models import PitchData
from app.db import SessionLocal
import uuid

def process_pitch_pdf_images(pitch_id: str, file_path: str):
    session = SessionLocal()
    try:
        total_pages = len(PdfReader(file_path).pages)
        chunks = ceil(total_pages / 4)

        all_insights = []

        for i in range(chunks):
            start = i * 4 + 1
            end = min(start + 3, total_pages)
            images_b64 = get_pdf_page_images(file_path, start, end)
            insights = extract_insights_from_images(images_b64)
            all_insights.append(f"Pages {start}-{end}:\n{insights}")

        combined = "\n\n".join(all_insights)

        pitch_data = PitchData(
            id=str(uuid.uuid4()),
            pitch_id=pitch_id,
            extras=combined  # store in extras
        )
        session.add(pitch_data)
        session.commit()
        return {"status": "success", "insights": combined}

    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

'''