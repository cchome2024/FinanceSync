# Quickstart: 财务数据统一平台

## 1. 环境准备
1. 克隆仓库并切换到 `001-finance-data-hub` 分支。
2. 安装依赖：
   - 后端：`cd backend && poetry install`
   - 前端：`cd frontend && npm install`
3. 配置环境变量：
   - 复制 `backend/.env.example` → `.env`，填写数据库连接、LLM API 密钥、Redis URL、监控目录。
   - 复制 `frontend/.env.example` → `.env`, 设置 API 基址与聊天助手标识。

## 2. 启动基础服务
1. 启动 PostgreSQL（本地或 Docker，如果使用 SQLite 可跳过）。
2. 在 `backend/` 运行 `poetry run alembic upgrade head` 创建数据库。
3. 启动 Redis（用于 Celery 任务队列，如果使用 SQLite 可跳过）。

## 2.1 创建管理员用户（首次使用必须）

```bash
cd backend
poetry run python scripts/create_admin.py admin@example.com your_password "管理员"
```

## 3. 运行后端
1. `cd backend`
2. `poetry run uvicorn app.main:app --reload`
3. 单独启动 worker：`poetry run celery -A app.worker worker -l info`

## 4. 运行前端
1. `cd frontend`
2. `npx expo start --tunnel`
3. 使用 Expo Go 或 Web 浏览器打开。

## 5. 用户管理

### 创建用户

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
# 或者不指定角色（默认为查看者）
poetry run python scripts/create_user.py viewer@example.com password123 "查看者"
```

### 用户角色说明

| 角色 | 权限 |
|------|------|
| **admin** | 所有权限（数据录入、确认、查看、导出、分析、NLQ查询、用户管理、系统配置） |
| **finance** | 数据录入、确认、查看、导出 |
| **viewer** | 查看、导出（默认角色） |

### 通过 API 注册用户（需要管理员权限）

```bash
# 1. 管理员登录获取 token
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "password123"}'

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

## 6. 快速验证功能
1. **使用管理员账户登录前端应用**
2. 在"数据录入"对话窗口输入："导入 2025/11/03 账户余额：至明 127200.39，资产 2296463.78，喀戎 94429.60。"
3. 确认系统返回候选记录 → 点击"确认写入"。
4. 输入："上传本月收入表格"，选择样例 `revenue.xlsx` → 检查预览与警告。
5. 切换到"查询分析"对话窗口，发送问题："对比上季度收入和本季度预测" → 查看占位回答与高亮提示。
6. 打开"财务看板"页面，选择"最新数据"与历史月份，确认图表刷新在 3 秒内完成。

## 7. 常用命令

### 数据库操作

```bash
# 创建新的迁移文件
poetry run alembic revision -m "migration_name"

# 运行迁移
poetry run alembic upgrade head

# 回滚迁移
poetry run alembic downgrade -1

# 查看迁移历史
poetry run alembic history

# 查看当前版本
poetry run alembic current
```

### 用户管理

```bash
# 创建管理员
poetry run python scripts/create_admin.py <email> <password> <display_name>

# 创建用户（支持所有角色）
poetry run python scripts/create_user.py <email> <password> <display_name> [role]
# 角色选项: admin, finance, viewer（默认）
```

### 开发工具

```bash
# 运行测试
poetry run pytest

# 代码格式化
poetry run black .
poetry run isort .

# 代码检查
poetry run ruff check .
```

## 8. 环境变量配置

在 `backend/.env` 文件中配置：

```env
# 数据库
DATABASE_URL=sqlite:///./finance_sync.db

# JWT 密钥（生产环境必须修改）
JWT_SECRET_KEY=your-secret-key-change-in-production

# LLM 配置
LLM_PROVIDER=azure_openai
LLM_ENDPOINT=https://example.openai.azure.com
LLM_DEPLOYMENT=gpt-4o
LLM_API_KEY=your-api-key
LLM_TIMEOUT_SECONDS=120

# 存储配置
STORAGE_PROVIDER=local
STORAGE_LOCAL_PATH=./storage
```

在 `frontend/.env` 文件中配置：

```env
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000
```

## 9. 调试与日志
- 后端日志：`backend/logs/app.log`
- Celery 任务日志：`backend/logs/worker.log`
- 导入任务状态：访问 `/api/v1/import-jobs/{jobId}`

## 10. 故障排查

### 迁移错误：表已存在

如果遇到 "table already exists" 错误，迁移文件已包含存在性检查，可以安全地重新运行：

```bash
poetry run alembic upgrade head
```

### 依赖安装问题

如果遇到依赖安装问题：

```bash
# 更新锁定文件
poetry lock

# 重新安装依赖
poetry install

# 或者只安装依赖（不安装项目本身）
poetry install --no-root
```

### 前端依赖问题

```bash
cd frontend
# 清除缓存并重新安装
rm -rf node_modules
npm install
```

## 11. 下一步
- 使用 `/speckit.tasks` 生成实现任务列表。
- 审核数据模型与契约后，与财务团队确认字段映射。
- 创建更多用户账户并测试权限控制。

