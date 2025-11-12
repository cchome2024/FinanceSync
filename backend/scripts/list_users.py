#!/usr/bin/env python3
"""
列举用户列表的脚本

用法:
    poetry run python scripts/list_users.py
    
示例:
    poetry run python scripts/list_users.py
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.db import SessionLocal
from app.models.financial import User, UserRole


def list_users() -> None:
    """列举所有用户"""
    session = SessionLocal()
    try:
        users = session.query(User).order_by(User.created_at.desc()).all()
        
        if not users:
            print("📋 当前没有用户")
            return
        
        print(f"\n📋 用户列表（共 {len(users)} 个用户）\n")
        print(f"{'ID':<38} {'邮箱':<30} {'显示名称':<20} {'角色':<10} {'状态':<8} {'创建时间':<20}")
        print("-" * 130)
        
        for user in users:
            status = "✅ 激活" if user.is_active else "❌ 禁用"
            role_display = {
                UserRole.ADMIN: "管理员",
                UserRole.FINANCE: "财务",
                UserRole.VIEWER: "查看者",
            }.get(user.role, user.role.value)
            
            created_at_str = user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else "未知"
            
            print(f"{user.id:<38} {user.email:<30} {user.display_name:<20} {role_display:<10} {status:<8} {created_at_str:<20}")
        
        print("\n" + "-" * 130)
        
        # 统计信息
        role_counts = {}
        active_count = 0
        for user in users:
            role_counts[user.role] = role_counts.get(user.role, 0) + 1
            if user.is_active:
                active_count += 1
        
        print(f"\n📊 统计信息:")
        print(f"   总用户数: {len(users)}")
        print(f"   激活用户: {active_count}")
        print(f"   禁用用户: {len(users) - active_count}")
        print(f"\n   角色分布:")
        for role, count in role_counts.items():
            role_name = {
                UserRole.ADMIN: "管理员",
                UserRole.FINANCE: "财务",
                UserRole.VIEWER: "查看者",
            }.get(role, role.value)
            print(f"     {role_name}: {count}")
        
    except Exception as e:
        print(f"❌ 列举用户失败: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    list_users()

