from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.financial import (
    AccountBalance,
    Attachment,
    Certainty,
    ConfirmationLog,
    ExpenseForecast,
    ExpenseRecord,
    ImportJob,
    ImportSource,
    ImportStatus,
    IncomeForecast,
    RevenueDetail,
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
        self._income_forecast_cleared_companies: set[str] = set()
        self._expense_forecast_cleared_companies: set[str] = set()

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
        user_id: str | None = None,
        initiator_id: str | None = None,  # 保留向后兼容
        initiator_role: str | None = None,  # 保留向后兼容
        llm_model: str | None = None,
    ) -> ImportJob:
        job = ImportJob(
            source_type=source_type,
            status=ImportStatus.PENDING_REVIEW,
            user_id=user_id,
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
            company_id = self._resolve_company_id(payload)
            raw_occurred = payload.get("occurred_on") or payload.get("occurredOn") or payload.get("date")
            if not raw_occurred:
                raise ValueError("Revenue detail missing occurred_on/date field")
            occurred_on = _as_date(raw_occurred)
            payload["occurred_on"] = occurred_on.isoformat()

            category_id = self._ensure_category(
                payload,
                CategoryType.REVENUE,
                fallback_keys=[
                    "category",
                    "subcategory",
                    "category_level1",
                    "categoryLevel1",
                    "category_level2",
                    "categoryLevel2",
                ],
            )

            amount_raw = payload.get("amount")
            if amount_raw is None:
                raise ValueError("Revenue detail missing amount")
            amount_value = Decimal(str(amount_raw))
            payload["amount"] = float(amount_value)

            description = (payload.get("description") or payload.get("item") or payload.get("item_name") or "").strip() or None
            account_name = (payload.get("account_name") or payload.get("account") or payload.get("accountName") or "").strip() or None
            category_text = payload.get("category_path_text") or payload.get("category")
            category_label = payload.get("category_label") or payload.get("category")
            subcategory_label = payload.get("subcategory_label") or payload.get("subcategory")

            # 排除当前导入任务中已插入的记录（在同一个事务中）
            # 只检查已提交的其他任务的记录，避免在同一个导入任务中误判为重复
            stmt = select(RevenueDetail).where(
                RevenueDetail.company_id == company_id,
                RevenueDetail.occurred_on == occurred_on,
                RevenueDetail.amount == amount_value,
            )
            # 排除当前任务中已插入的记录
            if job.id:
                stmt = stmt.where(RevenueDetail.import_job_id != job.id)
            
            if category_id:
                stmt = stmt.where(RevenueDetail.category_id == category_id)
            elif category_text:
                # 确保 category_text 不是空字符串
                category_text_clean = category_text.strip() if isinstance(category_text, str) else None
                if category_text_clean:
                    stmt = stmt.where(RevenueDetail.category_path_text == category_text_clean)
                else:
                    stmt = stmt.where(RevenueDetail.category_path_text.is_(None))
            else:
                # 如果既没有category_id也没有category_path_text，则匹配两者都为None的记录
                stmt = stmt.where(
                    RevenueDetail.category_id.is_(None),
                    RevenueDetail.category_path_text.is_(None),
                )
            if description:
                stmt = stmt.where(RevenueDetail.description == description)
            else:
                stmt = stmt.where(RevenueDetail.description.is_(None))
            if account_name:
                stmt = stmt.where(RevenueDetail.account_name == account_name)
            else:
                stmt = stmt.where(RevenueDetail.account_name.is_(None))
            
            # 调试日志
            print(f"[DUPLICATE CHECK] Checking for duplicate revenue:")
            print(f"  company_id: {company_id}")
            print(f"  occurred_on: {occurred_on}")
            print(f"  amount: {amount_value}")
            print(f"  category_id: {category_id}")
            print(f"  category_path_text: {category_text}")
            print(f"  description: {description}")
            print(f"  account_name: {account_name}")
            print(f"  current_job_id: {job.id} (excluding records from this job)")
            
            # 使用 first() 而不是 scalar_one_or_none()，因为可能有多条匹配的记录
            result = self.session.execute(stmt).first()
            existing_detail = result[0] if result else None
            
            if existing_detail:
                print(f"[DUPLICATE CHECK] Found existing record:")
                print(f"  ID: {existing_detail.id}")
                print(f"  import_job_id: {existing_detail.import_job_id}")
                print(f"  amount: {existing_detail.amount}")
                print(f"  category_path: {existing_detail.category_path_text}")
                print(f"  description: {existing_detail.description}")
                # 检查是否有多条匹配的记录
                all_matches = self.session.execute(stmt).all()
                if len(all_matches) > 1:
                    print(f"[DUPLICATE CHECK] WARNING: Found {len(all_matches)} matching records (duplicate data in database)")
            else:
                print(f"[DUPLICATE CHECK] No duplicate found")
            conflict_info = {
                "companyId": company_id,
                "occurredOn": occurred_on.isoformat(),
                "category": payload.get("category"),
                "categoryPath": payload.get("category_path_text"),
                "categoryLabel": category_label,
                "subcategory": subcategory_label,
                "description": description,
                "accountName": account_name,
                "amount": float(amount_value),
            }

            if existing_detail:
                if not overwrite:
                    raise DuplicateRecordError(record_type, conflict_info)
                existing_detail.import_job_id = job.id
                existing_detail.category_id = category_id or existing_detail.category_id
                existing_detail.category_path_text = category_text or existing_detail.category_path_text
                existing_detail.category_label = category_label or existing_detail.category_label
                existing_detail.subcategory_label = subcategory_label or existing_detail.subcategory_label
                existing_detail.amount = amount_value
                existing_detail.currency = payload.get("currency", existing_detail.currency)
                existing_detail.description = description
                existing_detail.account_name = account_name
                existing_detail.confidence = payload.get("confidence", existing_detail.confidence)
                existing_detail.notes = payload.get("notes", existing_detail.notes)
                self._session.flush()
                return existing_detail.id

            record = RevenueDetail(
                company_id=company_id,
                import_job_id=job.id,
                category_id=category_id,
                occurred_on=occurred_on,
                amount=amount_value,
                currency=payload.get("currency", "CNY"),
                description=description,
                account_name=account_name,
                category_path_text=category_text,
                category_label=category_label,
                subcategory_label=subcategory_label,
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
        elif record_type in (RecordType.INCOME_FORECAST, RecordType.REVENUE_FORECAST):
            category_id = self._ensure_category(
                payload,
                CategoryType.FORECAST,
                fallback_keys=[
                    "category",
                    "subcategory",
                    "category_level1",
                    "category_level2",
                    "categoryLevel1",
                    "categoryLevel2",
                ],
            )
            company_id = self._resolve_company_id(payload)
            self._ensure_income_forecast_reset(company_id)

            raw_date = (
                payload.get("cash_in_date")
                or payload.get("cashInDate")
                or payload.get("occurred_on")
                or payload.get("occurredOn")
                or payload.get("forecast_date")
                or payload.get("forecastDate")
            )
            if not raw_date:
                raise ValueError("Income forecast missing date field (cash_in_date/occurred_on/forecast_date)")
            cash_in_date = _as_date(str(raw_date))
            payload["cash_in_date"] = cash_in_date.isoformat()

            amount_raw = payload.get("expected_amount")
            if amount_raw is None:
                amount_raw = payload.get("amount")
            if amount_raw is None:
                raise ValueError("Income forecast missing amount field")
            amount_value = Decimal(str(amount_raw))
            payload["expected_amount"] = float(amount_value)

            description = (
                payload.get("description")
                or payload.get("item")
                or payload.get("item_name")
                or ""
            ).strip() or None
            account_name = (
                payload.get("account_name")
                or payload.get("account")
                or payload.get("accountName")
                or ""
            ).strip() or None
            category_text = payload.get("category_path_text")
            if not category_text:
                category_text = payload.get("category_path")
            category_label = payload.get("category")
            subcategory_label = payload.get("subcategory")
            if isinstance(category_text, (list, tuple)):
                category_path_text = "/".join(
                    str(part).strip() for part in category_text if str(part).strip()
                )
            elif isinstance(category_text, str):
                category_path_text = category_text
            else:
                category_path_text = None

            certainty_value = payload.get("certainty") or Certainty.CERTAIN.value
            record_certainty = Certainty(certainty_value)

            record = IncomeForecast(
                company_id=company_id,
                import_job_id=job.id,
                category_id=category_id,
                cash_in_date=cash_in_date,
                product_line=payload.get("product_line"),
                product_name=payload.get("product_name"),
                certainty=record_certainty,
                category=payload.get("category"),
                category_path_text=category_path_text,
                category_label=category_label,
                subcategory_label=subcategory_label,
                description=description,
                account_name=account_name,
                expected_amount=amount_value,
                currency=payload.get("currency", "CNY"),
                confidence=payload.get("confidence"),
                notes=payload.get("notes"),
            )
        elif record_type is RecordType.EXPENSE_FORECAST:
            category_id = self._ensure_category(
                payload,
                CategoryType.EXPENSE,
                fallback_keys=[
                    "category",
                    "subcategory",
                    "category_level1",
                    "category_level2",
                    "categoryLevel1",
                    "categoryLevel2",
                ],
            )
            company_id = self._resolve_company_id(payload)
            self._ensure_expense_forecast_reset(company_id)

            raw_date = (
                payload.get("cash_out_date")
                or payload.get("cashOutDate")
                or payload.get("occurred_on")
                or payload.get("occurredOn")
                or payload.get("forecast_date")
                or payload.get("forecastDate")
            )
            if not raw_date:
                raise ValueError("Expense forecast missing date field (cash_out_date/occurred_on/forecast_date)")
            cash_out_date = _as_date(str(raw_date))
            payload["cash_out_date"] = cash_out_date.isoformat()

            amount_raw = payload.get("expected_amount")
            if amount_raw is None:
                amount_raw = payload.get("amount")
            if amount_raw is None:
                raise ValueError("Expense forecast missing amount field")
            amount_value = Decimal(str(amount_raw))
            payload["expected_amount"] = float(amount_value)

            description = (
                payload.get("description")
                or payload.get("item")
                or payload.get("item_name")
                or ""
            ).strip() or None
            account_name = (
                payload.get("account_name")
                or payload.get("account")
                or payload.get("accountName")
                or ""
            ).strip() or None
            category_text = payload.get("category_path_text")
            if not category_text:
                category_text = payload.get("category_path")
            category_label = payload.get("category")
            subcategory_label = payload.get("subcategory")
            if isinstance(category_text, (list, tuple)):
                category_path_text = "/".join(
                    str(part).strip() for part in category_text if str(part).strip()
                )
            elif isinstance(category_text, str):
                category_path_text = category_text
            else:
                category_path_text = None

            certainty_value = payload.get("certainty") or Certainty.CERTAIN.value
            record_certainty = Certainty(certainty_value)

            record = ExpenseForecast(
                company_id=company_id,
                import_job_id=job.id,
                category_id=category_id,
                cash_out_date=cash_out_date,
                certainty=record_certainty,
                category=payload.get("category"),
                category_path_text=category_path_text,
                category_label=category_label,
                subcategory_label=subcategory_label,
                description=description,
                account_name=account_name,
                expected_amount=amount_value,
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
            payload["category_path_text"] = "/".join(names)
            return category.id
        return None

    def _ensure_income_forecast_reset(self, company_id: str) -> None:
        if company_id in self._income_forecast_cleared_companies:
            return
        self.session.query(IncomeForecast).filter(IncomeForecast.company_id == company_id).delete(
            synchronize_session=False
        )
        self._income_forecast_cleared_companies.add(company_id)

    def _ensure_expense_forecast_reset(self, company_id: str) -> None:
        if company_id in self._expense_forecast_cleared_companies:
            return
        self.session.query(ExpenseForecast).filter(ExpenseForecast.company_id == company_id).delete(
            synchronize_session=False
        )
        self._expense_forecast_cleared_companies.add(company_id)


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

