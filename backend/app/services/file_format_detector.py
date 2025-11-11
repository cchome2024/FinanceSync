from __future__ import annotations

from enum import Enum
from pathlib import Path


class FileFormat(str, Enum):
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    UNKNOWN = "unknown"


class FileFormatDetector:
    """检测文件格式"""

    @staticmethod
    def detect(file_path: str | Path) -> FileFormat:
        """根据文件扩展名检测格式"""
        path = Path(file_path) if isinstance(file_path, str) else file_path
        suffix = path.suffix.lower()

        if suffix == ".csv":
            return FileFormat.CSV
        elif suffix in (".xlsx", ".xls"):
            return FileFormat.EXCEL
        elif suffix == ".json":
            return FileFormat.JSON
        else:
            return FileFormat.UNKNOWN

    @staticmethod
    def detect_from_content_type(content_type: str | None) -> FileFormat:
        """根据Content-Type检测格式"""
        if not content_type:
            return FileFormat.UNKNOWN

        content_type_lower = content_type.lower()
        if "csv" in content_type_lower:
            return FileFormat.CSV
        elif "spreadsheet" in content_type_lower or "excel" in content_type_lower:
            return FileFormat.EXCEL
        elif "json" in content_type_lower:
            return FileFormat.JSON
        else:
            return FileFormat.UNKNOWN

