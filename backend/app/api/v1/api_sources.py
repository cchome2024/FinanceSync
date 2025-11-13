from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_db_session, get_import_job_repository, require_permission
from app.core.config import get_settings
from app.core.permissions import Permission
from app.models.financial import ImportSource, ImportStatus, User
from app.repositories.import_jobs import ImportJobRepository
from app.schemas.imports import CandidateRecord, ParseJobResponse
from app.services.api_source import ApiSourceConfig, SqlServerDataSource

router = APIRouter(prefix="/api/v1", tags=["api-sources"])

# SQL Server 查询语句（应付管理人报酬）
SQLSERVER_EXPENSE_QUERY = """
WITH tmp_data_relation AS (
SELECT a.PMID, b.FundName,a.TemplateID,c.TemplateName
 FROM [Flare-Base].dbo.UserDefaultTemplate a WITH(NOLOCK)
 LEFT JOIN [Flare-Fund].dbo.IMPMFundInfo b WITH(NOLOCK) ON a.PMID =b.PMID
 LEFT JOIN [FA-ODS]..FormatMapping c WITH(NOLOCK) ON a.TemplateID = c.TemplateID
 WHERE a.PMID != -1 AND a.UserID = 'df6b61cf-c409-4a59-bb9b-82012bf78d3b'
 AND  b.ClearFlag=3 --1:''已清盘'',2:''清盘中'',3:''运作中'',4:''测试中'' 默认''运作中
)
, max_pmid_date AS  (
SELECT A.PMID,MAX(A.Date) AS MaxDate FROM  [FA-ODS].dbo.Original_FundNetChild A WITH(NOLOCK) 
GROUP  BY A.PMID --每个母基金下最新一期的估值表
)
SELECT B.FlareAssetCode,B.TemplateID,C.TemplateName,A.*
FROM    [FA-ODS].dbo.Original_FundNetChild A WITH(NOLOCK)
left JOIN [FA-ODS].dbo.AssetMappingTable B 
ON B.OriginAssetCode = A.Code
INNER  JOIN tmp_data_relation C
ON C.PMID = A.PMID
AND C.TemplateID = B.TemplateID
INNER  JOIN max_pmid_date D
ON a.PMID=D.pmid
AND  A.Date=D.MaxDate
WHERE b.FlareAssetCode IN(2206,220601,220602) --应付管理人报酬的编码
ORDER  BY A.PMID,A.Date DESC
"""


class ApiSourceResponse(BaseModel):
    """API 数据源响应"""
    id: str
    name: str
    apiType: str
    enabled: bool
    lastRunAt: str | None = None
    schedule: str | None = None


class ApiSourceTriggerResponse(BaseModel):
    """API 数据源触发响应"""
    jobId: str
    status: str
    preview: List[CandidateRecord]
    rawResponse: Dict[str, Any] | None = None


def get_api_source_config() -> ApiSourceConfig:
    """获取 API 数据源配置"""
    return ApiSourceConfig.load()


@router.get("/api-sources", response_model=List[ApiSourceResponse])
def list_api_sources(
    user: User = Depends(require_permission(Permission.DATA_VIEW)),
    config: ApiSourceConfig = Depends(get_api_source_config),
) -> List[ApiSourceResponse]:
    """列举所有 API 数据源"""
    settings = get_settings()
    
    # 如果配置了 SQL Server，自动创建一个数据源
    sources = []
    if settings.sqlserver_host and settings.sqlserver_user and settings.sqlserver_password:
        # 从配置文件读取最后运行时间
        last_run_at = None
        for config_source in config.sources:
            if config_source.get("id") == "sqlserver-expense-forecast":
                last_run_at = config_source.get("lastRunAt")
                break
        
        sources.append({
            "id": "sqlserver-expense-forecast",
            "name": "SQL Server - 应付管理人报酬",
            "apiType": "sqlserver",
            "enabled": True,
            "lastRunAt": last_run_at,
            "schedule": None,
        })
    
    # 合并配置文件中的其他数据源（排除已添加的 SQL Server 数据源）
    for config_source in config.sources:
        if config_source.get("id") != "sqlserver-expense-forecast":
            sources.append(config_source)
    
    return [
        ApiSourceResponse(
            id=source["id"],
            name=source["name"],
            apiType=source.get("apiType", "unknown"),
            enabled=source.get("enabled", True),
            lastRunAt=source.get("lastRunAt"),
            schedule=source.get("schedule"),
        )
        for source in sources
    ]


@router.post(
    "/api-sources/{source_id}/trigger",
    response_model=ApiSourceTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_api_source(
    source_id: str,
    user: User = Depends(require_permission(Permission.DATA_IMPORT)),
    repo: ImportJobRepository = Depends(get_import_job_repository),
    config: ApiSourceConfig = Depends(get_api_source_config),
) -> ApiSourceTriggerResponse:
    """触发 API 数据源同步"""
    settings = get_settings()
    
    # 检查是否是 SQL Server 数据源
    if source_id == "sqlserver-expense-forecast":
        if not settings.sqlserver_host or not settings.sqlserver_user or not settings.sqlserver_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SQL Server 配置未完成，请在 .env 文件中配置 SQLSERVER_HOST, SQLSERVER_USER, SQLSERVER_PASSWORD"
            )
        
        # 创建导入任务
        job = repo.create_job(
            source_type=ImportSource.API_SYNC,
            user_id=user.id,
            initiator_id=user.id,
            initiator_role=user.role.value,
        )
        print(f"[API SOURCE] Created job {job.id} for SQL Server data source")
        
        try:
            # 连接 SQL Server 并查询数据
            data_source = SqlServerDataSource(
                host=settings.sqlserver_host,
                user=settings.sqlserver_user,
                password=settings.sqlserver_password,
                database=settings.sqlserver_database or "",
                port=settings.sqlserver_port,
            )
            
            records = data_source.fetch_expense_forecasts(SQLSERVER_EXPENSE_QUERY)
            print(f"[API SOURCE] Fetched {len(records)} records from SQL Server")
            
            # 保存预览
            repo.save_preview(job, records)
            repo.session.commit()
            
            # 更新配置中的最后运行时间
            config = ApiSourceConfig.load()
            for source in config.sources:
                if source["id"] == source_id:
                    source["lastRunAt"] = datetime.now().isoformat()
                    break
            else:
                # 如果配置中没有，添加一个
                config.sources.append({
                    "id": source_id,
                    "name": "SQL Server - 应付管理人报酬",
                    "apiType": "sqlserver",
                    "enabled": True,
                    "lastRunAt": datetime.now().isoformat(),
                    "schedule": None,
                })
            config.save()
            
            return ApiSourceTriggerResponse(
                jobId=job.id,
                status=job.status.value,
                preview=records,
                rawResponse={"source": "sqlserver", "records_count": len(records)},
            )
        except Exception as e:
            job.status = ImportStatus.FAILED
            repo.session.add(job)
            repo.session.commit()
            print(f"[API SOURCE] Failed to fetch data: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch data from SQL Server: {str(e)}"
            ) from e
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API source not found: {source_id}"
        )

