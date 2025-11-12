from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.models.financial import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    display_name: str = Field(..., min_length=1, max_length=128)
    role: UserRole = UserRole.VIEWER


class UserLogin(BaseModel):
    username: str  # 用户名（可以是display_name或email）
    password: str
    remember_me: bool = False  # 记住我选项，默认 False


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: UserRole
    is_active: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    user_id: str | None = None
    email: str | None = None
    role: UserRole | None = None

