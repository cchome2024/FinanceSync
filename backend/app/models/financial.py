from __future__ import annotations

import enum
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ImportSource(str, enum.Enum):
    MANUAL_UPLOAD = "manual_upload"
    WATCHED_DIR = "watched_dir"
    AI_CHAT = "ai_chat"


class ImportStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class Certainty(str, enum.Enum):
    CERTAIN = "certain"
    UNCERTAIN = "uncertain"


class NlqChartType(str, enum.Enum):
    LINE = "line"
    BAR = "bar"
    AREA = "area"
    PIE = "pie"
    TABLE = "table"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    account_balances: Mapped[list["AccountBalance"]] = relationship(back_populates="company")
    revenue_records: Mapped[list["RevenueRecord"]] = relationship(back_populates="company")
    expense_records: Mapped[list["ExpenseRecord"]] = relationship(back_populates="company")
    income_forecasts: Mapped[list["IncomeForecast"]] = relationship(back_populates="company")


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    source_type: Mapped[ImportSource] = mapped_column(Enum(ImportSource), nullable=False)
    status: Mapped[ImportStatus] = mapped_column(Enum(ImportStatus), nullable=False, default=ImportStatus.PENDING_REVIEW)
    initiator_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True))
    initiator_role: Mapped[str | None] = mapped_column(String(64))
    llm_model: Mapped[str | None] = mapped_column(String(64))
    confidence_score: Mapped[float | None] = mapped_column(Float)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload_ref: Mapped[str | None] = mapped_column(String(255))
    error_log: Mapped[str | None] = mapped_column(Text)

    attachments: Mapped[list["Attachment"]] = relationship(back_populates="import_job")
    confirmation_logs: Mapped[list["ConfirmationLog"]] = relationship(back_populates="import_job")


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    import_job_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("import_jobs.id"), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(255), nullable=False)
    text_snapshot: Mapped[str | None] = mapped_column(Text)
    checksum: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    import_job: Mapped[ImportJob] = relationship(back_populates="attachments")


class AccountBalance(Base):
    __tablename__ = "account_balances"
    __table_args__ = (
        UniqueConstraint("company_id", "reported_at", name="uq_account_balance_company_reported"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    company_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    import_job_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("import_jobs.id"))
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cash_balance: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    investment_balance: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    total_balance: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    notes: Mapped[str | None] = mapped_column(Text)

    company: Mapped[Company] = relationship(back_populates="account_balances")
    import_job: Mapped[ImportJob] = relationship()


class RevenueRecord(Base):
    __tablename__ = "revenue_records"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    company_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    import_job_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("import_jobs.id"))
    month: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String(64))
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    confidence: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)

    company: Mapped[Company] = relationship(back_populates="revenue_records")
    import_job: Mapped[ImportJob] = relationship()


class ExpenseRecord(Base):
    __tablename__ = "expense_records"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    company_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    import_job_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("import_jobs.id"))
    month: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    confidence: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)

    company: Mapped[Company] = relationship(back_populates="expense_records")
    import_job: Mapped[ImportJob] = relationship()


class IncomeForecast(Base):
    __tablename__ = "income_forecasts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    company_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    import_job_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("import_jobs.id"))
    cash_in_date: Mapped[date] = mapped_column(Date, nullable=False)
    product_line: Mapped[str | None] = mapped_column(String(64))
    product_name: Mapped[str | None] = mapped_column(String(64))
    certainty: Mapped[Certainty] = mapped_column(Enum(Certainty), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64))
    expected_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    confidence: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)

    company: Mapped[Company] = relationship(back_populates="income_forecasts")
    import_job: Mapped[ImportJob] = relationship()


class ConfirmationLog(Base):
    __tablename__ = "confirmation_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    import_job_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("import_jobs.id"), nullable=False)
    record_type: Mapped[str] = mapped_column(String(64), nullable=False)
    record_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True))
    actor_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True))
    actor_role: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    diff_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    import_job: Mapped[ImportJob] = relationship(back_populates="confirmation_logs")


class NlqQuery(Base):
    __tablename__ = "nlq_queries"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    generated_sql: Mapped[str | None] = mapped_column(Text)
    execution_result_ref: Mapped[str | None] = mapped_column(String(255))
    chart_type: Mapped[NlqChartType | None] = mapped_column(Enum(NlqChartType))
    chart_config: Mapped[dict | None] = mapped_column(JSONB)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

