from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_financial_overview_service
from app.schemas.overview import BalanceHistoryItem, FinancialOverview, RevenueSummaryResponse
from app.services.financial_overview import FinancialOverviewService

router = APIRouter(prefix="/api/v1", tags=["overview"])


@router.get(
    "/financial/overview",
    response_model=FinancialOverview,
    status_code=status.HTTP_200_OK,
)
def get_financial_overview(
    company_id: Optional[str] = Query(None, alias="companyId"),
    as_of: Optional[date] = Query(None, description="ISO8601 date used as snapshot reference"),
    service: FinancialOverviewService = Depends(get_financial_overview_service),
) -> FinancialOverview:
    return service.get_overview(as_of=as_of, company_id=company_id)


@router.get(
    "/financial/revenue-summary",
    response_model=RevenueSummaryResponse,
    status_code=status.HTTP_200_OK,
)
def get_revenue_summary(
    year: Optional[int] = Query(None),
    company_id: Optional[str] = Query(None, alias="companyId"),
    service: FinancialOverviewService = Depends(get_financial_overview_service),
) -> RevenueSummaryResponse:
    return service.get_revenue_summary(year=year, company_id=company_id)


@router.get(
    "/financial/balances",
    response_model=list[BalanceHistoryItem],
    status_code=status.HTTP_200_OK,
)
def get_balance_history(
    company_id: Optional[str] = Query(None, alias="companyId"),
    service: FinancialOverviewService = Depends(get_financial_overview_service),
) -> list[BalanceHistoryItem]:
    return service.list_balance_history(company_id=company_id)


