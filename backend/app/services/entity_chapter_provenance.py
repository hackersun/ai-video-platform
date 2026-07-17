"""Attach first-chapter provenance to novel-wide entity extraction results."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chapter


async def attach_first_chapter_provenance(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: str,
    items: list[dict[str, Any]],
) -> None:
    result = await db.execute(
        select(Chapter)
        .where(Chapter.user_id == user_id, Chapter.novel_id == novel_id)
        .order_by(Chapter.chapter_number, Chapter.created_at)
    )
    chapters = list(result.scalars().all())
    for item in items:
        if item.get("source_chapter_id"):
            continue
        evidence = str(item.get("evidence_span") or item.get("evidence") or "").strip()
        name = str(item.get("name") or "").strip()
        chapter = next(
            (
                candidate
                for candidate in chapters
                if (evidence and evidence in (candidate.content or ""))
                or (name and name in (candidate.content or ""))
            ),
            None,
        )
        if chapter:
            item["source_chapter_id"] = chapter.id
            item["source_chapter_number"] = chapter.chapter_number
