from __future__ import annotations

from typing import AsyncIterator, Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.repositories.import_jobs import ImportJobRepository
from app.services.ai_parser import AIParserService
from app.services.llm_client import LLMClient
from app.services.financial_overview import FinancialOverviewService
from app.services.nlq_service import NLQService
from app.services.storage_adapter import StorageAdapter, StorageFactory


def get_db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


async def get_ai_parser() -> AsyncIterator[AIParserService]:
    client = LLMClient()
    try:
        parser = AIParserService(client)
        yield parser
    finally:
        await client.close()


def get_storage_adapter() -> StorageAdapter:
    return StorageFactory.create()


def get_import_job_repository(session: Session = Depends(get_db_session)) -> ImportJobRepository:
    return ImportJobRepository(session)


def get_nlq_service(session: Session = Depends(get_db_session)) -> NLQService:
    return NLQService(session)


def get_financial_overview_service(session: Session = Depends(get_db_session)) -> FinancialOverviewService:
    return FinancialOverviewService(session)

