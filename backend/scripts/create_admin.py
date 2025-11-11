#!/usr/bin/env python3
"""
创建管理员用户的脚本

用法:
    poetry run python scripts/create_admin.py <email> <password> <display_name>
    
示例:
    poetry run python scripts/create_admin.py admin@example.com password123 "管理员"
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.core.security import hash_password
from app.db import SessionLocal
from app.models.financial import User, UserRole


def create_admin(email: str, password: str, display_name: str) -> None:
    """创建管理员用户"""
    session = SessionLocal()
    try:
        # 检查用户是否已存在
        existing_user = session.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"❌ 用户 {email} 已存在")
            sys.exit(1)
        
        # 创建管理员用户
        admin = User(
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(admin)
        session.commit()
        print(f"✅ 成功创建管理员用户: {email} ({display_name})")
    except Exception as e:
        session.rollback()
        print(f"❌ 创建用户失败: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("用法: python create_admin.py <email> <password> <display_name>")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    display_name = sys.argv[3]
    
    create_admin(email, password, display_name)

