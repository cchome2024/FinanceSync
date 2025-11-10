from __future__ import annotations

from datetime import date
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app import db
from app.main import create_app
from app.models.base import Base
from app.models.financial import (
    CategoryType,
    Certainty,
    Company,
    FinanceCategory,
    IncomeForecast,
    RevenueDetail,
    ImportJob,
    ImportSource,
    ImportStatus,
)


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
                RevenueDetail(
                    company_id=company.id,
                    import_job_id=import_job.id,
                    category_id=child.id,
                    occurred_on=date(2024, 1, 6),
                    amount=100,
                    currency="CNY",
                    category_path_text="互联网基金服务/报告服务",
                    category_label="报告服务",
                ),
                RevenueDetail(
                    company_id=company.id,
                    import_job_id=import_job.id,
                    category_id=child.id,
                    occurred_on=date(2024, 2, 12),
                    amount=200,
                    currency="CNY",
                    category_path_text="互联网基金服务/报告服务",
                    category_label="报告服务",
                ),
                RevenueDetail(
                    company_id=company.id,
                    import_job_id=import_job.id,
                    category_id=None,
                    occurred_on=date(2024, 2, 25),
                    amount=30,
                    currency="CNY",
                    category_path_text="互联网基金服务/报告服务/专项项目",
                    category_label="报告服务",
                    subcategory_label="专项项目",
                ),
                RevenueDetail(
                    company_id=company.id,
                    import_job_id=import_job.id,
                    category_id=None,
                    occurred_on=date(2024, 3, 20),
                    amount=50,
                    currency="CNY",
                    category_label="培训服务",
                    subcategory_label="合作培训",
                ),
            ]
        )
        session.add_all(
            [
                IncomeForecast(
                    company_id=company.id,
                    import_job_id=import_job.id,
                    category_id=child.id,
                    cash_in_date=date(2024, 4, 15),
                    certainty=Certainty.CERTAIN,
                    category="报告服务",
                    category_path_text="互联网基金服务/报告服务",
                    expected_amount=150,
                    currency="CNY",
                ),
                IncomeForecast(
                    company_id=company.id,
                    import_job_id=import_job.id,
                    category_id=None,
                    cash_in_date=date(2024, 5, 20),
                    certainty=Certainty.UNCERTAIN,
                    category_label="培训服务",
                    subcategory_label="合作培训",
                    expected_amount=80,
                    currency="CNY",
                ),
            ]
        )


def test_revenue_summary_returns_hierarchy(client: TestClient) -> None:
    _seed_data()

    response = client.get("/api/v1/financial/revenue-summary", params={"year": 2024})
    assert response.status_code == 200
    payload = response.json()

    assert payload["year"] == 2024
    assert payload["totals"]["total"] == 380.0
    assert payload["totals"]["monthly"][0] == 100.0
    assert payload["totals"]["monthly"][1] == 230.0
    assert payload["totals"]["monthly"][2] == 50.0
    assert payload["totals"].get("forecastCertainMonthly") in (None, [])
    assert payload["totals"].get("forecastUncertainMonthly") in (None, [])
    assert payload["totals"].get("forecastCertainTotal") in (None, 0)
    assert payload["totals"].get("forecastUncertainTotal") in (None, 0)

    nodes = payload["nodes"]
    assert len(nodes) == 2

    internet_services = next(node for node in nodes if node["label"] == "互联网基金服务")
    assert internet_services["level"] == 1
    assert internet_services["total"] == 330.0
    assert internet_services["monthly"][0] == 100.0
    assert internet_services["monthly"][1] == 230.0
    report_services = internet_services["children"][0]
    assert report_services["label"] == "报告服务"
    assert report_services["level"] == 2
    assert report_services["children"] == []

    training = next(node for node in nodes if node["label"] == "培训服务")
    assert training["level"] == 1
    assert training["total"] == 50.0
    assert training["monthly"][2] == 50.0
    assert training["children"][0]["label"] == "合作培训"

    # 请求更深层级
    response_full = client.get("/api/v1/financial/revenue-summary", params={"year": 2024, "maxLevel": 3})
    assert response_full.status_code == 200
    payload_full = response_full.json()
    nodes_full = payload_full["nodes"]
    internet_services_full = next(node for node in nodes_full if node["label"] == "互联网基金服务")
    report_full = next(child for child in internet_services_full["children"] if child["label"] == "报告服务")
    assert any(child["label"] == "专项项目" for child in report_full["children"])


def test_revenue_summary_with_forecast(client: TestClient) -> None:
    _seed_data()

    response = client.get(
        "/api/v1/financial/revenue-summary",
        params={"year": 2024, "includeForecast": True},
    )
    assert response.status_code == 200
    payload = response.json()

    totals = payload["totals"]
    assert totals["forecastCertainTotal"] == 150.0
    assert totals["forecastUncertainTotal"] == 80.0
    assert totals["forecastCertainMonthly"][3] == 150.0
    assert totals["forecastUncertainMonthly"][4] == 80.0

    nodes = payload["nodes"]
    internet_services = next(node for node in nodes if node["label"] == "互联网基金服务")
    assert internet_services["forecastCertainTotal"] == 150.0
    assert internet_services["forecastCertainMonthly"][3] == 150.0

    training = next(node for node in nodes if node["label"] == "培训服务")
    assert training["forecastUncertainTotal"] == 80.0
    assert training["forecastUncertainMonthly"][4] == 80.0
