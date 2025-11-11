from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BalanceSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    cash: float
    investment: float
    total: float
    reported_at: str = Field(alias="reportedAt")


class FlowSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    period: str
    amount: float
    currency: str = "CNY"


class ForecastSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    certain: float = 0.0
    uncertain: float = 0.0
    expenses_monthly: List["MonthlyExpenseItem"] = Field(default_factory=list, alias="expensesMonthly")
    incomes_monthly: List["MonthlyIncomeItem"] = Field(default_factory=list, alias="incomesMonthly")


class MonthlyExpenseItem(BaseModel):
    month: str
    amount: float


class MonthlyIncomeItem(BaseModel):
    month: str
    certain: float
    uncertain: float


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
    level: int
    monthly: List[float]
    total: float
    children: List['RevenueSummaryNode'] = Field(default_factory=list)
    forecast_monthly: Optional[List[float]] = Field(default=None, alias="forecastMonthly")
    forecast_total: Optional[float] = Field(default=None, alias="forecastTotal")
    forecast_certain_monthly: Optional[List[float]] = Field(
        default=None, alias="forecastCertainMonthly"
    )
    forecast_uncertain_monthly: Optional[List[float]] = Field(
        default=None, alias="forecastUncertainMonthly"
    )
    forecast_certain_total: Optional[float] = Field(default=None, alias="forecastCertainTotal")
    forecast_uncertain_total: Optional[float] = Field(
        default=None, alias="forecastUncertainTotal"
    )


class RevenueSummaryTotals(BaseModel):
    monthly: List[float]
    total: float
    forecast_monthly: Optional[List[float]] = Field(default=None, alias="forecastMonthly")
    forecast_total: Optional[float] = Field(default=None, alias="forecastTotal")
    forecast_certain_monthly: Optional[List[float]] = Field(
        default=None, alias="forecastCertainMonthly"
    )
    forecast_uncertain_monthly: Optional[List[float]] = Field(
        default=None, alias="forecastUncertainMonthly"
    )
    forecast_certain_total: Optional[float] = Field(default=None, alias="forecastCertainTotal")
    forecast_uncertain_total: Optional[float] = Field(
        default=None, alias="forecastUncertainTotal"
    )


class RevenueSummaryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    year: int
    company_id: Optional[str] = Field(alias="companyId", default=None)
    totals: RevenueSummaryTotals
    nodes: List[RevenueSummaryNode] = Field(default_factory=list)


RevenueSummaryNode.model_rebuild()
MonthlyExpenseItem.model_rebuild()
MonthlyIncomeItem.model_rebuild()


class BalanceHistoryItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    company_id: str = Field(alias="companyId")
    reported_at: str = Field(alias="reportedAt")
    total_balance: float = Field(alias="totalBalance")
    cash_balance: float = Field(alias="cashBalance")
    investment_balance: float = Field(alias="investmentBalance")
    currency: str = "CNY"


class ExpenseForecastDetailItem(BaseModel):
    """支出预测详细项（按分类分组）"""
    model_config = ConfigDict(populate_by_name=True)

    category_label: Optional[str] = Field(default=None, alias="categoryLabel")
    amount: float
    items: List["ExpenseForecastItem"] = Field(default_factory=list)


class ExpenseForecastItem(BaseModel):
    """单个支出预测项"""
    model_config = ConfigDict(populate_by_name=True)

    description: Optional[str] = None
    account_name: Optional[str] = Field(default=None, alias="accountName")
    amount: float


class ExpenseForecastDetailResponse(BaseModel):
    """支出预测详细信息响应"""
    model_config = ConfigDict(populate_by_name=True)

    month: str
    total: float
    categories: List[ExpenseForecastDetailItem] = Field(default_factory=list)


ExpenseForecastDetailItem.model_rebuild()
ExpenseForecastItem.model_rebuild()

