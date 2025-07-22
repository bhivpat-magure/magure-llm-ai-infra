from celery import Celery

def make_celery():
    return Celery(
        "worker",
        broker="redis://redis:6379/0",
        backend="redis://redis:6379/0"
    )
