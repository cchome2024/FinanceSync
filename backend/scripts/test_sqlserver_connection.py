#!/usr/bin/env python3
"""测试 SQL Server 连接脚本"""

import sys
from pathlib import Path
import os
#os.environ['TDSDUMP'] = 'stdout' 

# 添加项目根目录到路径
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

from app.core.config import get_settings
from sqlalchemy import create_engine
import pandas as pd

def test_connection():
    """测试 SQL Server 连接"""
    settings = get_settings()
    
    if not settings.sqlserver_host:
        print("❌ SQL Server 配置未找到，请检查 .env 文件")
        return False
    
    print(f"📋 连接配置:")
    print(f"   主机: {settings.sqlserver_host}")
    print(f"   端口: {settings.sqlserver_port or '1433 (默认)'}")
    print(f"   用户: {settings.sqlserver_user}")
    print(f"   数据库: {settings.sqlserver_database or 'master (默认)'}")
    print()
    
    # 构建连接参数
    port = settings.sqlserver_port or 1433
    database = settings.sqlserver_database or "master"
    
    print(f"🔌 尝试连接到 {settings.sqlserver_host}:{port}...")
    
    # 尝试使用不同的连接方式（使用 SQLAlchemy，与主代码一致）
    connection_strings = [
        # 方式1: 使用 pymssql
        f"mssql+pymssql://sa:Flare123456@10.168.40.61:1433/FA-ODS?charset=utf8"
    ]
    
    connect_args_options = [
        {},  # pymssql
        {"timeout": 30, "encrypt": "no"},  # 方式2
        {"timeout": 30, "encrypt": "no", "trustservercertificate": "yes"},  # 方式3
    ]
    
    engine = None
    last_error = None
    
    for i, conn_str in enumerate(connection_strings):
        try:
            method = "pymssql" if "pymssql" in conn_str else "pyodbc"
            print(f"   方式 {i+1}: 尝试使用 {method}...")
            
            # 获取对应的 connect_args
            connect_args = connect_args_options[i] if i < len(connect_args_options) else {}
            
            engine = create_engine(
                conn_str,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                connect_args=connect_args
            )
            
            # 测试连接（使用 text() 包装 SQL）
            from sqlalchemy import text
            with engine.connect() as conn:
                result = conn.execute(text("SELECT @@VERSION"))
                version = result.fetchone()
                print(f"✅ 连接成功！使用方式: {method}")
                print(f"📊 SQL Server 版本: {version[0][:150]}...")
                
                # 测试查询数据库
                if settings.sqlserver_database:
                    result = conn.execute(text("SELECT DB_NAME()"))
                    db_name = result.fetchone()
                    print(f"📊 当前数据库: {db_name[0]}")
            
            engine.dispose()
            return True
            
        except Exception as e:
            last_error = e
            error_msg = str(e)
            if len(error_msg) > 150:
                error_msg = error_msg[:150] + "..."
            print(f"   ❌ 方式 {i} 失败: {error_msg}")
            if engine:
                engine.dispose()
            continue
    
    if engine is None:
        print(f"❌ 所有连接方式都失败了")
        print(f"   最后错误: {last_error}")
        print()
        print("💡 可能的原因:")
        print("   1. SQL Server 服务未运行")
        print("   2. 端口不正确")
        print("   3. 防火墙阻止了连接")
        print("   4. SQL Server 配置不允许远程连接")
        print("   5. 需要安装 Microsoft ODBC Driver")
        print()
        print("🔧 建议:")
        print("   - 检查网络连接: nc -zv 10.168.40.61 1433")
        print("   - 安装 ODBC 驱动: HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql17")
        print("   - 检查可用驱动: odbcinst -q -d")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

