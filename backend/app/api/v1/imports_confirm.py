from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_import_job_repository
from app.repositories.import_jobs import DuplicateRecordError, ImportJobRepository
from app.schemas.imports import ConfirmationPayload, ConfirmationResult

router = APIRouter(prefix="/api/v1", tags=["imports"])


@router.post(
    "/import-jobs/{job_id}/confirm",
    response_model=ConfirmationResult,
    status_code=status.HTTP_200_OK,
)
def confirm_import_job(
    job_id: str,
    payload: ConfirmationPayload,
    repo: ImportJobRepository = Depends(get_import_job_repository),
) -> ConfirmationResult:
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")

    try:
        approved, rejected, records = repo.apply_confirmation(job, payload.actions)
        repo.session.commit()
    except DuplicateRecordError as exc:
        repo.session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "message": "duplicate_record",
                "recordType": exc.record_type.value,
                "conflict": exc.conflict,
            },
        )

    return ConfirmationResult(approvedCount=approved, rejectedCount=rejected, updatedRecords=records)

