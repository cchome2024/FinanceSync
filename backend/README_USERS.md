# 用户管理指南

## 添加用户的方法

### 方法1: 使用脚本创建用户（推荐）

#### 创建管理员
```bash
cd backend
poetry run python scripts/create_admin.py admin@example.com password123 "管理员"
```

#### 创建财务人员
```bash
poetry run python scripts/create_user.py finance@example.com password123 "财务人员" finance
```

#### 创建查看者
```bash
poetry run python scripts/create_user.py viewer@example.com password123 "查看者" viewer
```

或者不指定角色（默认为查看者）：
```bash
poetry run python scripts/create_user.py viewer@example.com password123 "查看者"
```

### 方法2: 通过 API 注册用户（需要管理员权限）

首先需要管理员登录获取 token，然后调用注册 API：

```bash
# 1. 管理员登录获取 token
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "password123"
  }'

# 2. 使用 token 注册新用户
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{
    "email": "finance@example.com",
    "password": "password123",
    "display_name": "财务人员",
    "role": "finance"
  }'
```

### 方法3: 使用 Python 交互式脚本

创建一个临时脚本 `add_user.py`：

```python
from app.core.security import hash_password
from app.db import SessionLocal
from app.models.financial import User, UserRole

session = SessionLocal()
try:
    user = User(
        email="user@example.com",
        password_hash=hash_password("password123"),
        display_name="用户",
        role=UserRole.FINANCE,
    )
    session.add(user)
    session.commit()
    print(f"用户创建成功: {user.email}")
finally:
    session.close()
```

然后运行：
```bash
poetry run python add_user.py
```

## 用户角色说明

| 角色 | 权限 |
|------|------|
| **admin** | 所有权限（数据录入、确认、查看、导出、分析、NLQ查询、用户管理、系统配置） |
| **finance** | 数据录入、确认、查看、导出 |
| **viewer** | 查看、导出（默认角色） |

## 批量创建用户

可以创建一个批量导入脚本 `scripts/batch_create_users.py`：

```python
#!/usr/bin/env python3
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.core.security import hash_password
from app.db import SessionLocal
from app.models.financial import User, UserRole

users = [
    ("admin@example.com", "password123", "管理员", UserRole.ADMIN),
    ("finance1@example.com", "password123", "财务1", UserRole.FINANCE),
    ("finance2@example.com", "password123", "财务2", UserRole.FINANCE),
    ("viewer1@example.com", "password123", "查看者1", UserRole.VIEWER),
]

session = SessionLocal()
try:
    for email, password, display_name, role in users:
        existing = session.query(User).filter(User.email == email).first()
        if existing:
            print(f"跳过已存在的用户: {email}")
            continue
        
        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            role=role,
        )
        session.add(user)
        print(f"创建用户: {email} ({display_name})")
    
    session.commit()
    print("✅ 批量创建完成")
except Exception as e:
    session.rollback()
    print(f"❌ 错误: {e}")
finally:
    session.close()
```

## 修改用户信息

### 修改密码

可以通过 API 或直接更新数据库：

```python
from app.core.security import hash_password
from app.db import SessionLocal
from app.models.financial import User

session = SessionLocal()
try:
    user = session.query(User).filter(User.email == "user@example.com").first()
    if user:
        user.password_hash = hash_password("new_password")
        session.commit()
        print("密码已更新")
finally:
    session.close()
```

### 修改角色

```python
from app.db import SessionLocal
from app.models.financial import User, UserRole

session = SessionLocal()
try:
    user = session.query(User).filter(User.email == "user@example.com").first()
    if user:
        user.role = UserRole.ADMIN  # 或 UserRole.FINANCE, UserRole.VIEWER
        session.commit()
        print("角色已更新")
finally:
    session.close()
```

### 禁用/启用用户

```python
from app.db import SessionLocal
from app.models.financial import User

session = SessionLocal()
try:
    user = session.query(User).filter(User.email == "user@example.com").first()
    if user:
        user.is_active = False  # 禁用用户
        # user.is_active = True  # 启用用户
        session.commit()
        print("用户状态已更新")
finally:
    session.close()
```

## 查看所有用户

```python
from app.db import SessionLocal
from app.models.financial import User

session = SessionLocal()
try:
    users = session.query(User).all()
    for user in users:
        print(f"{user.email} - {user.display_name} - {user.role.value} - {'激活' if user.is_active else '禁用'}")
finally:
    session.close()
```

