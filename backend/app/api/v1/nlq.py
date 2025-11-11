from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import get_nlq_service, require_permission
from app.core.permissions import Permission
from app.models.financial import User
from app.schemas.nlq import NlqRequest, NlqResponse
from app.services.nlq_service import NLQService

router = APIRouter(prefix="/api/v1", tags=["nlq"])


@router.post("/query", response_model=NlqResponse, status_code=status.HTTP_200_OK)
async def run_nlq_query(
    payload: NlqRequest,
    user: User = Depends(require_permission(Permission.NLQ_QUERY)),
    service: NLQService = Depends(get_nlq_service),
) -> NlqResponse:
    return await service.run_query(payload.question)



