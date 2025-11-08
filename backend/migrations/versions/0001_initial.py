from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="CNY"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_review"),
        sa.Column("initiator_id", postgresql.UUID(as_uuid=True)),
        sa.Column("initiator_role", sa.String(length=64)),
        sa.Column("llm_model", sa.String(length=64)),
        sa.Column("confidence_score", sa.Float()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("raw_payload_ref", sa.String(length=255)),
        sa.Column("error_log", sa.Text()),
    )

    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("storage_path", sa.String(length=255), nullable=False),
        sa.Column("text_snapshot", sa.Text()),
        sa.Column("checksum", sa.String(length=128)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "account_balances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cash_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("investment_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="CNY"),
        sa.Column("notes", sa.Text()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "uq_account_balance_company_reported",
        "account_balances",
        ["company_id", "reported_at"],
        unique=True,
    )

    op.create_table(
        "revenue_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True)),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("subcategory", sa.String(length=64)),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="CNY"),
        sa.Column("confidence", sa.Float()),
        sa.Column("notes", sa.Text()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "expense_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True)),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="CNY"),
        sa.Column("confidence", sa.Float()),
        sa.Column("notes", sa.Text()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "income_forecasts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True)),
        sa.Column("cash_in_date", sa.Date(), nullable=False),
        sa.Column("product_line", sa.String(length=64)),
        sa.Column("product_name", sa.String(length=64)),
        sa.Column("certainty", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=64)),
        sa.Column("expected_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="CNY"),
        sa.Column("confidence", sa.Float()),
        sa.Column("notes", sa.Text()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "confirmation_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_type", sa.String(length=64), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actor_role", sa.String(length=64)),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("diff_snapshot", postgresql.JSONB()),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "nlq_queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("generated_sql", sa.Text()),
        sa.Column("execution_result_ref", sa.String(length=255)),
        sa.Column("chart_type", sa.String(length=16)),
        sa.Column("chart_config", postgresql.JSONB()),
        sa.Column("responded_at", sa.DateTime(timezone=True)),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("nlq_queries")
    op.drop_table("confirmation_logs")
    op.drop_table("income_forecasts")
    op.drop_table("expense_records")
    op.drop_table("revenue_records")
    op.drop_index("uq_account_balance_company_reported", table_name="account_balances")
    op.drop_table("account_balances")
    op.drop_table("attachments")
    op.drop_table("import_jobs")
    op.drop_table("companies")
