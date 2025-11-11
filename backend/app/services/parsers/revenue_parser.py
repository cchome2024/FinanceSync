from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any, List

import pandas as pd

from app.schemas.imports import CandidateRecord, RecordType
from app.services.file_format_detector import FileFormat


class RevenueParser:
    """解析收入数据文件（Excel格式）"""

    def parse(self, file_bytes: bytes, format: FileFormat) -> List[CandidateRecord]:
        """解析文件并返回候选记录列表"""
        if format == FileFormat.EXCEL:
            return self._parse_excel(file_bytes)
        elif format == FileFormat.CSV:
            return self._parse_csv(file_bytes)
        elif format == FileFormat.JSON:
            return self._parse_json(file_bytes)
        else:
            raise ValueError(f"Unsupported file format: {format}")

    def _parse_excel(self, file_bytes: bytes) -> List[CandidateRecord]:
        """解析Excel文件，读取'总收入' sheet"""
        try:
            # 读取Excel文件
            excel_file = io.BytesIO(file_bytes)
            
            # 尝试读取"总收入"sheet
            try:
                df = pd.read_excel(excel_file, sheet_name="总收入", engine="openpyxl")
            except ValueError:
                # 如果"总收入"sheet不存在，尝试读取第一个sheet
                df = pd.read_excel(excel_file, sheet_name=0, engine="openpyxl")
            
            # 清理数据：删除空行
            df = df.dropna(how="all")
            
            records: List[CandidateRecord] = []
            skipped_count = 0
            skipped_reasons = {
                "no_date": 0,
                "no_amount": 0,
                "zero_amount": 0,
                "parse_error": 0,
            }
            
            # 列名映射（根据图片描述的列）
            # 公司, 发生日期, 收入金额, 款项内容, 对方名称, 到账账户, 大类, 二类, 费用类型, 月份, 收入(万)
            column_mapping = {
                "公司": "company",
                "发生日期": "occurred_on",
                "收入金额": "amount",
                "款项内容": "description",
                "对方名称": "counterparty",
                "到账账户": "account_name",
                "大类": "category_major",
                "二类": "category_minor",
                "费用类型": "fee_type",
                "月份": "month",
                "收入(万)": "amount_wan",
            }
            
            # 尝试匹配列名（支持中英文）
            actual_columns = {}
            for col in df.columns:
                col_str = str(col).strip()
                # 直接匹配
                if col_str in column_mapping:
                    actual_columns[column_mapping[col_str]] = col
                # 模糊匹配
                elif "公司" in col_str:
                    actual_columns["company"] = col
                elif "发生日期" in col_str or "日期" in col_str:
                    actual_columns["occurred_on"] = col
                elif "收入金额" in col_str:
                    actual_columns["amount"] = col
                elif "款项内容" in col_str or "内容" in col_str:
                    actual_columns["description"] = col
                elif "对方名称" in col_str or "对方" in col_str:
                    actual_columns["counterparty"] = col
                elif "到账账户" in col_str or "账户" in col_str:
                    actual_columns["account_name"] = col
                elif "大类" in col_str:
                    actual_columns["category_major"] = col
                elif "二类" in col_str:
                    actual_columns["category_minor"] = col
                elif "费用类型" in col_str or "费用" in col_str:
                    actual_columns["fee_type"] = col
                elif "月份" in col_str:
                    actual_columns["month"] = col
                elif "收入(万)" in col_str or "收入" in col_str:
                    actual_columns["amount_wan"] = col
            
            # 遍历每一行
            for idx, row in df.iterrows():
                try:
                    # 解析发生日期
                    occurred_on = None
                    if "occurred_on" in actual_columns:
                        date_value = row[actual_columns["occurred_on"]]
                        if pd.notna(date_value):
                            if isinstance(date_value, datetime):
                                occurred_on = date_value.date()
                            elif isinstance(date_value, str):
                                # 尝试解析 YYYY/MM/DD 格式
                                try:
                                    occurred_on = datetime.strptime(date_value, "%Y/%m/%d").date()
                                except ValueError:
                                    try:
                                        occurred_on = datetime.strptime(date_value, "%Y-%m-%d").date()
                                    except ValueError:
                                        occurred_on = pd.to_datetime(date_value).date()
                            else:
                                occurred_on = pd.to_datetime(date_value).date()
                    
                    if not occurred_on:
                        skipped_count += 1
                        skipped_reasons["no_date"] += 1
                        print(f"[REVENUE PARSER] Row {idx} skipped: no date")
                        continue  # 跳过没有日期的行
                    
                    # 解析收入金额（优先使用收入金额，如果没有则使用收入(万)*10000）
                    amount = None
                    if "amount" in actual_columns and pd.notna(row[actual_columns["amount"]]):
                        amount_value = row[actual_columns["amount"]]
                        if isinstance(amount_value, (int, float)):
                            amount = float(amount_value)
                    elif "amount_wan" in actual_columns and pd.notna(row[actual_columns["amount_wan"]]):
                        amount_value = row[actual_columns["amount_wan"]]
                        if isinstance(amount_value, (int, float)):
                            amount = float(amount_value) * 10000  # 万元转元
                    
                    if not amount:
                        skipped_count += 1
                        skipped_reasons["no_amount"] += 1
                        print(f"[REVENUE PARSER] Row {idx} skipped: no amount")
                        continue  # 跳过没有金额的行
                    
                    # 允许负数金额（可能是退款、冲正等情况）
                    if amount == 0:
                        skipped_count += 1
                        skipped_reasons["zero_amount"] += 1
                        print(f"[REVENUE PARSER] Row {idx} skipped: zero amount")
                        continue  # 只跳过金额为0的行
                    
                    # 构建payload
                    payload: dict[str, Any] = {
                        "occurred_on": occurred_on.isoformat(),
                        "amount": amount,
                        "currency": "CNY",
                    }
                    
                    # 添加可选字段
                    if "description" in actual_columns and pd.notna(row[actual_columns["description"]]):
                        payload["description"] = str(row[actual_columns["description"]]).strip()
                    
                    if "account_name" in actual_columns and pd.notna(row[actual_columns["account_name"]]):
                        payload["account_name"] = str(row[actual_columns["account_name"]]).strip()
                    
                    if "category_major" in actual_columns and pd.notna(row[actual_columns["category_major"]]):
                        payload["category_label"] = str(row[actual_columns["category_major"]]).strip()
                    
                    if "category_minor" in actual_columns and pd.notna(row[actual_columns["category_minor"]]):
                        payload["subcategory_label"] = str(row[actual_columns["category_minor"]]).strip()
                    
                    # 构建分类路径（包含三级分类：费用类型）
                    category_parts = []
                    if "category_major" in actual_columns and pd.notna(row[actual_columns["category_major"]]):
                        category_parts.append(str(row[actual_columns["category_major"]]).strip())
                    if "category_minor" in actual_columns and pd.notna(row[actual_columns["category_minor"]]):
                        category_parts.append(str(row[actual_columns["category_minor"]]).strip())
                    # 费用类型作为三级分类
                    if "fee_type" in actual_columns and pd.notna(row[actual_columns["fee_type"]]):
                        category_parts.append(str(row[actual_columns["fee_type"]]).strip())
                    if category_parts:
                        payload["category_path_text"] = "/".join(category_parts)
                    
                    # 添加备注信息（对方名称）
                    notes_parts = []
                    if "counterparty" in actual_columns and pd.notna(row[actual_columns["counterparty"]]):
                        notes_parts.append(f"对方：{str(row[actual_columns['counterparty']]).strip()}")
                    if notes_parts:
                        payload["notes"] = "；".join(notes_parts)
                    
                    records.append(
                        CandidateRecord(
                            record_type=RecordType.REVENUE,
                            payload=payload,
                            confidence=1.0,  # Excel文件解析置信度高
                            warnings=[],
                        )
                    )
                except Exception as e:
                    # 跳过解析失败的行，记录警告
                    skipped_count += 1
                    skipped_reasons["parse_error"] += 1
                    print(f"[REVENUE PARSER] Failed to parse row {idx}: {e}")
                    import traceback
                    print(f"[REVENUE PARSER] Traceback: {traceback.format_exc()}")
                    continue
            
            total_rows = len(df)
            print(f"[REVENUE PARSER] Parsing summary: {total_rows} total rows, {len(records)} records created, {skipped_count} rows skipped")
            print(f"[REVENUE PARSER] Skip reasons: {skipped_reasons}")
            
            return records
            
        except Exception as e:
            raise ValueError(f"Failed to parse Excel file: {e}") from e

    def _parse_csv(self, file_bytes: bytes) -> List[CandidateRecord]:
        """解析CSV文件"""
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8-sig")
            # CSV格式与Excel类似，可以复用解析逻辑
            # 这里简化处理，实际可以根据CSV格式调整
            return self._parse_dataframe(df)
        except Exception as e:
            raise ValueError(f"Failed to parse CSV file: {e}") from e

    def _parse_json(self, file_bytes: bytes) -> List[CandidateRecord]:
        """解析JSON文件"""
        import json
        
        try:
            data = json.loads(file_bytes.decode("utf-8"))
            records: List[CandidateRecord] = []
            
            # 假设JSON是数组格式
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        records.append(
                            CandidateRecord(
                                record_type=RecordType.REVENUE,
                                payload=item,
                                confidence=1.0,
                                warnings=[],
                            )
                        )
            
            return records
        except Exception as e:
            raise ValueError(f"Failed to parse JSON file: {e}") from e

    def _parse_dataframe(self, df: pd.DataFrame) -> List[CandidateRecord]:
        """从DataFrame解析数据（CSV复用）"""
        # 与Excel解析类似的逻辑
        records: List[CandidateRecord] = []
        # 实现类似_excel的逻辑
        return records

