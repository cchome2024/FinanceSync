from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any, Dict, Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.financial import (
    AccountBalance,
    Attachment,
    Certainty,
    ConfirmationLog,
    ExpenseRecord,
    ImportJob,
    ImportSource,
    ImportStatus,
    IncomeForecast,
    RevenueRecord,
    Company,
    CategoryType,
)
from app.schemas.imports import CandidateRecord, ConfirmationAction, ConfirmationOperation, RecordType
from app.services.category_service import FinanceCategoryService


class DuplicateRecordError(RuntimeError):
    """Raised when a record already exists and overwrite was not permitted."""

    def __init__(self, record_type: RecordType, conflict: Dict[str, Any]):
        self.record_type = record_type
        self.conflict = conflict
        super().__init__("Duplicate record detected")


class ImportJobRepository:
    """数据导入任务相关的持久层封装。"""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._category_service = FinanceCategoryService(session)

    @property
    def session(self) -> Session:
        return self._session

    # ------------------------------------------------------------------ #
    # Import job lifecycle
    # ------------------------------------------------------------------ #
    def create_job(
        self,
        *,
        source_type: ImportSource,
        initiator_id: str | None,
        initiator_role: str | None,
        llm_model: str | None = None,
    ) -> ImportJob:
        job = ImportJob(
            source_type=source_type,
            status=ImportStatus.PENDING_REVIEW,
            initiator_id=initiator_id,
            initiator_role=initiator_role,
            llm_model=llm_model,
        )
        self._session.add(job)
        self._session.flush()
        return job

    def get_job(self, job_id: str) -> ImportJob | None:
        return self.session.get(ImportJob, job_id)

    def save_preview(self, job: ImportJob, preview: Sequence[CandidateRecord]) -> None:
        job.raw_payload_ref = json.dumps(
            [record.model_dump(mode="json", by_alias=True) for record in preview],
            ensure_ascii=False,
        )
        job.confidence_score = _average_confidence(preview)
        self._session.add(job)
        self._session.flush()

    def load_preview(self, job: ImportJob) -> list[CandidateRecord]:
        if not job.raw_payload_ref:
            return []
        payload = json.loads(job.raw_payload_ref)
        return [CandidateRecord.model_validate(item) for item in payload]

    def complete_job(self, job: ImportJob, status: ImportStatus) -> None:
        job.status = status
        job.completed_at = datetime.now(UTC)
        self._session.add(job)

    # ------------------------------------------------------------------ #
    # Attachments
    # ------------------------------------------------------------------ #
    def add_attachment(self, job: ImportJob, *, file_type: str, storage_path: str, checksum: str | None = None) -> Attachment:
        attachment = Attachment(
            import_job_id=job.id,
            file_type=file_type,
            storage_path=storage_path,
            checksum=checksum,
        )
        self._session.add(attachment)
        self._session.flush()
        return attachment

    # ------------------------------------------------------------------ #
    # Confirmation & persistence
    # ------------------------------------------------------------------ #
    def apply_confirmation(
        self,
        job: ImportJob,
        actions: Iterable[ConfirmationAction],
    ) -> tuple[int, int, list[CandidateRecord]]:
        approved = 0
        rejected = 0
        resulting_records: list[CandidateRecord] = []

        preview_lookup: dict[RecordType, list[CandidateRecord]] = {}
        for record in self.load_preview(job):
            preview_lookup.setdefault(record.record_type, []).append(record)

        for action in actions:
            if action.operation is ConfirmationOperation.REJECT:
                rejected += 1
                self._log(job, action, record_id=None)
                continue

            payload = action.payload
            if payload is None:
                candidate_list = preview_lookup.get(action.record_type, [])
                payload = candidate_list.pop(0).payload if candidate_list else {}

            record_id = self._persist_record(
                job,
                action.record_type,
                payload,
                overwrite=bool(action.overwrite),
            )
            approved += 1
            self._log(job, action, record_id=record_id)
            resulting_records.append(
                CandidateRecord(
                    record_type=action.record_type,
                    payload=payload,
                    confidence=None,
                    warnings=[],
                )
            )

        self.complete_job(job, ImportStatus.APPROVED if approved else ImportStatus.REJECTED)
        return approved, rejected, resulting_records

    def _log(self, job: ImportJob, action: ConfirmationAction, record_id: str | None) -> None:
        log = ConfirmationLog(
            import_job_id=job.id,
            record_type=action.record_type.value,
            record_id=record_id,
            actor_id=job.initiator_id,
            actor_role=job.initiator_role,
            action=action.operation.value,
            diff_snapshot=action.payload,
            comment=action.comment,
        )
        self._session.add(log)

    _placeholder_company_id = "company-unknown"

    def _persist_record(
        self,
        job: ImportJob,
        record_type: RecordType,
        payload: Dict[str, Any],
        *,
        overwrite: bool,
    ) -> str:
        """根据 record_type 保存财务数据，并返回记录 ID。"""
        if record_type is RecordType.ACCOUNT_BALANCE:
            company_id = self._resolve_company_id(payload)
            reported_at = _as_datetime(payload["reported_at"])

            existing = self.session.execute(
                select(AccountBalance).where(
                    AccountBalance.company_id == company_id,
                    AccountBalance.reported_at == reported_at,
                )
            ).scalar_one_or_none()
            if existing:
                if not overwrite:
                    raise DuplicateRecordError(
                        record_type,
                        {"companyId": company_id, "reportedAt": reported_at.isoformat()},
                    )
                existing.import_job_id = job.id
                existing.cash_balance = payload.get("cash_balance", existing.cash_balance)
                existing.investment_balance = payload.get(
                    "investment_balance", existing.investment_balance
                )
                existing.total_balance = payload.get("total_balance", existing.total_balance)
                existing.currency = payload.get("currency", existing.currency)
                existing.notes = payload.get("notes", existing.notes)
                self._session.flush()
                return existing.id

            record = AccountBalance(
                company_id=company_id,
                import_job_id=job.id,
                reported_at=reported_at,
                cash_balance=payload.get("cash_balance", 0),
                investment_balance=payload.get("investment_balance", 0),
                total_balance=payload.get("total_balance", 0),
                currency=payload.get("currency", "CNY"),
                notes=payload.get("notes"),
            )
        elif record_type is RecordType.REVENUE:
            category_id = self._ensure_category(
                payload,
                CategoryType.REVENUE,
                fallback_keys=["category", "subcategory"],
            )
            company_id = self._resolve_company_id(payload)
            month = _as_date(payload["month"])

            stmt = select(RevenueRecord).where(
                RevenueRecord.company_id == company_id,
                RevenueRecord.month == month,
            )
            if category_id:
                stmt = stmt.where(RevenueRecord.category_id == category_id)
            else:
                stmt = stmt.where(RevenueRecord.category == payload.get("category", ""))
                if payload.get("subcategory") is None:
                    stmt = stmt.where(RevenueRecord.subcategory.is_(None))
                else:
                    stmt = stmt.where(RevenueRecord.subcategory == payload.get("subcategory"))

            existing_revenue = self.session.execute(stmt).scalar_one_or_none()
            conflict_info = {
                "companyId": company_id,
                "month": month.isoformat(),
                "category": payload.get("category"),
                "subcategory": payload.get("subcategory"),
            }

            if existing_revenue:
                if not overwrite:
                    raise DuplicateRecordError(record_type, conflict_info)
                existing_revenue.import_job_id = job.id
                existing_revenue.category_id = category_id or existing_revenue.category_id
                existing_revenue.category = payload.get("category", existing_revenue.category)
                existing_revenue.subcategory = payload.get("subcategory", existing_revenue.subcategory)
                existing_revenue.amount = payload.get("amount", existing_revenue.amount)
                existing_revenue.currency = payload.get("currency", existing_revenue.currency)
                existing_revenue.confidence = payload.get("confidence", existing_revenue.confidence)
                existing_revenue.notes = payload.get("notes", existing_revenue.notes)
                self._session.flush()
                return existing_revenue.id

            record = RevenueRecord(
                company_id=company_id,
                import_job_id=job.id,
                category_id=category_id,
                month=month,
                category=payload.get("category", ""),
                subcategory=payload.get("subcategory"),
                amount=payload.get("amount", 0),
                currency=payload.get("currency", "CNY"),
                confidence=payload.get("confidence"),
                notes=payload.get("notes"),
            )
        elif record_type is RecordType.EXPENSE:
            category_id = self._ensure_category(
                payload,
                CategoryType.EXPENSE,
                fallback_keys=["category"],
            )
            company_id = self._resolve_company_id(payload)
            record = ExpenseRecord(
                company_id=company_id,
                import_job_id=job.id,
                category_id=category_id,
                month=_as_date(payload["month"]),
                category=payload.get("category", ""),
                amount=payload.get("amount", 0),
                currency=payload.get("currency", "CNY"),
                confidence=payload.get("confidence"),
                notes=payload.get("notes"),
            )
        elif record_type is RecordType.INCOME_FORECAST:
            category_id = self._ensure_category(
                payload,
                CategoryType.FORECAST,
                fallback_keys=["category"],
            )
            company_id = self._resolve_company_id(payload)
            record = IncomeForecast(
                company_id=company_id,
                import_job_id=job.id,
                category_id=category_id,
                cash_in_date=_as_date(payload["cash_in_date"]),
                product_line=payload.get("product_line"),
                product_name=payload.get("product_name"),
                certainty=Certainty(payload.get("certainty", Certainty.CERTAIN.value)),
                category=payload.get("category"),
                expected_amount=payload.get("expected_amount", 0),
                currency=payload.get("currency", "CNY"),
                confidence=payload.get("confidence"),
                notes=payload.get("notes"),
            )
        else:
            raise ValueError(f"Unsupported record type: {record_type}")

        self._session.add(record)
        self._session.flush()
        return record.id

    def _resolve_company_id(self, payload: Dict[str, Any]) -> str:
        raw_id = str(payload.get("company_id") or payload.get("companyId") or "").strip()
        if raw_id:
            payload["company_id"] = raw_id
            return raw_id

        placeholder = self._session.get(Company, self._placeholder_company_id)
        if placeholder is None:
            placeholder = Company(
                id=self._placeholder_company_id,
                name="未指定公司",
                display_name="未指定公司",
                currency="CNY",
            )
            self._session.add(placeholder)
            self._session.flush()

        payload["company_id"] = placeholder.id
        return placeholder.id

    def _ensure_category(
        self,
        payload: Dict[str, Any],
        category_type: CategoryType,
        fallback_keys: Sequence[str],
    ) -> str | None:
        path = payload.pop("category_path", None) or payload.pop("categoryPath", None)
        names: list[str] = []
        if isinstance(path, str):
            names = [part.strip() for part in path.split("/") if part.strip()]
        elif isinstance(path, Sequence):
            names = [str(item).strip() for item in path if str(item).strip()]
        if not names:
            for key in fallback_keys:
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    names.append(value.strip())
        if not names:
            return None
        category = self._category_service.get_or_create(names=names, category_type=category_type)
        if category:
            payload["category"] = names[-1]
            return category.id
        return None


def _average_confidence(records: Sequence[CandidateRecord]) -> float | None:
    confidences = [record.confidence for record in records if record.confidence is not None]
    if not confidences:
        return None
    return sum(confidences) / len(confidences)


def _as_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _as_date(value: str) -> date:
    return datetime.fromisoformat(value).date()

