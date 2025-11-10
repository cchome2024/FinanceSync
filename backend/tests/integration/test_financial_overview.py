from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app import db
from app.main import create_app
from app.models.base import Base
from app.models.financial import (
    AccountBalance,
    Company,
    ExpenseForecast,
    ExpenseRecord,
    ImportJob,
    ImportSource,
    ImportStatus,
    IncomeForecast,
    RevenueDetail,
    Certainty,
)


@pytest.fixture(name="client")
def client_fixture(tmp_path) -> TestClient:
    database_url = f"sqlite:///{tmp_path/'overview.db'}"
    db.configure_engine(database_url)
    Base.metadata.create_all(bind=db.engine)

    app = create_app()

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=db.engine)


def _seed_data():
    today = datetime(2025, 11, 3, 12, 0, 0)
    with db.session_scope() as session:
        session.query(ExpenseForecast).delete()
        session.query(IncomeForecast).delete()
        session.query(ExpenseRecord).delete()
        session.query(RevenueDetail).delete()
        session.query(AccountBalance).delete()
        session.query(Company).delete()

        acme = Company(id="company-acme", name="ACME", display_name="ACME 集团", currency="CNY")
        beta = Company(id="company-beta", name="BETA", display_name="贝塔科技", currency="CNY")
        session.add_all([acme, beta])
        session.flush()

        job = ImportJob(
            id="job-dashboard",
            source_type=ImportSource.AI_CHAT,
            status=ImportStatus.APPROVED,
        )
        session.add(job)
        session.flush()

        session.add_all(
            [
                AccountBalance(
                    company_id=acme.id,
                    import_job_id=job.id,
                    reported_at=today,
                    cash_balance=100000,
                    investment_balance=50000,
                    total_balance=150000,
                ),
                AccountBalance(
                    company_id=beta.id,
                    import_job_id=job.id,
                    reported_at=today,
                    cash_balance=80000,
                    investment_balance=20000,
                    total_balance=100000,
                ),
                RevenueDetail(
                    company_id=acme.id,
                    import_job_id=job.id,
                    occurred_on=date(2025, 11, 5),
                    amount=88000,
                    currency="CNY",
                    category_path_text="主营收入",
                    category_label="主营收入",
                ),
                ExpenseRecord(
                    company_id=acme.id,
                    import_job_id=job.id,
                    month=date(2025, 11, 1),
                    category="运营支出",
                    amount=42000,
                    currency="CNY",
                ),
                IncomeForecast(
                    company_id=acme.id,
                    import_job_id=job.id,
                    cash_in_date=date(2025, 11, 2),
                    certainty=Certainty.CERTAIN,
                    expected_amount=20000,
                    currency="CNY",
                ),
                IncomeForecast(
                    company_id=acme.id,
                    import_job_id=job.id,
                    cash_in_date=date(2025, 12, 1),
                    certainty=Certainty.CERTAIN,
                    expected_amount=60000,
                    currency="CNY",
                ),
                IncomeForecast(
                    company_id=acme.id,
                    import_job_id=job.id,
                    cash_in_date=date(2026, 1, 15),
                    certainty=Certainty.UNCERTAIN,
                    expected_amount=40000,
                    currency="CNY",
                ),
                ExpenseForecast(
                    company_id=acme.id,
                    import_job_id=job.id,
                    cash_out_date=date(2025, 11, 20),
                    certainty=Certainty.CERTAIN,
                    expected_amount=25000,
                    currency="CNY",
                ),
                ExpenseForecast(
                    company_id=acme.id,
                    import_job_id=job.id,
                    cash_out_date=date(2025, 12, 5),
                    certainty=Certainty.UNCERTAIN,
                    expected_amount=18000,
                    currency="CNY",
                ),
            ]
        )


def test_financial_overview_returns_latest_snapshot(client: TestClient) -> None:
    _seed_data()

    response = client.get("/api/v1/financial/overview")
    assert response.status_code == 200
    payload = response.json()

    assert payload["companies"][0]["companyName"] == "ACME 集团"
    balances = payload["companies"][0]["balances"]
    assert balances["total"] == 150000

    revenue = payload["companies"][0]["revenue"]
    assert revenue["amount"] == 88000
    assert revenue["period"] == "2025-11"

    forecast = payload["companies"][0]["forecast"]
    assert forecast["certain"] == 80000
    assert forecast["uncertain"] == 40000
    assert forecast["expensesMonthly"][0] == {"month": "2025-11", "amount": 25000.0}
    assert forecast["expensesMonthly"][1] == {"month": "2025-12", "amount": 18000.0}


def test_financial_overview_filters_by_company(client: TestClient) -> None:
    _seed_data()

    response = client.get("/api/v1/financial/overview", params={"companyId": "company-beta"})
    assert response.status_code == 200
    payload = response.json()

    assert len(payload["companies"]) == 1
    assert payload["companies"][0]["companyId"] == "company-beta"
    assert payload["companies"][0]["balances"]["total"] == 100000


