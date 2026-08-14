from celery import Celery
from celery.schedules import schedule
from celery.signals import worker_process_init

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
        "app.workers.tasks_discovery_prewarm",
    ]
)
celery_app.conf.task_default_queue = "crawlio"


@worker_process_init.connect
def _hydrate_integration_overrides(**kwargs) -> None:
    """Load admin-set API-key overrides into the worker process's runtime cache
    so e.g. a Brevo key changed from the panel applies to background email sends
    without a worker restart."""
    import asyncio

    from app.services.admin import integration_service

    try:
        asyncio.run(integration_service.hydrate_runtime_from_db())
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Could not hydrate integration overrides in worker")

# First periodic (Celery beat) task in this project — refreshes discovery_cache
# rows before they go stale. The task itself is a no-op unless
# discovery_prewarm_enabled is on, so this schedule entry is harmless when the
# feature is off; it just means beat wakes up every tick and immediately
# returns. Requires a `celery ... beat` process actually running in addition
# to the worker (see docker-compose.yml's `beat` service).
celery_app.conf.beat_schedule = {
    "prewarm-discovery-cache": {
        "task": "prewarm_discovery_cache",
        "schedule": schedule(settings.discovery_prewarm_interval_minutes * 60),
    },
}
