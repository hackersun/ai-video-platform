"""Impact analysis for changing story entity continuity facts."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models import Novel, Script, Shot, StoryEntity, Storyboard
from app.services.entity_ref_normalizer import entity_ref_ids
from app.services.series_production import SERIES_PLAN_KEY


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _entity_ref_key(entity_type: str) -> str:
    return {
        "character": "characters",
        "scene": "scenes",
        "prop": "props",
        "event": "events",
    }.get(entity_type, f"{entity_type}s")


def _entity_ref_keys(entity_type: str) -> List[str]:
    key = _entity_ref_key(entity_type)
    singular = {
        "characters": "character",
        "scenes": "scene",
        "props": "prop",
        "events": "event",
    }.get(key, entity_type)
    return [item for item in (key, singular) if item]


def _episode_chapter_ids(episode: Dict[str, Any]) -> List[str]:
    ids = [str(item) for item in _json_list(episode.get("chapter_ids")) if item]
    if ids:
        return ids
    chapters = _json_list(episode.get("chapters"))
    return [str(item.get("id")) for item in chapters if isinstance(item, dict) and item.get("id")]


def _episode_index(episode: Dict[str, Any], fallback: int) -> int:
    value = episode.get("episode_index")
    if value is None:
        value = episode.get("episode_number")
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _names_for_entity(entity: StoryEntity) -> List[str]:
    names = [entity.name, entity.canonical_name, *_json_list(entity.aliases)]
    result: List[str] = []
    for value in names:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _ref_matches_entity(refs: Iterable[Any], entity: StoryEntity, names: List[str]) -> bool:
    for ref in refs:
        if isinstance(ref, dict):
            ref_id = ref.get("entity_id") or ref.get("character_id") or ref.get("id")
            if ref_id and str(ref_id) == entity.id:
                return True
            ref_name = str(ref.get("name") or ref.get("canonical_name") or ref.get("character_name") or "").strip()
            if ref_name and ref_name in names:
                return True
        elif str(ref or "").strip() in {entity.id, *names}:
            return True
    return False


def _shot_references_entity(shot: Shot, entity: StoryEntity, names: List[str]) -> bool:
    extra = _json_dict(shot.extra_data)
    entity_refs = _json_dict(extra.get("entity_refs"))
    for refs_key in _entity_ref_keys(entity.entity_type):
        if entity.id in entity_ref_ids(entity_refs, refs_key):
            return True
        if _ref_matches_entity(_json_list(entity_refs.get(refs_key)), entity, names):
            return True
    if entity.entity_type == "character" and _ref_matches_entity(_json_list(shot.character_refs), entity, names):
        return True
    return False


def _shot_payload(shot: Shot, chapter_id: Optional[str]) -> Dict[str, Any]:
    return {
        "id": shot.id,
        "chapter_id": chapter_id,
        "storyboard_id": shot.storyboard_id,
        "shot_number": shot.shot_number,
        "prompt": shot.prompt,
        "video_status": shot.video_status,
        "audio_status": shot.audio_status,
    }


def _storyboard_chapter_id(storyboard: Optional[Storyboard], script: Optional[Script]) -> Optional[str]:
    if storyboard:
        content_chapter_id = _json_dict(storyboard.content).get("chapter_id")
        if content_chapter_id:
            return str(content_chapter_id)
    if script:
        script_chapter_id = script.chapter_id or _json_dict(script.extra_data).get("chapter_id")
        if script_chapter_id:
            return str(script_chapter_id)
    return None


async def analyze_entity_change_impact(db: AsyncSession, user_id: str, entity_id: str) -> Dict[str, Any]:
    """Return episodes and shots that should be reviewed when an entity changes."""
    entity_result = await db.execute(
        select(StoryEntity).where(and_(StoryEntity.id == entity_id, StoryEntity.user_id == user_id))
    )
    entity = entity_result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="实体不存在")
    if not entity.novel_id:
        return {
            "entity": {"id": entity.id, "name": entity.name, "entity_type": entity.entity_type},
            "novel_id": None,
            "affected_episode_count": 0,
            "affected_shot_count": 0,
            "episodes": [],
            "shots": [],
            "apply_options": [],
        }

    novel_result = await db.execute(
        select(Novel).where(and_(Novel.id == entity.novel_id, Novel.user_id == user_id))
    )
    novel = novel_result.scalar_one_or_none()
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="小说不存在")

    plan = _json_dict(_json_dict(novel.extra_data).get(SERIES_PLAN_KEY))
    raw_episodes = [item for item in _json_list(plan.get("episodes")) if isinstance(item, dict)]
    episodes = [
        {
            **episode,
            "episode_index": _episode_index(episode, position + 1),
            "chapter_ids": _episode_chapter_ids(episode),
        }
        for position, episode in enumerate(raw_episodes)
    ]

    scripts = list((await db.execute(
        select(Script).where(and_(Script.user_id == user_id, Script.novel_id == entity.novel_id))
    )).scalars().all())
    scripts_by_id = {script.id: script for script in scripts}
    script_ids = list(scripts_by_id)

    storyboard_conditions = [Storyboard.user_id == user_id]
    if script_ids:
        storyboard_conditions.append(
            (Storyboard.novel_id == entity.novel_id) | (Storyboard.script_id.in_(script_ids))
        )
    else:
        storyboard_conditions.append(Storyboard.novel_id == entity.novel_id)
    storyboards = list((await db.execute(select(Storyboard).where(and_(*storyboard_conditions)))).scalars().all())
    storyboards_by_id = {storyboard.id: storyboard for storyboard in storyboards}
    storyboard_ids = list(storyboards_by_id)

    shots = list((await db.execute(
        select(Shot).where(and_(Shot.user_id == user_id, Shot.storyboard_id.in_(storyboard_ids)))
        if storyboard_ids
        else select(Shot).where(Shot.user_id == "__no_storyboards__")
    )).scalars().all())

    names = _names_for_entity(entity)
    affected_shots: List[Dict[str, Any]] = []
    for shot in shots:
        storyboard = storyboards_by_id.get(shot.storyboard_id)
        script = scripts_by_id.get(storyboard.script_id) if storyboard else None
        chapter_id = _json_dict(shot.extra_data).get("chapter_id") or _storyboard_chapter_id(storyboard, script)
        if _shot_references_entity(shot, entity, names):
            affected_shots.append(_shot_payload(shot, chapter_id))

    shot_count_by_chapter: Dict[str, int] = {}
    shots_by_chapter: Dict[str, List[Dict[str, Any]]] = {}
    for shot in affected_shots:
        chapter_id = shot.get("chapter_id")
        if not chapter_id:
            continue
        shot_count_by_chapter[chapter_id] = shot_count_by_chapter.get(chapter_id, 0) + 1
        shots_by_chapter.setdefault(chapter_id, []).append(shot)

    first_chapter_id = entity.first_seen_chapter_id or entity.chapter_id
    first_episode_index = None
    if first_chapter_id:
        for episode in episodes:
            if first_chapter_id in episode["chapter_ids"]:
                first_episode_index = int(episode["episode_index"])
                break
    if first_episode_index is None:
        direct_chapter_ids = [shot.get("chapter_id") for shot in affected_shots if shot.get("chapter_id")]
        for episode in episodes:
            if any(chapter_id in episode["chapter_ids"] for chapter_id in direct_chapter_ids):
                first_episode_index = int(episode["episode_index"])
                break
    if first_episode_index is None:
        first_episode_index = 1 if episodes and entity.novel_id else None

    impacted_episodes = [
        episode for episode in episodes
        if first_episode_index is not None and int(episode["episode_index"]) >= first_episode_index
    ]
    episode_payloads: List[Dict[str, Any]] = []
    for episode in impacted_episodes:
        episode_shots = [
            shot for chapter_id in episode["chapter_ids"]
            for shot in shots_by_chapter.get(chapter_id, [])
        ]
        episode_payloads.append({
            "episode_index": episode["episode_index"],
            "episode_number": episode.get("episode_number") or episode["episode_index"],
            "title": episode.get("title"),
            "chapter_ids": episode["chapter_ids"],
            "affected_shot_count": len(episode_shots),
            "affected_shots": episode_shots,
            "recommended_policy": "apply_from_episode",
        })

    apply_options = [
        {
            "episode_index": episode["episode_index"],
            "label": f"从第 {episode['episode_index']} 集起应用新设定",
            "affected_episode_count": len([item for item in impacted_episodes if int(item["episode_index"]) >= int(episode["episode_index"])]),
            "affected_shot_count": sum(
                payload["affected_shot_count"]
                for payload in episode_payloads
                if int(payload["episode_index"]) >= int(episode["episode_index"])
            ),
        }
        for episode in impacted_episodes
    ]

    return {
        "entity": {
            "id": entity.id,
            "name": entity.name,
            "canonical_name": entity.canonical_name,
            "entity_type": entity.entity_type,
            "version": entity.version,
        },
        "novel_id": entity.novel_id,
        "first_affected_episode_index": first_episode_index,
        "affected_episode_count": len(episode_payloads),
        "affected_shot_count": len(affected_shots),
        "episodes": episode_payloads,
        "shots": affected_shots,
        "apply_options": apply_options,
    }


async def mark_entity_change_impact_for_review(
    db: AsyncSession,
    user_id: str,
    entity_id: str,
    *,
    episode_index: int,
    change_note: Optional[str] = None,
) -> Dict[str, Any]:
    """Mark impacted shots from the selected episode onward for continuity review."""
    if episode_index < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="episode_index 必须大于等于 1")

    impact = await analyze_entity_change_impact(db, user_id, entity_id)
    entity = impact.get("entity") or {}
    selected_episodes = [
        episode for episode in _json_list(impact.get("episodes"))
        if int(episode.get("episode_index") or 0) >= episode_index
    ]
    shot_ids: List[str] = []
    for episode in selected_episodes:
        for shot in _json_list(episode.get("affected_shots")):
            shot_id = shot.get("id") if isinstance(shot, dict) else None
            if shot_id and shot_id not in shot_ids:
                shot_ids.append(str(shot_id))

    if not selected_episodes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到可应用的受影响集数")
    if not shot_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到需要复审的受影响镜头")

    shots: List[Shot] = []
    if shot_ids:
        shots = list((await db.execute(
            select(Shot).where(and_(Shot.user_id == user_id, Shot.id.in_(shot_ids)))
        )).scalars().all())

    now = utc_now()
    review_reason = f"{entity.get('name') or '实体'} 从第 {episode_index} 集起应用新设定"
    if change_note:
        review_reason = f"{review_reason}：{change_note}"

    for shot in shots:
        extra_data = dict(_json_dict(shot.extra_data))
        production_context = dict(_json_dict(extra_data.get("production_context")))
        continuity_change = {
            "entity_id": entity_id,
            "entity_name": entity.get("name"),
            "entity_type": entity.get("entity_type"),
            "entity_version": entity.get("version"),
            "episode_index": episode_index,
            "change_note": change_note,
            "marked_at": now.isoformat(),
        }
        extra_data["needs_review"] = True
        extra_data["review_reason"] = review_reason
        extra_data["review_at"] = now.isoformat()
        production_context["review_state"] = "changes_requested"
        production_context["review_notes"] = review_reason
        production_context["continuity_change"] = continuity_change
        production_context["updated_at"] = now.isoformat()
        extra_data["production_context"] = production_context
        shot.extra_data = extra_data
        shot.updated_at = now

    await db.commit()

    return {
        "status": "review_plan_created",
        "entity": entity,
        "novel_id": impact.get("novel_id"),
        "episode_index": episode_index,
        "change_note": change_note,
        "affected_episode_count": len(selected_episodes),
        "marked_shot_count": len(shots),
        "shot_ids": shot_ids,
        "review_reason": review_reason,
    }
