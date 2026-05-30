"""Small helpers for user-visible AI generation feedback."""

from __future__ import annotations

from typing import Any, Optional


def _names(items: Any, limit: int = 6) -> list[str]:
    if not isinstance(items, list):
        return []
    names: list[str] = []
    for item in items:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("title") or "").strip()
        else:
            name = str(item or "").strip()
        if name and name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return names


def summarize_story_context(context: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Compact story context for API responses and UI status panels."""
    if not isinstance(context, dict):
        return {}
    return {
        "novel_id": context.get("novel_id"),
        "chapter_id": context.get("chapter_id"),
        "title": context.get("title"),
        "chapter_title": context.get("chapter_title"),
        "genre": context.get("genre"),
        "style": context.get("style"),
        "story_bible_id": context.get("story_bible_id"),
        "characters": _names(context.get("characters")),
        "scenes": _names(context.get("scenes")),
        "props": _names(context.get("props")),
        "events": _names(context.get("events")),
        "chapter_count": len(context.get("chapters") or []),
    }


def build_ai_generation_feedback(
    *,
    stage: str,
    message: str,
    context: Optional[dict[str, Any]] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    warnings: Optional[list[str]] = None,
    error_reason: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    feedback = {
        "stage": stage,
        "message": message,
        "context_summary": summarize_story_context(context),
        "provider": provider,
        "model": model,
        "warnings": warnings or [],
        "error_reason": error_reason,
    }
    if extra:
        feedback.update(extra)
    return feedback
