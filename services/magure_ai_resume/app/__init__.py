# app/__init__.py
'''


import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from dotenv import load_dotenv
from celery_app import make_celery

import cloudinary
import cloudinary.uploader
import os
load_dotenv()
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)



def upload_to_cloudinary(filepath, resource_type="auto", folder="resumes"):
    return cloudinary.uploader.upload(
        filepath,
        resource_type=resource_type,
        folder=folder
    )




app = Flask(__name__)
CORS(app)

basedir = os.path.abspath(os.path.dirname(__file__ + '/../'))
UPLOAD_FOLDER = os.path.join(basedir, 'uploaded_cvs')
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=70 * 1024 * 1024,
    SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(basedir, 'cv_uploads.db'),
    SECRET_KEY=os.getenv('FLASK_SECRET_KEY', 'fallback-insecure-key')
)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = SQLAlchemy(app)

# Create and expose celery instance here
celery = make_celery(app)

celery.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_transport_options={"visibility_timeout": 3600},
)
celery.conf.task_routes = {
    'tasks.upload_to_cloudinary_task': {'queue': 'resume_tasks'},
    'tasks.parse_resume_task': {'queue': 'resume_tasks'},
}

# Import routes and register
from app.routes import api
app.register_blueprint(api, url_prefix='/api')
'''
# app/__init__.py

import os
from flask import Flask, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from dotenv import load_dotenv
from celery_app import make_celery
from jose import jwt, JWTError
import cloudinary
import cloudinary.uploader



# ─── Load Env ─────────────────────────────────────────────
load_dotenv()


SECRET_KEY=os.getenv('SECRET_KEY')
# Shared with chatbox_backend
JWT_ALGORITHM=os.getenv('ALGORITHM', 'HS256')

# ─── Cloudinary Config ────────────────────────────────────
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

def upload_to_cloudinary(filepath, resource_type="auto", folder="resumes"):
    return cloudinary.uploader.upload(
        filepath,
        resource_type=resource_type,
        folder=folder
    )

# ─── Flask App Setup ──────────────────────────────────────
app = Flask(__name__)
CORS(app)

basedir = os.path.abspath(os.path.dirname(__file__ + '/../'))
UPLOAD_FOLDER = os.path.join(basedir, 'uploaded_cvs')
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=70 * 1024 * 1024,
    SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(basedir, 'cv_uploads.db'),
    #SECRET_KEY=os.getenv('FLASK_SECRET_KEY', 'fallback-insecure-key'),
    SECRET_KEY=os.getenv('SECRET_KEY'),  # Shared with chatbox_backend
    JWT_ALGORITHM=os.getenv('JWT_ALGORITHM', 'HS256')
)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ─── DB Init ───────────────────────────────────────────────
db = SQLAlchemy(app)

# ─── Celery Init ───────────────────────────────────────────
celery = make_celery(app)
celery.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_transport_options={"visibility_timeout": 3600},
)
celery.conf.task_routes = {
    'tasks.upload_to_cloudinary_task': {'queue': 'resume_tasks'},
    'tasks.parse_resume_task': {'queue': 'resume_tasks'},
}


# Define routes that don't require JWT
EXCLUDED_PATHS = [
    "/docs",
    "/openapi.json",

]


@app.before_request
def jwt_auth_middleware():
    path = request.path

    # Skip auth check for excluded routes
    if any(path.startswith(p) for p in EXCLUDED_PATHS) or request.endpoint == 'static':
        return

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"detail": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(" ")[1]

    try:
        print("JWT:", JWT_ALGORITHM, SECRET_KEY)
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )
        g.user_id = payload.get("sub")
        if g.user_id is None:
            return jsonify({"detail": "Token missing user_id (sub)"}), 401
    except JWTError as e:
        return jsonify({"detail": "Invalid token", "error": str(e)}), 401


# ─── Register Routes ───────────────────────────────────────
from app.routes import api
app.register_blueprint(api, url_prefix='/api')
