from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_current_user, require_role
from app.core.auth import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, ACCESS_TOKEN_EXPIRE_MINUTES_REMEMBER
from datetime import timedelta
from app.core.security import hash_password, verify_password
from app.models.financial import User, UserRole
from app.schemas.auth import UserCreate, UserLogin, TokenResponse, UserResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),  # 只有管理员可以注册新用户
    session: Session = Depends(get_db_session),
) -> UserResponse:
    """注册新用户（仅管理员可用）"""
    # 检查邮箱是否已存在
    existing_user = session.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # 创建新用户
    user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        display_name=user_data.display_name,
        role=user_data.role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: UserLogin,
    session: Session = Depends(get_db_session),
) -> TokenResponse:
    """用户登录（支持用户名或邮箱登录）"""
    # 尝试通过display_name（用户名）或email登录
    user = session.query(User).filter(
        (User.display_name == credentials.username) | (User.email == credentials.username)
    ).first()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # 创建访问令牌（根据 remember_me 设置过期时间）
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES_REMEMBER) if credentials.remember_me else None
    access_token = create_access_token(
        data={
            "user_id": user.id,
            "email": user.email,
            "role": user.role.value,
        },
        expires_delta=expires_delta
    )
    
    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    user: User = Depends(get_current_user),
) -> UserResponse:
    """获取当前用户信息"""
    return UserResponse.model_validate(user)

