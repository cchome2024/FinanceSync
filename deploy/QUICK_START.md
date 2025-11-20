# FinanceSync 快速部署指南

## 一键部署（推荐）

```bash
# 1. 上传代码到服务器
scp -r FinanceSync user@10.168.20.199:/opt/

# 2. SSH 登录服务器
ssh user@10.168.20.199

# 3. 运行自动化部署脚本
cd /opt/FinanceSync
sudo bash deploy/setup.sh

# 4. 配置环境变量
cd /opt/FinanceSync/backend
nano .env  # 编辑配置文件，参考下面的配置示例

# 5. 安装依赖并启动
cd /opt/FinanceSync/backend
poetry install --no-dev
poetry run alembic upgrade head
poetry run python scripts/create_admin.py

# 6. 启动服务
pm2 start ecosystem.config.js
pm2 startup
pm2 save

# 7. 验证
curl http://10.168.20.199:8085/health
```

## 环境变量配置示例

创建 `/opt/FinanceSync/backend/.env`:

```env
# SQL Server 配置
SQLSERVER_HOST=10.168.40.61
SQLSERVER_PORT=1433
SQLSERVER_USER=sas
SQLSERVER_PASSWORD=Flare123456
SQLSERVER_DATABASE=FA-ODS

# JWT 密钥（生产环境请修改）
JWT_SECRET_KEY=your-production-secret-key-change-this

# 数据库（默认 SQLite）
DATABASE_URL=sqlite:///./finance_sync.db
```

## 常用命令

### PM2 管理
```bash
# 启动
pm2 start /opt/FinanceSync/backend/ecosystem.config.js

# 停止
pm2 stop financesync-backend

# 重启
pm2 restart financesync-backend

# 查看状态
pm2 status

# 查看日志
pm2 logs financesync-backend

# 查看详细信息
pm2 show financesync-backend
```

### Nginx 管理
```bash
# 重启
sudo systemctl restart nginx

# 查看状态
sudo systemctl status nginx

# 测试配置
sudo nginx -t

# 查看日志
sudo tail -f /var/log/nginx/financesync-access.log
sudo tail -f /var/log/nginx/financesync-error.log
```

### 更新代码
```bash
cd /opt/FinanceSync
git pull  # 或上传新代码
cd backend
poetry install --no-dev  # 如果需要更新依赖
poetry run alembic upgrade head  # 如果需要数据库迁移
pm2 restart financesync-backend
```

## 访问地址

- **前端访问**: http://10.168.20.199:8085
- **API 健康检查**: http://10.168.20.199:8085/health
- **后端直接访问**（仅本地）: http://127.0.0.1:8000/health

## 故障排查

### 后端无法启动
```bash
# 检查 PM2 状态
pm2 status

# 查看详细日志
pm2 logs financesync-backend --lines 100

# 手动测试启动
cd /opt/FinanceSync/backend
poetry run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Nginx 502 错误
```bash
# 检查后端是否运行
pm2 status

# 检查后端端口
curl http://127.0.0.1:8000/health

# 检查 Nginx 错误日志
sudo tail -f /var/log/nginx/financesync-error.log
```

### 无法访问
```bash
# 检查端口监听
sudo netstat -tlnp | grep 8085
sudo netstat -tlnp | grep 8000

# 检查防火墙
sudo ufw status
```

## 文件位置

- **应用目录**: `/opt/FinanceSync`
- **后端代码**: `/opt/FinanceSync/backend`
- **前端代码**: `/opt/FinanceSync/frontend`
- **日志目录**: `/opt/FinanceSync/logs`
- **PM2 配置**: `/opt/FinanceSync/backend/ecosystem.config.js`
- **Nginx 配置**: `/etc/nginx/sites-available/financesync`
- **环境变量**: `/opt/FinanceSync/backend/.env`

