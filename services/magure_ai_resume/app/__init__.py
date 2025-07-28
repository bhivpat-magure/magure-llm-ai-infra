# app/__init__.py

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
