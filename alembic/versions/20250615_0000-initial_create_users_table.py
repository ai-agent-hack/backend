"""Initial create users table

Revision ID: initial_users
Revises:
Create Date: 2025-06-15 00:00:00.000000+00:00

"""

from alembic import op
import sqlalchemy as sa

# リビジョン識別子、Alembicが使用
revision = "initial_users"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """初期ユーザーテーブルを作成。"""
    # ユーザーテーブルを作成
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column(
            "hashed_password", sa.String(), nullable=False
        ),  # 後のマイグレーションで削除されます
        sa.Column(
            "full_name", sa.String(length=100), nullable=True
        ),  # 後のマイグレーションで削除されます
        sa.Column("is_active", sa.Boolean(), nullable=True, default=True),
        sa.Column("is_superuser", sa.Boolean(), nullable=True, default=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # インデックスを作成
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)


def downgrade() -> None:
    """ユーザーテーブルを削除。"""
    # インデックスを削除
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")

    # テーブルを削除
    op.drop_table("users")
