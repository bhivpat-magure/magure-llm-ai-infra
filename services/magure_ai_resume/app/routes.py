from flask import Blueprint, request, jsonify, g
from app import app, db
from app.models import Group, UploadedCV, JsonData
import traceback
import logging
from datetime import datetime

from .controller import (
    search_resume_matches,
    enrich_candidate_details,
    parse_experience_to_years,
    handle_cv_upload,
    handle_jd_upload,
    clear_all_data,
    delete_cv,
    add_comment_to_cv,
    get_processing_info
)

from .audit import log_audit, fetch_audit_logs

logger = logging.getLogger(__name__)
api = Blueprint('api', __name__)



def get_client_ip():
    """Try to get client IP for logging."""
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr


@api.route("/", methods=["GET"])
def index():
    log_audit(
        service_name="resume_service",
        action="INDEX",
        user_id=g.get("user_id"),
        ip_address=get_client_ip(),
        request_data=None,
        response_data={"message": "Welcome to the Resume Analyzer API", "status": "SUCCESS"}
    )
    return jsonify({"message": "Welcome to the Resume Analyzer API"}), 200


@api.route("/groups", methods=["GET"])
def list_groups():
    groups = [g.as_dict() for g in Group.query.all()]
    log_audit(
        service_name="resume_service",
        action="LIST_GROUPS",
        user_id=g.get("user_id"),
        ip_address=get_client_ip(),
        request_data=None,
        response_data={"count": len(groups), "status": "SUCCESS"}
    )
    return jsonify(groups), 200


@api.route("/groups", methods=["POST"])
def create_group():
    data = request.get_json()
    name = data.get("name")
    if not name:
        log_audit(
            service_name="resume_service",
            action="CREATE_GROUP",
            user_id=g.get("user_id"),
            ip_address=get_client_ip(),
            request_data=data,
            response_data={"error": "Missing group name", "status": "FAILURE"}
        )
        return jsonify({"error": "Group name required"}), 400

    if Group.query.filter_by(name=name).first():
        log_audit(
            service_name="resume_service",
            action="CREATE_GROUP",
            user_id=g.get("user_id"),
            ip_address=get_client_ip(),
            request_data=data,
            response_data={"error": f"Group exists: {name}", "status": "FAILURE"}
        )
        return jsonify({"error": "Group already exists"}), 400

    db.session.add(Group(name=name))
    db.session.commit()

    log_audit(
        service_name="resume_service",
        action="CREATE_GROUP",
        user_id=g.get("user_id"),
        ip_address=get_client_ip(),
        request_data=data,
        response_data={"message": f"Created group: {name}", "status": "SUCCESS"}
    )
    return jsonify({"message": "Group created"}), 201


@api.route("/groups/<int:group_id>", methods=["DELETE"])
def delete_group(group_id):
    group = Group.query.get_or_404(group_id)
    if group.cvs:
        log_audit(
            service_name="resume_service",
            action="DELETE_GROUP",
            user_id=g.get("user_id"),
            ip_address=get_client_ip(),
            request_data={"group_id": group_id},
            response_data={"error": "Group has associated CVs", "status": "FAILURE"}
        )
        return jsonify({"error": "Group has associated CVs"}), 400

    db.session.delete(group)
    db.session.commit()

    log_audit(
        service_name="resume_service",
        action="DELETE_GROUP",
        user_id=g.get("user_id"),
        ip_address=get_client_ip(),
        request_data={"group_id": group_id},
        response_data={"message": "Group deleted", "status": "SUCCESS"}
    )
    return jsonify({"message": "Group deleted"}), 200


@api.route("/upload_cv", methods=["POST"])
def upload_cv():
    try:
        uploaded_files, errors = handle_cv_upload(
            request.files.getlist('cv'),
            request.form.get("group")
        )
        log_audit(
            service_name="resume_service",
            action="UPLOAD_CV",
            user_id=g.get("user_id"),
            ip_address=get_client_ip(),
            request_data={"group": request.form.get("group")},
            response_data={"uploaded_count": len(uploaded_files), "errors_count": len(errors), "status": "SUCCESS"}
        )
        return jsonify({"uploaded": uploaded_files, "errors": errors}), 200
    except Exception as e:
        logger.error(traceback.format_exc())
        log_audit(
            service_name="resume_service",
            action="UPLOAD_CV",
            user_id=g.get("user_id"),
            ip_address=get_client_ip(),
            request_data={"group": request.form.get("group")},
            response_data={"error": str(e), "status": "FAILURE"}
        )
        return jsonify({"error": str(e)}), 500


@api.route("/search_api", methods=["POST"])
def search_api():
    data = request.get_json()
    try:
        query = data.get("query")
        group_name = data.get("group")
        results = search_resume_matches(query, group_name)
        from utils.llm import build_prompt, query_with_openai_sdk
        prompt = build_prompt(query, results)
        answer = query_with_openai_sdk(prompt)
        if answer.get("summary") not in ["1", "2"] and answer.get("candidate_details"):
            enrich_candidate_details(answer["candidate_details"])

        log_audit(
            service_name="resume_service",
            action="SEARCH_API",
            user_id=g.get("user_id"),
            ip_address=get_client_ip(),
            request_data=data,
            response_data={"query": query, "group": group_name, "results_count": len(results), "status": "SUCCESS"}
        )
        return jsonify({"answer": answer, "results": results}), 200
    except Exception as e:
        logger.error(traceback.format_exc())
        log_audit(
            service_name="resume_service",
            action="SEARCH_API",
            user_id=g.get("user_id"),
            ip_address=get_client_ip(),
            request_data=data,
            response_data={"error": str(e), "status": "FAILURE"}
        )
        return jsonify({"error": str(e)}), 500


@api.route("/upload_jd", methods=["POST"])
def upload_jd():
    try:
        query, results, answer = handle_jd_upload(
            request.files.get("file"),
            request.form.get("group")
        )
        if answer.get("summary") not in ["1", "2"] and answer.get("candidate_details"):
            enrich_candidate_details(answer["candidate_details"])

        log_audit(
            service_name="resume_service",
            action="UPLOAD_JD",
            user_id=g.get("user_id"),
            ip_address=get_client_ip(),
            request_data={"group": request.form.get("group")},
            response_data={"query": query, "results_count": len(results), "status": "SUCCESS"}
        )
        return jsonify({"answer": answer, "results": results}), 200
    except Exception as e:
        logger.error(traceback.format_exc())
        log_audit(
            service_name="resume_service",
            action="UPLOAD_JD",
            user_id=g.get("user_id"),
            ip_address=get_client_ip(),
            request_data={"group": request.form.get("group")},
            response_data={"error": str(e), "status": "FAILURE"}
        )
        return jsonify({"error": str(e)}), 500


@api.route("/clear_all", methods=["DELETE"])
def clear_all():
    clear_all_data()
    log_audit(
        service_name="resume_service",
        action="CLEAR_ALL",
        user_id=g.get("user_id"),
        ip_address=get_client_ip(),
        request_data=None,
        response_data={"message": "All data cleared", "status": "SUCCESS"}
    )
    return jsonify({"message": "All data cleared"}), 200


@api.route("/delete/<int:cv_id>", methods=["DELETE"])
def delete_cv_route(cv_id):
    try:
        delete_cv(cv_id)
        log_audit(
            service_name="resume_service",
            action="DELETE_CV",
            user_id=g.get("user_id"),
            ip_address=get_client_ip(),
            request_data={"cv_id": cv_id},
            response_data={"message": "CV deleted", "status": "SUCCESS"}
        )
        return jsonify({"message": "CV deleted"}), 200
    except Exception as e:
        log_audit(
            service_name="resume_service",
            action="DELETE_CV",
            user_id=g.get("user_id"),
            ip_address=get_client_ip(),
            request_data={"cv_id": cv_id},
            response_data={"error": str(e), "status": "FAILURE"}
        )
        return jsonify({"error": str(e)}), 500


@api.route("/cv/<int:cv_id>/comment", methods=["POST"])
def add_comment_route(cv_id):
    data = request.get_json()
    if not data.get("comment"):
        log_audit(
            service_name="resume_service",
            action="ADD_COMMENT",
            user_id=g.get("user_id"),
            ip_address=get_client_ip(),
            request_data={"cv_id": cv_id, "comment": data.get("comment")},
            response_data={"error": "Missing comment", "status": "FAILURE"}
        )
        return jsonify({"error": "Comment is required"}), 400

    cv_dict = add_comment_to_cv(cv_id, data["comment"])
    log_audit(
        service_name="resume_service",
        action="ADD_COMMENT",
        user_id=g.get("user_id"),
        ip_address=get_client_ip(),
        request_data={"cv_id": cv_id, "comment": data["comment"]},
        response_data={"message": "Comment saved", "status": "SUCCESS"}
    )
    return jsonify({"message": "Comment saved", "cv": cv_dict}), 200


@api.route("/resume-processing", methods=["GET"])
def get_processing_info_route():
    try:
        info = get_processing_info()
        log_audit(
            service_name="resume_service",
            action="RESUME_PROCESSING",
            user_id=g.get("user_id"),
            ip_address=get_client_ip(),
            request_data=None,
            response_data={**info, "status": "SUCCESS"}
        )
        return jsonify(info), 200
    except Exception as e:
        log_audit(
            service_name="resume_service",
            action="RESUME_PROCESSING",
            user_id=g.get("user_id"),
            ip_address=get_client_ip(),
            request_data=None,
            response_data={"error": str(e), "status": "FAILURE"}
        )
        return jsonify({"error": str(e)}), 500


@api.route("/audit_logs", methods=["GET"])
def get_audit_logs():
    try:
        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))
        user_id = request.args.get("user_id") or g.get("user_id")
        print("route data", limit, offset, user_id)
        #service_name = request.args.get("service_name")


        logs = fetch_audit_logs(limit=limit, offset=offset, user_id=user_id)

        if isinstance(logs, dict) and logs.get("error"):
            # Error occurred in fetching logs
            return jsonify({"error": logs["error"]}), 500

        return jsonify({"logs": logs, "count": len(logs)}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/cvs", methods=["POST"])
def get_cvs():
    data = request.get_json() or {}
    group_name = data.get("group")
    results = []

    log_audit(
        service_name="resume_service",
        action="FETCH_ALLRESUME",
        user_id=g.get("user_id"),
        ip_address=get_client_ip(),
        request_data=group_name,
        response_data={"message": "All Resumes fetched", "status": "SUCCESS"}
    )

    # ─── 1. Group Filtering ───
    if group_name and group_name.lower() not in ["null", "undefined", ""]:
        group = Group.query.filter_by(name=group_name).first()
        if not group:
            return jsonify([]), 200
        cvs = UploadedCV.query.filter_by(group_id=group.id).order_by(UploadedCV.upload_time.desc()).all()
    else:
        cvs = UploadedCV.query.order_by(UploadedCV.upload_time.desc()).all()

    # ─── 2. Get JsonData for all CVs ───
    json_map = {
        jd.cv_id: jd
        for jd in JsonData.query.filter(JsonData.cv_id.in_([cv.id for cv in cvs])).all()
    }

    for cv in cvs:
        jd = json_map.get(cv.id)
        if not jd:
            continue

        # ─── 3. Base CV Data ───
        cv_dict = cv.as_dict()
        cv_dict.update({
            "name": jd.data.get("name", "Data not found") if jd.data else "Data not found",
            "job_profile": jd.data.get("job_profile", "Data not found") if jd.data else "Data not found",
            "total_experience": jd.total_experience or "Data not found"
        })

        # ─── 4. Filter by CV ID ───
        if "cv_id" in data:
            if int(data["cv_id"]) != cv.id:
                continue

        # ─── 5. Filter by Experience Range ───
        if "experience" in data:
            try:
                exp_str = jd.total_experience or ""
                exp = parse_experience_to_years(exp_str)
                min_exp, max_exp = float(data["experience"][0]), float(data["experience"][1])
                if not (min_exp <= exp <= max_exp):
                    continue
            except Exception as e:
                logger.warning(f"Experience parsing failed for CV {cv.id}: {e}")
                continue

        # ─── 6. Filter by Skills ───
        if "skills" in data:
            required_skills = set([s.strip().lower() for s in data["skills"]])
            candidate_skills = set([s.strip().lower() for s in jd.skills or []])
            matched_skills = required_skills & candidate_skills

            cv_dict["total_skills_candidate"] = len(candidate_skills)
            cv_dict["matched_skills_count"] = len(matched_skills)

            if not matched_skills:
                continue

        # ─── 7. Filter by Location ───
        if "location" in data:
            candidate_location = (jd.location or "").strip().lower()
            if candidate_location != data["location"].strip().lower():
                continue

        # ─── 8. Filter by Education ───
        if "education" in data:
            edu_required = data["education"].strip().lower()
            edu_list = [e.strip().lower() for e in jd.education or []]
            if edu_required not in edu_list:
                continue

        # ─── 9. Filter by Availability ───
        if "availability" in data:
            if not jd.last_working_date:
                continue  # Currently working → exclude

            try:
                lwd = jd.last_working_date
                if isinstance(lwd, str):
                    lwd = datetime.fromisoformat(lwd)

                today = datetime.utcnow()
                delta_days = (today - lwd).days
                avail_req = data["availability"].strip().lower()

                if avail_req == "immediately":
                    if lwd > today:
                        continue
                elif avail_req == "15 days" and delta_days < -15:
                    continue
                elif avail_req == "30 days" and delta_days < -30:
                    continue
                elif avail_req == "45 days" and delta_days < -45:
                    continue
                else:
                    pass  # Unknown availability term will fall through
            except Exception as e:
                logger.warning(f"Availability filter failed for CV {cv.id}: {e}")
                continue

        # ─── 10. Calculate Days Available ───
        if jd.last_working_date:
            try:
                lwd = jd.last_working_date
                if isinstance(lwd, str):
                    lwd = datetime.fromisoformat(lwd)
                cv_dict["days_available"] = (datetime.utcnow() - lwd).days
            except Exception:
                cv_dict["days_available"] = "Invalid date format"
        else:
            cv_dict["days_available"] = "Currently Working"

        results.append(cv_dict)

    return jsonify(results), 200

