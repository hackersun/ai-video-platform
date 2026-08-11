"""Add private media registry and lifecycle evidence.

Revision ID: 20260809_0006
Revises: 20260809_0005
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20260809_0006"
down_revision = "20260809_0005"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _table_names()
    if "media_objects" not in tables:
        op.create_table(
            "media_objects",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("project_id", sa.String(36), nullable=True),
            sa.Column("media_kind", sa.String(20), nullable=False),
            sa.Column("lifecycle_class", sa.String(20), nullable=False),
            sa.Column("storage_provider", sa.String(30), nullable=False),
            sa.Column("storage_config_id", sa.String(36), nullable=True),
            sa.Column("object_key", sa.String(700), nullable=False),
            sa.Column("canonical_url", sa.Text(), nullable=True),
            sa.Column("delivery_fingerprint", sa.String(64), nullable=True),
            sa.Column("sha256", sa.String(64), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("content_type", sa.String(100), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("retention_until", sa.DateTime(), nullable=True),
            sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("media_metadata", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("storage_provider", "object_key", name="uq_media_object_storage_key"),
        )
        for column in ("user_id", "project_id", "media_kind", "lifecycle_class", "storage_config_id", "status", "retention_until", "delivery_fingerprint"):
            op.create_index(f"ix_media_objects_{column}", "media_objects", [column])
    _create_evidence_tables()
    _create_receipt_guards()


def _create_evidence_tables() -> None:
    tables = _table_names()
    if "provider_media_inputs" not in tables:
        op.create_table(
            "provider_media_inputs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("media_object_id", sa.String(36), sa.ForeignKey("media_objects.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("project_id", sa.String(36), nullable=True),
            sa.Column("submission_id", sa.String(100), nullable=False),
            sa.Column("provider_task_id", sa.String(200), nullable=True),
            sa.Column("purpose", sa.String(100), nullable=False),
            sa.Column("input_order", sa.Integer(), nullable=False),
            sa.Column("delivery_method", sa.String(50), nullable=False),
            sa.Column("canonical_url", sa.Text(), nullable=False),
            sa.Column("url_fingerprint", sa.String(64), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("media_object_id", "submission_id", "purpose", "input_order", name="uq_provider_media_input_slot"),
        )
        for column in ("media_object_id", "user_id", "project_id", "submission_id", "provider_task_id"):
            op.create_index(f"ix_provider_media_inputs_{column}", "provider_media_inputs", [column])
    if "media_deletion_requests" not in tables:
        op.create_table(
            "media_deletion_requests",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("media_object_id", sa.String(36), sa.ForeignKey("media_objects.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("user_id", sa.String(36), nullable=False),
            sa.Column("idempotency_key", sa.String(200), nullable=False),
            sa.Column("reason", sa.String(300), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
            sa.Column("requested_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("user_id", "idempotency_key", name="uq_media_deletion_idempotency"),
        )
        for column in ("media_object_id", "user_id", "status"):
            op.create_index(f"ix_media_deletion_requests_{column}", "media_deletion_requests", [column])
    if "media_deletion_receipts" not in tables:
        op.create_table(
            "media_deletion_receipts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("media_object_id", sa.String(36), sa.ForeignKey("media_objects.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("request_id", sa.String(36), nullable=False, unique=True),
            sa.Column("outcome", sa.String(30), nullable=False),
            sa.Column("object_key_sha256", sa.String(64), nullable=False),
            sa.Column("detail", sa.String(300), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        for column in ("media_object_id", "request_id"):
            op.create_index(f"ix_media_deletion_receipts_{column}", "media_deletion_receipts", [column])


def _create_receipt_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION reject_media_receipt_mutation()
            RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'media deletion receipts are append-only'; END;
            $$ LANGUAGE plpgsql
        """)
        op.execute("DROP TRIGGER IF EXISTS trg_media_deletion_receipts_append_only ON media_deletion_receipts")
        op.execute("CREATE TRIGGER trg_media_deletion_receipts_append_only BEFORE UPDATE OR DELETE ON media_deletion_receipts FOR EACH ROW EXECUTE FUNCTION reject_media_receipt_mutation()")
    elif dialect == "sqlite":
        for operation in ("UPDATE", "DELETE"):
            name = f"trg_media_deletion_receipts_no_{operation.lower()}"
            op.execute(f"DROP TRIGGER IF EXISTS {name}")
            op.execute(f"CREATE TRIGGER {name} BEFORE {operation} ON media_deletion_receipts BEGIN SELECT RAISE(ABORT, 'media deletion receipts are append-only'); END")


def downgrade() -> None:
    raise RuntimeError("私有媒体迁移不可安全降级；请恢复迁移前备份")
