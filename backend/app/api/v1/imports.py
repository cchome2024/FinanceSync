from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.deps import get_ai_parser, get_import_job_repository, get_storage_adapter
from app.models.financial import ImportSource, ImportStatus
from app.repositories.import_jobs import ImportJobRepository
from app.schemas.imports import ImportJobDetail, ParseJobResponse
from app.services.ai_parser import AIParserService
from app.services.llm_client import LLMClientError, LLMClientParseError
from app.services.storage_adapter import StorageAdapter

router = APIRouter(prefix="/api/v1", tags=["imports"])


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

