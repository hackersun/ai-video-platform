"""Deterministic scene units for long-form chapter storyboard planning."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ChapterScenePlan:
    scene_index: int
    title: str
    source_text: str
    shot_count: int
    continuity: dict[str, int | None]


_HEADING = re.compile(r"^\s*(?:【([^】]{1,30})】|第[一二三四五六七八九十百\d]+[幕场节]\s*[:：]?\s*([^\n]{0,24}))")
_SENTENCE = re.compile(r".*?[。！？!?](?:[”’\"']?)(?=.|$)|.+$", re.S)


def _compact_length(value: str) -> int:
    return len(re.sub(r"\s+", "", value or ""))


def _sentence_chunks(text: str, target_chars: int, max_chars: int) -> list[str]:
    sentences = [match.group(0) for match in _SENTENCE.finditer(text) if match.group(0)]
    if not sentences:
        return [text] if text else []
    chunks: list[str] = []
    buffer = ""
    for sentence in sentences:
        if buffer and len(buffer) + len(sentence) > max_chars:
            chunks.append(buffer)
            buffer = ""
        buffer += sentence
        if len(buffer) >= target_chars:
            chunks.append(buffer)
            buffer = ""
    if buffer:
        if chunks and len(buffer) < target_chars // 2 and len(chunks[-1]) + len(buffer) <= max_chars:
            chunks[-1] += buffer
        else:
            chunks.append(buffer)
    return chunks


def _paragraph_units(content: str, target_chars: int, max_chars: int) -> list[str]:
    paragraphs = re.split(r"(?<=\S)(\n\s*\n+)", content)
    units: list[str] = []
    current = ""
    for part in paragraphs:
        if not part:
            continue
        if re.fullmatch(r"\n\s*\n+", part):
            current += part
            continue
        if _compact_length(part) > max_chars:
            if current:
                units.append(current)
                current = ""
            units.extend(_sentence_chunks(part, target_chars, max_chars))
            continue
        if current and _compact_length(current + part) > max_chars:
            units.append(current)
            current = ""
        current += part
        if _compact_length(current) >= target_chars or _HEADING.match(part):
            units.append(current)
            current = ""
    if current:
        units.append(current)
    return [unit for unit in units if unit]


def _title(text: str, chapter_title: str, index: int) -> str:
    match = _HEADING.match(text)
    heading = next((value for value in (match.groups() if match else ()) if value), None)
    if heading:
        return heading.strip()
    first = re.sub(r"\s+", "", text)[:16].strip("，。！？:：")
    return first or f"{chapter_title}·场景{index}"


def _shot_count(text: str, *, long_form: bool) -> int:
    if not long_form:
        return 1
    length_score = max(2, round(_compact_length(text) / 190))
    dialogue_score = len(re.findall(r"[：:][“\"'‘]", text))
    action_score = len(re.findall(r"战|追|逃|冲|拔剑|爆|坠|跃|挡|破阵", text))
    return max(2, min(6, length_score + int(dialogue_score >= 3 or action_score >= 4)))


def plan_chapter_scenes(
    content: str,
    *,
    chapter_title: str = "章节",
    target_chars: int = 650,
    max_chars: int = 950,
) -> list[ChapterScenePlan]:
    """Split a chapter without dropping or reordering source characters."""
    if not content:
        return []
    long_form = _compact_length(content) >= max(900, target_chars * 2)
    units = _paragraph_units(content, target_chars, max_chars) if long_form else [content]
    total = len(units)
    return [
        ChapterScenePlan(
            scene_index=index,
            title=_title(unit, chapter_title, index),
            source_text=unit,
            shot_count=_shot_count(unit, long_form=long_form),
            continuity={
                "previous_scene_index": index - 1 if index > 1 else None,
                "next_scene_index": index + 1 if index < total else None,
            },
        )
        for index, unit in enumerate(units, start=1)
    ]


__all__ = ["ChapterScenePlan", "plan_chapter_scenes"]
