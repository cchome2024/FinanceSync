"""add revenue details table

Revision ID: 0002_add_revenue_details
Revises: 0001_initial
Create Date: 2025-11-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_add_revenue_details"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revenue_details",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("import_job_id", sa.String(length=36), nullable=True),
        sa.Column("category_id", sa.String(length=36), nullable=True),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="CNY"),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("account_name", sa.String(length=64), nullable=True),
        sa.Column("category_path_text", sa.String(length=512), nullable=True),
        sa.Column("category_label", sa.String(length=128), nullable=True),
        sa.Column("subcategory_label", sa.String(length=128), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["category_id"], ["finance_categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "occurred_on",
            "amount",
            "category_id",
            "description",
            "account_name",
            name="uq_revenue_detail_natural_key",
        ),
    )
    op.create_index(
        "ix_revenue_details_company_occurred",
        "revenue_details",
        ["company_id", "occurred_on"],
    )


def downgrade() -> None:
    op.drop_index("ix_revenue_details_company_occurred", table_name="revenue_details")
    op.drop_table("revenue_details")

