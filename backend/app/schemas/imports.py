from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field


class RecordType(str, Enum):
    ACCOUNT_BALANCE = "account_balance"
    REVENUE = "revenue"
    EXPENSE = "expense"
    INCOME_FORECAST = "income_forecast"
    EXPENSE_FORECAST = "expense_forecast"
    REVENUE_FORECAST = "revenue_forecast"


class CandidateRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=lambda s: "".join(
        [s.split("_")[0]] + [word.capitalize() for word in s.split("_")[1:]]
    ))

    record_type: RecordType = Field(alias="recordType")
    payload: Dict[str, Any]
    confidence: Optional[float] = None
    warnings: List[str] = Field(default_factory=list)


class ParseJobResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    job_id: str = Field(alias="jobId")
    status: str
    preview: List[CandidateRecord] = Field(default_factory=list)
    raw_response: Any | None = Field(alias="rawResponse", default=None)


class AttachmentInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    file_type: str = Field(alias="fileType")
    storage_path: str = Field(alias="storagePath")


class ImportJobDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    job_id: str = Field(alias="jobId")
    status: str
    source_type: str = Field(alias="sourceType")
    attachments: List[AttachmentInfo] = Field(default_factory=list)
    preview: List[CandidateRecord] = Field(default_factory=list)


class ConfirmationOperation(str, Enum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


class ConfirmationAction(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    record_id: Optional[str] = Field(alias="recordId", default=None)
    record_type: RecordType = Field(alias="recordType")
    operation: ConfirmationOperation
    payload: Optional[Dict[str, Any]] = None
    comment: Optional[str] = None
    overwrite: bool = False


class ConfirmationPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    actions: Sequence[ConfirmationAction]


class ConfirmationResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    approved_count: int = Field(alias="approvedCount")
    rejected_count: int = Field(alias="rejectedCount")
    updated_records: List[CandidateRecord] = Field(alias="updatedRecords", default_factory=list)

