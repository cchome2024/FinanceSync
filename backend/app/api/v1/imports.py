from __future__ import annotations

import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from sqlalchemy.orm import Session

from app.api.deps import get_ai_parser, get_db_session, get_import_job_repository, get_storage_adapter
from app.models.financial import ImportSource, ImportStatus, IncomeForecast, RevenueDetail
from app.repositories.import_jobs import ImportJobRepository
from app.schemas.imports import ImportJobDetail, ParseJobResponse
from app.services.ai_parser import AIParserService
from app.services.file_format_detector import FileFormat, FileFormatDetector
from app.services.parsers.revenue_parser import RevenueParser
from app.services.llm_client import LLMClientError, LLMClientParseError
from app.services.storage_adapter import StorageAdapter

router = APIRouter(prefix="/api/v1", tags=["imports"])

# 配置文件路径存储位置（使用绝对路径，存储在backend目录）
# 从 app/api/v1/imports.py 向上三级到 backend 目录
BACKEND_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
CONFIG_FILE_PATH = BACKEND_ROOT / "file_import_config.json"


class FileImportConfig(BaseModel):
    """文件导入配置"""
    watch_path: str = ""


class FileImportConfigResponse(BaseModel):
    """文件导入配置响应"""
    watch_path: str
    path_exists: bool
    file_count: int = 0


def load_config() -> FileImportConfig:
    """加载配置"""
    if CONFIG_FILE_PATH.exists():
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return FileImportConfig(**data)
        except Exception as e:
            print(f"[CONFIG] Failed to load config: {e}")
    return FileImportConfig()


def save_config(config: FileImportConfig) -> None:
    """保存配置"""
    try:
        # 确保目录存在
        CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        # 保存配置
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)
        print(f"[CONFIG] Saved config to {CONFIG_FILE_PATH}: watch_path={config.watch_path}")
    except Exception as e:
        print(f"[CONFIG] Failed to save config to {CONFIG_FILE_PATH}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save config: {str(e)}") from e


@router.post(
    "/parse/upload",
    response_model=ParseJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def parse_upload(
    prompt: str = Form(...),
    company_id: str | None = Form(None),
    file: UploadFile | None = File(None),
    repo: ImportJobRepository = Depends(get_import_job_repository),
    parser: AIParserService = Depends(get_ai_parser),
    storage: StorageAdapter = Depends(get_storage_adapter),
) -> ParseJobResponse:
    job = repo.create_job(
        source_type=ImportSource.AI_CHAT,
        initiator_id=None,
        initiator_role="finance_user",
    )
    print(f"[IMPORT] created job {job.id}")

    attachments_bytes = []
    if file is not None:
        data = await file.read()
        attachments_bytes.append(data)
        stored_path = await storage.save(file.filename or f"{job.id}.upload", data)
        repo.add_attachment(
            job,
            file_type=file.content_type or "application/octet-stream",
            storage_path=stored_path,
        )
        print(f"[IMPORT] stored attachment path={stored_path}")

    try:
        preview, raw = await parser.parse_prompt(prompt, attachments_bytes)
    except LLMClientParseError as exc:
        job.status = ImportStatus.FAILED
        repo.session.add(job)
        repo.session.commit()
        return ParseJobResponse(
            jobId=job.id,
            status=job.status.value,
            preview=[],
            rawResponse={"rawText": exc.raw_text, "error": str(exc)},
        )
    except LLMClientError as exc:
        repo.session.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    print(f"[IMPORT] parser returned {len(preview)} candidate(s)")
    if company_id:
        for record in preview:
            record.payload.setdefault("company_id", company_id)

    repo.save_preview(job, preview)
    print(f"[IMPORT] preview persisted for job {job.id}")
    repo.session.commit()
    print(f"[IMPORT] job {job.id} committed")

    return ParseJobResponse(
        jobId=job.id,
        status=job.status.value,
        preview=preview,
        rawResponse=raw,
    )


@router.post(
    "/parse/file",
    response_model=ParseJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def parse_file_upload(
    files: List[UploadFile] = File(..., description="Files to parse"),
    repo: ImportJobRepository = Depends(get_import_job_repository),
    storage: StorageAdapter = Depends(get_storage_adapter),
) -> ParseJobResponse:
    """解析上传的文件（Excel、CSV、JSON格式）"""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    job = repo.create_job(
        source_type=ImportSource.MANUAL_UPLOAD,
        initiator_id=None,
        initiator_role="finance_user",
    )
    print(f"[IMPORT] created file import job {job.id}")

    all_preview: list = []
    detector = FileFormatDetector()
    parser = RevenueParser()

    for file in files:
        try:
            data = await file.read()
            stored_path = await storage.save(file.filename or f"{job.id}_{file.filename}", data)
            repo.add_attachment(
                job,
                file_type=file.content_type or "application/octet-stream",
                storage_path=stored_path,
            )
            print(f"[IMPORT] stored file path={stored_path}")

            # 检测文件格式
            file_format = detector.detect_from_content_type(file.content_type)
            if file_format == FileFormat.UNKNOWN:
                file_format = detector.detect(file.filename or "")

            if file_format == FileFormat.UNKNOWN:
                raise HTTPException(status_code=400, detail=f"Unsupported file format: {file.filename}")

            # 解析文件
            try:
                file_preview = parser.parse(data, file_format)
                all_preview.extend(file_preview)
                print(f"[IMPORT] parsed {file.filename}, got {len(file_preview)} records")
            except Exception as e:
                print(f"[IMPORT] failed to parse {file.filename}: {e}")
                raise HTTPException(status_code=400, detail=f"Failed to parse file {file.filename}: {str(e)}") from e

        except HTTPException:
            raise
        except Exception as e:
            print(f"[IMPORT] error processing file {file.filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing file {file.filename}: {str(e)}") from e

    repo.save_preview(job, all_preview)
    print(f"[IMPORT] preview persisted for job {job.id}, total {len(all_preview)} records")
    repo.session.commit()
    print(f"[IMPORT] job {job.id} committed")

    return ParseJobResponse(
        jobId=job.id,
        status=job.status.value,
        preview=all_preview,
        rawResponse={"files_processed": len(files), "records_count": len(all_preview)},
    )


@router.delete("/revenue-details", status_code=status.HTTP_200_OK)
def clear_revenue_details(
    session: Session = Depends(get_db_session),
) -> dict[str, int]:
    """清空所有收入明细记录"""
    try:
        count = session.query(RevenueDetail).delete()
        session.commit()
        print(f"[IMPORT] Cleared {count} revenue detail records")
        return {"deleted_count": count}
    except Exception as e:
        session.rollback()
        print(f"[IMPORT] Failed to clear revenue details: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear revenue details: {str(e)}") from e


@router.delete("/income-forecasts", status_code=status.HTTP_200_OK)
def clear_income_forecasts(
    session: Session = Depends(get_db_session),
) -> dict[str, int]:
    """清空所有预测收入记录"""
    try:
        count = session.query(IncomeForecast).delete()
        session.commit()
        print(f"[IMPORT] Cleared {count} income forecast records")
        return {"deleted_count": count}
    except Exception as e:
        session.rollback()
        print(f"[IMPORT] Failed to clear income forecasts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear income forecasts: {str(e)}") from e


@router.get("/file-import/config", response_model=FileImportConfigResponse)
def get_file_import_config() -> FileImportConfigResponse:
    """获取文件导入配置"""
    config = load_config()
    print(f"[CONFIG] Loading config from {CONFIG_FILE_PATH}, exists: {CONFIG_FILE_PATH.exists()}")
    print(f"[CONFIG] Loaded config: watch_path={config.watch_path}")
    
    watch_path = Path(config.watch_path) if config.watch_path else None
    
    path_exists = watch_path.exists() if watch_path else False
    file_count = 0
    
    if path_exists:
        if watch_path.is_file():
            # 如果是文件，检查是否是支持的Excel格式
            supported_extensions = {".xlsx", ".xls"}
            if watch_path.suffix.lower() in supported_extensions:
                file_count = 1
        elif watch_path.is_dir():
            # 如果是目录，统计支持的Excel文件数量
            supported_extensions = {".xlsx", ".xls"}
            file_count = sum(
                1 for f in watch_path.iterdir()
                if f.is_file() and f.suffix.lower() in supported_extensions
            )
    
    print(f"[CONFIG] Returning config: path_exists={path_exists}, file_count={file_count}")
    return FileImportConfigResponse(
        watch_path=config.watch_path,
        path_exists=path_exists,
        file_count=file_count,
    )


@router.post("/file-import/config", response_model=FileImportConfigResponse)
def set_file_import_config(config: FileImportConfig) -> FileImportConfigResponse:
    """设置文件导入配置（支持文件路径或目录路径）"""
    if config.watch_path:
        watch_path = Path(config.watch_path)
        if not watch_path.exists():
            raise HTTPException(status_code=400, detail=f"路径不存在: {config.watch_path}")
        if watch_path.is_file():
            # 如果是文件，检查是否是支持的Excel格式
            supported_extensions = {".xlsx", ".xls"}
            if watch_path.suffix.lower() not in supported_extensions:
                raise HTTPException(status_code=400, detail=f"不支持的文件格式: {config.watch_path}。请使用 .xlsx 或 .xls 文件")
            print(f"[CONFIG] 配置为文件路径: {watch_path}")
        elif watch_path.is_dir():
            print(f"[CONFIG] 配置为目录路径: {watch_path}")
        else:
            raise HTTPException(status_code=400, detail=f"路径无效: {config.watch_path}。请输入文件路径或目录路径")
    
    save_config(config)
    
    # 返回更新后的配置
    return get_file_import_config()


@router.post(
    "/file-import/scan",
    response_model=ParseJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def scan_file_import_path(
    repo: ImportJobRepository = Depends(get_import_job_repository),
    storage: StorageAdapter = Depends(get_storage_adapter),
) -> ParseJobResponse:
    """扫描配置的文件路径并解析文件（支持文件路径或目录路径）"""
    config = load_config()
    if not config.watch_path:
        raise HTTPException(status_code=400, detail="未配置文件路径")
    
    watch_path = Path(config.watch_path)
    if not watch_path.exists():
        raise HTTPException(status_code=400, detail=f"路径不存在: {config.watch_path}")
    
    # 确定要处理的文件列表
    supported_extensions = {".xlsx", ".xls"}
    if watch_path.is_file():
        # 如果是文件，直接使用该文件
        if watch_path.suffix.lower() not in supported_extensions:
            raise HTTPException(status_code=400, detail=f"不支持的文件格式: {config.watch_path}。请使用 .xlsx 或 .xls 文件")
        files = [watch_path]
        print(f"[FILE IMPORT] Processing single file: {watch_path}")
    elif watch_path.is_dir():
        # 如果是目录，查找所有支持的Excel文件
        files = [f for f in watch_path.iterdir() if f.is_file() and f.suffix.lower() in supported_extensions]
        if not files:
            raise HTTPException(status_code=404, detail=f"目录中没有找到支持的Excel文件: {config.watch_path}")
        print(f"[FILE IMPORT] Scanning directory {watch_path}, found {len(files)} files")
    else:
        raise HTTPException(status_code=400, detail=f"路径无效: {config.watch_path}")
    
    job = repo.create_job(
        source_type=ImportSource.MANUAL_UPLOAD,
        initiator_id=None,
        initiator_role="finance_user",
    )
    print(f"[IMPORT] created file scan job {job.id}")
    
    all_preview: list = []
    detector = FileFormatDetector()
    parser = RevenueParser()
    
    for file_path in files:
        try:
            file_name = file_path.name
            print(f"[FILE IMPORT] Processing file: {file_name}")
            
            # 读取文件内容
            data = file_path.read_bytes()
            
            # 保存到存储
            stored_path = await storage.save(f"{job.id}_{file_name}", data)
            repo.add_attachment(
                job,
                file_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                storage_path=stored_path,
            )
            print(f"[IMPORT] stored file path={stored_path}")
            
            # 检测文件格式
            file_format = detector.detect(file_name)
            if file_format == FileFormat.UNKNOWN:
                raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_name}")
            
            # 解析文件
            try:
                file_preview = parser.parse(data, file_format)
                all_preview.extend(file_preview)
                print(f"[IMPORT] parsed {file_name}, got {len(file_preview)} records")
            except Exception as e:
                print(f"[IMPORT] failed to parse {file_name}: {e}")
                raise HTTPException(status_code=400, detail=f"Failed to parse file {file_name}: {str(e)}") from e
        
        except HTTPException:
            raise
        except Exception as e:
            print(f"[IMPORT] error processing file {file_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing file {file_path}: {str(e)}") from e
    
    repo.save_preview(job, all_preview)
    print(f"[IMPORT] preview persisted for job {job.id}, total {len(all_preview)} records")
    repo.session.commit()
    print(f"[IMPORT] job {job.id} committed")
    
    return ParseJobResponse(
        jobId=job.id,
        status=job.status.value,
        preview=all_preview,
        rawResponse={"files_processed": len(files), "records_count": len(all_preview)},
    )


@router.get("/import-jobs/{job_id}", response_model=ImportJobDetail)
def get_import_job(job_id: str, repo: ImportJobRepository = Depends(get_import_job_repository)) -> ImportJobDetail:
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")

    preview = repo.load_preview(job)
    attachments = [
        {"id": attachment.id, "fileType": attachment.file_type, "storagePath": attachment.storage_path}
        for attachment in job.attachments
    ]

    return ImportJobDetail(
        jobId=job.id,
        status=job.status.value,
        sourceType=job.source_type.value,
        attachments=attachments,
        preview=preview,
    )

