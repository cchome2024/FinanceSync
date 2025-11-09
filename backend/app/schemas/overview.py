from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BalanceSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    cash: float
    investment: float
    total: float


class FlowSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    period: str
    amount: float
    currency: str = "CNY"


class ForecastSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    certain: float = 0.0
    uncertain: float = 0.0


class CompanyOverview(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    company_id: str = Field(alias="companyId")
    company_name: str = Field(alias="companyName")
    balances: Optional[BalanceSummary] = None
    revenue: Optional[FlowSummary] = None
    expense: Optional[FlowSummary] = None
    forecast: Optional[ForecastSummary] = None


class FinancialOverview(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    as_of: date = Field(alias="asOf")
    companies: List[CompanyOverview]


class RevenueSummaryNode(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    label: str
    monthly: List[float]
    total: float
    children: List['RevenueSummaryNode'] = Field(default_factory=list)


class RevenueSummaryTotals(BaseModel):
    monthly: List[float]
    total: float


class RevenueSummaryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    year: int
    company_id: Optional[str] = Field(alias="companyId", default=None)
    totals: RevenueSummaryTotals
    nodes: List[RevenueSummaryNode] = Field(default_factory=list)


RevenueSummaryNode.model_rebuild()


class BalanceHistoryItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    company_id: str = Field(alias="companyId")
    reported_at: str = Field(alias="reportedAt")
    total_balance: float = Field(alias="totalBalance")
    cash_balance: float = Field(alias="cashBalance")
    investment_balance: float = Field(alias="investmentBalance")
    currency: str = "CNY"

