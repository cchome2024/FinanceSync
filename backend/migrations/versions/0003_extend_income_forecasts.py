"""extend income forecasts table with detail columns

Revision ID: 0003_extend_income_forecasts
Revises: 0002_add_revenue_details
Create Date: 2025-11-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_extend_income_forecasts"
down_revision = "0002_add_revenue_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("income_forecasts")}

    columns_to_add: list[tuple[str, sa.types.TypeEngine]] = [
        ("category_path_text", sa.String(length=512)),
        ("category_label", sa.String(length=128)),
        ("subcategory_label", sa.String(length=128)),
        ("description", sa.String(length=255)),
        ("account_name", sa.String(length=64)),
    ]

    with op.batch_alter_table("income_forecasts", recreate="auto") as batch_op:
        for column_name, column_type in columns_to_add:
            if column_name not in existing_columns:
                batch_op.add_column(sa.Column(column_name, column_type, nullable=True))

    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("income_forecasts")}
    if "uq_income_forecast_natural_key" not in existing_indexes:
        op.create_index(
            "uq_income_forecast_natural_key",
            "income_forecasts",
            [
                "company_id",
                "cash_in_date",
                "expected_amount",
                "category_id",
                "description",
                "account_name",
            ],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index("uq_income_forecast_natural_key", table_name="income_forecasts")
    with op.batch_alter_table("income_forecasts", recreate="auto") as batch_op:
        batch_op.drop_column("account_name")
        batch_op.drop_column("description")
        batch_op.drop_column("subcategory_label")
        batch_op.drop_column("category_label")
        batch_op.drop_column("category_path_text")


