#!/bin/bash
# PM2 启动脚本
# 此脚本由 PM2 调用，用于启动后端服务

cd /opt/FinanceSync/backend

# 确保 Poetry 在 PATH 中
export PATH="$HOME/.local/bin:$PATH"

# 启动 uvicorn
exec poetry run uvicorn app.main:app --host 127.0.0.1 --port 8000

