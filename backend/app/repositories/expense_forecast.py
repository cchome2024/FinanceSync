from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.financial import ExpenseForecast, Company, Certainty
from app.services.category_service import FinanceCategoryService


class ExpenseForecastRepository:
    """支出预测数据仓库"""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._category_service = FinanceCategoryService(session)

    @property
    def session(self) -> Session:
        return self._session

    def create(
        self,
        month: str,
        category_label: Optional[str],
        description: Optional[str],
        account_name: Optional[str],
        amount: float,
        certainty: Certainty = Certainty.CERTAIN,
        company_id: Optional[str] = None,
    ) -> ExpenseForecast:
        """创建支出预测记录"""
        # 解析月份
        year, month_num = map(int, month.split("-"))
        cash_out_date = date(year, month_num, 1)

        # 获取或创建公司
        if not company_id:
            company = self._session.query(Company).filter(Company.name == "company-unknown").first()
            if not company:
                company = Company(name="company-unknown", display_name="未知公司")
                self._session.add(company)
                self._session.flush()
            company_id = company.id

        # 获取分类
        category_id = None
        if category_label:
            category = self._category_service.find_by_label("expense", category_label)
            if category:
                category_id = category.id

        # 创建记录
        forecast = ExpenseForecast(
            company_id=company_id,
            cash_out_date=cash_out_date,
            category_id=category_id,
            category_label=category_label,
            description=description,
            account_name=account_name,
            expected_amount=amount,
            certainty=certainty,
        )
        self._session.add(forecast)
        self._session.flush()
        return forecast

    def get_by_id(self, forecast_id: str) -> Optional[ExpenseForecast]:
        """根据ID获取支出预测记录"""
        return self._session.query(ExpenseForecast).filter(ExpenseForecast.id == forecast_id).first()

    def update(
        self,
        forecast_id: str,
        description: Optional[str] = None,
        account_name: Optional[str] = None,
        amount: Optional[float] = None,
        category_label: Optional[str] = None,
        certainty: Optional[Certainty] = None,
    ) -> Optional[ExpenseForecast]:
        """更新支出预测记录"""
        forecast = self.get_by_id(forecast_id)
        if not forecast:
            return None

        if description is not None:
            forecast.description = description
        if account_name is not None:
            forecast.account_name = account_name
        if amount is not None:
            forecast.expected_amount = amount
        if category_label is not None:
            forecast.category_label = category_label
            # 更新分类ID
            if category_label:
                category = self._category_service.find_by_label("expense", category_label)
                forecast.category_id = category.id if category else None
            else:
                forecast.category_id = None
        if certainty is not None:
            forecast.certainty = certainty

        self._session.add(forecast)
        self._session.flush()
        return forecast

    def delete(self, forecast_id: str) -> bool:
        """删除支出预测记录"""
        forecast = self.get_by_id(forecast_id)
        if not forecast:
            return False

        self._session.delete(forecast)
        self._session.flush()
        return True

