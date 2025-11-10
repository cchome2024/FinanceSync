"""add expense forecasts table

Revision ID: 0004_add_expense_forecasts
Revises: 0003_extend_income_forecasts
Create Date: 2025-11-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0004_add_expense_forecasts"
down_revision = "0003_extend_income_forecasts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expense_forecasts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("import_job_id", sa.String(length=36), nullable=True),
        sa.Column("category_id", sa.String(length=36), nullable=True),
        sa.Column("cash_out_date", sa.Date(), nullable=False),
        sa.Column("certainty", sa.Enum("certain", "uncertain", name="certainty"), nullable=False, server_default="certain"),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("category_path_text", sa.String(length=512), nullable=True),
        sa.Column("category_label", sa.String(length=128), nullable=True),
        sa.Column("subcategory_label", sa.String(length=128), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("account_name", sa.String(length=64), nullable=True),
        sa.Column("expected_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="CNY"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["category_id"], ["finance_categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "cash_out_date",
            "expected_amount",
            "category_id",
            "description",
            "account_name",
            name="uq_expense_forecast_natural_key",
        ),
    )
    op.create_index(
        "ix_expense_forecasts_company_date",
        "expense_forecasts",
        ["company_id", "cash_out_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_expense_forecasts_company_date", table_name="expense_forecasts")
    op.drop_table("expense_forecasts")


