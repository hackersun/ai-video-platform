"""Canonical construction of auditable StoryEntity evidence mentions."""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from app.models import StoryEntityMention


def mention_offsets(text: str, item: dict[str, Any]) -> tuple[Optional[int], Optional[int], str]:
    evidence = str(item.get("evidence") or item.get("name") or "")
    if evidence and evidence in text:
        start = text.find(evidence)
        return start, start + len(evidence), evidence
    name = str(item.get("name") or "")
    if name and name in text:
        start = text.find(name)
        return start, start + len(name), name
    return None, None, evidence or name


def build_story_entity_mention(
    *, user_id: str, run_id: str | None, entity_id: Optional[str],
    novel_id: Optional[str], chapter_id: Optional[str], script_id: Optional[str],
    source_type: str, source_id: Optional[str], text: str, item: dict[str, Any],
) -> StoryEntityMention:
    char_start, char_end, mention_text = mention_offsets(text, item)
    return StoryEntityMention(
        id=str(uuid4()), user_id=user_id, run_id=run_id, entity_id=entity_id,
        novel_id=novel_id, chapter_id=chapter_id, script_id=script_id,
        source_type=source_type, source_id=source_id,
        mention_text=mention_text[:500] if mention_text else None,
        evidence=str(item.get("evidence") or "")[:1000] or None,
        char_start=char_start, char_end=char_end,
        confidence=float(item.get("confidence") or 0),
        extractor=str(item.get("source") or "deterministic"),
        extra_data={"entity_type": item.get("entity_type"), "entity_name": item.get("name")},
    )
