from __future__ import annotations

from app.models.financial import UserRole


class Permission(str):
    """权限枚举"""
    # 数据录入
    DATA_IMPORT = "data:import"
    DATA_CONFIRM = "data:confirm"
    
    # 数据查看
    DATA_VIEW = "data:view"
    DATA_EXPORT = "data:export"
    
    # 数据分析
    DATA_ANALYZE = "data:analyze"
    NLQ_QUERY = "nlq:query"
    
    # 管理（仅管理员）
    USER_MANAGE = "user:manage"
    SYSTEM_CONFIG = "system:config"


# 角色-权限映射
ROLE_PERMISSIONS: dict[UserRole, list[str]] = {
    UserRole.ADMIN: [
        Permission.DATA_IMPORT,
        Permission.DATA_CONFIRM,
        Permission.DATA_VIEW,
        Permission.DATA_EXPORT,
        Permission.DATA_ANALYZE,
        Permission.NLQ_QUERY,
        Permission.USER_MANAGE,
        Permission.SYSTEM_CONFIG,
    ],
    UserRole.FINANCE: [
        Permission.DATA_IMPORT,
        Permission.DATA_CONFIRM,
        Permission.DATA_VIEW,
        Permission.DATA_EXPORT,
    ],
    UserRole.VIEWER: [
        Permission.DATA_VIEW,
        Permission.DATA_EXPORT,
    ],
}


def has_permission(user_role: UserRole, permission: str) -> bool:
    """检查角色是否有指定权限"""
    user_permissions = ROLE_PERMISSIONS.get(user_role, [])
    return permission in user_permissions

