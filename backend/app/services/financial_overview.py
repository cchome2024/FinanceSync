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
    RevenueDetail,
    Certainty,
)
from app.schemas.overview import (
    BalanceHistoryItem,
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
    revenue: Optional["_RevenueMonthlySnapshot"] = None
    expense: Optional[ExpenseRecord] = None
    forecasts: List[IncomeForecast] = None


@dataclass
class _RevenueMonthlySnapshot:
    company_id: str
    period: date
    amount: Decimal
    currency: str


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

        month_expr = func.strftime('%Y-%m-01', RevenueDetail.occurred_on).label("period_start")
        stmt = (
            select(
                RevenueDetail.company_id,
                month_expr,
                func.sum(RevenueDetail.amount).label("total_amount"),
                func.max(RevenueDetail.currency).label("currency"),
            )
            .where(RevenueDetail.company_id.in_(company_ids))
            .where(RevenueDetail.occurred_on <= as_of)
            .group_by(RevenueDetail.company_id, month_expr)
            .order_by(RevenueDetail.company_id, month_expr.desc())
        )
        latest: Dict[str, _RevenueMonthlySnapshot] = {}
        for row in self._session.execute(stmt):
            company_id_value: str = row[0]
            period_str: str = row[1]
            total_amount: Decimal = row[2] or Decimal(0)
            currency: str = row[3] or "CNY"
            if company_id_value not in latest:
                latest[company_id_value] = _RevenueMonthlySnapshot(
                    company_id=company_id_value,
                    period=date.fromisoformat(period_str),
                    amount=total_amount,
                    currency=currency,
                )

        missing_ids = [cid for cid in company_ids if cid not in latest]
        if missing_ids:
            fallback_stmt = (
                select(
                    RevenueDetail.company_id,
                    month_expr,
                    func.sum(RevenueDetail.amount).label("total_amount"),
                    func.max(RevenueDetail.currency).label("currency"),
                )
                .where(RevenueDetail.company_id.in_(missing_ids))
                .group_by(RevenueDetail.company_id, month_expr)
                .order_by(RevenueDetail.company_id, month_expr.desc())
            )
            for row in self._session.execute(fallback_stmt):
                company_id_value: str = row[0]
                period_str: str = row[1]
                total_amount: Decimal = row[2] or Decimal(0)
                currency: str = row[3] or "CNY"
                if company_id_value not in latest:
                    latest[company_id_value] = _RevenueMonthlySnapshot(
                        company_id=company_id_value,
                        period=date.fromisoformat(period_str),
                        amount=total_amount,
                        currency=currency,
                    )

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
            reported_at=balance.reported_at.date().isoformat(),
        )

    def _build_flow_summary(
        self,
        record: Optional[_RevenueMonthlySnapshot | ExpenseRecord],
    ) -> Optional[FlowSummary]:
        if not record:
            return None

        if isinstance(record, _RevenueMonthlySnapshot):
            period_str = record.period.strftime("%Y-%m")
            amount_value = record.amount
            currency = record.currency
        else:
            period_str = record.month.strftime("%Y-%m")
            currency = getattr(record, "currency", "CNY")
            amount_value = getattr(record, "amount", None)

        if amount_value is None:
            return None
        return FlowSummary(period=period_str, amount=self._to_float(amount_value), currency=currency)

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

    def get_revenue_summary(
        self,
        year: Optional[int] = None,
        company_id: Optional[str] = None,
        max_level: Optional[int] = None,
        include_forecast: bool = False,
    ) -> RevenueSummaryResponse:
        if year is None:
            year = datetime.now(UTC).year

        stmt = (
            select(RevenueDetail, FinanceCategory)
            .outerjoin(FinanceCategory, RevenueDetail.category_ref)
            .where(func.strftime('%Y', RevenueDetail.occurred_on) == str(year))
        )
        if company_id:
            stmt = stmt.where(RevenueDetail.company_id == company_id)

        results = self._session.execute(stmt).all()

        forecast_results: List[Tuple[IncomeForecast, FinanceCategory | None]] = []
        if include_forecast:
            forecast_stmt = (
                select(IncomeForecast, FinanceCategory)
                .outerjoin(FinanceCategory, IncomeForecast.category_ref)
                .where(func.strftime('%Y', IncomeForecast.cash_in_date) == str(year))
            )
            if company_id:
                forecast_stmt = forecast_stmt.where(IncomeForecast.company_id == company_id)
            forecast_results = self._session.execute(forecast_stmt).all()

        if not results and not forecast_results:
            return RevenueSummaryResponse(
                year=year,
                companyId=company_id,
                totals=RevenueSummaryTotals(monthly=[0.0] * 12, total=0.0),
                nodes=[],
            )

        if max_level is None or max_level < 1:
            max_level = 2

        path_stats: Dict[Tuple[str, ...], Dict[str, List[float] | float]] = {}
        root_order: List[Tuple[str, ...]] = []
        children_order: Dict[Tuple[str, ...], List[Tuple[str, ...]]] = {}

        def ensure_path(path: Tuple[str, ...]) -> Dict[str, List[float] | float]:
            if path not in path_stats:
                path_stats[path] = {
                    "actual_monthly": [0.0] * 12,
                    "actual_sum": 0.0,
                    "forecast_monthly": [0.0] * 12,
                    "forecast_sum": 0.0,
                }
            return path_stats[path]

        def add_child(parent: Tuple[str, ...], child: Tuple[str, ...]) -> None:
            children = children_order.setdefault(parent, [])
            if child not in children:
                children.append(child)

        def iter_paths(category: FinanceCategory | None, path_text: str | None, label: str | None, sublabel: str | None) -> Tuple[str, ...]:
            if category and category.full_path:
                segments = [segment for segment in category.full_path.split('/') if segment]
            elif path_text:
                segments = [segment for segment in path_text.split('/') if segment]
            else:
                segments = [segment for segment in [label, sublabel] if segment]
            if not segments:
                segments = ["未分类"]
            return tuple(segments)

        grand_actual_monthly = [0.0] * 12
        grand_forecast_monthly = [0.0] * 12

        for detail, category in results:
            amount = self._to_float(detail.amount)
            month_idx = detail.occurred_on.month - 1
            tuple_path = iter_paths(category, detail.category_path_text, detail.category_label, detail.subcategory_label)

            for depth in range(1, len(tuple_path) + 1):
                subpath = tuple_path[:depth]
                stats = ensure_path(subpath)
                stats["actual_monthly"][month_idx] += amount  # type: ignore[index]
                stats["actual_sum"] += amount  # type: ignore[operator]

                if depth == 1 and subpath not in root_order:
                    root_order.append(subpath)
                if depth > 1:
                    parent = tuple_path[: depth - 1]
                    add_child(parent, subpath)

            grand_actual_monthly[month_idx] += amount

        for forecast, category in forecast_results:
            amount = self._to_float(forecast.expected_amount)
            month_idx = forecast.cash_in_date.month - 1
            tuple_path = iter_paths(
                category,
                forecast.category_path_text,
                forecast.category_label,
                forecast.subcategory_label,
            )

            for depth in range(1, len(tuple_path) + 1):
                subpath = tuple_path[:depth]
                stats = ensure_path(subpath)
                stats["forecast_monthly"][month_idx] += amount  # type: ignore[index]
                stats["forecast_sum"] += amount  # type: ignore[operator]

                if depth == 1 and subpath not in root_order:
                    root_order.append(subpath)
                if depth > 1:
                    parent = tuple_path[: depth - 1]
                    add_child(parent, subpath)

            grand_forecast_monthly[month_idx] += amount

        def build_node(path: Tuple[str, ...]) -> RevenueSummaryNode:
            level = len(path)
            if level >= max_level:
                children_paths: List[Tuple[str, ...]] = []
            else:
                children_paths = [
                    child for child in children_order.get(path, []) if len(child) <= max_level
                ]
            children = [build_node(child) for child in children_paths]

            stats = ensure_path(path)
            actual_monthly = [round(value, 2) for value in stats["actual_monthly"]]  # type: ignore[arg-type]
            actual_total = round(stats["actual_sum"], 2)  # type: ignore[arg-type]

            node_kwargs = dict(
                label=path[-1],
                level=level,
                monthly=actual_monthly,
                total=actual_total,
                children=children,
            )

            if include_forecast:
                forecast_monthly = [round(value, 2) for value in stats["forecast_monthly"]]  # type: ignore[arg-type]
                forecast_total = round(stats["forecast_sum"], 2)  # type: ignore[arg-type]
                node_kwargs["forecastMonthly"] = forecast_monthly
                node_kwargs["forecastTotal"] = forecast_total

            return RevenueSummaryNode(**node_kwargs)

        nodes = [build_node(path) for path in root_order]

        grand_actual = [round(value, 2) for value in grand_actual_monthly]
        grand_actual_total = round(sum(grand_actual_monthly), 2)

        totals_kwargs = dict(
            monthly=grand_actual,
            total=grand_actual_total,
        )

        if include_forecast:
            grand_forecast = [round(value, 2) for value in grand_forecast_monthly]
            grand_forecast_total = round(sum(grand_forecast_monthly), 2)
            totals_kwargs["forecastMonthly"] = grand_forecast
            totals_kwargs["forecastTotal"] = grand_forecast_total

        return RevenueSummaryResponse(
            year=year,
            companyId=company_id,
            totals=RevenueSummaryTotals(**totals_kwargs),
            nodes=nodes,
        )



