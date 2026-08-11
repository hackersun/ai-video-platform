"""Mark the schema managed by the legacy compatibility bootstrap.

Revision ID: 20260808_0001
Revises:
Create Date: 2026-08-08
"""

revision = "20260808_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Schema creation is performed before this marker is stamped."""


def downgrade() -> None:
    raise RuntimeError(
        "The baseline cannot be downgraded safely; restore the pre-migration backup."
    )
