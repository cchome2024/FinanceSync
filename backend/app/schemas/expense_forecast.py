from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.financial import Certainty


class ExpenseForecastCreate(BaseModel):
    """创建支出预测"""
    month: str = Field(..., description="月份，格式为 YYYY-MM")
    category_label: Optional[str] = Field(None, alias="categoryLabel")
    description: Optional[str] = None
    account_name: Optional[str] = Field(None, alias="accountName")
    amount: float = Field(..., gt=0, description="金额（元）")
    certainty: Certainty = Certainty.CERTAIN


class ExpenseForecastUpdate(BaseModel):
    """更新支出预测"""
    description: Optional[str] = None
    account_name: Optional[str] = Field(None, alias="accountName")
    amount: Optional[float] = Field(None, gt=0, description="金额（元）")
    category_label: Optional[str] = Field(None, alias="categoryLabel")
    certainty: Optional[Certainty] = None


class ExpenseForecastResponse(BaseModel):
    """支出预测响应"""
    id: str
    month: str
    category_label: Optional[str] = Field(None, alias="categoryLabel")
    description: Optional[str] = None
    account_name: Optional[str] = Field(None, alias="accountName")
    amount: float
    certainty: Certainty

    class Config:
        from_attributes = True

