#!/usr/bin/env python3
"""
创建用户的脚本（支持所有角色）

用法:
    poetry run python scripts/create_user.py <email> <password> <display_name> [role]
    
角色选项:
    admin    - 管理员（所有权限）
    finance  - 财务人员（录入、确认、查看、导出）
    viewer   - 查看者（仅查看和导出）
    
示例:
    poetry run python scripts/create_user.py user@example.com password123 "财务人员" finance
    poetry run python scripts/create_user.py viewer@example.com password123 "查看者" viewer
    poetry run python scripts/create_user.py admin@example.com password123 "管理员" admin
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.core.security import hash_password
from app.db import SessionLocal
from app.models.financial import User, UserRole


def create_user(email: str, password: str, display_name: str, role: UserRole = UserRole.VIEWER) -> None:
    """创建用户"""
    session = SessionLocal()
    try:
        # 检查用户是否已存在
        existing_user = session.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"❌ 用户 {email} 已存在")
            sys.exit(1)
        
        # 创建用户
        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            role=role,
            is_active=True,
        )
        session.add(user)
        session.commit()
        print(f"✅ 成功创建用户: {email} ({display_name})")
        print(f"   角色: {role.value}")
        print(f"   状态: 已激活")
    except Exception as e:
        session.rollback()
        print(f"❌ 创建用户失败: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    if len(sys.argv) < 4 or len(sys.argv) > 5:
        print("用法: python create_user.py <email> <password> <display_name> [role]")
        print("\n角色选项:")
        print("  admin   - 管理员（所有权限）")
        print("  finance - 财务人员（录入、确认、查看、导出）")
        print("  viewer  - 查看者（仅查看和导出，默认）")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    display_name = sys.argv[3]
    
    # 解析角色
    if len(sys.argv) == 5:
        role_str = sys.argv[4].lower()
        role_map = {
            "admin": UserRole.ADMIN,
            "finance": UserRole.FINANCE,
            "viewer": UserRole.VIEWER,
        }
        if role_str not in role_map:
            print(f"❌ 无效的角色: {role_str}")
            print("有效角色: admin, finance, viewer")
            sys.exit(1)
        role = role_map[role_str]
    else:
        role = UserRole.VIEWER  # 默认为查看者
    
    create_user(email, password, display_name, role)

