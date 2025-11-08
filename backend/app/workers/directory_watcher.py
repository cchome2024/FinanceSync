from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterable

from watchfiles import awatch

from backend.app.core.config import get_settings
from backend.app.workers import celery_app


async def watch_directories() -> None:
    settings = get_settings()
    directories = _parse_directories(settings.watch_directories)
    if not directories:
        return

    async for changes in awatch(*directories, poll_delay=settings.watch_poll_interval_seconds):
        for change_type, path in changes:
            celery_app.send_task(
                "backend.app.workers.import_processor.schedule_file_import",
                kwargs={"file_path": path, "change_type": change_type.name},
            )


def _parse_directories(value: str) -> Iterable[Path]:
    return [Path(item.strip()) for item in value.split(",") if item.strip()]


def start_watcher_loop() -> None:
    asyncio.run(watch_directories())
