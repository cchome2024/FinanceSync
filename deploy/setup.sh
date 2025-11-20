#!/bin/bash
# FinanceSync 自动化部署脚本
# 使用方法: sudo bash deploy/setup.sh

set -e

echo "=========================================="
echo "FinanceSync 部署脚本"
echo "=========================================="

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then 
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# 配置变量
APP_DIR="/opt/FinanceSync"
APP_USER="${SUDO_USER:-$USER}"
NGINX_SITE="financesync"

echo "应用目录: $APP_DIR"
echo "运行用户: $APP_USER"
echo ""

# 1. 创建目录结构
echo "1. 创建目录结构..."
mkdir -p "$APP_DIR/logs"
mkdir -p "$APP_DIR/backend/storage"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
echo "✓ 目录创建完成"

# 2. 安装系统依赖
echo ""
echo "2. 检查系统依赖..."
if ! command -v node &> /dev/null; then
    echo "安装 Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt install -y nodejs
fi

if ! command -v pm2 &> /dev/null; then
    echo "安装 PM2..."
    npm install -g pm2
fi

if ! command -v poetry &> /dev/null; then
    echo "安装 Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
fi

if ! command -v nginx &> /dev/null; then
    echo "安装 Nginx..."
    apt update
    apt install -y nginx
fi

# 安装 SQL Server 驱动依赖
if ! dpkg -l | grep -q freetds-dev; then
    echo "安装 FreeTDS..."
    apt install -y freetds-dev freetds-bin unixodbc-dev
fi

echo "✓ 系统依赖检查完成"

# 3. 配置 Nginx
echo ""
echo "3. 配置 Nginx..."
if [ -f "$APP_DIR/deploy/nginx.conf" ]; then
    cp "$APP_DIR/deploy/nginx.conf" "/etc/nginx/sites-available/$NGINX_SITE"
    if [ ! -L "/etc/nginx/sites-enabled/$NGINX_SITE" ]; then
        ln -s "/etc/nginx/sites-available/$NGINX_SITE" "/etc/nginx/sites-enabled/"
    fi
    
    # 创建日志目录
    mkdir -p /var/log/nginx
    
    # 测试配置
    if nginx -t; then
        systemctl restart nginx
        echo "✓ Nginx 配置完成"
    else
        echo "✗ Nginx 配置测试失败"
        exit 1
    fi
else
    echo "✗ 未找到 Nginx 配置文件: $APP_DIR/deploy/nginx.conf"
    exit 1
fi

# 4. 配置防火墙
echo ""
echo "4. 配置防火墙..."
if command -v ufw &> /dev/null; then
    ufw allow 8085/tcp
    echo "✓ 防火墙规则已添加"
elif command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=8085/tcp
    firewall-cmd --reload
    echo "✓ 防火墙规则已添加"
else
    echo "⚠ 未找到防火墙工具，请手动配置端口 8085"
fi

# 5. 提示后续步骤
echo ""
echo "=========================================="
echo "部署脚本执行完成！"
echo "=========================================="
echo ""
echo "后续步骤："
echo "1. 配置后端环境变量:"
echo "   cd $APP_DIR/backend"
echo "   cp .env.example .env  # 如果存在"
echo "   nano .env  # 编辑配置文件"
echo ""
echo "2. 安装 Python 依赖:"
echo "   cd $APP_DIR/backend"
echo "   poetry install --no-dev"
echo ""
echo "3. 初始化数据库:"
echo "   cd $APP_DIR/backend"
echo "   poetry run alembic upgrade head"
echo "   poetry run python scripts/create_admin.py"
echo ""
echo "4. 启动后端服务:"
echo "   cd $APP_DIR/backend"
echo "   pm2 start ecosystem.config.js"
echo "   pm2 startup"
echo "   pm2 save"
echo ""
echo "5. 验证部署:"
echo "   curl http://10.168.20.199:8085/health"
echo ""
echo "详细说明请查看: $APP_DIR/deploy/DEPLOYMENT.md"
echo "=========================================="

