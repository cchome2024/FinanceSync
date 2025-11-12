#!/bin/bash
# 检查后端服务器配置

echo "=========================================="
echo "检查后端服务器配置"
echo "=========================================="

# 检查端口占用
echo "1. 检查端口 8000 占用情况："
lsof -i :8000 2>/dev/null | grep LISTEN || echo "   端口 8000 未被占用"

echo ""
echo "2. 测试本地连接："
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✅ localhost:8000 可以访问"
    curl -s http://localhost:8000/health
else
    echo "   ❌ localhost:8000 无法访问"
fi

echo ""
echo "3. 获取本机 IP 地址："
if [[ "$OSTYPE" == "darwin"* ]]; then
    LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | head -1 | awk '{print $2}')
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    LOCAL_IP=$(hostname -I | awk '{print $1}')
else
    LOCAL_IP="未知"
fi
echo "   本机 IP: $LOCAL_IP"

echo ""
echo "4. 测试 IP 地址连接："
if [ "$LOCAL_IP" != "未知" ]; then
    if curl -s http://$LOCAL_IP:8000/health > /dev/null 2>&1; then
        echo "   ✅ $LOCAL_IP:8000 可以访问"
        curl -s http://$LOCAL_IP:8000/health
    else
        echo "   ❌ $LOCAL_IP:8000 无法访问"
        echo ""
        echo "   ⚠️  问题：服务器只监听 localhost，需要重启为 --host 0.0.0.0"
        echo ""
        echo "   解决方案："
        echo "   1. 停止当前服务器（Ctrl+C 或 kill 进程）"
        echo "   2. 使用以下命令重启："
        echo "      cd backend"
        echo "      poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
        echo "   或使用启动脚本："
        echo "      cd backend && ./start_server.sh"
    fi
fi

echo ""
echo "=========================================="

