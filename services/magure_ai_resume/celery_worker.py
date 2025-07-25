# celery_worker.py

from app import app, celery  # Import the actual instances
import app.celery_tasks      # Ensures tasks are registered

if __name__ == '__main__':
    with app.app_context():
        celery.start()
