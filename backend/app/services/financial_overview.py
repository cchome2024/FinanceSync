from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.financial import (
    AccountBalance,
    Company,
    ExpenseRecord,
    FinanceCategory,
    IncomeForecast,
    RevenueRecord,
    Certainty,
)
from app.schemas.overview import (
    BalanceSummary,
    CompanyOverview,
    FinancialOverview,
    FlowSummary,
    ForecastSummary,
    RevenueSummaryNode,
    RevenueSummaryResponse,
    RevenueSummaryTotals,
)


@dataclass
class _CompanyAggregates:
    company: Company
    balance: Optional[AccountBalance] = None
    revenue: Optional[RevenueRecord] = None
    expense: Optional[ExpenseRecord] = None
    forecasts: List[IncomeForecast] = None


class FinancialOverviewService:
    """Aggregate financial data for dashboard view."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_overview(self, as_of: Optional[date] = None, company_id: Optional[str] = None) -> FinancialOverview:
        if as_of is None:
            as_of = datetime.now(UTC).date()

        companies = self._load_companies(company_id)
        aggregates = {company.id: _CompanyAggregates(company=company, forecasts=[]) for company in companies}

        self._attach_latest_balances(aggregates.values(), as_of)
        self._attach_latest_revenue(aggregates.values(), as_of)
        self._attach_latest_expense(aggregates.values(), as_of)
        self._attach_forecasts(aggregates.values(), as_of)

        items = [
            CompanyOverview(
                companyId=aggregate.company.id,
                companyName=aggregate.company.display_name or aggregate.company.name,
                balances=self._build_balance_summary(aggregate.balance),
                revenue=self._build_flow_summary(aggregate.revenue),
                expense=self._build_flow_summary(aggregate.expense),
                forecast=self._build_forecast_summary(aggregate.forecasts),
            )
            for aggregate in aggregates.values()
        ]

        return FinancialOverview(asOf=as_of, companies=items)

    def _load_companies(self, company_id: Optional[str]) -> Iterable[Company]:
        stmt = select(Company)
        if company_id:
            stmt = stmt.where(Company.id == company_id)
        stmt = stmt.order_by(Company.display_name, Company.name)
        return [row[0] for row in self._session.execute(stmt).all()]

    def _attach_latest_balances(self, aggregates: Iterable[_CompanyAggregates], as_of: date) -> None:
        company_ids = [aggregate.company.id for aggregate in aggregates]
        if not company_ids:
            return

        cutoff = datetime.combine(as_of, datetime.max.time(), tzinfo=UTC)
        stmt = (
            select(AccountBalance)
            .where(AccountBalance.company_id.in_(company_ids))
            .where(AccountBalance.reported_at <= cutoff)
            .order_by(AccountBalance.company_id, AccountBalance.reported_at.desc())
        )
        latest: Dict[str, AccountBalance] = {}
        for balance, in self._session.execute(stmt):
            if balance.company_id not in latest:
                latest[balance.company_id] = balance

        missing_ids = [aggregate.company.id for aggregate in aggregates if aggregate.company.id not in latest]
        if missing_ids:
            fallback_stmt = (
                select(AccountBalance)
                .where(AccountBalance.company_id.in_(missing_ids))
                .order_by(AccountBalance.company_id, AccountBalance.reported_at.desc())
            )
            for balance, in self._session.execute(fallback_stmt):
                if balance.company_id not in latest:
                    latest[balance.company_id] = balance

        for aggregate in aggregates:
            aggregate.balance = latest.get(aggregate.company.id)

    def _attach_latest_revenue(self, aggregates: Iterable[_CompanyAggregates], as_of: date) -> None:
        company_ids = [aggregate.company.id for aggregate in aggregates]
        if not company_ids:
            return

        stmt = (
            select(RevenueRecord)
            .where(RevenueRecord.company_id.in_(company_ids))
            .where(RevenueRecord.month <= as_of)
            .order_by(RevenueRecord.company_id, RevenueRecord.month.desc())
        )
        latest: Dict[str, RevenueRecord] = {}
        for record, in self._session.execute(stmt):
            if record.company_id not in latest:
                latest[record.company_id] = record

        for aggregate in aggregates:
            aggregate.revenue = latest.get(aggregate.company.id)

    def _attach_latest_expense(self, aggregates: Iterable[_CompanyAggregates], as_of: date) -> None:
        company_ids = [aggregate.company.id for aggregate in aggregates]
        if not company_ids:
            return

        stmt = (
            select(ExpenseRecord)
            .where(ExpenseRecord.company_id.in_(company_ids))
            .where(ExpenseRecord.month <= as_of)
            .order_by(ExpenseRecord.company_id, ExpenseRecord.month.desc())
        )
        latest: Dict[str, ExpenseRecord] = {}
        for record, in self._session.execute(stmt):
            if record.company_id not in latest:
                latest[record.company_id] = record

        for aggregate in aggregates:
            aggregate.expense = latest.get(aggregate.company.id)

    def _attach_forecasts(self, aggregates: Iterable[_CompanyAggregates], as_of: date) -> None:
        company_ids = [aggregate.company.id for aggregate in aggregates]
        if not company_ids:
            return

        stmt = (
            select(IncomeForecast)
            .where(IncomeForecast.company_id.in_(company_ids))
            .where(IncomeForecast.cash_in_date >= as_of)
        )
        grouped: Dict[str, List[IncomeForecast]] = {aggregate.company.id: [] for aggregate in aggregates}
        for forecast, in self._session.execute(stmt):
            grouped.setdefault(forecast.company_id, []).append(forecast)

        for aggregate in aggregates:
            aggregate.forecasts = grouped.get(aggregate.company.id, [])

    def _build_balance_summary(self, balance: Optional[AccountBalance]) -> Optional[BalanceSummary]:
        if not balance:
            return None
        return BalanceSummary(
            cash=self._to_float(balance.cash_balance),
            investment=self._to_float(balance.investment_balance),
            total=self._to_float(balance.total_balance),
        )

    def _build_flow_summary(self, record: Optional[RevenueRecord | ExpenseRecord]) -> Optional[FlowSummary]:
        if not record:
            return None
        period = record.month.strftime("%Y-%m")
        currency = getattr(record, "currency", "CNY")
        amount_value = getattr(record, "amount", None)
        if amount_value is None:
            return None
        return FlowSummary(period=period, amount=self._to_float(amount_value), currency=currency)

    def _build_forecast_summary(self, forecasts: Optional[List[IncomeForecast]]) -> Optional[ForecastSummary]:
        if not forecasts:
            return None
        certain_total = 0.0
        uncertain_total = 0.0
        for forecast in forecasts:
            amt = self._to_float(forecast.expected_amount)
            if forecast.certainty == Certainty.CERTAIN:
                certain_total += amt
            else:
                uncertain_total += amt
        return ForecastSummary(certain=certain_total, uncertain=uncertain_total)

    @staticmethod
    def _to_float(value: Decimal | float | int | None) -> float:
        if value is None:
            return 0.0
        return float(value)

    def list_balance_history(self, company_id: Optional[str] = None) -> List[BalanceHistoryItem]:
        stmt = select(AccountBalance).order_by(AccountBalance.company_id, AccountBalance.reported_at.desc())
        if company_id:
            stmt = stmt.where(AccountBalance.company_id == company_id)

        history: List[BalanceHistoryItem] = []
        for balance, in self._session.execute(stmt):
            history.append(
                BalanceHistoryItem(
                    companyId=balance.company_id,
                    reportedAt=balance.reported_at.isoformat(),
                    totalBalance=self._to_float(balance.total_balance),
                    cashBalance=self._to_float(balance.cash_balance),
                    investmentBalance=self._to_float(balance.investment_balance),
                    currency=balance.currency,
                )
            )
        return history

    def get_revenue_summary(self, year: Optional[int] = None, company_id: Optional[str] = None) -> RevenueSummaryResponse:
        if year is None:
            year = datetime.now(UTC).year

        stmt = (
            select(RevenueRecord, FinanceCategory)
            .outerjoin(FinanceCategory, RevenueRecord.category_ref)
            .where(func.strftime('%Y', RevenueRecord.month) == str(year))
        )
        if company_id:
            stmt = stmt.where(RevenueRecord.company_id == company_id)

        results = self._session.execute(stmt).all()

        if not results:
            return RevenueSummaryResponse(
                year=year,
                companyId=company_id,
                totals=RevenueSummaryTotals(monthly=[0.0] * 12, total=0.0),
                nodes=[],
            )

        totals_by_path: Dict[Tuple[str, ...], List[float]] = {}
        totals_sum: Dict[Tuple[str, ...], float] = {}
        root_order: List[Tuple[str, ...]] = []
        children_order: Dict[Tuple[str, ...], List[Tuple[str, ...]]] = {}

        def ensure_path(path: Tuple[str, ...]) -> None:
            if path not in totals_by_path:
                totals_by_path[path] = [0.0] * 12
                totals_sum[path] = 0.0

        def add_child(parent: Tuple[str, ...], child: Tuple[str, ...]) -> None:
            children = children_order.setdefault(parent, [])
            if child not in children:
                children.append(child)

        for record, category in results:
            amount = self._to_float(record.amount)
            month_idx = record.month.month - 1

            if category and category.full_path:
                path_segments = [segment for segment in category.full_path.split('/') if segment]
            else:
                path_segments = [segment for segment in [record.category, record.subcategory] if segment]

            if not path_segments:
                path_segments = ['未分类']

            tuple_path = tuple(path_segments)

            for depth in range(1, len(tuple_path) + 1):
                subpath = tuple_path[:depth]
                ensure_path(subpath)
                totals_by_path[subpath][month_idx] += amount
                totals_sum[subpath] += amount

                if depth == 1 and subpath not in root_order:
                    root_order.append(subpath)
                if depth > 1:
                    parent = tuple_path[: depth - 1]
                    add_child(parent, subpath)

        def build_node(path: Tuple[str, ...]) -> RevenueSummaryNode:
            children = [build_node(child) for child in children_order.get(path, [])]
            monthly = [round(value, 2) for value in totals_by_path[path]]
            total_value = round(totals_sum[path], 2)
            return RevenueSummaryNode(
                label=path[-1],
                monthly=monthly,
                total=total_value,
                children=children,
            )

        nodes = [build_node(path) for path in root_order]

        grand_monthly = [0.0] * 12
        for path in root_order:
            for idx, value in enumerate(totals_by_path[path]):
                grand_monthly[idx] += value
        grand_totals = [round(value, 2) for value in grand_monthly]
        grand_total_value = round(sum(grand_monthly), 2)

        return RevenueSummaryResponse(
            year=year,
            companyId=company_id,
            totals=RevenueSummaryTotals(monthly=grand_totals, total=grand_total_value),
            nodes=nodes,
        )



