from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterable, Sequence

from watchfiles import awatch

from app.core.config import get_settings
from app.db import SessionLocal
from app.models.financial import ImportStatus
from app.repositories.import_jobs import ImportJobRepository
from app.services.ai_parser import AIParserService
from app.services.llm_client import LLMClient
from app.services.storage_adapter import StorageFactory
from app.workers import celery_app


@celery_app.task(name="app.workers.import_processor.process_prompt")
def process_prompt(job_id: str, prompt: str, attachment_paths: Sequence[str] | None = None) -> None:
    """后台解析导入任务。"""

    async def _run() -> None:
        client = LLMClient()
        parser = AIParserService(client)
        storage = StorageFactory.create()

        attachments = []
        for path in attachment_paths or []:
            attachments.append(await storage.read(path))

        preview = await parser.parse_prompt(prompt, attachments)

        with SessionLocal() as session:
            repo = ImportJobRepository(session)
            job = repo.get_job(job_id)
            if not job:
                return
            repo.save_preview(job, preview)
            job.status = ImportStatus.PENDING_REVIEW
            session.commit()

    asyncio.run(_run())


@celery_app.task(name="app.workers.import_processor.enqueue_file")
def enqueue_file(file_path: str) -> None:
    """目录监控后续扩展，此处占位。"""
    return None


async def watch_directories() -> None:
    """监听配置目录，一旦有新文件即触发 Celery 任务。"""
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

