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
