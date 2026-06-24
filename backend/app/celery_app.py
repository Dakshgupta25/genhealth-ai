"""
Celery application configuration.

Configures the Celery task queue with Redis as both the broker and result
backend. Tasks are auto-discovered from the app.tasks modules.
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

# Create the Celery application
celery_app = Celery(
    "genhealth",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.ocr_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.risk_tasks",
    ],
)

# ─── Configuration ────────────────────────────────────────────────────────────
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="Asia/Kolkata",
    enable_utc=True,
    # Task acknowledgment (mark task as acknowledged only after completion)
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Result expiry: keep results for 24 hours
    result_expires=86400,
    # Retry configuration
    task_max_retries=3,
    task_default_retry_delay=60,  # seconds
    # Task routing
    task_routes={
        "app.tasks.ocr_tasks.*": {"queue": "ocr"},
        "app.tasks.risk_tasks.*": {"queue": "risk"},
        "app.tasks.notification_tasks.*": {"queue": "notifications"},
    },
    # Default queue
    task_default_queue="default",
    # Beat schedule (periodic tasks)
    beat_schedule={
        "refresh-risk-predictions-daily": {
            "task": "app.tasks.risk_tasks.refresh_all_risk_predictions",
            "schedule": 86400.0,  # Every 24 hours
        },
    },
)


@celery_app.task(name="app.tasks.health_check")
def health_check() -> dict:
    """Simple health check task to verify Celery worker is running."""
    return {"status": "ok", "worker": "genhealth-worker"}
