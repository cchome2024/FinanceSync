"""add user authentication

Revision ID: 0005_add_user_auth
Revises: 0004_add_expense_forecasts
Create Date: 2025-01-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0005_add_user_auth"
down_revision = "0004_add_expense_forecasts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 检查表是否已存在
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    
    # 创建users表（如果不存在）
    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("email", sa.String(length=255), nullable=False, unique=True),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("display_name", sa.String(length=128), nullable=False),
            sa.Column("role", sa.String(length=16), nullable=False, server_default="viewer"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)
    
    # 为import_jobs表添加user_id外键（如果列不存在）
    if "import_jobs" in tables:
        columns = [col["name"] for col in inspector.get_columns("import_jobs")]
        if "user_id" not in columns:
            op.add_column("import_jobs", sa.Column("user_id", sa.String(length=36), nullable=True))
            
            # 检查外键是否已存在
            foreign_keys = inspector.get_foreign_keys("import_jobs")
            fk_exists = any(fk["name"] == "fk_import_jobs_user_id" for fk in foreign_keys)
            if not fk_exists:
                op.create_foreign_key(
                    "fk_import_jobs_user_id",
                    "import_jobs",
                    "users",
                    ["user_id"],
                    ["id"],
                    ondelete="SET NULL"
                )


def downgrade() -> None:
    # 检查表是否存在
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    
    # 删除import_jobs表的user_id外键和列
    if "import_jobs" in tables:
        columns = [col["name"] for col in inspector.get_columns("import_jobs")]
        foreign_keys = inspector.get_foreign_keys("import_jobs")
        
        if "user_id" in columns:
            # 先删除外键约束
            fk_exists = any(fk["name"] == "fk_import_jobs_user_id" for fk in foreign_keys)
            if fk_exists:
                op.drop_constraint("fk_import_jobs_user_id", "import_jobs", type_="foreignkey")
            # 再删除列
            op.drop_column("import_jobs", "user_id")
    
    # 删除users表
    if "users" in tables:
        # 检查索引是否存在
        indexes = inspector.get_indexes("users")
        index_exists = any(idx["name"] == "ix_users_email" for idx in indexes)
        if index_exists:
            op.drop_index("ix_users_email", table_name="users")
        op.drop_table("users")

