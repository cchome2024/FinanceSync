from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import AsyncIterator, Dict, Iterable

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app import db
from app.api.deps import get_ai_parser, get_import_job_repository, get_storage_adapter
from app.main import create_app
from app.models.base import Base
from app.repositories.import_jobs import ImportJobRepository
from app.schemas.imports import CandidateRecord, RecordType


class MemoryStorage:
    def __init__(self) -> None:
        self._store: Dict[str, bytes] = {}

    async def save(self, filename: str, data: bytes) -> str:
        self._store[filename] = data
        return filename

    async def read(self, path: str) -> bytes:
        return self._store[path]


class FakeParser:
    async def parse_prompt(self, prompt: str, attachments: Iterable[bytes]) -> tuple[list[CandidateRecord], dict]:
        records = [
            CandidateRecord(
                record_type=RecordType.ACCOUNT_BALANCE,
                payload={
                    "reported_at": "2025-01-01T00:00:00+00:00",
                    "cash_balance": 1000,
                    "investment_balance": 2000,
                    "total_balance": 3000,
                    "currency": "CNY",
                    "category_path": ["资产", "现金余额"],
                },
                confidence=0.92,
            )
        ]
        return records, {"records": [r.model_dump(mode="json", by_alias=True) for r in records]}


@pytest.fixture(name="client")
def client_fixture(tmp_path) -> TestClient:
    database_url = f"sqlite:///{tmp_path/'test.db'}"
    db.configure_engine(database_url)
    Base.metadata.create_all(bind=db.engine)

    app = create_app()

    async def override_parser() -> FakeParser:
        return FakeParser()

    def override_storage() -> MemoryStorage:
        return MemoryStorage()

    def override_repo() -> AsyncIterator[ImportJobRepository]:
        session = db.SessionLocal()
        repo = ImportJobRepository(session)
        try:
            yield repo
        finally:
            session.close()

    app.dependency_overrides[get_ai_parser] = override_parser
    app.dependency_overrides[get_storage_adapter] = override_storage
    app.dependency_overrides[get_import_job_repository] = override_repo

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=db.engine)


def test_parse_upload_returns_preview(client: TestClient) -> None:
    response = client.post(
        "/api/v1/parse/upload",
        data={"prompt": "账户余额见附件", "company_id": str(uuid.uuid4())},
    )
    assert response.status_code == 202
    payload = response.json()

    assert payload["status"] == "pending_review"
    assert isinstance(payload["jobId"], str)
    assert len(payload["preview"]) == 1
    record = payload["preview"][0]
    assert record["recordType"] == "account_balance"
    assert record["payload"]["total_balance"] == 3000
    assert "rawResponse" in payload
    assert isinstance(payload["rawResponse"], dict)

