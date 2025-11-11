from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.permissions import Permission
from app.models.financial import User, Certainty
from app.repositories.expense_forecast import ExpenseForecastRepository
from app.schemas.expense_forecast import ExpenseForecastCreate, ExpenseForecastUpdate, ExpenseForecastResponse

router = APIRouter(prefix="/api/v1", tags=["expense-forecast"])


def get_expense_forecast_repository(session: Session = Depends(get_db_session)) -> ExpenseForecastRepository:
    return ExpenseForecastRepository(session)


@router.post(
    "/expense-forecast",
    response_model=ExpenseForecastResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_expense_forecast(
    data: ExpenseForecastCreate,
    company_id: Optional[str] = None,
    user: User = Depends(require_permission(Permission.DATA_IMPORT)),
    repo: ExpenseForecastRepository = Depends(get_expense_forecast_repository),
) -> ExpenseForecastResponse:
    """创建支出预测记录"""
    forecast = repo.create(
        month=data.month,
        category_label=data.category_label,
        description=data.description,
        account_name=data.account_name,
        amount=data.amount,
        certainty=data.certainty,
        company_id=company_id,
    )
    repo.session.commit()
    
    return ExpenseForecastResponse(
        id=forecast.id,
        month=data.month,
        category_label=forecast.category_label,
        description=forecast.description,
        account_name=forecast.account_name,
        amount=float(forecast.expected_amount),
        certainty=forecast.certainty,
    )


@router.put(
    "/expense-forecast/{forecast_id}",
    response_model=ExpenseForecastResponse,
    status_code=status.HTTP_200_OK,
)
def update_expense_forecast(
    forecast_id: str,
    data: ExpenseForecastUpdate,
    user: User = Depends(require_permission(Permission.DATA_IMPORT)),
    repo: ExpenseForecastRepository = Depends(get_expense_forecast_repository),
) -> ExpenseForecastResponse:
    """更新支出预测记录"""
    forecast = repo.update(
        forecast_id=forecast_id,
        description=data.description,
        account_name=data.account_name,
        amount=data.amount,
        category_label=data.category_label,
        certainty=data.certainty,
    )
    
    if not forecast:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense forecast not found"
        )
    
    repo.session.commit()
    
    # 计算月份字符串
    month = f"{forecast.cash_out_date.year}-{forecast.cash_out_date.month:02d}"
    
    return ExpenseForecastResponse(
        id=forecast.id,
        month=month,
        category_label=forecast.category_label,
        description=forecast.description,
        account_name=forecast.account_name,
        amount=float(forecast.expected_amount),
        certainty=forecast.certainty,
    )


@router.delete(
    "/expense-forecast/{forecast_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_expense_forecast(
    forecast_id: str,
    user: User = Depends(require_permission(Permission.DATA_IMPORT)),
    repo: ExpenseForecastRepository = Depends(get_expense_forecast_repository),
):
    """删除支出预测记录"""
    success = repo.delete(forecast_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense forecast not found"
        )
    
    repo.session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

