from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "crawlio",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.tasks_scoring",
        "app.workers.tasks_email",
        "app.workers.tasks_email_agent",
        "app.workers.tasks_enrichment",
    ]
)
celery_app.conf.task_default_queue = "crawlio"
