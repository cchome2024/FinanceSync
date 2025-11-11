from __future__ import annotations

from typing import AsyncIterator, Iterator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.auth import decode_access_token
from app.core.permissions import Permission, has_permission
from app.db import SessionLocal
from app.models.financial import User, UserRole
from app.repositories.import_jobs import ImportJobRepository
from app.services.ai_parser import AIParserService
from app.services.llm_client import LLMClient
from app.services.financial_overview import FinancialOverviewService
from app.services.nlq_service import NLQService
from app.services.storage_adapter import StorageAdapter, StorageFactory

security = HTTPBearer()


def get_db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_db_session),
) -> User:
    """验证JWT并返回当前用户"""
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        user = session.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


def require_permission(permission: Permission):
    """权限检查装饰器工厂"""
    def check_permission(
        user: User = Depends(get_current_user),
    ) -> User:
        if not has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}"
            )
        return user
    return check_permission


def require_role(role: UserRole):
    """角色检查装饰器工厂"""
    def check_role(
        user: User = Depends(get_current_user),
    ) -> User:
        if user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {role.value}"
            )
        return user
    return check_role


async def get_ai_parser() -> AsyncIterator[AIParserService]:
    client = LLMClient()
    try:
        parser = AIParserService(client)
        yield parser
    finally:
        await client.close()


def get_storage_adapter() -> StorageAdapter:
    return StorageFactory.create()


def get_import_job_repository(session: Session = Depends(get_db_session)) -> ImportJobRepository:
    return ImportJobRepository(session)


def get_nlq_service(session: Session = Depends(get_db_session)) -> NLQService:
    return NLQService(session)


def get_financial_overview_service(session: Session = Depends(get_db_session)) -> FinancialOverviewService:
    return FinancialOverviewService(session)

