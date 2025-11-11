from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_financial_overview_service, require_permission
from app.core.permissions import Permission
from app.models.financial import User
from app.schemas.overview import (
    BalanceHistoryItem,
    ExpenseForecastDetailResponse,
    FinancialOverview,
    RevenueSummaryResponse,
)
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
    user: User = Depends(require_permission(Permission.DATA_VIEW)),
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
    max_level: Optional[int] = Query(2, alias="maxLevel", ge=1, le=6),
    include_forecast: bool = Query(False, alias="includeForecast"),
    user: User = Depends(require_permission(Permission.DATA_VIEW)),
    service: FinancialOverviewService = Depends(get_financial_overview_service),
) -> RevenueSummaryResponse:
    return service.get_revenue_summary(
        year=year,
        company_id=company_id,
        max_level=max_level,
        include_forecast=include_forecast,
    )


@router.get(
    "/financial/balances",
    response_model=list[BalanceHistoryItem],
    status_code=status.HTTP_200_OK,
)
def get_balance_history(
    company_id: Optional[str] = Query(None, alias="companyId"),
    user: User = Depends(require_permission(Permission.DATA_VIEW)),
    service: FinancialOverviewService = Depends(get_financial_overview_service),
) -> list[BalanceHistoryItem]:
    return service.list_balance_history(company_id=company_id)


@router.get(
    "/financial/expense-forecast-detail",
    response_model=ExpenseForecastDetailResponse,
    status_code=status.HTTP_200_OK,
)
def get_expense_forecast_detail(
    month: str = Query(..., description="月份，格式为 YYYY-MM"),
    company_id: Optional[str] = Query(None, alias="companyId"),
    user: User = Depends(require_permission(Permission.DATA_VIEW)),
    service: FinancialOverviewService = Depends(get_financial_overview_service),
) -> ExpenseForecastDetailResponse:
    return service.get_expense_forecast_detail(month=month, company_id=company_id)


