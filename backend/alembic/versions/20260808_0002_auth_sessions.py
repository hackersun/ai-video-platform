"""Add verified accounts and persistent refresh sessions.

Revision ID: 20260808_0002
Revises: 20260808_0001
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa


revision = "20260808_0002"
down_revision = "20260808_0001"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = _column_names("users")
    additions = (
        sa.Column("account_status", sa.String(32), nullable=True),
        sa.Column("email_verified_at", sa.DateTime(), nullable=True),
        sa.Column("email_verification_token_hash", sa.String(64), nullable=True),
        sa.Column("email_verification_token_expires_at", sa.DateTime(), nullable=True),
    )
    for column in additions:
        if column.name not in user_columns:
            op.add_column("users", column)

    users = sa.table(
        "users",
        sa.column("account_status", sa.String()),
        sa.column("email_verified_at", sa.DateTime()),
        sa.column("email_verification_token_hash", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("is_active", sa.Boolean()),
    )
    op.execute(
        users.update()
        .where(users.c.account_status.is_(None))
        .values(account_status=sa.case((users.c.is_active.is_(True), "active"), else_="disabled"))
    )
    op.execute(
        users.update()
        .where(users.c.is_active.is_(True))
        .values(email_verified_at=sa.func.coalesce(users.c.email_verified_at, users.c.created_at, sa.func.now()))
    )
    if "ix_users_email_verification_token_hash" not in _index_names("users"):
        op.create_index(
            "ix_users_email_verification_token_hash",
            "users",
            ["email_verification_token_hash"],
            unique=True,
        )

    if "user_sessions" not in inspector.get_table_names():
        op.create_table(
            "user_sessions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("family_id", sa.String(36), nullable=False),
            sa.Column("refresh_token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("device_summary", sa.String(200), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("replaced_by_id", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
        op.create_index("ix_user_sessions_family_id", "user_sessions", ["family_id"])
        op.create_index("ix_user_sessions_refresh_token_hash", "user_sessions", ["refresh_token_hash"], unique=True)
        op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])
        op.create_index("ix_user_sessions_revoked_at", "user_sessions", ["revoked_at"])
        op.create_index(
            "ix_user_sessions_user_active",
            "user_sessions",
            ["user_id", "revoked_at", "expires_at"],
        )

    if "auth_notification_outbox" not in inspector.get_table_names():
        op.create_table(
            "auth_notification_outbox",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("recipient", sa.String(320), nullable=False),
            sa.Column("kind", sa.String(32), nullable=False),
            sa.Column("encrypted_payload", sa.Text(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
            sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("last_error_code", sa.String(80), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_auth_notification_outbox_delivery",
            "auth_notification_outbox",
            ["status", "next_attempt_at"],
        )
        op.create_index(
            "ix_auth_notification_outbox_user",
            "auth_notification_outbox",
            ["user_id", "created_at"],
        )


def downgrade() -> None:
    raise RuntimeError("认证会话迁移不可安全降级；请恢复迁移前备份")
