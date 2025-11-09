from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import create_app
from app.models.base import Base
from app.models.financial import CategoryType, Company, FinanceCategory, RevenueRecord, ImportJob, ImportSource, ImportStatus


@pytest.fixture(name="client")
def client_fixture(tmp_path: Path) -> TestClient:
    database_url = f"sqlite:///{tmp_path/'revenue_summary.db'}"
    db.configure_engine(database_url)
    Base.metadata.create_all(bind=db.engine)

    app = create_app()

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=db.engine)


def _seed_data() -> None:
    with db.session_scope() as session:
        company = Company(id="company-1", name="Acme", display_name="Acme", currency="CNY")
        session.add(company)
        session.flush()

        import_job = ImportJob(
            id="job-1",
            source_type=ImportSource.AI_CHAT,
            status=ImportStatus.APPROVED,
        )
        session.add(import_job)
        session.flush()

        root = FinanceCategory(
            id="cat-root",
            category_type=CategoryType.REVENUE,
            name="互联网基金服务",
            level=1,
            full_path="互联网基金服务",
        )
        child = FinanceCategory(
            id="cat-child",
            category_type=CategoryType.REVENUE,
            name="报告服务",
            parent_id=root.id,
            level=2,
            full_path="互联网基金服务/报告服务",
        )
        session.add_all([root, child])
        session.flush()

        session.add_all(
            [
                RevenueRecord(
                    company_id=company.id,
                    import_job_id=import_job.id,
                    category_id=child.id,
                    month=date(2024, 1, 1),
                    category="报告服务",
                    subcategory=None,
                    amount=100,
                ),
                RevenueRecord(
                    company_id=company.id,
                    import_job_id=import_job.id,
                    category_id=child.id,
                    month=date(2024, 2, 1),
                    category="报告服务",
                    subcategory=None,
                    amount=200,
                ),
                RevenueRecord(
                    company_id=company.id,
                    import_job_id=import_job.id,
                    category_id=None,
                    month=date(2024, 3, 1),
                    category="培训服务",
                    subcategory="合作培训",
                    amount=50,
                ),
            ]
        )


def test_revenue_summary_returns_hierarchy(client: TestClient) -> None:
    _seed_data()

    response = client.get("/api/v1/financial/revenue-summary", params={"year": 2024})
    assert response.status_code == 200
    payload = response.json()

    assert payload["year"] == 2024
    assert payload["totals"]["total"] == 350.0
    assert payload["totals"]["monthly"][0] == 100.0
    assert payload["totals"]["monthly"][1] == 200.0
    assert payload["totals"]["monthly"][2] == 50.0

    nodes = payload["nodes"]
    assert len(nodes) == 2

    internet_services = next(node for node in nodes if node["label"] == "互联网基金服务")
    assert internet_services["total"] == 300.0
    assert internet_services["monthly"][0] == 100.0
    assert internet_services["monthly"][1] == 200.0
    assert internet_services["children"][0]["label"] == "报告服务"

    training = next(node for node in nodes if node["label"] == "培训服务")
    assert training["total"] == 50.0
    assert training["monthly"][2] == 50.0
    assert training["children"][0]["label"] == "合作培训"
