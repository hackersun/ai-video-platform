"""Story Bible state machine helpers.

The state machine is a lightweight production layer stored in
StoryBible.extra_data. It summarizes how characters, scenes, props and events
change across chapters and episodes, so downstream prompts can inherit concrete
continuity constraints instead of relying on prose alone.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.time_utils import utc_now
from app.models import Chapter, Novel, StoryBible, StoryEntity
from app.services.entity_extraction_service import ENTITY_TYPES, extract_story_entities


STATE_MACHINE_KEY = "state_machine"


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _compact(value: Optional[str], limit: int = 120) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _uniq(values: Iterable[Any], limit: int = 12) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


async def _load_story_bible(db: AsyncSession, user_id: str, story_bible_id: str) -> StoryBible:
    result = await db.execute(
        select(StoryBible).where(StoryBible.id == story_bible_id, StoryBible.user_id == user_id)
    )
    story_bible = result.scalar_one_or_none()
    if story_bible is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story Bible 不存在")
    return story_bible


async def _load_novel(db: AsyncSession, user_id: str, novel_id: str) -> Novel:
    result = await db.execute(select(Novel).where(Novel.id == novel_id, Novel.user_id == user_id))
    novel = result.scalar_one_or_none()
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="小说不存在")
    return novel


def _entity_payload(entity: StoryEntity) -> Dict[str, Any]:
    return {
        "id": entity.id,
        "entity_type": entity.entity_type,
        "name": entity.name,
        "description": entity.description,
        "chapter_id": entity.chapter_id,
        "attributes": _json_dict(entity.attributes),
        "evidence": entity.evidence,
        "source": entity.source or "manual",
    }


def _extracted_payload(item: Dict[str, Any], chapter: Chapter) -> Dict[str, Any]:
    return {
        "id": None,
        "entity_type": item.get("entity_type"),
        "name": item.get("name"),
        "description": item.get("description") or item.get("evidence"),
        "chapter_id": chapter.id,
        "attributes": _json_dict(item.get("attributes")),
        "evidence": item.get("evidence"),
        "source": item.get("source") or "deterministic",
    }


def _group_entities_for_chapter(
    entities: List[StoryEntity],
    extracted_by_chapter: Dict[str, List[Dict[str, Any]]],
    chapter: Chapter,
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {entity_type: [] for entity_type in ENTITY_TYPES}
    seen: set[tuple[str, str]] = set()

    for entity in entities:
        if entity.chapter_id not in {None, chapter.id}:
            continue
        key = (entity.entity_type, entity.name)
        if key in seen:
            continue
        grouped.setdefault(entity.entity_type, []).append(_entity_payload(entity))
        seen.add(key)

    for item in extracted_by_chapter.get(chapter.id, []):
        entity_type = item.get("entity_type")
        name = item.get("name")
        if not entity_type or not name:
            continue
        key = (entity_type, name)
        if key in seen:
            continue
        grouped.setdefault(entity_type, []).append(item)
        seen.add(key)

    return grouped


def _character_state(entity: Dict[str, Any], chapter: Chapter) -> Dict[str, Any]:
    attrs = _json_dict(entity.get("attributes"))
    visual_dna = _json_dict(attrs.get("visual_dna"))
    return {
        "name": entity.get("name"),
        "state": attrs.get("state") or attrs.get("status") or attrs.get("emotion") or "已登场",
        "costume": attrs.get("costume") or attrs.get("costume_state") or visual_dna.get("costume") or "默认服装",
        "location": attrs.get("location"),
        "goal": attrs.get("goal") or attrs.get("objective"),
        "relationships": _json_list(attrs.get("relationships")),
        "visual_dna": visual_dna,
        "source_entity_id": entity.get("id"),
        "last_changed_chapter_id": chapter.id,
        "last_changed_chapter_number": chapter.chapter_number,
        "evidence": _compact(entity.get("evidence") or entity.get("description"), 160),
    }


def _scene_state(entity: Dict[str, Any], chapter: Chapter) -> Dict[str, Any]:
    attrs = _json_dict(entity.get("attributes"))
    scene_dna = _json_dict(attrs.get("scene_dna") or attrs.get("visual_dna"))
    tags = attrs.get("scene_tags") or attrs.get("tags") or []
    if isinstance(tags, str):
        tags = [item.strip() for item in tags.split(",") if item.strip()]
    return {
        "name": entity.get("name"),
        "time": attrs.get("time") or scene_dna.get("time"),
        "weather": attrs.get("weather") or scene_dna.get("weather"),
        "lighting": attrs.get("lighting") or scene_dna.get("lighting"),
        "layout": attrs.get("layout") or scene_dna.get("layout"),
        "tags": tags if isinstance(tags, list) else [],
        "scene_dna": scene_dna,
        "source_entity_id": entity.get("id"),
        "last_changed_chapter_id": chapter.id,
        "last_changed_chapter_number": chapter.chapter_number,
        "evidence": _compact(entity.get("evidence") or entity.get("description"), 160),
    }


def _prop_state(entity: Dict[str, Any], chapter: Chapter) -> Dict[str, Any]:
    attrs = _json_dict(entity.get("attributes"))
    prop_dna = _json_dict(attrs.get("prop_dna") or attrs.get("visual_dna"))
    return {
        "name": entity.get("name"),
        "state": attrs.get("state") or attrs.get("prop_state") or prop_dna.get("state") or "已出现",
        "owner": attrs.get("owner") or attrs.get("holder"),
        "location": attrs.get("location"),
        "prop_dna": prop_dna,
        "source_entity_id": entity.get("id"),
        "last_changed_chapter_id": chapter.id,
        "last_changed_chapter_number": chapter.chapter_number,
        "evidence": _compact(entity.get("evidence") or entity.get("description"), 160),
    }


def _event_state(entity: Dict[str, Any], chapter: Chapter, sequence_fallback: int) -> Dict[str, Any]:
    attrs = _json_dict(entity.get("attributes"))
    return {
        "name": entity.get("name"),
        "status": attrs.get("status") or "occurred",
        "sequence": attrs.get("sequence") or sequence_fallback,
        "chapter_id": chapter.id,
        "chapter_number": chapter.chapter_number,
        "participants": _json_list(attrs.get("participants")),
        "location": attrs.get("location"),
        "prop_state_changes": _json_list(attrs.get("prop_state_changes")),
        "source_entity_id": entity.get("id"),
        "evidence": _compact(entity.get("evidence") or entity.get("description"), 180),
    }


def _merge_character_state(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = {**existing, **incoming}
    for key, placeholder in (("state", "已登场"), ("costume", "默认服装")):
        if incoming.get(key) == placeholder and existing.get(key):
            merged[key] = existing[key]
    if not incoming.get("visual_dna") and existing.get("visual_dna"):
        merged["visual_dna"] = existing["visual_dna"]
    if not incoming.get("relationships") and existing.get("relationships"):
        merged["relationships"] = existing["relationships"]
    for key in ("location", "goal"):
        if not incoming.get(key) and existing.get(key):
            merged[key] = existing[key]
    return merged


def _merge_scene_state(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = {**existing, **incoming}
    for key in ("time", "weather", "lighting", "layout"):
        if not incoming.get(key) and existing.get(key):
            merged[key] = existing[key]
    if not incoming.get("tags") and existing.get("tags"):
        merged["tags"] = existing["tags"]
    if not incoming.get("scene_dna") and existing.get("scene_dna"):
        merged["scene_dna"] = existing["scene_dna"]
    return merged


def _merge_prop_state(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = {**existing, **incoming}
    if incoming.get("state") == "已出现" and existing.get("state"):
        merged["state"] = existing["state"]
    for key in ("owner", "location"):
        if not incoming.get(key) and existing.get(key):
            merged[key] = existing[key]
    if not incoming.get("prop_dna") and existing.get("prop_dna"):
        merged["prop_dna"] = existing["prop_dna"]
    return merged


def _apply_event_prop_changes(
    event: Dict[str, Any],
    current_props: Dict[str, Dict[str, Any]],
    prop_flows: Dict[str, List[Dict[str, Any]]],
    issues: List[Dict[str, Any]],
) -> None:
    for change in event.get("prop_state_changes") or []:
        if not isinstance(change, dict):
            continue
        prop_name = str(change.get("prop") or change.get("name") or "").strip()
        if not prop_name:
            continue
        previous = current_props.get(prop_name)
        from_state = change.get("from")
        to_state = change.get("to") or change.get("state")
        owner = change.get("owner") or change.get("holder")
        if previous and from_state and previous.get("state") not in {from_state, to_state}:
            issues.append(
                {
                    "code": "prop_state_jump",
                    "severity": "warning",
                    "entity_type": "prop",
                    "name": prop_name,
                    "chapter_number": event.get("chapter_number"),
                    "message": f"道具状态从 {previous.get('state')} 变为 {to_state}，但事件声明来源状态为 {from_state}",
                }
            )
        updated = {
            **(previous or {"name": prop_name, "source_entity_id": None}),
            "state": to_state or (previous or {}).get("state") or "状态变化",
            "owner": owner or (previous or {}).get("owner"),
            "last_changed_chapter_id": event.get("chapter_id"),
            "last_changed_chapter_number": event.get("chapter_number"),
            "changed_by_event": event.get("name"),
        }
        current_props[prop_name] = updated
        prop_flows[prop_name].append(
            {
                "chapter_id": event.get("chapter_id"),
                "chapter_number": event.get("chapter_number"),
                "event": event.get("name"),
                "from": from_state,
                "to": updated.get("state"),
                "owner": updated.get("owner"),
            }
        )


def _build_issues(
    *,
    current_characters: Dict[str, Dict[str, Any]],
    current_scenes: Dict[str, Dict[str, Any]],
    current_props: Dict[str, Dict[str, Any]],
    event_timeline: List[Dict[str, Any]],
    chapters: List[Chapter],
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    character_names = set(current_characters.keys())
    prop_names = set(current_props.keys())

    if not current_characters:
        issues.append({"code": "missing_character_state", "severity": "blocking", "message": "状态机没有可用人物状态"})
    if not current_scenes:
        issues.append({"code": "missing_scene_state", "severity": "warning", "message": "状态机没有可用场景状态"})
    if not event_timeline:
        issues.append({"code": "missing_event_timeline", "severity": "warning", "message": "状态机没有可用事件线"})

    for name, state in current_characters.items():
        if not state.get("costume") or state.get("costume") == "默认服装":
            issues.append(
                {
                    "code": "missing_character_costume",
                    "severity": "warning",
                    "entity_type": "character",
                    "name": name,
                    "message": "角色缺少明确服装状态，跨集形象容易漂移",
                }
            )
        if not state.get("visual_dna"):
            issues.append(
                {
                    "code": "missing_character_visual_dna",
                    "severity": "warning",
                    "entity_type": "character",
                    "name": name,
                    "message": "角色缺少视觉 DNA，建议补齐发型、脸型、体型和服装",
                }
            )

    for name, state in current_scenes.items():
        if not state.get("weather") and not state.get("lighting") and not state.get("tags"):
            issues.append(
                {
                    "code": "missing_scene_state_detail",
                    "severity": "warning",
                    "entity_type": "scene",
                    "name": name,
                    "message": "场景缺少天气、光影或标签，跨镜头环境一致性不足",
                }
            )

    for name, state in current_props.items():
        if not state.get("prop_dna"):
            issues.append(
                {
                    "code": "missing_prop_dna",
                    "severity": "warning",
                    "entity_type": "prop",
                    "name": name,
                    "message": "道具缺少视觉 DNA，跨集形态难以锁定",
                }
            )

    last_sequence = -1
    for event in event_timeline:
        sequence = event.get("sequence") or 0
        if sequence < last_sequence:
            issues.append(
                {
                    "code": "event_sequence_regression",
                    "severity": "warning",
                    "entity_type": "event",
                    "name": event.get("name"),
                    "message": "事件序号出现倒退，可能影响剧情因果",
                }
            )
        last_sequence = max(last_sequence, sequence)
        for participant in event.get("participants") or []:
            if participant and participant not in character_names:
                issues.append(
                    {
                        "code": "unknown_event_participant",
                        "severity": "warning",
                        "entity_type": "event",
                        "name": event.get("name"),
                        "message": f"事件参与者未登记人物状态：{participant}",
                    }
                )
        for change in event.get("prop_state_changes") or []:
            if isinstance(change, dict):
                prop_name = change.get("prop") or change.get("name")
                if prop_name and prop_name not in prop_names:
                    issues.append(
                        {
                            "code": "unknown_event_prop",
                            "severity": "warning",
                            "entity_type": "event",
                            "name": event.get("name"),
                            "message": f"事件涉及道具未登记状态：{prop_name}",
                        }
                    )

    chapter_event_numbers = {event.get("chapter_number") for event in event_timeline}
    for chapter in chapters:
        if chapter.chapter_number not in chapter_event_numbers:
            issues.append(
                {
                    "code": "chapter_without_event",
                    "severity": "notice",
                    "chapter_id": chapter.id,
                    "chapter_number": chapter.chapter_number,
                    "message": f"第{chapter.chapter_number}章没有明确事件状态，建议补一个承上启下事件",
                }
            )

    return issues


def _episode_states(novel: Novel, state_machine: Dict[str, Any]) -> List[Dict[str, Any]]:
    series_plan = _json_dict(_json_dict(novel.extra_data).get("series_plan"))
    episodes = _json_list(series_plan.get("episodes"))
    if not episodes:
        return []
    snapshots = _json_list(state_machine.get("chapter_snapshots"))
    snapshots_by_id = {snapshot.get("chapter_id"): snapshot for snapshot in snapshots}
    result = []
    for episode in episodes:
        chapter_ids = episode.get("chapter_ids") or []
        episode_snapshots = [snapshots_by_id[chapter_id] for chapter_id in chapter_ids if chapter_id in snapshots_by_id]
        latest = episode_snapshots[-1] if episode_snapshots else {}
        result.append(
            {
                "episode_number": episode.get("episode_number"),
                "title": episode.get("title"),
                "chapter_ids": chapter_ids,
                "latest_chapter_number": latest.get("chapter_number"),
                "characters": latest.get("characters") or {},
                "props": latest.get("props") or {},
                "scenes": latest.get("scenes") or {},
                "events": latest.get("events") or [],
                "bridge": _json_dict(episode.get("narrative")).get("next_episode_bridge"),
            }
        )
    return result


async def build_story_state_machine(
    db: AsyncSession,
    user_id: str,
    *,
    story_bible_id: str,
    novel_id: Optional[str] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    story_bible = await _load_story_bible(db, user_id, story_bible_id)
    resolved_novel_id = novel_id or story_bible.novel_id
    if not resolved_novel_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Story Bible 未绑定小说，无法生成状态机")
    novel = await _load_novel(db, user_id, resolved_novel_id)

    chapter_result = await db.execute(
        select(Chapter)
        .where(and_(Chapter.user_id == user_id, Chapter.novel_id == novel.id))
        .order_by(Chapter.chapter_number, Chapter.created_at)
    )
    chapters = list(chapter_result.scalars().all())
    if not chapters:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="小说没有章节，无法生成状态机")

    entity_result = await db.execute(
        select(StoryEntity)
        .where(
            StoryEntity.user_id == user_id,
            or_(StoryEntity.novel_id == novel.id, StoryEntity.novel_id.is_(None)),
        )
        .order_by(StoryEntity.chapter_id, StoryEntity.entity_type, StoryEntity.updated_at)
    )
    entities = list(entity_result.scalars().all())

    known = {(entity.entity_type, entity.name, entity.chapter_id) for entity in entities}
    extracted_by_chapter: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for chapter in chapters:
        extracted = extract_story_entities(chapter.content or "", set(ENTITY_TYPES))
        for item in extracted:
            key_exact = (item.get("entity_type"), item.get("name"), chapter.id)
            key_global = (item.get("entity_type"), item.get("name"), None)
            if key_exact in known or key_global in known:
                continue
            extracted_by_chapter[chapter.id].append(_extracted_payload(item, chapter))

    current_characters: Dict[str, Dict[str, Any]] = {}
    current_scenes: Dict[str, Dict[str, Any]] = {}
    current_props: Dict[str, Dict[str, Any]] = {}
    character_timelines: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    scene_timelines: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    prop_flows: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    event_timeline: List[Dict[str, Any]] = []
    chapter_snapshots: List[Dict[str, Any]] = []
    event_counter = 1
    event_prop_issues: List[Dict[str, Any]] = []

    for chapter in chapters:
        grouped = _group_entities_for_chapter(entities, extracted_by_chapter, chapter)

        for entity in grouped.get("character", []):
            state = _character_state(entity, chapter)
            name = state.get("name")
            if not name:
                continue
            current_characters[name] = _merge_character_state(current_characters.get(name, {}), state)
            character_timelines[name].append(
                {
                    "chapter_id": chapter.id,
                    "chapter_number": chapter.chapter_number,
                    "state": state.get("state"),
                    "costume": state.get("costume"),
                    "location": state.get("location"),
                    "goal": state.get("goal"),
                    "evidence": state.get("evidence"),
                }
            )

        for entity in grouped.get("scene", []):
            state = _scene_state(entity, chapter)
            name = state.get("name")
            if not name:
                continue
            current_scenes[name] = _merge_scene_state(current_scenes.get(name, {}), state)
            scene_timelines[name].append(
                {
                    "chapter_id": chapter.id,
                    "chapter_number": chapter.chapter_number,
                    "time": state.get("time"),
                    "weather": state.get("weather"),
                    "lighting": state.get("lighting"),
                    "tags": state.get("tags"),
                    "evidence": state.get("evidence"),
                }
            )

        for entity in grouped.get("prop", []):
            state = _prop_state(entity, chapter)
            name = state.get("name")
            if not name:
                continue
            current_props[name] = _merge_prop_state(current_props.get(name, {}), state)
            prop_flows[name].append(
                {
                    "chapter_id": chapter.id,
                    "chapter_number": chapter.chapter_number,
                    "state": state.get("state"),
                    "owner": state.get("owner"),
                    "location": state.get("location"),
                    "evidence": state.get("evidence"),
                }
            )

        chapter_events = []
        for entity in grouped.get("event", []):
            event = _event_state(entity, chapter, event_counter)
            event_counter += 1
            event_timeline.append(event)
            chapter_events.append(event)
            _apply_event_prop_changes(event, current_props, prop_flows, event_prop_issues)

        chapter_snapshots.append(
            {
                "chapter_id": chapter.id,
                "chapter_number": chapter.chapter_number,
                "title": chapter.title,
                "characters": current_characters,
                "scenes": current_scenes,
                "props": current_props,
                "events": chapter_events,
                "summary": _compact(chapter.content, 220),
            }
        )

    issues = event_prop_issues + _build_issues(
        current_characters=current_characters,
        current_scenes=current_scenes,
        current_props=current_props,
        event_timeline=event_timeline,
        chapters=chapters,
    )

    generated_at = utc_now().isoformat()
    state_machine = {
        "version": 1,
        "story_bible_id": story_bible.id,
        "novel_id": novel.id,
        "novel_title": novel.title,
        "generated_at": generated_at,
        "updated_at": generated_at,
        "chapter_count": len(chapters),
        "summary": {
            "characters": len(current_characters),
            "scenes": len(current_scenes),
            "props": len(current_props),
            "events": len(event_timeline),
            "issues": len(issues),
        },
        "current_state": {
            "characters": current_characters,
            "scenes": current_scenes,
            "props": current_props,
            "events": event_timeline[-12:],
        },
        "character_timelines": dict(character_timelines),
        "scene_timelines": dict(scene_timelines),
        "prop_flows": dict(prop_flows),
        "event_timeline": sorted(
            event_timeline,
            key=lambda item: (item.get("chapter_number") or 0, item.get("sequence") or 0, item.get("name") or ""),
        ),
        "chapter_snapshots": chapter_snapshots,
        "rules": [
            "后续章节和分镜必须继承 current_state 中的人物、场景、道具和事件状态。",
            "角色服装、伤势、关系、目标发生变化时必须由事件或章节说明驱动。",
            "道具持有人、破损、能量、位置等状态不得无原因跳变。",
            "场景时间、天气、光影和空间布局变化必须保留转场或时间跳跃说明。",
        ],
        "issues": issues,
    }
    state_machine["episode_states"] = _episode_states(novel, state_machine)

    if persist:
        extra_data = dict(_json_dict(story_bible.extra_data))
        extra_data[STATE_MACHINE_KEY] = state_machine
        extra_data["character_states"] = current_characters
        extra_data["scene_states"] = current_scenes
        extra_data["prop_flows"] = dict(prop_flows)
        extra_data["event_state_machine"] = state_machine["event_timeline"]
        story_bible.extra_data = extra_data
        story_bible.updated_at = utc_now()
        flag_modified(story_bible, "extra_data")
        await db.commit()
        await db.refresh(story_bible)

    return state_machine


async def get_story_state_machine(
    db: AsyncSession,
    user_id: str,
    *,
    story_bible_id: str,
) -> Dict[str, Any]:
    story_bible = await _load_story_bible(db, user_id, story_bible_id)
    return _json_dict(_json_dict(story_bible.extra_data).get(STATE_MACHINE_KEY))


async def check_story_state_machine(
    db: AsyncSession,
    user_id: str,
    *,
    story_bible_id: str,
    novel_id: Optional[str] = None,
) -> Dict[str, Any]:
    state_machine = await get_story_state_machine(db, user_id, story_bible_id=story_bible_id)
    generated = False
    if not state_machine:
        state_machine = await build_story_state_machine(
            db,
            user_id,
            story_bible_id=story_bible_id,
            novel_id=novel_id,
            persist=False,
        )
        generated = True
    issues = _json_list(state_machine.get("issues"))
    return {
        "story_bible_id": story_bible_id,
        "novel_id": state_machine.get("novel_id") or novel_id,
        "generated_transient": generated,
        "issue_count": len(issues),
        "issues": issues,
        "summary": state_machine.get("summary") or {},
    }


def format_state_machine_summary(state_machine: Optional[Dict[str, Any]], *, limit: int = 6) -> str:
    if not state_machine:
        return ""
    current = _json_dict(state_machine.get("current_state"))
    parts = []
    characters = _json_dict(current.get("characters"))
    if characters:
        values = []
        for name, state in list(characters.items())[:limit]:
            values.append(f"{name}：{state.get('state') or '已登场'}，服装 {state.get('costume') or '未锁定'}")
        parts.append("人物状态：" + "；".join(values))
    props = _json_dict(current.get("props"))
    if props:
        values = []
        for name, state in list(props.items())[:limit]:
            owner = f"，持有人 {state.get('owner')}" if state.get("owner") else ""
            values.append(f"{name}：{state.get('state') or '已出现'}{owner}")
        parts.append("道具状态：" + "；".join(values))
    scenes = _json_dict(current.get("scenes"))
    if scenes:
        values = []
        for name, state in list(scenes.items())[:limit]:
            detail = "，".join(_uniq([state.get("weather"), state.get("lighting"), state.get("time")], 3))
            values.append(f"{name}：{detail or '环境待细化'}")
        parts.append("场景状态：" + "；".join(values))
    events = _json_list(state_machine.get("event_timeline"))
    if events:
        values = [f"第{event.get('chapter_number')}章 {event.get('name')}" for event in events[-limit:]]
        parts.append("最近事件：" + "；".join(values))
    return "\n".join(parts)
