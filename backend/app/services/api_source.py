from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from sqlalchemy import create_engine

from app.schemas.imports import CandidateRecord, RecordType

# API 数据源配置文件路径
BACKEND_ROOT = Path(__file__).parent.parent.parent.resolve()
API_SOURCES_CONFIG_PATH = BACKEND_ROOT / "api_sources_config.json"


class ApiSourceConfig:
    """API 数据源配置"""

    def __init__(self) -> None:
        self.sources: List[Dict[str, Any]] = []

    @classmethod
    def load(cls) -> "ApiSourceConfig":
        """从文件加载配置"""
        config = cls()
        if API_SOURCES_CONFIG_PATH.exists():
            try:
                with open(API_SOURCES_CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    config.sources = data.get("sources", [])
            except Exception as e:
                print(f"[API SOURCE] Failed to load config: {e}")
        return config

    def save(self) -> None:
        """保存配置到文件"""
        try:
            API_SOURCES_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(API_SOURCES_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"sources": self.sources}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[API SOURCE] Failed to save config: {e}")
            raise


class SqlServerDataSource:
    """SQL Server 数据源服务"""

    def __init__(self, host: str, user: str, password: str, database: str, port: int | None = None) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database

    def execute_query(self, query: str) -> pd.DataFrame:
        """执行 SQL 查询并返回 DataFrame"""
        try:
            # 使用 SQLAlchemy + pymssql（与测试脚本一致）
            port = self.port or 1433
            database = self.database if self.database else "master"
            
            # 构建连接字符串（与测试脚本格式一致）
            connection_string = f"mssql+pymssql://{self.user}:{self.password}@{self.host}:{port}/{database}?charset=utf8"
            
            print(f"[SQL SERVER] Connecting to {self.host}:{port} as {self.user}...")
            print(f"[SQL SERVER] Database: {database}")
            
            # 使用 SQLAlchemy 创建引擎（与测试脚本一致）
            engine = create_engine(
                connection_string,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
            )
            
            # 执行查询（使用 text() 包装 SQL，然后手动构建 DataFrame）
            from sqlalchemy import text
            with engine.connect() as conn:
                result = conn.execute(text(query))
                # 获取列名
                columns = result.keys()
                # 获取所有行
                rows = result.fetchall()
                # 构建 DataFrame
                df = pd.DataFrame(rows, columns=columns)
            engine.dispose()
            return df
                
        except Exception as e:
            print(f"[SQL SERVER] Query execution failed: {e}")
            print(f"[SQL SERVER] Connection details: host={self.host}, port={self.port or '1433 (default)'}, user={self.user}, database={self.database or 'master'}")
            import traceback
            traceback.print_exc()
            raise

    def fetch_expense_forecasts(self, query: str) -> List[CandidateRecord]:
        """从 SQL Server 查询数据并转换为支出预测记录"""
        df = self.execute_query(query)
        print(f"[SQL SERVER] Query returned {len(df)} rows")
        print(f"[SQL SERVER] Columns: {list(df.columns)}")

        records: List[CandidateRecord] = []
        for idx, row in df.iterrows():
            try:
                # 解析日期字段（查询结果中的 Date 字段）
                date_value = None
                date_fields = ["Date", "date", "DATE", "MaxDate"]
                for field in date_fields:
                    if field in row and pd.notna(row[field]):
                        try:
                            if isinstance(row[field], (datetime, pd.Timestamp)):
                                date_value = row[field].date()
                            elif isinstance(row[field], date):
                                date_value = row[field]
                            elif isinstance(row[field], str):
                                # 尝试解析各种日期格式
                                try:
                                    date_value = datetime.fromisoformat(row[field].replace("Z", "+00:00")).date()
                                except:
                                    date_value = datetime.strptime(row[field].split()[0], "%Y-%m-%d").date()
                            break
                        except Exception as e:
                            print(f"[SQL SERVER] Failed to parse date field {field}: {e}")
                            continue

                # 解析金额字段（新查询返回 cost 字段）
                amount = None
                amount_fields = ["cost", "Cost", "COST", "NetValue", "Amount", "Value", "Balance", "ExpectedAmount", "Net"]
                for field in amount_fields:
                    if field in row and pd.notna(row[field]):
                        try:
                            amount = float(row[field])
                            if amount != 0:  # 跳过金额为0的记录
                                break
                        except (ValueError, TypeError):
                            continue

                if not date_value:
                    print(f"[SQL SERVER] Row {idx} skipped: missing date. Available fields: {list(row.index)}")
                    continue
                
                if amount is None or amount == 0:
                    print(f"[SQL SERVER] Row {idx} skipped: missing or zero amount")
                    continue

                # 构建分类路径（使用 FundName）
                category_parts = []
                if "FundName" in row and pd.notna(row["FundName"]):
                    category_parts.append(str(row["FundName"]).strip())
                if "TemplateName" in row and pd.notna(row["TemplateName"]):
                    category_parts.append(str(row["TemplateName"]).strip())
                
                # 如果没有分类信息，使用默认分类
                if not category_parts:
                    category_parts.append("应付管理人报酬")

                # 构建描述（包含资产编码和名称信息）
                description_parts = []
                if "name" in row and pd.notna(row["name"]):
                    description_parts.append(str(row["name"]).strip())
                if "FlareAssetCode" in row and pd.notna(row["FlareAssetCode"]):
                    description_parts.append(f"资产编码: {row['FlareAssetCode']}")
                
                if not description_parts:
                    description_parts.append("应付管理人报酬")

                payload: Dict[str, Any] = {
                    "cash_out_date": date_value.isoformat(),
                    "expected_amount": amount,
                    "currency": "CNY",
                    "certainty": "certain",
                    "category_path_text": "/".join(category_parts),
                    "category_label": category_parts[0] if category_parts else "应付管理人报酬",
                    "description": " | ".join(description_parts),
                }

                # 添加备注（包含其他有用信息）
                notes_parts = []
                if "FlareAssetCode" in row and pd.notna(row["FlareAssetCode"]):
                    notes_parts.append(f"资产编码: {row['FlareAssetCode']}")
                if notes_parts:
                    payload["notes"] = "；".join(notes_parts)

                records.append(
                    CandidateRecord(
                        record_type=RecordType.EXPENSE_FORECAST,
                        payload=payload,
                        confidence=1.0,  # SQL 查询的数据置信度为 1.0
                        warnings=[],
                    )
                )
            except Exception as e:
                print(f"[SQL SERVER] Failed to convert row {idx} to record: {e}")
                print(f"  Row data: {dict(row)}")
                import traceback
                traceback.print_exc()
                continue

        print(f"[SQL SERVER] Converted {len(records)} records")
        return records

