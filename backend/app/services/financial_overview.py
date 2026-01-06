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
    ExpenseForecast,
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
    ExpenseForecastDetailItem,
    ExpenseForecastDetailResponse,
    ExpenseForecastItem,
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
    income_forecasts: List[IncomeForecast] = None
    expense_forecasts: List[ExpenseForecast] = None


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
        aggregates = {
            company.id: _CompanyAggregates(
                company=company,
                income_forecasts=[],
                expense_forecasts=[],
            )
            for company in companies
        }

        self._attach_latest_balances(aggregates.values(), as_of)
        self._attach_latest_revenue(aggregates.values(), as_of)
        self._attach_latest_expense(aggregates.values(), as_of)
        self._attach_forecasts(aggregates.values(), as_of)

        items = []
        for aggregate in aggregates.values():
            forecast = self._build_forecast_summary(
                aggregate.income_forecasts,
                aggregate.expense_forecasts,
                as_of,
                aggregate.company.id,
            )
            
            # 检查公司是否有预测数据
            has_forecast_data = forecast is not None and (
                (forecast.incomes_monthly and len(forecast.incomes_monthly) > 0 and
                 any(item.certain > 0 or item.uncertain > 0 for item in forecast.incomes_monthly)) or
                (forecast.expenses_monthly and len(forecast.expenses_monthly) > 0) or
                forecast.certain > 0 or
                forecast.uncertain > 0
            )
            
            print(f"[DEBUG] 公司检查: id={aggregate.company.id}, name={aggregate.company.name}, display_name={aggregate.company.display_name}")
            print(f"[DEBUG]   has_forecast_data={has_forecast_data}, forecast={forecast}")
            if forecast:
                print(f"[DEBUG]   forecast.incomes_monthly={forecast.incomes_monthly}, forecast.certain={forecast.certain}, forecast.uncertain={forecast.uncertain}")
            
            # 如果没有指定 company_id，优先过滤掉没有预测数据的公司（特别是 company-unknown）
            # 这样可以确保前端只看到有实际数据的公司
            if company_id is None:
                # 如果公司名称是 "company-unknown" 或 "未知公司"，且没有预测数据，跳过它
                is_unknown_company = (aggregate.company.name == "company-unknown" or 
                                      aggregate.company.display_name == "未知公司")
                print(f"[DEBUG]   is_unknown_company={is_unknown_company}, company_id={company_id}")
                if is_unknown_company and not has_forecast_data:
                    print(f"[DEBUG] 跳过没有预测数据的默认公司: {aggregate.company.id} ({aggregate.company.display_name or aggregate.company.name})")
                    continue
                
                # 如果公司没有任何数据（没有余额、没有收入、没有支出、没有预测），也跳过
                has_balance = aggregate.balance is not None
                has_revenue = aggregate.revenue is not None
                has_expense = aggregate.expense is not None
                if not (has_balance or has_revenue or has_expense or has_forecast_data):
                    print(f"[DEBUG] 跳过没有数据的公司: {aggregate.company.id} ({aggregate.company.display_name or aggregate.company.name})")
                    continue
            
            items.append(
                CompanyOverview(
                    companyId=aggregate.company.id,
                    companyName=aggregate.company.display_name or aggregate.company.name,
                    balances=self._build_balance_summary(aggregate.balance),
                    revenue=self._build_flow_summary(aggregate.revenue),
                    expense=self._build_flow_summary(aggregate.expense),
                    forecast=forecast,
                )
            )

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

        # 总是取 reported_at 最新的记录，不管日期是什么（支持未来日期的余额数据）
        # 直接查询所有记录，按 reported_at 降序排序，然后只取每个公司的第一条（最新的）
        stmt = (
            select(AccountBalance)
            .where(AccountBalance.company_id.in_(company_ids))
            .order_by(AccountBalance.company_id, AccountBalance.reported_at.desc())
        )
        latest: Dict[str, AccountBalance] = {}
        all_balances = list(self._session.execute(stmt).scalars().all())
        
        # 调试日志：打印所有查询到的余额记录
        print(f"[BALANCE QUERY] Found {len(all_balances)} balance records for companies: {company_ids}")
        for balance in all_balances:
            print(f"[BALANCE QUERY] Company: {balance.company_id}, reported_at: {balance.reported_at}, total: {balance.total_balance}")
        
        for balance in all_balances:
            # 只取每个公司的第一条记录（因为已经按 reported_at.desc() 排序，第一条就是最新的）
            if balance.company_id not in latest:
                latest[balance.company_id] = balance
                print(f"[BALANCE QUERY] Selected latest for company {balance.company_id}: reported_at={balance.reported_at}, total={balance.total_balance}")

        for aggregate in aggregates:
            aggregate.balance = latest.get(aggregate.company.id)
            if aggregate.balance:
                print(f"[BALANCE QUERY] Assigned balance to company {aggregate.company.id}: reported_at={aggregate.balance.reported_at}, total={aggregate.balance.total_balance}")

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

        income_stmt = (
            select(IncomeForecast)
            .where(IncomeForecast.company_id.in_(company_ids))
        )
        income_grouped: Dict[str, List[IncomeForecast]] = {aggregate.company.id: [] for aggregate in aggregates}
        all_income_forecasts: List[IncomeForecast] = []
        for forecast, in self._session.execute(income_stmt):
            income_grouped.setdefault(forecast.company_id, []).append(forecast)
            all_income_forecasts.append(forecast)

        expense_stmt = (
            select(ExpenseForecast)
            .where(ExpenseForecast.company_id.in_(company_ids))
        )
        expense_grouped: Dict[str, List[ExpenseForecast]] = {aggregate.company.id: [] for aggregate in aggregates}
        all_expense_forecasts: List[ExpenseForecast] = []
        for forecast, in self._session.execute(expense_stmt):
            expense_grouped.setdefault(forecast.company_id, []).append(forecast)
            all_expense_forecasts.append(forecast)

        for aggregate in aggregates:
            aggregate.income_forecasts = all_income_forecasts
            aggregate.expense_forecasts = all_expense_forecasts

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

    def _build_forecast_summary(
        self,
        income_forecasts: Optional[List[IncomeForecast]],
        expense_forecasts: Optional[List[ExpenseForecast]],
        as_of: date,
        company_id: str,
    ) -> Optional[ForecastSummary]:
        # 计算当前月份的第一天，用于判断哪些数据需要归到当前月份
        # 注意：as_of 是当前日期，我们需要将早于当前月份的数据归到当前月份
        # 如果数据是当前月份的，应该正常显示
        current_month_start = date(as_of.year, as_of.month, 1)
        current_month_str = as_of.strftime("%Y-%m")
        
        # 直接查询所有预测收入数据（不限制年份）
        forecast_stmt = (
            select(IncomeForecast, FinanceCategory)
            .outerjoin(FinanceCategory, IncomeForecast.category_ref)
        )
        if company_id:
            forecast_stmt = forecast_stmt.where(IncomeForecast.company_id == company_id)
        
        forecast_results = self._session.execute(forecast_stmt).all()
        
        print(f"[DEBUG] _build_forecast_summary: as_of={as_of}, company_id={company_id}, current_month_str={current_month_str}, current_month_start={current_month_start}")
        print(f"[DEBUG] 查询到 {len(forecast_results)} 条预测收入记录 (company_id={company_id})")
        
        # 统计所有预测收入数据
        income_stats: Dict[str, Dict[str, float]] = {}
        certain_total = 0.0
        uncertain_total = 0.0
        
        # 当前月份累计的早于当前月份的数据
        current_month_certain = 0.0
        current_month_uncertain = 0.0
        
        for idx, (forecast, category) in enumerate(forecast_results):
            forecast_date = forecast.cash_in_date
            forecast_month_str = forecast_date.strftime("%Y-%m")
            amount = self._to_float(forecast.expected_amount)
            is_past = forecast_date < current_month_start
            
            if idx < 5:  # 只打印前5条记录
                print(f"[DEBUG] 记录 {idx+1}: date={forecast_date}, month={forecast_month_str}, amount={amount}, certainty={forecast.certainty.value}, is_past={is_past}")
            
            # 如果预测日期早于当前月份的第一天，累加到当前月份
            # 如果预测日期是当前月份或之后，按原月份统计
            if forecast_date < current_month_start:
                # 早于当前月份的数据，累加到当前月份
                if forecast.certainty == Certainty.CERTAIN:
                    current_month_certain += amount
                    certain_total += amount
                else:
                    current_month_uncertain += amount
                    uncertain_total += amount
            else:
                # 当前月份及之后的数据，按月份统计
                if forecast.certainty == Certainty.CERTAIN:
                    if forecast_month_str not in income_stats:
                        income_stats[forecast_month_str] = {"certain": 0.0, "uncertain": 0.0}
                    income_stats[forecast_month_str]["certain"] += amount
                    certain_total += amount
                else:
                    if forecast_month_str not in income_stats:
                        income_stats[forecast_month_str] = {"certain": 0.0, "uncertain": 0.0}
                    income_stats[forecast_month_str]["uncertain"] += amount
                    uncertain_total += amount
        
        # 将早于当前月份的数据添加到当前月份（即使为0也要确保当前月份存在）
        # 确保当前月份总是存在，即使没有数据也要显示
        if current_month_str not in income_stats:
            income_stats[current_month_str] = {"certain": 0.0, "uncertain": 0.0}
        income_stats[current_month_str]["certain"] += current_month_certain
        income_stats[current_month_str]["uncertain"] += current_month_uncertain
        
        print(f"[DEBUG] 早于当前月份的数据: certain={current_month_certain}, uncertain={current_month_uncertain}")
        print(f"[DEBUG] 当前月份统计: {income_stats.get(current_month_str, {})}")
        print(f"[DEBUG] 总计: certain_total={certain_total}, uncertain_total={uncertain_total}")

        if not income_stats and not expense_forecasts:
            return None
        expense_monthly: Dict[str, float] = {}
        for forecast in expense_forecasts or []:
            key = forecast.cash_out_date.strftime("%Y-%m")
            expense_monthly[key] = expense_monthly.get(key, 0.0) + self._to_float(forecast.expected_amount)

        sorted_expenses = [
            {"month": month, "amount": round(amount, 2)}
            for month, amount in sorted(expense_monthly.items())
        ]

        # 确保当前月份总是包含在返回结果中，即使值为0（因为可能有早于当前月份的数据被合并过来）
        incomes_monthly = []
        for month, values in sorted(income_stats.items()):
            # 只有当certain或uncertain有值时，或者月份是当前月份时，才包含
            if values["certain"] > 0 or values["uncertain"] > 0 or month == current_month_str:
                incomes_monthly.append({
                    "month": month,
                    "certain": round(values["certain"], 2),
                    "uncertain": round(values["uncertain"], 2),
                })
        
        print(f"[DEBUG] 返回的 incomes_monthly ({len(incomes_monthly)} 条):")
        for item in incomes_monthly[:10]:  # 只打印前10条
            print(f"  {item}")

        return ForecastSummary(
            certain=certain_total,
            uncertain=uncertain_total,
            expenses_monthly=sorted_expenses,
            incomes_monthly=incomes_monthly,
        )

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

    def get_available_revenue_years(
        self,
        company_id: Optional[str] = None,
        include_forecast: bool = True,
    ) -> List[int]:
        """获取所有有收入数据的年份（包括实际收入和预测收入）"""
        years = set()
        
        # 从 RevenueDetail 获取有数据的年份
        revenue_stmt = select(func.strftime('%Y', RevenueDetail.occurred_on).label('year')).distinct()
        if company_id:
            revenue_stmt = revenue_stmt.where(RevenueDetail.company_id == company_id)
        
        revenue_years = self._session.execute(revenue_stmt).scalars().all()
        for year_str in revenue_years:
            try:
                years.add(int(year_str))
            except (ValueError, TypeError):
                continue
        
        # 从 IncomeForecast 获取有数据的年份（如果包含预测）
        if include_forecast:
            forecast_stmt = select(func.strftime('%Y', IncomeForecast.cash_in_date).label('year')).distinct()
            if company_id:
                forecast_stmt = forecast_stmt.where(IncomeForecast.company_id == company_id)
            
            forecast_years = self._session.execute(forecast_stmt).scalars().all()
            for year_str in forecast_years:
                try:
                    years.add(int(year_str))
                except (ValueError, TypeError):
                    continue
        
        return sorted(list(years), reverse=True)

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
                    "forecast_certain_monthly": [0.0] * 12,
                    "forecast_uncertain_monthly": [0.0] * 12,
                    "forecast_certain_sum": 0.0,
                    "forecast_uncertain_sum": 0.0,
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
        grand_forecast_certain_monthly = [0.0] * 12
        grand_forecast_uncertain_monthly = [0.0] * 12

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
                if forecast.certainty == Certainty.CERTAIN:
                    stats["forecast_certain_monthly"][month_idx] += amount  # type: ignore[index]
                    stats["forecast_certain_sum"] += amount  # type: ignore[operator]
                else:
                    stats["forecast_uncertain_monthly"][month_idx] += amount  # type: ignore[index]
                    stats["forecast_uncertain_sum"] += amount  # type: ignore[operator]

                if depth == 1 and subpath not in root_order:
                    root_order.append(subpath)
                if depth > 1:
                    parent = tuple_path[: depth - 1]
                    add_child(parent, subpath)

            if forecast.certainty == Certainty.CERTAIN:
                grand_forecast_certain_monthly[month_idx] += amount
            else:
                grand_forecast_uncertain_monthly[month_idx] += amount

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
            # 月度数据四舍五入显示
            actual_monthly = [round(value, 2) for value in stats["actual_monthly"]]  # type: ignore[arg-type]
            # 合计从精确值相加后再四舍五入，保证精度
            actual_total = round(stats["actual_sum"], 2)  # type: ignore[arg-type]

            node_kwargs = dict(
                label=path[-1],
                level=level,
                monthly=actual_monthly,
                total=actual_total,
                children=children,
            )

            if include_forecast:
                forecast_certain_monthly = [round(value, 2) for value in stats["forecast_certain_monthly"]]  # type: ignore[arg-type]
                forecast_uncertain_monthly = [round(value, 2) for value in stats["forecast_uncertain_monthly"]]  # type: ignore[arg-type]
                forecast_certain_total = round(stats["forecast_certain_sum"], 2)  # type: ignore[arg-type]
                forecast_uncertain_total = round(stats["forecast_uncertain_sum"], 2)  # type: ignore[arg-type]
                node_kwargs["forecastCertainMonthly"] = forecast_certain_monthly
                node_kwargs["forecastUncertainMonthly"] = forecast_uncertain_monthly
                node_kwargs["forecastCertainTotal"] = forecast_certain_total
                node_kwargs["forecastUncertainTotal"] = forecast_uncertain_total

            return RevenueSummaryNode(**node_kwargs)

        nodes = [build_node(path) for path in root_order]

        # 先计算精确的总和，然后再四舍五入，保证精度
        grand_actual_total_precise = sum(grand_actual_monthly)
        grand_actual = [round(value, 2) for value in grand_actual_monthly]
        grand_actual_total = round(grand_actual_total_precise, 2)

        totals_kwargs = dict(
            monthly=grand_actual,
            total=grand_actual_total,
        )

        if include_forecast:
            # 先计算精确的总和，然后再四舍五入
            grand_certain_total_precise = sum(grand_forecast_certain_monthly)
            grand_uncertain_total_precise = sum(grand_forecast_uncertain_monthly)
            grand_certain = [round(value, 2) for value in grand_forecast_certain_monthly]
            grand_uncertain = [round(value, 2) for value in grand_forecast_uncertain_monthly]
            totals_kwargs["forecastCertainMonthly"] = grand_certain
            totals_kwargs["forecastUncertainMonthly"] = grand_uncertain
            totals_kwargs["forecastCertainTotal"] = round(grand_certain_total_precise, 2)
            totals_kwargs["forecastUncertainTotal"] = round(grand_uncertain_total_precise, 2)

        return RevenueSummaryResponse(
            year=year,
            companyId=company_id,
            totals=RevenueSummaryTotals(**totals_kwargs),
            nodes=nodes,
        )

    def get_expense_forecast_detail(
        self,
        month: str,
        company_id: Optional[str] = None,
    ) -> ExpenseForecastDetailResponse:
        """
        获取指定月份的支出预测详细信息，按分类分组。
        
        Args:
            month: 月份字符串，格式为 "YYYY-MM"
            company_id: 可选的公司ID，如果为None则返回所有公司的数据
        """
        # 解析月份
        try:
            year, month_num = map(int, month.split("-"))
            month_start = date(year, month_num, 1)
            # 计算下个月第一天，用于范围查询
            if month_num == 12:
                month_end = date(year + 1, 1, 1)
            else:
                month_end = date(year, month_num + 1, 1)
        except (ValueError, IndexError):
            return ExpenseForecastDetailResponse(month=month, total=0.0, categories=[])

        # 查询该月范围内的支出预测
        stmt = select(ExpenseForecast).where(
            ExpenseForecast.cash_out_date >= month_start,
            ExpenseForecast.cash_out_date < month_end,
        )
        if company_id:
            stmt = stmt.where(ExpenseForecast.company_id == company_id)

        forecasts = [row[0] for row in self._session.execute(stmt)]

        if not forecasts:
            return ExpenseForecastDetailResponse(month=month, total=0.0, categories=[])

        # 按分类分组
        category_map: Dict[str, ExpenseForecastDetailItem] = {}
        total_amount = 0.0

        for forecast in forecasts:
            category_label = forecast.category_label or forecast.category or "未分类"
            amount = self._to_float(forecast.expected_amount)
            total_amount += amount

            if category_label not in category_map:
                category_map[category_label] = ExpenseForecastDetailItem(
                    categoryLabel=category_label,
                    amount=0.0,
                    items=[],
                )

            category_item = category_map[category_label]
            category_item.amount += amount
            category_item.items.append(
                ExpenseForecastItem(
                    id=forecast.id,
                    description=forecast.description,
                    accountName=forecast.account_name,
                    amount=amount,
                    categoryLabel=category_label,
                )
            )

        # 转换为列表并排序（按金额降序）
        categories = sorted(
            category_map.values(),
            key=lambda x: x.amount,
            reverse=True,
        )

        return ExpenseForecastDetailResponse(
            month=month,
            total=round(total_amount, 2),
            categories=categories,
        )



