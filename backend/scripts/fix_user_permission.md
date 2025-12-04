# 修复用户权限问题

## 问题
用户遇到 `Permission denied: data:import` 错误，说明当前用户角色没有 `data:import` 权限。

## 解决方案

### 1. 查看当前用户列表

```bash
cd /opt/FinanceSync/backend
poetry run python scripts/list_users.py
```

### 2. 修改用户角色

将用户角色改为 `finance`（财务人员）或 `admin`（管理员），这两个角色都有 `data:import` 权限。

#### 方法1：使用脚本修改（推荐）

```bash
# 将用户改为财务人员（推荐）
poetry run python scripts/change_user_role.py <用户邮箱或显示名称> finance

# 或者改为管理员
poetry run python scripts/change_user_role.py <用户邮箱或显示名称> admin
```

示例：
```bash
# 如果用户邮箱是 user@example.com
poetry run python scripts/change_user_role.py user@example.com finance

# 如果用户显示名称是 "财务人员"
poetry run python scripts/change_user_role.py "财务人员" finance
```

#### 方法2：直接修改数据库

如果脚本不可用，可以直接修改数据库：

```bash
cd /opt/FinanceSync/backend
poetry run python
```

然后在 Python 交互式环境中执行：

```python
from app.db import SessionLocal
from app.models.financial import User, UserRole

session = SessionLocal()
try:
    # 替换为实际的用户邮箱
    user = session.query(User).filter(User.email == "your_email@example.com").first()
    if user:
        user.role = UserRole.FINANCE  # 或 UserRole.ADMIN
        session.commit()
        print(f"✅ 用户 {user.email} 的角色已更新为 {user.role.value}")
    else:
        print("❌ 未找到用户")
finally:
    session.close()
```

### 3. 重新登录

修改角色后，用户需要**重新登录**才能生效（因为 JWT token 中包含用户角色信息）。

## 权限说明

| 角色 | data:import 权限 | 说明 |
|------|-----------------|------|
| **admin** | ✅ | 管理员，拥有所有权限 |
| **finance** | ✅ | 财务人员，可以录入、确认、查看、导出数据 |
| **viewer** | ❌ | 查看者，只能查看和导出数据 |

## 验证

修改后，可以再次查看用户列表确认：

```bash
poetry run python scripts/list_users.py
```

然后让用户重新登录，再次尝试触发 API 数据源同步。


