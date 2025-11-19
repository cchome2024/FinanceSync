from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_import_job_repository, require_permission
from app.core.config import get_settings
from app.core.permissions import Permission
from app.models.financial import Certainty, Company, ImportSource, ImportStatus, IncomeForecast, User
from app.repositories.import_jobs import ImportJobRepository
from app.schemas.imports import CandidateRecord, ParseJobResponse
from app.services.api_source import ApiSourceConfig, SqlServerDataSource
from app.services.category_service import FinanceCategoryService

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

SELECT B.FlareAssetCode,A.FundName,A.[Date],a.name,a.cost

FROM    [FA-ODS].dbo.Original_FundNetChild A WITH(NOLOCK)

left JOIN [FA-ODS].dbo.AssetMappingTable B 

ON B.OriginAssetCode = A.Code

INNER  JOIN tmp_data_relation C

ON C.PMID = A.PMID

AND C.TemplateID = B.TemplateID

INNER  JOIN max_pmid_date D

ON a.PMID=D.pmid

AND  A.Date=D.MaxDate

WHERE b.FlareAssetCode IN(2241,220601,220602,221001,221002) --应付管理人报酬的编码

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
            
            # 先执行原始查询获取数据
            df = data_source.execute_query(SQLSERVER_EXPENSE_QUERY)
            print(f"[API SOURCE] Fetched {len(df)} rows from SQL Server")
            
            # 将DataFrame转换为字典列表，用于返回原始数据
            # 处理日期字段，确保可以JSON序列化
            import pandas as pd
            df_copy = df.copy()
            for col in df_copy.columns:
                # 只处理日期相关的列，避免误处理其他字段（如资产编码）
                if 'date' in col.lower() or 'Date' in col:
                    if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
                        df_copy[col] = df_copy[col].dt.strftime('%Y-%m-%d')
                    elif pd.api.types.is_object_dtype(df_copy[col]):
                        # 尝试转换datetime对象
                        try:
                            df_copy[col] = pd.to_datetime(df_copy[col], errors='ignore').dt.strftime('%Y-%m-%d')
                        except:
                            pass
            
            raw_data = df_copy.to_dict(orient='records')
            
            # 转换为支出预测记录
            records = data_source.fetch_expense_forecasts(SQLSERVER_EXPENSE_QUERY)
            print(f"[API SOURCE] Converted {len(records)} records from SQL Server")
            
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
                rawResponse={
                    "source": "sqlserver",
                    "records_count": len(records),
                    "raw_data": raw_data,  # 添加原始查询结果
                },
            )
        except Exception as e:
            job.status = ImportStatus.FAILED
            repo.session.add(job)
            repo.session.commit()
            print(f"[API SOURCE] Failed to fetch data: {e}")
            
            # 检查是否是连接错误
            error_str = str(e).lower()
            if 'connection refused' in error_str or 'unable to connect' in error_str or 'unavailable' in error_str:
                error_detail = (
                    f"无法连接到 SQL Server 数据库 ({settings.sqlserver_host}:{settings.sqlserver_port or 1433})。\n"
                    f"请检查：\n"
                    f"1. SQL Server 服务是否正在运行\n"
                    f"2. 网络连接是否正常\n"
                    f"3. 防火墙是否允许连接\n"
                    f"4. 服务器地址和端口是否正确\n"
                    f"原始错误: {str(e)}"
                )
            elif 'login failed' in error_str or 'authentication' in error_str:
                error_detail = (
                    f"SQL Server 认证失败。\n"
                    f"请检查用户名和密码是否正确。\n"
                    f"原始错误: {str(e)}"
                )
            else:
                error_detail = f"从 SQL Server 获取数据失败: {str(e)}"
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_detail
            ) from e
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API source not found: {source_id}"
        )


class ApiSourceConfirmRequest(BaseModel):
    """API数据源确认入库请求"""
    data: List[Dict[str, Any]]  # 编辑后的数据列表


class ApiSourceConfirmResponse(BaseModel):
    """API数据源确认入库响应"""
    deleted_count: int
    imported_count: int


@router.post(
    "/api-sources/{source_id}/confirm",
    response_model=ApiSourceConfirmResponse,
    status_code=status.HTTP_200_OK,
)
def confirm_api_source(
    source_id: str,
    payload: ApiSourceConfirmRequest,
    user: User = Depends(require_permission(Permission.DATA_IMPORT)),
    session: Session = Depends(get_db_session),
) -> ApiSourceConfirmResponse:
    """确认API数据源入库：删除所有一级分类为'资产管理'的预计收入数据，然后导入新数据"""
    if source_id != "sqlserver-expense-forecast":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API source not found: {source_id}"
        )
    
    try:
        # 1. 删除所有一级分类为"资产管理"的预计收入数据
        deleted_count = session.query(IncomeForecast).filter(
            IncomeForecast.category_path_text.like('资产管理%')
        ).delete(synchronize_session=False)
        session.commit()
        print(f"[API SOURCE] Deleted {deleted_count} income forecasts with category '资产管理'")
        
        # 2. 获取或创建公司
        company = session.query(Company).filter(Company.name == "company-unknown").first()
        if not company:
            company = Company(name="company-unknown", display_name="未知公司")
            session.add(company)
            session.flush()
        
        # 3. 获取分类服务
        category_service = FinanceCategoryService(session)
        
        # 4. 创建导入任务
        repo = ImportJobRepository(session)
        job = repo.create_job(
            source_type=ImportSource.API_SYNC,
            user_id=user.id,
            initiator_id=user.id,
            initiator_role=user.role.value,
        )
        
        # 5. 导入预计收入非0的数据
        imported_count = 0
        for item in payload.data:
            # 只导入预计收入非0的数据
            expected_amount = item.get('expectedAmount') or item.get('expected_amount') or 0
            if expected_amount == 0 or expected_amount is None:
                continue
            
            # 解析日期
            date_str = item.get('Date') or item.get('date')
            if not date_str:
                continue
            
            try:
                if isinstance(date_str, str):
                    # 尝试多种日期格式
                    try:
                        cash_in_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
                    except:
                        try:
                            cash_in_date = datetime.strptime(date_str.split()[0], '%Y-%m-%d').date()
                        except:
                            cash_in_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                elif isinstance(date_str, date):
                    cash_in_date = date_str
                elif isinstance(date_str, datetime):
                    cash_in_date = date_str.date()
                else:
                    continue
            except Exception as e:
                print(f"[API SOURCE] Failed to parse date: {date_str}, error: {e}")
                continue
            
            # 构建分类路径
            category_path_parts = []
            if item.get('categoryLevel1'):
                category_path_parts.append(str(item['categoryLevel1']))
            if item.get('categoryLevel2'):
                category_path_parts.append(str(item['categoryLevel2']))
            if item.get('categoryLevel3'):
                category_path_parts.append(str(item['categoryLevel3']))
            if item.get('categoryLevel4'):
                category_path_parts.append(str(item['categoryLevel4']))
            
            category_path_text = '/'.join(category_path_parts) if category_path_parts else None
            
            # 获取或创建分类ID
            category_id = None
            if category_path_parts:
                from app.models.financial import CategoryType
                category = category_service.get_or_create(
                    names=category_path_parts,
                    category_type=CategoryType.FORECAST
                )
                if category:
                    category_id = category.id
            
            # 确定certainty
            income_status = item.get('incomeStatus') or ''
            certainty = Certainty.UNCERTAIN if income_status == '未确认' else Certainty.CERTAIN
            
            # 创建收入预测记录
            forecast = IncomeForecast(
                company_id=company.id,
                import_job_id=job.id,
                category_id=category_id,
                cash_in_date=cash_in_date,
                product_name=item.get('categoryLevel4') or item.get('FundName'),
                certainty=certainty,
                category=item.get('categoryLevel2'),
                category_path_text=category_path_text,
                category_label=item.get('categoryLevel2'),
                subcategory_label=item.get('categoryLevel3'),
                description=item.get('name') or item.get('description'),
                account_name=None,
                expected_amount=float(expected_amount),
                currency="CNY",
                confidence=1.0,
                notes=f"资产编码: {item.get('FlareAssetCode', '')}" if item.get('FlareAssetCode') else None,
            )
            session.add(forecast)
            imported_count += 1
        
        session.commit()
        print(f"[API SOURCE] Imported {imported_count} income forecasts")
        
        return ApiSourceConfirmResponse(
            deleted_count=deleted_count,
            imported_count=imported_count,
        )
    except Exception as e:
        session.rollback()
        print(f"[API SOURCE] Failed to confirm import: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to confirm import: {str(e)}"
        ) from e

