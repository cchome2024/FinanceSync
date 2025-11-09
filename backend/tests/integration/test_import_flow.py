from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Iterable

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app import db
from app.api.deps import get_ai_parser, get_import_job_repository, get_storage_adapter
from app.main import create_app
from app.models.base import Base
from app.models.financial import Company, RevenueRecord
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
    def __init__(self, month: str, amount: float) -> None:
        self._month = month
        self._amount = amount

    async def parse_prompt(self, prompt: str, attachments: Iterable[bytes]) -> tuple[list[CandidateRecord], dict]:
        records = [
            CandidateRecord(
                record_type=RecordType.REVENUE,
                payload={
                    "month": self._month,
                    "category": "主营业务收入",
                    "category_path": ["主营业务收入"],
                    "amount": self._amount,
                    "currency": "CNY",
                },
                confidence=0.88,
            )
        ]
        return records, {"records": [r.model_dump(mode="json", by_alias=True) for r in records]}


@pytest.fixture(name="client")
def client_fixture(tmp_path) -> TestClient:
    database_url = f"sqlite:///{tmp_path/'integration.db'}"
    db.configure_engine(database_url)
    Base.metadata.create_all(bind=db.engine)

    app = create_app()
    parser = FakeParser(month="2025-02-01", amount=123456.78)
    app.state.fake_parser = parser

    async def override_parser() -> FakeParser:
        return parser

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


def test_parse_and_confirm_flow(client: TestClient) -> None:
    company_id = str(uuid.uuid4())
    with db.session_scope() as session:
        session.add(
            Company(
                id=company_id,
                name="Test Co",
                display_name="测试公司",
                currency="CNY",
            )
        )

    response = client.post(
        "/api/v1/parse/upload",
        data={"prompt": "收入情况如下", "company_id": company_id},
    )
    assert response.status_code == 202
    job_payload = response.json()

    job_id = job_payload["jobId"]
    preview_record = job_payload["preview"][0]

    confirm_response = client.post(
        f"/api/v1/import-jobs/{job_id}/confirm",
        json={
            "actions": [
                {
                    "recordType": preview_record["recordType"],
                    "operation": "approve",
                    "payload": preview_record["payload"],
                }
            ]
        },
    )
    assert confirm_response.status_code == 200
    confirm_payload = confirm_response.json()
    assert confirm_payload["approvedCount"] == 1
    assert confirm_payload["rejectedCount"] == 0

    with db.session_scope() as verify_session:
        records: list[RevenueRecord] = (
            verify_session.query(RevenueRecord).filter_by(company_id=company_id).all()
        )
        assert len(records) == 1
        assert float(records[0].amount) == 123456.78
        assert records[0].category_id is not None


def test_confirm_revenue_requires_overwrite(client: TestClient) -> None:
    company_id = str(uuid.uuid4())
    with db.session_scope() as session:
        session.add(
            Company(
                id=company_id,
                name="Duplicate Co",
                display_name="重复公司",
                currency="CNY",
            )
        )

    # 首次导入
    response = client.post(
        "/api/v1/parse/upload",
        data={"prompt": "收入情况1", "company_id": company_id},
    )
    job_payload = response.json()
    job_id = job_payload["jobId"]
    preview_record = job_payload["preview"][0]

    confirm_response = client.post(
        f"/api/v1/import-jobs/{job_id}/confirm",
        json={
            "actions": [
                {
                    "recordType": preview_record["recordType"],
                    "operation": "approve",
                    "payload": preview_record["payload"],
                }
            ]
        },
    )
    assert confirm_response.status_code == 200

    # 第二次导入，同月同分类，先尝试覆盖前的确认
    # 调整解析器金额以便验证覆盖
    client.app.state.fake_parser._amount = 999999.0

    response2 = client.post(
        "/api/v1/parse/upload",
        data={"prompt": "收入情况2", "company_id": company_id},
    )
    job_payload2 = response2.json()
    job_id2 = job_payload2["jobId"]
    preview_record2 = job_payload2["preview"][0]

    conflict_response = client.post(
        f"/api/v1/import-jobs/{job_id2}/confirm",
        json={
            "actions": [
                {
                    "recordType": preview_record2["recordType"],
                    "operation": "approve",
                    "payload": preview_record2["payload"],
                }
            ]
        },
    )
    assert conflict_response.status_code == 409
    detail = conflict_response.json()["detail"]
    assert detail["recordType"] == "revenue"
    assert detail["conflict"]["month"].startswith("2025-02-01")

    # 带 overwrite 的确认应成功
    overwrite_response = client.post(
        f"/api/v1/import-jobs/{job_id2}/confirm",
        json={
            "actions": [
                {
                    "recordType": preview_record2["recordType"],
                    "operation": "approve",
                    "payload": preview_record2["payload"],
                    "overwrite": True,
                }
            ]
        },
    )
    assert overwrite_response.status_code == 200
    payload = overwrite_response.json()
    assert payload["approvedCount"] == 1

    with db.session_scope() as session:
        records = (
            session.query(RevenueRecord)
            .filter_by(company_id=company_id)
            .order_by(RevenueRecord.month)
            .all()
        )
        assert len(records) == 1
        assert float(records[0].amount) == 999999.0

