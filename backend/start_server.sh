#!/bin/bash
# 启动后端服务器，允许手机访问

# 获取本机 IP 地址（macOS）
if [[ "$OSTYPE" == "darwin"* ]]; then
    LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | head -1 | awk '{print $2}')
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    LOCAL_IP=$(hostname -I | awk '{print $1}')
else
    LOCAL_IP="0.0.0.0"
fi

echo "=========================================="
echo "启动后端服务器（允许手机访问）"
echo "=========================================="
echo "本机 IP 地址: $LOCAL_IP"
echo "服务器地址: http://$LOCAL_IP:8000"
echo "=========================================="
echo ""
echo "⚠️  请确保："
echo "1. 手机和电脑连接到同一个 Wi-Fi 网络"
echo "2. 防火墙允许 8000 端口访问"
echo "3. 前端配置使用此 IP 地址：http://$LOCAL_IP:8000"
echo ""
echo "按 Ctrl+C 停止服务器"
echo "=========================================="
echo ""

# 启动 uvicorn，监听所有网络接口
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

