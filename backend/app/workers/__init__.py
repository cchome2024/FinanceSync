from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "financesync",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_default_queue="financesync-default",
    task_routes={
        "app.workers.import_processor.*": {"queue": "import-jobs"},
        "app.workers.directory_watcher.*": {"queue": "watcher"},
    },
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

__all__ = ["celery_app"]
