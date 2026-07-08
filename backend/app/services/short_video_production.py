"""Short-video production planning and shot contract helpers."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_registry import get_task_default
from app.core.time_utils import utc_now
from app.models import Asset, Chapter, Novel, Script, Shot, StoryBible, StoryEntity, Storyboard, Workflow
from app.services.default_anime_library import ensure_default_anime_assets
from app.services.shot_quality_service import build_shot_quality_report, estimate_shot_generation_budget
from app.services.story_prompt_context import compact_text, load_story_prompt_context


SHORT_VIDEO_TASKS = [
    "chapter_writing",
    "script_generation",
    "storyboard_generation",
    "character_image",
    "scene_reference_image",
    "shot_video",
    "shot_audio_video",
    "tts_dialogue",
    "subtitle_generation",
    "final_synthesis",
]

FALLBACK_SHORT_VIDEO_ASPECT_RATIOS = [
    {"ratio": "9:16", "label": "竖屏短剧", "use_case": "红果短剧、抖音、快手、小红书"},
    {"ratio": "16:9", "label": "横屏预告", "use_case": "B站、YouTube、横屏宣传片"},
    {"ratio": "1:1", "label": "方形参考", "use_case": "角色头像、道具设定、社媒封面"},
    {"ratio": "3:4", "label": "竖构图参考", "use_case": "角色立绘、封面草图"},
    {"ratio": "4:3", "label": "经典镜头", "use_case": "复古、纪录感、场景设定"},
    {"ratio": "21:9", "label": "影院宽屏", "use_case": "电影感预告、大场景横移"},
]


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _names(items: Iterable[Any], limit: int = 6) -> List[str]:
    values: List[str] = []
    for item in items:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("title") or item.get("character_name") or "").strip()
        else:
            name = str(item or "").strip()
        if name and name not in values:
            values.append(name)
        if len(values) >= limit:
            break
    return values


def _task_route(task: str) -> Optional[Dict[str, Any]]:
    default = get_task_default(task)
    if not default:
        return None
    model = default.get("default_model") or {}
    return {
        "task": task,
        "display_name": default.get("display_name") or task,
        "default_model_id": default.get("default_model_id"),
        "fallback_model_ids": default.get("fallback_model_ids") or [],
        "required_capabilities": default.get("required_capabilities") or [],
        "model": {
            "id": model.get("id"),
            "provider_id": model.get("provider_id"),
            "api_model_id": model.get("api_model_id"),
            "display_name": model.get("display_name"),
            "modality": model.get("modality"),
            "capabilities": model.get("capabilities") or [],
            "status": model.get("status") or {},
        },
        "reason": _route_reason(task, model),
    }


def _route_reason(task: str, model: Dict[str, Any]) -> str:
    name = model.get("display_name") or model.get("id") or "默认模型"
    reasons = {
        "chapter_writing": "长上下文文本模型用于承接前后章节、人物状态和事件因果。",
        "script_generation": "结构化文本模型用于把章节改编成可分镜的短剧剧本。",
        "storyboard_generation": "结构化输出模型用于生成镜头、对白、运镜和字幕草稿。",
        "character_image": "图像模型用于角色定稿图和多角度参考。",
        "scene_reference_image": "图像模型用于场景空间、天气和光影参考。",
        "shot_video": "静音视频模型适合先锁定画面运动和镜头一致性。",
        "shot_audio_video": "直生音视频模型适合短视频草稿、对白音效和字幕同步。",
        "tts_dialogue": "语音模型用于角色音色一致的对白配音。",
        "subtitle_generation": "字幕模型或本地导出器用于生成可审阅字幕轨。",
        "final_synthesis": "合成执行器用于按时间线混音、字幕和导出。",
    }
    return f"{name}：{reasons.get(task, '按任务能力要求选择默认模型。')}"


def build_short_video_model_route() -> Dict[str, Any]:
    routes = {}
    for task in SHORT_VIDEO_TASKS:
        route = _task_route(task)
        if route:
            routes[task] = route
    return routes


def _safe_target_duration(target_duration_seconds: int) -> int:
    return max(30, min(90, int(target_duration_seconds or 60)))


def _build_rhythm(target_duration_seconds: int) -> List[Dict[str, Any]]:
    duration = _safe_target_duration(target_duration_seconds)
    ranges = [
        (0.0, 0.05, "opening_hook", "开场钩子", "3 秒内抛出反常画面、强情绪或关键台词"),
        (0.05, 0.25, "setup", "人物处境", "快速交代主角状态、地点和即时目标"),
        (0.25, 0.50, "conflict_escalation", "冲突升级", "让阻碍变强，推动角色做选择"),
        (0.50, 0.78, "payoff_or_reversal", "爽点/反转", "给出动作、线索或关系反转"),
        (0.78, 1.0, "cliffhanger", "结尾悬念", "留下未解决问题或下一集承接钩子"),
    ]
    beats = []
    for start_ratio, end_ratio, code, label, goal in ranges:
        start = round(duration * start_ratio, 1)
        end = round(duration * end_ratio, 1)
        beats.append({
            "code": code,
            "label": label,
            "start_seconds": start,
            "end_seconds": max(start + 1, end),
            "goal": goal,
        })
    return beats


def _first_name(items: Iterable[Any], fallback: str) -> str:
    names = _names(items, 1)
    return names[0] if names else fallback


def _episode_plan_from_context(
    context: Dict[str, Any],
    *,
    target_duration_seconds: int,
    aspect_ratio: str,
    style: Optional[str],
) -> Dict[str, Any]:
    protagonist = _first_name(context.get("characters") or [], "主角")
    scene = _first_name(context.get("scenes") or [], "核心场景")
    prop = _first_name(context.get("props") or [], "关键道具")
    event = _first_name(context.get("events") or [], "关键事件")
    chapter_title = context.get("chapter_title") or "当前章节"
    duration = _safe_target_duration(target_duration_seconds)

    return {
        "title": f"《{context.get('title') or '未命名小说'}》{chapter_title}短视频出片规划",
        "format": {
            "target_duration_seconds": duration,
            "aspect_ratio": aspect_ratio or "9:16",
            "priority": "vertical_short_drama",
            "style": style or context.get("style") or "anime",
            "target_window_seconds": [30, 90],
        },
        "narrative_control": {
            "hook": f"前 3 秒用{scene}中的异常变化或{prop}特写抓住注意力。",
            "conflict": f"{protagonist}围绕{event}遭遇直接阻碍，目标必须清晰。",
            "turning_point": f"让{prop}或人物关系发生可见变化，形成爽点或反转。",
            "cliffhanger": "结尾保留一个未解决动作、危险信号或关键对白，承接下一条短视频。",
            "next_episode_bridge": "下一集从悬念结果开场，不重复解释已发生事件。",
        },
        "emotional_curve": [
            {"beat": "hook", "emotion": "紧张/好奇", "intensity": 0.75},
            {"beat": "conflict", "emotion": "压迫/对抗", "intensity": 0.85},
            {"beat": "turning_point", "emotion": "惊讶/释放", "intensity": 0.9},
            {"beat": "cliffhanger", "emotion": "悬念/期待", "intensity": 0.8},
        ],
        "shot_rhythm": _build_rhythm(duration),
        "story_context": {
            "novel_id": context.get("novel_id"),
            "chapter_id": context.get("chapter_id"),
            "story_bible_id": context.get("story_bible_id"),
            "title": context.get("title"),
            "chapter_title": context.get("chapter_title"),
            "genre": context.get("genre"),
            "characters": _names(context.get("characters") or [], 8),
            "scenes": _names(context.get("scenes") or [], 6),
            "props": _names(context.get("props") or [], 6),
            "events": _names(context.get("events") or [], 6),
        },
        "model_route": build_short_video_model_route(),
        "rules": [
            "优先 9:16 竖屏构图，人物脸部和关键道具必须在移动端可读。",
            "每个镜头必须能追溯到小说、章节、剧本、分镜、镜头、实体和字幕。",
            "同一角色的脸型、发型、服装、音色和口吻不能无原因变化。",
            "道具状态变化必须由事件驱动，并在后续镜头继承。",
        ],
    }


async def build_short_episode_plan(
    db: AsyncSession,
    user_id: str,
    *,
    novel_id: str,
    chapter_id: Optional[str] = None,
    target_duration_seconds: int = 60,
    aspect_ratio: str = "9:16",
    style: Optional[str] = None,
) -> Dict[str, Any]:
    context = await load_story_prompt_context(
        db,
        user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        style=style,
    )
    if not context.get("novel_id"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="小说不存在")
    return _episode_plan_from_context(
        context,
        target_duration_seconds=target_duration_seconds,
        aspect_ratio=aspect_ratio,
        style=style,
    )


async def _load_story_bible(
    db: AsyncSession,
    user_id: str,
    novel_id: Optional[str],
) -> Optional[StoryBible]:
    if not novel_id:
        return None
    result = await db.execute(
        select(StoryBible)
        .where(StoryBible.user_id == user_id, StoryBible.novel_id == novel_id)
        .order_by(desc(StoryBible.updated_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _load_entities(
    db: AsyncSession,
    user_id: str,
    *,
    novel_id: Optional[str],
    chapter_id: Optional[str],
) -> List[StoryEntity]:
    if not novel_id:
        return []
    query = select(StoryEntity).where(StoryEntity.user_id == user_id, StoryEntity.novel_id == novel_id)
    if chapter_id:
        query = query.where((StoryEntity.chapter_id == chapter_id) | (StoryEntity.chapter_id.is_(None)))
    result = await db.execute(query.order_by(StoryEntity.entity_type, desc(StoryEntity.updated_at)))
    return list(result.scalars().all())


def _entity_to_ref(entity: StoryEntity) -> Dict[str, Any]:
    attrs = _json_dict(entity.attributes)
    return {
        "entity_id": entity.id,
        "entity_type": entity.entity_type,
        "name": entity.name,
        "description": entity.description,
        "aliases": entity.aliases or [],
        "attributes": attrs,
        "visual_dna": attrs.get("visual_dna") or attrs.get("scene_dna") or attrs.get("prop_dna") or {},
        "asset_pack": attrs.get("asset_pack") or attrs.get("reference_assets") or attrs.get("scene_assets") or attrs.get("prop_assets") or {},
    }


def _asset_view_key(asset: Asset) -> Optional[str]:
    params = _json_dict(asset.generation_params)
    value = params.get("view_key") or params.get("asset_subtype") or params.get("view_angle")
    return str(value).strip() if value else None


def _flatten_grouped_entity_ids(grouped_refs: Dict[str, List[Dict[str, Any]]]) -> set[str]:
    entity_ids: set[str] = set()
    for refs in grouped_refs.values():
        for ref in refs:
            entity_id = str(ref.get("entity_id") or "").strip()
            if entity_id:
                entity_ids.add(entity_id)
    return entity_ids


async def _load_locked_assets_for_refs(
    db: AsyncSession,
    user_id: str,
    grouped_refs: Dict[str, List[Dict[str, Any]]],
) -> List[Asset]:
    entity_ids = _flatten_grouped_entity_ids(grouped_refs)
    if not entity_ids:
        return []
    result = await db.execute(
        select(Asset)
        .where(
            Asset.user_id == user_id,
            Asset.entity_id.in_(entity_ids),
            Asset.is_active == True,
            Asset.is_locked == True,
            Asset.is_final == True,
        )
        .order_by(Asset.entity_type, Asset.entity_id, Asset.version.desc(), Asset.updated_at.desc())
    )
    return list(result.scalars().all())


def _asset_lock_items(assets: List[Asset]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for asset in assets:
        view_key = _asset_view_key(asset) or "main"
        key = (str(asset.entity_id or ""), str(asset.entity_type or asset.category or ""), view_key)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "asset_id": asset.id,
                "entity_id": asset.entity_id,
                "entity_type": asset.entity_type or asset.category,
                "name": asset.name,
                "view_key": view_key,
                "url": asset.url,
                "version": asset.version or 1,
                "is_locked": bool(asset.is_locked),
                "is_final": bool(asset.is_final),
                "source": "locked_entity_asset",
            }
        )
    return items


def _character_multiview_refs_from_assets(assets: List[Asset]) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for asset in assets:
        entity_type = asset.entity_type or asset.category
        if entity_type != "character":
            continue
        view_key = _asset_view_key(asset)
        if view_key not in {"front", "side", "back", "full_body"}:
            continue
        if not asset.url:
            continue
        key = (str(asset.entity_id or ""), view_key)
        if key in seen:
            continue
        seen.add(key)
        refs.append(
            {
                "asset_id": asset.id,
                "entity_id": asset.entity_id,
                "character_id": asset.character_id,
                "character": asset.name,
                "view_key": view_key,
                "url": asset.url,
                "version": asset.version or 1,
                "source": "locked_entity_asset",
            }
        )
    return refs


def _group_entities_for_shot(
    entities: List[StoryEntity],
    shot: Shot,
    existing_refs: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    grouped = {
        "characters": list(_json_list(existing_refs.get("characters"))),
        "scenes": list(_json_list(existing_refs.get("scenes"))),
        "props": list(_json_list(existing_refs.get("props"))),
        "events": list(_json_list(existing_refs.get("events"))),
    }
    if all(grouped.values()):
        return grouped

    text = " ".join(
        value
        for value in [shot.prompt, shot.dialogue, shot.visual_description, shot.music_cue, shot.sfx_cue]
        if value
    )
    mapping = {"character": "characters", "scene": "scenes", "prop": "props", "event": "events"}
    for entity_type, target_key in mapping.items():
        if grouped[target_key]:
            continue
        typed = [entity for entity in entities if entity.entity_type == entity_type]
        matched = [
            entity for entity in typed
            if entity.name and entity.name in text
            or any(alias and alias in text for alias in (entity.aliases or []))
        ]
        selected = matched or typed[:1]
        grouped[target_key] = [_entity_to_ref(entity) for entity in selected[:3]]
    return grouped


async def _resolve_shot_lineage(
    db: AsyncSession,
    user_id: str,
    shot_id: str,
) -> Dict[str, Any]:
    result = await db.execute(select(Shot).where(and_(Shot.id == shot_id, Shot.user_id == user_id)))
    shot = result.scalar_one_or_none()
    if shot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="镜头不存在")

    storyboard_result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == shot.storyboard_id, Storyboard.user_id == user_id))
    )
    storyboard = storyboard_result.scalar_one_or_none()
    if storyboard is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分镜不存在")

    script_result = await db.execute(
        select(Script).where(and_(Script.id == storyboard.script_id, Script.user_id == user_id))
    )
    script = script_result.scalar_one_or_none()

    storyboard_content = _json_dict(storyboard.content)
    script_extra = _json_dict(script.extra_data) if script else {}
    chapter_id = storyboard_content.get("chapter_id") or script_extra.get("chapter_id")
    novel_id = storyboard.novel_id or (script.novel_id if script else None)

    chapter = None
    if chapter_id:
        chapter_result = await db.execute(select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id)))
        chapter = chapter_result.scalar_one_or_none()
        if chapter:
            novel_id = novel_id or chapter.novel_id

    novel = None
    if novel_id:
        novel_result = await db.execute(select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id)))
        novel = novel_result.scalar_one_or_none()

    shots_result = await db.execute(
        select(Shot)
        .where(and_(Shot.storyboard_id == storyboard.id, Shot.user_id == user_id))
        .order_by(Shot.shot_number)
    )
    storyboard_shots = list(shots_result.scalars().all())
    return {
        "shot": shot,
        "storyboard": storyboard,
        "script": script,
        "chapter": chapter,
        "novel": novel,
        "storyboard_shots": storyboard_shots,
        "novel_id": novel_id,
        "chapter_id": chapter_id,
    }


def _stable_seed(*values: Any) -> int:
    text = "|".join(str(value) for value in values if value)
    if not text:
        text = utc_now().isoformat()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _shot_role(shot: Shot, ordered_shots: List[Shot]) -> Dict[str, Any]:
    total = max(1, len(ordered_shots))
    index = next((idx for idx, item in enumerate(ordered_shots, start=1) if item.id == shot.id), shot.shot_number or 1)
    if index == 1:
        role = "opening_hook"
        label = "开场钩子"
    elif index == total:
        role = "cliffhanger"
        label = "结尾悬念"
    elif index <= max(2, total // 3):
        role = "setup"
        label = "人物处境"
    elif index <= max(3, total * 2 // 3):
        role = "conflict_escalation"
        label = "冲突升级"
    else:
        role = "payoff_or_reversal"
        label = "爽点/反转"
    return {
        "code": role,
        "label": label,
        "shot_index": index,
        "shot_count": total,
        "goal": {
            "opening_hook": "3 秒内用强画面、强情绪或关键对白抓住注意力。",
            "setup": "快速交代人物目标、地点和关系。",
            "conflict_escalation": "放大阻碍，推动人物选择和事件因果。",
            "payoff_or_reversal": "兑现动作、线索或关系反转。",
            "cliffhanger": "留下下一镜头或下一集必须承接的问题。",
        }[role],
    }


def _story_bible_state(story_bible: Optional[StoryBible]) -> Dict[str, Any]:
    if not story_bible:
        return {
            "story_bible_id": None,
            "status": "missing",
            "rules": [],
            "state_maps": {},
        }
    extra = _json_dict(story_bible.extra_data)
    return {
        "story_bible_id": story_bible.id,
        "status": "available",
        "style": story_bible.style,
        "worldview": compact_text(story_bible.worldview, 700),
        "negative_prompt": compact_text(story_bible.negative_prompt, 300),
        "rules": {
            "characters": story_bible.character_rules or [],
            "scenes": story_bible.scene_rules or [],
            "props": story_bible.prop_rules or [],
            "events": story_bible.event_timeline or [],
        },
        "state_maps": {
            "character_states": extra.get("character_states") or {},
            "costume_states": extra.get("costume_states") or {},
            "prop_flows": extra.get("prop_flows") or {},
            "scene_states": extra.get("scene_states") or {},
            "forbidden_changes": extra.get("forbidden_changes") or [],
        },
    }


def _build_contract_issues(
    shot: Shot,
    grouped_refs: Dict[str, List[Dict[str, Any]]],
    production_context: Dict[str, Any],
    story_bible: Optional[StoryBible],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    blockers: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    extra = _json_dict(shot.extra_data)

    if not (shot.prompt or "").strip() and not (shot.visual_description or "").strip():
        blockers.append({"code": "missing_visual_prompt", "message": "缺少镜头提示词和视觉描述，无法稳定生成视频。"})
    if not (shot.dialogue or extra.get("subtitle_text") or "").strip():
        blockers.append({"code": "missing_subtitle", "message": "短视频出片要求字幕一等公民，当前镜头缺少对白或字幕文本。"})
    if not grouped_refs["characters"]:
        warnings.append({"code": "missing_character_refs", "message": "镜头未绑定人物角色，人物一致性不可控。"})
    if not grouped_refs["scenes"]:
        warnings.append({"code": "missing_scene_refs", "message": "镜头未绑定场景环境，空间、天气和光影承接较弱。"})
    if not grouped_refs["props"]:
        warnings.append({"code": "missing_prop_refs", "message": "镜头未绑定关键道具，道具状态流转不可追踪。"})
    if not grouped_refs["events"]:
        warnings.append({"code": "missing_event_refs", "message": "镜头未绑定事件，剧情因果承接较弱。"})
    if not story_bible:
        warnings.append({"code": "missing_story_bible", "message": "当前小说缺少 Story Bible，建议先生成或同步一致性设定。"})
    if not _json_list(production_context.get("asset_version_locks")):
        warnings.append({"code": "missing_asset_locks", "message": "未锁定角色/场景/道具参考资产版本，重生成可能漂移。"})
    if not _json_list(production_context.get("character_multiview_refs")):
        warnings.append({"code": "missing_multiview_refs", "message": "未提供角色多视图参考，多镜头人物外观一致性较弱。"})
    if not _json_list(shot.keyframes or production_context.get("keyframes")):
        warnings.append({"code": "missing_keyframes", "message": "未设置关键帧，建议至少补 start/end 画面锚点。"})
    if int(shot.duration or 0) < 3 or int(shot.duration or 0) > 10:
        warnings.append({"code": "short_video_duration_out_of_range", "message": "短视频镜头建议控制在 3-10 秒，便于节奏和模型稳定。"})
    return blockers, warnings


def _issue_recommendations(blockers: List[Dict[str, Any]], warnings: List[Dict[str, Any]]) -> List[str]:
    codes = {issue.get("code") for issue in blockers + warnings}
    recommendations: List[str] = []
    if "missing_story_bible" in codes:
        recommendations.append("先在 Story Bible 生成/同步小说设定，再刷新镜头合约。")
    if "missing_character_refs" in codes:
        recommendations.append("从当前小说/章节提取角色，并把角色绑定到分镜镜头。")
    if "missing_asset_locks" in codes or "missing_multiview_refs" in codes:
        recommendations.append("为主要角色、场景和道具生成参考图，并在镜头生产上下文中锁定版本。")
    if "missing_subtitle" in codes:
        recommendations.append("补齐镜头对白或字幕文本，视频生成后才能稳定导出字幕轨。")
    if "missing_keyframes" in codes:
        recommendations.append("补充 start/end 关键帧，必要时添加角色近景或道具特写帧。")
    if not recommendations:
        recommendations.append("镜头合约已具备生产输入，可进入视频/直生音视频生成。")
    return recommendations


async def build_shot_production_contract(
    db: AsyncSession,
    user_id: str,
    shot_id: str,
) -> Dict[str, Any]:
    lineage = await _resolve_shot_lineage(db, user_id, shot_id)
    shot: Shot = lineage["shot"]
    storyboard: Storyboard = lineage["storyboard"]
    script: Optional[Script] = lineage["script"]
    chapter: Optional[Chapter] = lineage["chapter"]
    novel: Optional[Novel] = lineage["novel"]
    novel_id = lineage["novel_id"]
    chapter_id = lineage["chapter_id"]

    story_bible = await _load_story_bible(db, user_id, novel_id)
    entities = await _load_entities(db, user_id, novel_id=novel_id, chapter_id=chapter_id)
    extra = _json_dict(shot.extra_data)
    production_context = _json_dict(extra.get("production_context"))
    existing_refs = _json_dict(extra.get("entity_refs"))
    grouped_refs = _group_entities_for_shot(entities, shot, existing_refs)
    locked_assets = await _load_locked_assets_for_refs(db, user_id, grouped_refs)
    derived_asset_locks = _asset_lock_items(locked_assets)
    derived_multiview_refs = _character_multiview_refs_from_assets(locked_assets)
    effective_production_context = {
        **production_context,
        "asset_version_locks": production_context.get("asset_version_locks") or derived_asset_locks,
        "character_multiview_refs": production_context.get("character_multiview_refs") or derived_multiview_refs,
    }
    blockers, warnings = _build_contract_issues(shot, grouped_refs, effective_production_context, story_bible)
    quality_report = build_shot_quality_report(shot)
    budget_estimate = estimate_shot_generation_budget(shot)
    seed = production_context.get("seed") or extra.get("seed") or _stable_seed(
        novel_id,
        chapter_id,
        storyboard.id,
        shot.id,
        shot.prompt,
        shot.dialogue,
    )

    contract = {
        "contract_version": "short-video-v1",
        "generated_at": utc_now().isoformat(),
        "lineage": {
            "novel_id": novel_id,
            "novel_title": novel.title if novel else None,
            "chapter_id": chapter_id,
            "chapter_title": chapter.title if chapter else None,
            "chapter_number": chapter.chapter_number if chapter else None,
            "script_id": script.id if script else None,
            "script_title": script.title if script else None,
            "storyboard_id": storyboard.id,
            "storyboard_title": storyboard.title,
            "storyboard_style": storyboard.style,
            "storyboard_genre": storyboard.genre,
            "shot_id": shot.id,
            "shot_number": shot.shot_number or 1,
        },
        "short_video_role": _shot_role(shot, lineage["storyboard_shots"]),
        "characters": grouped_refs["characters"],
        "scenes": grouped_refs["scenes"],
        "props": grouped_refs["props"],
        "events": grouped_refs["events"],
        "dialogue_subtitle": {
            "dialogue": shot.dialogue,
            "subtitle_text": extra.get("subtitle_text") or shot.dialogue,
            "duration_seconds": shot.duration or 4,
            "subtitle_required": True,
        },
        "visual_controls": {
            "prompt": shot.prompt,
            "visual_description": shot.visual_description,
            "camera_angle": shot.camera_angle,
            "camera_movement": shot.camera_movement,
            "emotion": shot.emotion,
            "lighting": shot.lighting,
            "color_grading": shot.color_grading,
            "music_cue": shot.music_cue,
            "sfx_cue": shot.sfx_cue,
            "ambient_sound": shot.ambient_sound,
            "keyframes": shot.keyframes or effective_production_context.get("keyframes") or [],
        },
        "asset_locks": effective_production_context.get("asset_version_locks") or [],
        "character_multiview_refs": effective_production_context.get("character_multiview_refs") or [],
        "lip_sync": effective_production_context.get("lip_sync") or {},
        "review_state": effective_production_context.get("review_state") or "pending_review",
        "seed": seed,
        "model_route": build_short_video_model_route(),
        "story_bible_state": _story_bible_state(story_bible),
        "continuity_rules": [
            "人物身份、脸型、发型、服装、音色和说话口吻必须继承 Story Bible 与角色资产。",
            "场景空间、天气、光影和时间变化必须在镜头说明或转场中解释。",
            "道具外观和归属状态必须承接事件时间线，不允许无原因消失或变形。",
            "字幕文本必须与镜头对白、TTS/直生音频含义一致。",
        ],
        "quality_report": quality_report,
        "budget_estimate": budget_estimate,
        "blocking_issues": blockers,
        "warnings": warnings,
        "recommendations": _issue_recommendations(blockers, warnings),
        "status": "blocked" if blockers else ("warning" if warnings else "ready"),
    }
    return contract


def persist_contract_to_shot(shot: Shot, contract: Dict[str, Any]) -> None:
    extra = dict(_json_dict(shot.extra_data))
    production_context = dict(_json_dict(extra.get("production_context")))
    production_context["production_contract"] = contract
    production_context["seed"] = contract.get("seed")
    production_context["review_state"] = production_context.get("review_state") or "pending_review"
    production_context["updated_at"] = utc_now().isoformat()
    extra["production_context"] = production_context
    extra["quality_report"] = contract.get("quality_report")
    extra["budget_estimate"] = contract.get("budget_estimate")
    shot.extra_data = extra
    shot.updated_at = utc_now()


async def _workflow_shots(db: AsyncSession, workflow: Workflow, user_id: str) -> List[Shot]:
    if not workflow.storyboard_id:
        return []
    result = await db.execute(
        select(Shot)
        .where(and_(Shot.storyboard_id == workflow.storyboard_id, Shot.user_id == user_id))
        .order_by(Shot.shot_number)
    )
    return list(result.scalars().all())


def _summarize_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "shot_id": contract["lineage"]["shot_id"],
        "shot_number": contract["lineage"]["shot_number"],
        "status": contract["status"],
        "role": contract["short_video_role"],
        "characters": _names(contract.get("characters") or [], 5),
        "scenes": _names(contract.get("scenes") or [], 3),
        "props": _names(contract.get("props") or [], 4),
        "events": _names(contract.get("events") or [], 4),
        "subtitle_text": contract.get("dialogue_subtitle", {}).get("subtitle_text"),
        "asset_lock_count": len(contract.get("asset_locks") or []),
        "warning_count": len(contract.get("warnings") or []),
        "blocking_issue_count": len(contract.get("blocking_issues") or []),
        "recommendations": contract.get("recommendations") or [],
    }


def _asset_matches_key(asset: Asset, key: str) -> bool:
    source_url = str(asset.source_url or "")
    params = _json_dict(asset.generation_params)
    return source_url == f"starter:{key}" or params.get("starter_library_key") == key


def _asset_base_summary(asset: Optional[Asset]) -> Optional[Dict[str, Any]]:
    if not asset:
        return None
    shot_template = _json_dict(asset.shot_template)
    views = _json_list(shot_template.get("views"))
    return {
        "id": asset.id,
        "name": asset.name,
        "category": asset.category,
        "asset_type": asset.asset_type,
        "description": asset.description,
        "url": asset.url,
        "thumbnail_url": asset.thumbnail_url or asset.url,
        "source_url": asset.source_url,
        "tags": _json_list(asset.tags),
        "style_tags": _json_list(asset.style_tags),
        "prompt_template": asset.prompt_template,
        "variables": _json_list(asset.variables),
        "shot_template": shot_template,
        "view_count": shot_template.get("view_count") or len(views),
        "views": views,
        "recommended_aspect_ratio": shot_template.get("recommended_aspect_ratio"),
        "locked_fields": _json_list(shot_template.get("locked_fields")),
    }


def _build_aspect_ratio_options(aspect_asset: Optional[Asset], selected_aspect_ratio: str) -> List[Dict[str, Any]]:
    shot_template = _json_dict(aspect_asset.shot_template) if aspect_asset else {}
    raw_ratios = _json_list(shot_template.get("aspect_ratios")) or FALLBACK_SHORT_VIDEO_ASPECT_RATIOS
    selected_ratio = selected_aspect_ratio or shot_template.get("default_ratio") or "9:16"
    options: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_ratios:
        if isinstance(item, dict):
            ratio = str(item.get("ratio") or "").strip()
            label = str(item.get("label") or ratio).strip()
            use_case = str(item.get("use_case") or "").strip()
        else:
            ratio = str(item or "").strip()
            label = ratio
            use_case = ""
        if not ratio or ratio in seen:
            continue
        seen.add(ratio)
        options.append({
            "ratio": ratio,
            "label": label,
            "use_case": use_case,
            "selected": ratio == selected_ratio,
        })
    if selected_ratio and selected_ratio not in seen:
        options.insert(0, {
            "ratio": selected_ratio,
            "label": selected_ratio,
            "use_case": "当前自定义画幅",
            "selected": True,
        })
    return options


def _style_reference_summary(asset: Asset, selected_style_asset_id: Optional[str]) -> Dict[str, Any]:
    shot_template = _json_dict(asset.shot_template)
    return {
        "id": asset.id,
        "name": asset.name,
        "description": asset.description,
        "url": asset.url,
        "thumbnail_url": asset.thumbnail_url or asset.url,
        "prompt_template": asset.prompt_template,
        "prompt_summary": compact_text(asset.prompt_template or asset.description or "", 120),
        "tags": _json_list(asset.tags),
        "style_tags": _json_list(asset.style_tags),
        "recommended_aspect_ratios": _json_list(shot_template.get("recommended_aspect_ratios")),
        "best_for": _json_list(shot_template.get("best_for")),
        "avoid": _json_list(shot_template.get("avoid")),
        "selected": bool(selected_style_asset_id and asset.id == selected_style_asset_id),
    }


async def build_short_video_production_presets(
    db: AsyncSession,
    user_id: str,
    *,
    selected_aspect_ratio: str = "9:16",
    selected_style_asset_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Load editable starter assets that guide short-video consistency work."""
    await ensure_default_anime_assets(db, user_id)
    result = await db.execute(
        select(Asset)
        .where(
            Asset.is_active.is_(True),
            Asset.category.in_(["style", "aspect_ratio", "character", "scene", "prop"]),
            or_(Asset.user_id == user_id, Asset.is_public.is_(True)),
        )
        .order_by(Asset.category, desc(Asset.updated_at))
    )
    assets = list(result.scalars().all())

    character_template = next((asset for asset in assets if _asset_matches_key(asset, "asset-character-three-view-template")), None)
    scene_template = next((asset for asset in assets if _asset_matches_key(asset, "asset-scene-four-view-template")), None)
    prop_template = next((asset for asset in assets if _asset_matches_key(asset, "asset-prop-multiview-dna-template")), None)
    aspect_asset = next((asset for asset in assets if _asset_matches_key(asset, "asset-short-video-aspect-ratio-preset")), None)
    style_assets = [
        asset
        for asset in assets
        if asset.category == "style"
        and (
            "style-reference" in _json_list(asset.style_tags)
            or str(asset.source_url or "").startswith("starter:asset-style-")
        )
    ]

    style_references = [_style_reference_summary(asset, selected_style_asset_id) for asset in style_assets]
    selected_style = next((item for item in style_references if item["selected"]), None)
    return {
        "selected": {
            "aspect_ratio": selected_aspect_ratio or "9:16",
            "style_asset_id": selected_style_asset_id,
            "style_name": selected_style.get("name") if selected_style else None,
            "style_prompt": selected_style.get("prompt_template") if selected_style else None,
        },
        "aspect_ratios": _build_aspect_ratio_options(aspect_asset, selected_aspect_ratio),
        "style_references": style_references,
        "consistency_templates": {
            "character_three_view": _asset_base_summary(character_template),
            "scene_multi_view": _asset_base_summary(scene_template),
            "prop_multi_view": _asset_base_summary(prop_template),
        },
        "guidance": [
            "先为主角、反派和重要配角生成三视图定稿，再进入分镜和视频生成。",
            "核心场景使用四视图锁定入口、主视角、反打和俯视关系，减少跨镜头空间漂移。",
            "关键道具用多视图视觉 DNA 记录材质、纹路、状态变化和归属。",
            "整集选择一张风格图作为画面锚点，所有镜头共享风格提示词和画幅安全区。",
        ],
    }


async def build_workflow_short_video_readiness(
    db: AsyncSession,
    user_id: str,
    workflow_id: str,
    *,
    target_duration_seconds: int = 60,
    aspect_ratio: str = "9:16",
    style_asset_id: Optional[str] = None,
) -> Dict[str, Any]:
    result = await db.execute(select(Workflow).where(and_(Workflow.id == workflow_id, Workflow.user_id == user_id)))
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    production_presets = await build_short_video_production_presets(
        db,
        user_id,
        selected_aspect_ratio=aspect_ratio,
        selected_style_asset_id=style_asset_id,
    )
    episode_plan = None
    if workflow.novel_id:
        episode_plan = await build_short_episode_plan(
            db,
            user_id,
            novel_id=workflow.novel_id,
            chapter_id=workflow.chapter_id,
            target_duration_seconds=target_duration_seconds,
            aspect_ratio=aspect_ratio,
            style=production_presets.get("selected", {}).get("style_name"),
        )

    shots = await _workflow_shots(db, workflow, user_id)
    contracts = [await build_shot_production_contract(db, user_id, shot.id) for shot in shots]
    total_duration = sum(int(getattr(shot, "duration", 0) or 0) for shot in shots)
    blockers = [issue for contract in contracts for issue in contract.get("blocking_issues") or []]
    warnings = [issue for contract in contracts for issue in contract.get("warnings") or []]
    if workflow.storyboard_id and not shots:
        blockers.append({
            "code": "missing_shots",
            "message": "当前分镜下没有镜头，无法进入短视频生成和连续成片。",
        })
    missing_contract_count = 0
    for shot in shots:
        production_context = _json_dict(_json_dict(shot.extra_data).get("production_context"))
        if not production_context.get("production_contract"):
            missing_contract_count += 1

    recommendations = []
    if not workflow.novel_id or not workflow.chapter_id or not workflow.storyboard_id:
        recommendations.append("先绑定小说、章节和分镜，短视频一致性检查才能完整执行。")
    if workflow.storyboard_id and not shots:
        recommendations.append("先生成或创建镜头，再刷新生产合约并进入批量视频/音频生成。")
    if missing_contract_count:
        recommendations.append("刷新镜头生产合约，把人物、场景、道具、事件、字幕和模型路线锁到每个镜头。")
    if blockers:
        recommendations.append("先处理阻断项，再进入批量视频或直生音视频生成。")
    if total_duration and (total_duration < 30 or total_duration > 90):
        recommendations.append("调整镜头数量或时长，把单集总时长控制在 30-90 秒。")
    if not recommendations:
        recommendations.append("短视频出片链路已就绪，可进入批量生成和合成预检。")

    return {
        "workflow_id": workflow.id,
        "episode_plan": episode_plan,
        "summary": {
            "ready": bool(shots) and not blockers and total_duration >= 30 and total_duration <= 90,
            "shot_count": len(shots),
            "estimated_duration_seconds": total_duration,
            "target_duration_seconds": _safe_target_duration(target_duration_seconds),
            "aspect_ratio": aspect_ratio,
            "blocking_issue_count": len(blockers),
            "warning_count": len(warnings),
            "missing_contract_count": missing_contract_count,
        },
        "contracts": [_summarize_contract(contract) for contract in contracts],
        "blocking_issues": blockers[:30],
        "warnings": warnings[:50],
        "recommendations": recommendations,
        "model_route": build_short_video_model_route(),
        "production_presets": production_presets,
    }


async def refresh_workflow_shot_contracts(
    db: AsyncSession,
    user_id: str,
    workflow_id: str,
    *,
    shot_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    result = await db.execute(select(Workflow).where(and_(Workflow.id == workflow_id, Workflow.user_id == user_id)))
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")

    shots = await _workflow_shots(db, workflow, user_id)
    if shot_ids:
        allowed = set(shot_ids)
        shots = [shot for shot in shots if shot.id in allowed]
    contracts: List[Dict[str, Any]] = []
    for shot in shots:
        contract = await build_shot_production_contract(db, user_id, shot.id)
        persist_contract_to_shot(shot, contract)
        contracts.append(contract)

    workflow.metadata_ = {
        **_json_dict(workflow.metadata_),
        "short_video_mode": {
            "enabled": True,
            "last_contract_refresh_at": utc_now().isoformat(),
            "contract_count": len(contracts),
            "blocking_issue_count": sum(len(contract.get("blocking_issues") or []) for contract in contracts),
            "warning_count": sum(len(contract.get("warnings") or []) for contract in contracts),
        },
    }
    workflow.updated_at = utc_now()
    return {
        "workflow_id": workflow.id,
        "refreshed_count": len(contracts),
        "contracts": [_summarize_contract(contract) for contract in contracts],
        "summary": workflow.metadata_["short_video_mode"],
    }
