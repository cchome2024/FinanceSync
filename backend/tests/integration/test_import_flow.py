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
from app.models.financial import Company, RevenueDetail, IncomeForecast, ExpenseForecast
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
    def __init__(self, occurred_on: str, amount: float) -> None:
        self._occurred_on = occurred_on
        self._amount = amount
        self._custom_records: list[CandidateRecord] | None = None

    def set_custom_records(self, records: list[CandidateRecord] | None) -> None:
        self._custom_records = records

    async def parse_prompt(self, prompt: str, attachments: Iterable[bytes]) -> tuple[list[CandidateRecord], dict]:
        if self._custom_records is not None:
            records = self._custom_records
        else:
            records = [
                CandidateRecord(
                    record_type=RecordType.REVENUE,
                    payload={
                        "occurred_on": self._occurred_on,
                        "category_path": ["主营业务收入", "产品销售"],
                        "category": "产品销售",
                        "description": "测试收入",
                        "account_name": "基本户",
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
    parser = FakeParser(occurred_on="2025-02-10", amount=123456.78)
    app.state.fake_parser = parser

    async def override_parser() -> FakeParser:
        return app.state.fake_parser

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
        records: list[RevenueDetail] = (
            verify_session.query(RevenueDetail).filter_by(company_id=company_id).all()
        )
        assert len(records) == 1
        assert float(records[0].amount) == 123456.78
        assert records[0].category_id is not None
        assert records[0].occurred_on.isoformat() == "2025-02-10"


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
    assert detail["conflict"]["occurredOn"].startswith("2025-02-10")

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
            session.query(RevenueDetail)
            .filter_by(company_id=company_id)
            .order_by(RevenueDetail.occurred_on)
            .all()
        )
        assert len(records) == 1
        assert float(records[0].amount) == 999999.0


def test_income_forecast_full_replace(client: TestClient) -> None:
    company_id = str(uuid.uuid4())
    with db.session_scope() as session:
        session.add(
            Company(
                id=company_id,
                name="Forecast Co",
                display_name="预测公司",
                currency="CNY",
            )
        )

    parser: FakeParser = client.app.state.fake_parser
    first_records = [
        CandidateRecord(
            record_type=RecordType.REVENUE_FORECAST,
            payload={
                "company_id": company_id,
                "cash_in_date": "2025-06-15",
                "category_path": ["预测收入", "咨询服务"],
                "category": "咨询服务",
                "description": "预测款项A",
                "account_name": "预测账号",
                "expected_amount": 500000,
                "currency": "CNY",
                "certainty": "certain",
            },
            confidence=0.75,
        ),
        CandidateRecord(
            record_type=RecordType.REVENUE_FORECAST,
            payload={
                "company_id": company_id,
                "cash_in_date": "2025-07-20",
                "category_path": ["预测收入", "咨询服务"],
                "category": "咨询服务",
                "description": "预测款项B",
                "account_name": "预测账号",
                "expected_amount": 200000,
                "currency": "CNY",
                "certainty": "uncertain",
            },
            confidence=0.6,
        ),
    ]
    parser.set_custom_records(first_records)

    response = client.post(
        "/api/v1/parse/upload",
        data={"prompt": "预测收入", "company_id": company_id},
    )
    assert response.status_code == 202
    job_payload = response.json()
    job_id = job_payload["jobId"]

    confirm_actions = [
        {
            "recordType": record["recordType"],
            "operation": "approve",
            "payload": record["payload"],
        }
        for record in job_payload["preview"]
    ]
    confirm_response = client.post(
        f"/api/v1/import-jobs/{job_id}/confirm",
        json={"actions": confirm_actions},
    )
    assert confirm_response.status_code == 200

    with db.session_scope() as session:
        saved = (
            session.query(IncomeForecast)
            .filter(IncomeForecast.company_id == company_id)
            .order_by(IncomeForecast.cash_in_date)
            .all()
        )
        assert len(saved) == 2
        assert saved[0].description == "预测款项A"
        assert float(saved[1].expected_amount) == 200000

    second_records = [
        CandidateRecord(
            record_type=RecordType.REVENUE_FORECAST,
            payload={
                "company_id": company_id,
                "cash_in_date": "2025-08-10",
                "category_path": ["预测收入", "咨询服务"],
                "category": "咨询服务",
                "description": "预测款项C",
                "account_name": "预测账号",
                "expected_amount": 1000000,
                "currency": "CNY",
            },
        )
    ]
    parser.set_custom_records(second_records)

    response2 = client.post(
        "/api/v1/parse/upload",
        data={"prompt": "预测收入更新", "company_id": company_id},
    )
    assert response2.status_code == 202
    job_payload2 = response2.json()
    job_id2 = job_payload2["jobId"]

    confirm_response2 = client.post(
        f"/api/v1/import-jobs/{job_id2}/confirm",
        json={
            "actions": [
                {
                    "recordType": job_payload2["preview"][0]["recordType"],
                    "operation": "approve",
                    "payload": job_payload2["preview"][0]["payload"],
                }
            ]
        },
    )
    assert confirm_response2.status_code == 200

    with db.session_scope() as session:
        saved_after = session.query(IncomeForecast).filter_by(company_id=company_id).all()
        assert len(saved_after) == 1
        assert saved_after[0].description == "预测款项C"
        assert float(saved_after[0].expected_amount) == 1000000

    parser.set_custom_records(None)


def test_expense_forecast_full_replace(client: TestClient) -> None:
    company_id = str(uuid.uuid4())
    with db.session_scope() as session:
        session.add(
            Company(
                id=company_id,
                name="Expense Forecast Co",
                display_name="支出预测公司",
                currency="CNY",
            )
        )

    parser: FakeParser = client.app.state.fake_parser
    first_records = [
        CandidateRecord(
            record_type=RecordType.EXPENSE_FORECAST,
            payload={
                "company_id": company_id,
                "cash_out_date": "2025-06-05",
                "category_path": ["费用预算", "市场推广"],
                "category": "市场推广",
                "description": "广告投放预算",
                "account_name": "运营账户",
                "expected_amount": 300000,
                "currency": "CNY",
                "certainty": "certain",
            },
        ),
        CandidateRecord(
            record_type=RecordType.EXPENSE_FORECAST,
            payload={
                "company_id": company_id,
                "cash_out_date": "2025-06-28",
                "category_path": ["费用预算", "市场推广"],
                "category": "市场推广",
                "description": "活动物料采购",
                "expected_amount": 80000,
                "currency": "CNY",
                "certainty": "uncertain",
            },
        ),
    ]
    parser.set_custom_records(first_records)

    response = client.post(
        "/api/v1/parse/upload",
        data={"prompt": "支出预算", "company_id": company_id},
    )
    assert response.status_code == 202
    job_payload = response.json()
    job_id = job_payload["jobId"]

    confirm_actions = [
        {
            "recordType": record["recordType"],
            "operation": "approve",
            "payload": record["payload"],
        }
        for record in job_payload["preview"]
    ]
    confirm_response = client.post(
        f"/api/v1/import-jobs/{job_id}/confirm",
        json={"actions": confirm_actions},
    )
    assert confirm_response.status_code == 200

    with db.session_scope() as session:
        saved = (
            session.query(ExpenseForecast)
            .filter(ExpenseForecast.company_id == company_id)
            .order_by(ExpenseForecast.cash_out_date)
            .all()
        )
        assert len(saved) == 2
        assert saved[0].description == "广告投放预算"
        assert float(saved[1].expected_amount) == 80000

    second_records = [
        CandidateRecord(
            record_type=RecordType.EXPENSE_FORECAST,
            payload={
                "company_id": company_id,
                "cash_out_date": "2025-07-10",
                "category_path": ["费用预算", "研发投入"],
                "category": "研发投入",
                "description": "研发外包阶段款",
                "expected_amount": 1200000,
                "currency": "CNY",
            },
        )
    ]
    parser.set_custom_records(second_records)

    response2 = client.post(
        "/api/v1/parse/upload",
        data={"prompt": "支出预算更新", "company_id": company_id},
    )
    assert response2.status_code == 202
    job_payload2 = response2.json()
    job_id2 = job_payload2["jobId"]

    confirm_response2 = client.post(
        f"/api/v1/import-jobs/{job_id2}/confirm",
        json={
            "actions": [
                {
                    "recordType": job_payload2["preview"][0]["recordType"],
                    "operation": "approve",
                    "payload": job_payload2["preview"][0]["payload"],
                }
            ]
        },
    )
    assert confirm_response2.status_code == 200

    with db.session_scope() as session:
        saved_after = session.query(ExpenseForecast).filter_by(company_id=company_id).all()
        assert len(saved_after) == 1
        assert saved_after[0].description == "研发外包阶段款"
        assert float(saved_after[0].expected_amount) == 1200000

    parser.set_custom_records(None)
