import os
import re
import random
import string
import logging
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo
from werkzeug.utils import secure_filename
from app import app, db
from app.models import Group, UploadedCV, JsonData
from app.celery_tasks import parse_resume_task, upload_to_cloudinary_task
from utils.cv_processing import (
    process_and_store_embeddings,
    delete_cv_data,
    extract_text_from_pdf,
    extract_text_from_docx
)
from utils.retriever import retrieve_similar_chunks
from utils.llm import build_prompt, query_with_openai_sdk
import shutil

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx'}


def search_resume_matches(query, group_name):
    if not query:
        raise ValueError("No query provided")

    results = []
    if not group_name or group_name.lower() in ["null", "undefined", ""]:
        for grp in Group.query.all():
            results.extend(retrieve_similar_chunks(query, k=5, group=grp.name))
    else:
        group_obj = Group.query.filter_by(name=group_name).first()
        if not group_obj:
            raise LookupError(f"Group '{group_name}' not found")
        results = retrieve_similar_chunks(query, k=5, group=group_obj.name)
    return results


def enrich_candidate_details(candidate_details):
    if not candidate_details:
        return
    file_names = [c.get("file_name") for c in candidate_details if "file_name" in c]
    cvs = UploadedCV.query.filter(UploadedCV.stored_filename.in_(file_names)).all()
    cv_map = {cv.stored_filename: cv for cv in cvs}
    json_data_list = JsonData.query.filter(JsonData.cv_id.in_([cv.id for cv in cvs])).all()
    jd_map = {jd.cv_id: jd for jd in json_data_list}

    for candidate in candidate_details:
        file_name = candidate.get("file_name")
        cv = cv_map.get(file_name)
        if not cv:
            continue
        jd = jd_map.get(cv.id)
        candidate.update({
            "cv_id": cv.id,
            "comment": cv.comment,
            "commented_at": cv.commented_at.isoformat() if cv.commented_at else None,
            "email": jd.email if jd else [],
            "phone": jd.phone if jd else [],
            "college": jd.college if jd else [],
            "job_profile": jd.job_profile if jd else None,
            "total_experience": jd.total_experience if jd else None
        })


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_unique_id(length=5):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def parse_experience_to_years(exp_str: str) -> float:
    if not exp_str or not isinstance(exp_str, str):
        return 0.0
    year_match = re.search(r"(\d+)\s*year", exp_str)
    month_match = re.search(r"(\d+)\s*month", exp_str)
    years = int(year_match.group(1)) if year_match else 0
    months = int(month_match.group(1)) if month_match else 0
    return round(years + (months / 12), 2)


def handle_cv_upload(files, group_name):
    if not files or files == [None]:
        raise ValueError("No files selected")
    if not group_name:
        raise ValueError("No group selected")

    group_obj = Group.query.filter_by(name=group_name).first()
    if not group_obj:
        group_obj = Group(name=group_name)
        db.session.add(group_obj)
        db.session.commit()

    uploaded_files, errors = [], []
    for file in files:
        if file and allowed_file(file.filename):
            unique_filename = f"{generate_unique_id()}_{secure_filename(file.filename)}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            uploaded = UploadedCV(
                original_filename=file.filename,
                stored_filename=unique_filename,
                filepath=filepath,
                group_id=group_obj.id
            )
            db.session.add(uploaded)
            db.session.commit()
            parse_resume_task.delay(uploaded.id, group_name)
            upload_to_cloudinary_task.delay(uploaded.id)
            uploaded_files.append(uploaded.as_dict())
        else:
            errors.append({"filename": file.filename, "error": "Invalid file type"})
    return uploaded_files, errors


def handle_jd_upload(file, group_name):
    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.pdf':
        raw_text = extract_text_from_pdf(file)
    elif ext == '.docx':
        raw_text = extract_text_from_docx(file)
    else:
        raise ValueError("Unsupported file type")
    query = raw_text.strip()
    if not query:
        raise ValueError("Could not derive search query from file")
    results = search_resume_matches(query, group_name)
    prompt = build_prompt(query, results)
    answer = query_with_openai_sdk(prompt)
    return query, results, answer


def clear_all_data():
    UploadedCV.query.delete()
    JsonData.query.delete()
    Group.query.delete()
    db.session.commit()
    vector_dir = os.path.join(os.path.dirname(__file__), '..', 'vector_store')
    if os.path.exists(vector_dir):
        shutil.rmtree(vector_dir)
        os.makedirs(vector_dir)
    shutil.rmtree(app.config['UPLOAD_FOLDER'], ignore_errors=True)
    os.makedirs(app.config['UPLOAD_FOLDER'])


def delete_cv(cv_id):
    cv = UploadedCV.query.get_or_404(cv_id)
    if os.path.exists(cv.filepath):
        os.remove(cv.filepath)
    json_entry = JsonData.query.filter_by(cv_id=cv.id).first()
    if json_entry:
        db.session.delete(json_entry)
    delete_cv_data(cv.stored_filename, group=cv.group_rel.name)
    db.session.delete(cv)
    db.session.commit()


def add_comment_to_cv(cv_id, comment):
    cv = UploadedCV.query.get_or_404(cv_id)
    cv.comment = comment
    cv.commented_at = datetime.now(ZoneInfo("Asia/Kolkata"))
    db.session.commit()
    return cv.as_dict()


def get_processing_info():
    total_cvs = db.session.query(UploadedCV).count()
    parsed_cvs = db.session.query(JsonData).filter_by(parsed=1).count()
    return {
        "total_cvs": total_cvs,
        "parsed_cvs": parsed_cvs,
        "pending_cvs": total_cvs - parsed_cvs
    }
