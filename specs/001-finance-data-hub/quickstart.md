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
1. 启动 PostgreSQL（本地或 Docker）。
2. 在 `backend/` 运行 `poetry run alembic upgrade head` 创建数据库。
3. 启动 Redis（用于 Celery 任务队列）。

## 3. 运行后端
1. `cd backend`
2. `poetry run uvicorn app.main:app --reload`
3. 单独启动 worker：`poetry run celery -A app.worker worker -l info`

## 4. 运行前端
1. `cd frontend`
2. `npx expo start --tunnel`
3. 使用 Expo Go 或 Web 浏览器打开。

## 5. 快速验证功能
1. 在前端 AI 聊天输入：“导入 2025/11/03 账户余额：至明 127200.39，资产 2296463.78，喀戎 94429.60。”
2. 确认系统返回候选记录 → 点击“确认写入”。
3. 输入：“上传本月收入表格”，选择样例 `revenue.xlsx` → 检查预览与警告。
4. 发送问题：“对比上季度收入和本季度预测” → 查看图表与摘要。
5. 打开看板页面，选择“最新数据”与历史月份，确认图表刷新在 3 秒内完成。

## 6. 调试与日志
- 后端日志：`backend/logs/app.log`
- Celery 任务日志：`backend/logs/worker.log`
- 导入任务状态：访问 `/api/v1/import-jobs/{jobId}`

## 7. 下一步
- 使用 `/speckit.tasks` 生成实现任务列表。
- 审核数据模型与契约后，与财务团队确认字段映射。

