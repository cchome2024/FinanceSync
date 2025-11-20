# FinanceSync 部署指南

## 服务器信息
- **服务器地址**: 10.168.20.199
- **程序目录**: /opt/FinanceSync
- **访问端口**: 8085 (通过 Nginx)
- **后端端口**: 8000 (内部，PM2 管理)
- **进程管理**: PM2
- **Web 服务器**: Nginx

## 前置要求

### 1. 系统依赖
```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础工具
sudo apt install -y python3 python3-pip python3-venv curl git build-essential

# 安装 Node.js 和 npm (用于 PM2)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# 安装 PM2
sudo npm install -g pm2

# 安装 Poetry (Python 依赖管理)
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
# 或者添加到 ~/.bashrc
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 安装 Nginx
sudo apt install -y nginx
```

### 2. 安装 SQL Server 驱动依赖
```bash
# 安装 FreeTDS 开发库（SQL Server 连接需要）
sudo apt install -y freetds-dev freetds-bin unixodbc-dev
```

## 部署步骤

### 1. 创建目录结构
```bash
sudo mkdir -p /opt/FinanceSync
sudo mkdir -p /opt/FinanceSync/logs
sudo chown -R $USER:$USER /opt/FinanceSync
```

### 2. 上传代码
```bash
# 方式1: 使用 git clone
cd /opt/FinanceSync
git clone <your-repo-url> .

# 方式2: 使用 scp 上传
# 在本地执行: scp -r /path/to/FinanceSync user@10.168.20.199:/opt/
```

### 3. 配置后端环境

#### 3.1 安装 Python 依赖
```bash
cd /opt/FinanceSync/backend
poetry install --no-dev
```

#### 3.2 配置环境变量
创建 `/opt/FinanceSync/backend/.env` 文件：
```bash
cd /opt/FinanceSync/backend
cat > .env << EOF
# 数据库配置
DATABASE_URL=sqlite:///./finance_sync.db
# 或者使用 PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost:5432/financesync

# SQL Server 配置（用于 API 数据源）
SQLSERVER_HOST=10.168.40.61
SQLSERVER_PORT=1433
SQLSERVER_USER=sas
SQLSERVER_PASSWORD=Flare123456
SQLSERVER_DATABASE=FA-ODS

# JWT 密钥（生产环境请修改）
JWT_SECRET_KEY=your-production-secret-key-change-this

# Redis 配置（如果需要）
REDIS_URL=redis://localhost:6379/0

# LLM 配置（如果需要）
LLM_PROVIDER=deepseek
LLM_ENDPOINT=https://api.deepseek.com
LLM_API_KEY=your-api-key

# 日志级别
LOG_LEVEL=INFO
EOF
```

#### 3.3 初始化数据库
```bash
cd /opt/FinanceSync/backend
poetry run alembic upgrade head

# 创建管理员用户
poetry run python scripts/create_admin.py
```

### 4. 配置 PM2

#### 4.1 复制 PM2 配置文件
```bash
# 配置文件已在 backend/ecosystem.config.js
# 确保路径正确
```

#### 4.2 启动后端服务
```bash
cd /opt/FinanceSync/backend
pm2 start ecosystem.config.js

# 查看状态
pm2 status

# 查看日志
pm2 logs financesync-backend

# 设置开机自启
pm2 startup
pm2 save
```

### 5. 配置 Nginx

#### 5.1 复制 Nginx 配置文件
```bash
sudo cp /opt/FinanceSync/deploy/nginx.conf /etc/nginx/sites-available/financesync
sudo ln -s /etc/nginx/sites-available/financesync /etc/nginx/sites-enabled/
```

#### 5.2 如果前端是静态构建
```bash
# 构建前端（在本地或服务器上）
cd /opt/FinanceSync/frontend
npm install
npm run build  # 或 expo export，根据项目配置

# 确保构建输出目录存在
sudo mkdir -p /opt/FinanceSync/frontend/dist
```

#### 5.3 测试并重启 Nginx
```bash
# 测试配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx

# 查看状态
sudo systemctl status nginx
```

### 6. 配置防火墙
```bash
# 允许 8085 端口
sudo ufw allow 8085/tcp

# 如果使用 firewalld
sudo firewall-cmd --permanent --add-port=8085/tcp
sudo firewall-cmd --reload
```

## 验证部署

### 1. 检查后端服务
```bash
# 检查 PM2 状态
pm2 status

# 检查后端健康状态
curl http://127.0.0.1:8000/health

# 查看后端日志
pm2 logs financesync-backend
```

### 2. 检查 Nginx
```bash
# 检查 Nginx 状态
sudo systemctl status nginx

# 测试访问
curl http://10.168.20.199:8085/health
```

### 3. 浏览器访问
打开浏览器访问: `http://10.168.20.199:8085`

## 常用操作

### 重启服务
```bash
# 重启后端
pm2 restart financesync-backend

# 重启 Nginx
sudo systemctl restart nginx
```

### 查看日志
```bash
# 后端日志
pm2 logs financesync-backend

# Nginx 访问日志
sudo tail -f /var/log/nginx/financesync-access.log

# Nginx 错误日志
sudo tail -f /var/log/nginx/financesync-error.log
```

### 更新代码
```bash
cd /opt/FinanceSync
git pull  # 或上传新代码

# 更新后端依赖（如果需要）
cd backend
poetry install --no-dev

# 运行数据库迁移（如果需要）
poetry run alembic upgrade head

# 重启服务
pm2 restart financesync-backend
```

## 故障排查

### 后端无法启动
1. 检查 `.env` 文件是否存在且配置正确
2. 检查 Python 依赖是否安装完整: `poetry install`
3. 查看 PM2 日志: `pm2 logs financesync-backend`
4. 检查端口是否被占用: `sudo netstat -tlnp | grep 8000`

### Nginx 502 错误
1. 检查后端是否运行: `pm2 status`
2. 检查后端端口: `curl http://127.0.0.1:8000/health`
3. 查看 Nginx 错误日志: `sudo tail -f /var/log/nginx/financesync-error.log`

### 无法访问
1. 检查防火墙: `sudo ufw status`
2. 检查 Nginx 配置: `sudo nginx -t`
3. 检查端口监听: `sudo netstat -tlnp | grep 8085`

## 安全建议

1. **修改默认密码**: 确保 `.env` 文件中的密码和密钥都已修改
2. **文件权限**: 确保 `.env` 文件权限为 600: `chmod 600 /opt/FinanceSync/backend/.env`
3. **HTTPS**: 生产环境建议配置 SSL 证书，使用 HTTPS
4. **防火墙**: 只开放必要的端口
5. **定期备份**: 定期备份数据库和配置文件

## 备份

### 备份数据库
```bash
# SQLite
cp /opt/FinanceSync/backend/finance_sync.db /backup/finance_sync_$(date +%Y%m%d).db

# PostgreSQL (如果使用)
pg_dump -U user financesync > /backup/financesync_$(date +%Y%m%d).sql
```

### 备份配置文件
```bash
tar -czf /backup/financesync_config_$(date +%Y%m%d).tar.gz \
  /opt/FinanceSync/backend/.env \
  /opt/FinanceSync/backend/api_sources_config.json \
  /etc/nginx/sites-available/financesync
```

