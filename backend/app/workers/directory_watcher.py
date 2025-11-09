from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterable

from watchfiles import awatch

from app.core.config import get_settings
from app.workers import celery_app


async def watch_directories() -> None:
    settings = get_settings()
    directories = _parse_directories(settings.watch_directories)
    if not directories:
        return

    async for changes in awatch(*directories, poll_delay=settings.watch_poll_interval_seconds):
        for _, path in changes:
            celery_app.send_task("app.workers.import_processor.enqueue_file", kwargs={"file_path": path})


def _parse_directories(value: str) -> Iterable[Path]:
    return [Path(item.strip()) for item in value.split(",") if item.strip()]


def start_watcher_loop() -> None:
    asyncio.run(watch_directories())
