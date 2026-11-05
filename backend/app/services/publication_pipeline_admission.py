"""Admission rule for one-click pipelines: one active pipeline per novel (R04)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.publication_pipeline import NovelPublicationPipeline

# Statuses that hold the per-novel slot. blocked/failed are retryable via the
# same idempotency key but do not block a fresh run; succeeded/cancelled are terminal.
ACTIVE_PIPELINE_STATUSES = frozenset({"queued", "running", "paused"})


async def find_active_pipeline(
    db: AsyncSession, *, user_id: str, novel_id: str
) -> Optional[NovelPublicationPipeline]:
    return await db.scalar(
        select(NovelPublicationPipeline)
        .where(
            NovelPublicationPipeline.user_id == user_id,
            NovelPublicationPipeline.novel_id == novel_id,
            NovelPublicationPipeline.status.in_(ACTIVE_PIPELINE_STATUSES),
        )
        .order_by(NovelPublicationPipeline.created_at.desc())
        .limit(1)
    )
