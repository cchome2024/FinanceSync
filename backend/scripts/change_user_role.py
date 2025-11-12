#!/usr/bin/env python3
"""
转换用户角色的脚本

用法:
    poetry run python scripts/change_user_role.py <email_or_username> <new_role>
    
角色选项:
    admin    - 管理员（所有权限）
    finance  - 财务人员（录入、确认、查看、导出）
    viewer   - 查看者（仅查看和导出）
    
示例:
    poetry run python scripts/change_user_role.py user@example.com admin
    poetry run python scripts/change_user_role.py "财务人员" finance
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.db import SessionLocal
from app.models.financial import User, UserRole


def change_user_role(identifier: str, new_role: UserRole) -> None:
    """转换用户角色
    
    Args:
        identifier: 用户标识（邮箱或显示名称）
        new_role: 新角色
    """
    session = SessionLocal()
    try:
        # 尝试通过邮箱查找
        user = session.query(User).filter(User.email == identifier).first()
        
        # 如果没找到，尝试通过显示名称查找
        if not user:
            user = session.query(User).filter(User.display_name == identifier).first()
        
        if not user:
            print(f"❌ 未找到用户: {identifier}")
            print("   提示: 可以使用邮箱或显示名称来标识用户")
            sys.exit(1)
        
        old_role = user.role
        old_role_display = {
            UserRole.ADMIN: "管理员",
            UserRole.FINANCE: "财务",
            UserRole.VIEWER: "查看者",
        }.get(old_role, old_role.value)
        
        new_role_display = {
            UserRole.ADMIN: "管理员",
            UserRole.FINANCE: "财务",
            UserRole.VIEWER: "查看者",
        }.get(new_role, new_role.value)
        
        if old_role == new_role:
            print(f"ℹ️  用户 {user.email} ({user.display_name}) 的角色已经是 {new_role_display}，无需修改")
            return
        
        # 更新角色
        user.role = new_role
        session.commit()
        
        print(f"✅ 成功转换用户角色:")
        print(f"   用户: {user.email} ({user.display_name})")
        print(f"   原角色: {old_role_display}")
        print(f"   新角色: {new_role_display}")
        
    except Exception as e:
        session.rollback()
        print(f"❌ 转换角色失败: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python change_user_role.py <email_or_username> <new_role>")
        print("\n角色选项:")
        print("  admin   - 管理员（所有权限）")
        print("  finance - 财务人员（录入、确认、查看、导出）")
        print("  viewer  - 查看者（仅查看和导出）")
        print("\n示例:")
        print("  python change_user_role.py user@example.com admin")
        print("  python change_user_role.py \"财务人员\" finance")
        sys.exit(1)
    
    identifier = sys.argv[1]
    role_str = sys.argv[2].lower()
    
    # 解析角色
    role_map = {
        "admin": UserRole.ADMIN,
        "finance": UserRole.FINANCE,
        "viewer": UserRole.VIEWER,
    }
    
    if role_str not in role_map:
        print(f"❌ 无效的角色: {role_str}")
        print("有效角色: admin, finance, viewer")
        sys.exit(1)
    
    new_role = role_map[role_str]
    change_user_role(identifier, new_role)

