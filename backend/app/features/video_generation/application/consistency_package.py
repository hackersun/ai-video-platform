"""Build the consistency package shared by video-generation callers."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Any, Optional

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.model_registry import get_task_default
from app.features.video_generation.constants import MAX_PROVIDER_SEED
from app.features.video_generation.errors import VideoGenerationError
from app.services.consistency_context import get_project_for_context, get_story_bible_for_context
from app.services.novel_continuity import build_novel_continuity_package
from app.services.prompt_composer import compose_generation_prompt
from app.services.prompt_skill_service import active_prompt_skill_entries
from app.services.story_prompt_context import build_video_continuity_constraints, load_story_prompt_context

VideoConsistencyPackageError = VideoGenerationError


@dataclass(frozen=True)
class VideoConsistencyPackageContext:
    db: AsyncSession
    user_id: str
    request: Any
    lineage: dict[str, Any]


@dataclass
class _PackageState:
    context: VideoConsistencyPackageContext
    shot: Any
    shot_context: dict[str, Any]
    novel_id: Optional[str]
    chapter_id: Optional[str]
    characters: list[Any]
    character_by_id: dict[str, Any]
    story_character_by_id: dict[str, Any] = field(default_factory=dict)
    character_refs: list[dict[str, Any]] = field(default_factory=list)
    filtered_refs: list[dict[str, Any]] = field(default_factory=list)
    scene_refs: list[dict[str, Any]] = field(default_factory=list)
    prop_refs: list[dict[str, Any]] = field(default_factory=list)
    event_refs: list[dict[str, Any]] = field(default_factory=list)
    asset_locks: list[dict[str, Any]] = field(default_factory=list)
    multiview_refs: list[dict[str, Any]] = field(default_factory=list)
    reference_image: Optional[str] = None
    reference_source: Optional[str] = None
    story_context: dict[str, Any] = field(default_factory=dict)
    project: Any = None
    story_bible: Any = None
    continuity: dict[str, Any] = field(default_factory=dict)
    seeds: dict[str, Optional[int]] = field(default_factory=dict)
    style_lock: dict[str, Any] = field(default_factory=dict)
    prompt_skills: list[dict[str, Any]] = field(default_factory=list)
    final_prompt: str = ""


def json_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def extract_shot_generation_context(shot: Any) -> dict[str, Any]:
    if not shot:
        return {"character_refs": [], "scene_refs": [], "prop_refs": [], "event_refs": [],
                "environment_context": None, "subtitle_text": None}
    extra = json_dict(getattr(shot, "extra_data", None))
    entity_refs = json_dict(extra.get("entity_refs"))
    return {
        "character_refs": getattr(shot, "character_refs", None) or entity_refs.get("characters") or [],
        "scene_refs": extra.get("scene_refs") or entity_refs.get("scenes") or [],
        "prop_refs": extra.get("prop_refs") or entity_refs.get("props") or [],
        "event_refs": extra.get("event_refs") or entity_refs.get("events") or [],
        "environment_context": extra.get("environment_context"),
        "subtitle_text": extra.get("subtitle_text") or getattr(shot, "dialogue", None),
    }


def derive_stable_seed(parts: list[Optional[str]]) -> Optional[int]:
    seed_source = "|".join(str(part) for part in parts if part)
    if not seed_source:
        return None
    digest = hashlib.sha256(seed_source.encode("utf-8")).hexdigest()
    return (int(digest[:12], 16) % MAX_PROVIDER_SEED) or 1


def _ref_name(ref: Any) -> str:
    return str(ref.get("name") or ref.get("entity_name") or "").strip() if isinstance(ref, dict) else str(ref or "").strip()


def _dedupe_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result, seen = [], set()
    for ref in refs:
        key = str(ref.get("character_id") or ref.get("entity_id") or ref.get("name") or "").strip()
        if key and key not in seen:
            seen.add(key)
            result.append(ref)
    return result


def _merge_character_ref(character: Any, source: str, ref: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    merged = dict(ref or {})
    merged.update({"character_id": character.id, "name": character.name, "description": character.description,
                   "appearance": character.appearance, "personality": character.personality,
                   "voice": character.voice, "avatar": character.avatar, "source": source})
    return merged


def _merge_story_character_ref(entity: Any, ref: dict[str, Any]) -> dict[str, Any]:
    attrs = json_dict(getattr(entity, "attributes", None))
    merged = dict(ref)
    merged.update({
        "entity_id": entity.id,
        "name": entity.canonical_name or entity.name,
        "description": entity.description,
        "appearance": entity.appearance,
        "visual_dna": attrs.get("visual_dna") or {},
        "source": "story_entity_lock",
    })
    return merged


def lookup_character_by_name(characters: list[Any], name: str, novel_id: Optional[str], chapter_id: Optional[str]) -> Any:
    def matches(item: Any) -> bool:
        names = [getattr(item, "name", None)]
        tags = getattr(item, "tags", None)
        if isinstance(tags, list):
            names.extend(str(value) for value in tags)
        return bool(name and any(value and str(value).strip() == name for value in names))
    found = [item for item in characters if matches(item)]
    if not found and name in {"主角", "主人公"}:
        scoped = [item for item in characters if getattr(item, "novel_id", None) == novel_id]
        found = scoped if len(scoped) == 1 else []
    def rank(item: Any) -> tuple[int, str]:
        scope = 4 if chapter_id and getattr(item, "chapter_id", None) == chapter_id else 3 if novel_id and getattr(item, "novel_id", None) == novel_id else 1 if getattr(item, "novel_id", None) is None else 0
        return scope, str(getattr(item, "updated_at", "") or "")
    return sorted(found, key=rank, reverse=True)[0] if found else None


def _valid_story_character(ref: dict[str, Any]) -> bool:
    name = _ref_name(ref)
    invalid = {"疼痛", "狂喜", "活着", "阳光", "年轻", "瘦弱", "身躯", "眼睛", "双手", "起身", "个人"}
    evidence, description = str(ref.get("evidence") or ""), str(ref.get("description") or "")
    return bool(name and name not in invalid and "规则识别人物" not in description and "规则识别人物" not in evidence
                and (ref.get("entity_id") or "文本标注角色" in description or "角色" in evidence))


def _format_visual_locks(refs: list[dict[str, Any]]) -> str:
    lines = []
    for ref in refs[:6]:
        details = [f"{label}:{ref[key]}" for key, label in (("appearance", "外貌"), ("description", "身份"), ("personality", "性格")) if ref.get(key)]
        visual_dna = json_dict(ref.get("visual_dna"))
        if visual_dna:
            details.append("视觉DNA:" + "、".join(f"{key}={value}" for key, value in visual_dna.items()))
        if ref.get("name"):
            lines.append(f"{ref['name']}（{'；'.join(details) if details else '使用角色设定'}）")
    return "；".join(lines)


def _format_refs(refs: list[dict[str, Any]]) -> str:
    return "、".join(str(ref.get("name")) for ref in refs if ref.get("name"))


def _format_asset_locks(locks: list[dict[str, Any]], limit: int = 8) -> str:
    parts = []
    for lock in locks[:limit]:
        name, category = lock.get("entity_name") or lock.get("name"), lock.get("category")
        url = lock.get("url") or lock.get("thumbnail_url")
        if name:
            parts.append(f"{name}({category or 'reference'}): {url}" if url else str(name))
    return "；".join(parts)


def collect_character_multiview_refs(assets: list[Any], character_refs: list[dict[str, Any]], per_character: int = 8) -> list[dict[str, Any]]:
    names = {str(ref.get("character_id")): str(ref.get("name") or "") for ref in character_refs if ref.get("character_id")}
    entity_ids = {str(ref.get("entity_id")): str(ref.get("character_id")) for ref in character_refs if ref.get("entity_id") and ref.get("character_id")}
    angles = {"front": 0, "three_quarter": 1, "3/4": 1, "side": 2, "back": 3, "closeup": 4, "expression": 5, "costume": 6}
    candidates, seen, counts = [], set(), {}
    for asset in assets:
        character_id = str(getattr(asset, "character_id", "") or "") or entity_ids.get(str(getattr(asset, "entity_id", "") or ""), "")
        params = getattr(asset, "generation_params", None) if isinstance(getattr(asset, "generation_params", None), dict) else {}
        role = str(params.get("reference_role") or params.get("role") or "").strip()
        angle = str(params.get("view_angle") or params.get("angle") or "reference").strip()
        url = getattr(asset, "url", None) or getattr(asset, "thumbnail_url", None)
        valid_role = role in {"character_multiview", "multi_view", "multiview"} or "view" in role or params.get("view_angle")
        key = (character_id, angle, url)
        if character_id not in names or getattr(asset, "category", None) != "character" or not url or not valid_role or not (getattr(asset, "is_locked", False) or getattr(asset, "is_final", False)) or key in seen:
            continue
        seen.add(key); counts[character_id] = counts.get(character_id, 0) + 1
        if counts[character_id] > per_character:
            continue
        ref = {"asset_id": getattr(asset, "id", None), "character_id": character_id, "character_name": names[character_id],
               "name": getattr(asset, "name", None), "view_angle": angle, "url": url,
               "thumbnail_url": getattr(asset, "thumbnail_url", None), "version": getattr(asset, "version", None),
               "is_locked": bool(getattr(asset, "is_locked", False)), "is_final": bool(getattr(asset, "is_final", False)),
               "reference_role": role or "character_multiview"}
        candidates.append((list(names).index(character_id), angles.get(angle, 99), -int(getattr(asset, "version", None) or 0), ref))
    candidates.sort(key=lambda item: item[:3])
    return [item[3] for item in candidates]


def _format_multiview(refs: list[dict[str, Any]], limit: int = 12) -> str:
    parts = []
    for ref in refs[:limit]:
        name, angle, url = ref.get("character_name") or ref.get("name"), ref.get("view_angle"), ref.get("url")
        if name and url:
            parts.append(f"{name}-{angle}: {url}" if angle else f"{name}: {url}")
    return "；".join(parts)


async def _load_state(context: VideoConsistencyPackageContext) -> _PackageState:
    from app.models import Character, StoryEntity
    request, lineage = context.request, context.lineage
    novel_id, chapter_id = request.novel_id or lineage.get("novel_id"), request.chapter_id or lineage.get("chapter_id")
    filters = [Character.user_id == context.user_id]
    if novel_id:
        filters.append(or_(Character.novel_id == novel_id, Character.novel_id.is_(None)))
    elif chapter_id:
        filters.append(or_(Character.chapter_id == chapter_id, Character.novel_id.is_(None)))
    characters = list((await context.db.scalars(select(Character).where(and_(*filters)).order_by(desc(Character.updated_at)))).all())
    entity_filters = [StoryEntity.user_id == context.user_id, StoryEntity.entity_type == "character"]
    if novel_id:
        entity_filters.append(StoryEntity.novel_id == novel_id)
    story_entities = list((await context.db.scalars(select(StoryEntity).where(and_(*entity_filters)))).all())
    story_by_id = {item.id: item for item in story_entities}
    for item in story_entities:
        canonical_id = str((item.attributes or {}).get("merged_into_entity_id") or "")
        if canonical_id and canonical_id in story_by_id:
            story_by_id[item.id] = story_by_id[canonical_id]
    return _PackageState(context, lineage.get("shot"), extract_shot_generation_context(lineage.get("shot")),
                         novel_id, chapter_id, characters, {item.id: item for item in characters}, story_by_id)


def _resolve_character_refs(state: _PackageState) -> None:
    request = state.context.request
    missing = [item for item in request.character_ids if item not in state.character_by_id]
    if missing:
        raise VideoConsistencyPackageError(422, "所选角色不存在或不属于当前小说，请重新选择当前小说下的角色参考")
    for ref in [item for item in state.shot_context.get("character_refs") or [] if isinstance(item, dict)]:
        character = state.character_by_id.get(ref.get("character_id") or ref.get("id")) or lookup_character_by_name(state.characters, _ref_name(ref), state.novel_id, state.chapter_id)
        if character:
            state.character_refs.append(_merge_character_ref(character, ref.get("source") or "shot_ref", ref))
        elif story := state.story_character_by_id.get(
            str(ref.get("canonical_entity_id") or ref.get("entity_id") or ref.get("source_entity_id") or "")
        ):
            state.character_refs.append(_merge_story_character_ref(story, ref))
        elif _valid_story_character(ref):
            state.character_refs.append(dict(ref))
        else:
            state.filtered_refs.append(ref)
    state.character_refs.extend(_merge_character_ref(state.character_by_id[item], "request_character") for item in request.character_ids)
    shot_text = " ".join(str(value or "") for value in (getattr(state.shot, "prompt", None), getattr(state.shot, "visual_description", None), getattr(state.shot, "dialogue", None), state.shot_context.get("subtitle_text")))
    matched = [item for item in state.characters if item.novel_id == state.novel_id and item.name and item.name in shot_text]
    if not state.character_refs:
        matched = matched or [item for item in state.characters if item.novel_id == state.novel_id]
        source = "novel_character_fallback"
    else:
        source = "shot_text_match"
    state.character_refs.extend(_merge_character_ref(item, source) for item in matched[:3])
    state.character_refs = _dedupe_refs(state.character_refs)


def _resolve_entity_refs(state: _PackageState) -> None:
    state.scene_refs = _dedupe_refs([ref for ref in state.shot_context.get("scene_refs") or [] if isinstance(ref, dict)])
    state.event_refs = _dedupe_refs([ref for ref in state.shot_context.get("event_refs") or [] if isinstance(ref, dict)])
    character_names = {str(ref.get("name")) for ref in state.character_refs if ref.get("name")}
    props = []
    for ref in [item for item in state.shot_context.get("prop_refs") or [] if isinstance(item, dict)]:
        if any(name and name in _ref_name(ref) for name in character_names):
            state.filtered_refs.append(ref)
        else:
            props.append(ref)
    state.prop_refs = _dedupe_refs(props)
    production = json_dict(json_dict(getattr(state.shot, "extra_data", None)).get("production_context")) if state.shot else {}
    state.asset_locks = [item for item in production.get("asset_version_locks") or [] if isinstance(item, dict)]
    state.multiview_refs = [item for item in production.get("character_multiview_refs") or [] if isinstance(item, dict)]


async def _load_multiview(state: _PackageState) -> None:
    if state.multiview_refs or not state.character_refs:
        return
    from app.models import Asset
    character_ids = [ref.get("character_id") for ref in state.character_refs if ref.get("character_id")]
    entity_ids = [ref.get("entity_id") for ref in state.character_refs if ref.get("entity_id")]
    links = ([Asset.character_id.in_(character_ids)] if character_ids else []) + ([Asset.entity_id.in_(entity_ids)] if entity_ids else [])
    if not links:
        return
    query = select(Asset).where(and_(Asset.is_active == True, or_(Asset.user_id == state.context.user_id, Asset.is_public == True), Asset.category == "character", or_(*links), or_(Asset.is_locked == True, Asset.is_final == True))).order_by(desc(Asset.is_final), desc(Asset.is_locked), desc(Asset.version), desc(Asset.updated_at)).limit(200)
    state.multiview_refs = collect_character_multiview_refs(list((await state.context.db.scalars(query)).all()), state.character_refs)


def _locked_reference(state: _PackageState) -> tuple[Optional[str], Optional[str]]:
    request = state.context.request
    if request.image_url:
        return request.image_url, "request"
    if getattr(state.shot, "image_url", None):
        return state.shot.image_url, "shot_image"
    candidates = [((lock.get("url") or lock.get("thumbnail_url")), "asset_lock_character") for lock in state.asset_locks if lock.get("category") == "character"]
    candidates += [(ref.get("url"), "character_multiview") for ref in state.multiview_refs]
    candidates += [(ref.get("avatar"), "character_avatar") for ref in state.character_refs]
    candidates += [((lock.get("url") or lock.get("thumbnail_url")), "asset_lock") for lock in state.asset_locks]
    return next(((url, source) for url, source in candidates if url), (None, None))


async def _resolve_reference(state: _PackageState) -> None:
    from app.models import Asset
    state.reference_image, state.reference_source = _locked_reference(state)
    if state.reference_image or not (state.character_refs or state.scene_refs or state.prop_refs):
        return
    names = {_ref_name(ref) for ref in [*state.character_refs, *state.scene_refs, *state.prop_refs] if _ref_name(ref)}
    character_ids = {ref.get("character_id") for ref in state.character_refs if ref.get("character_id")}
    filters = [Asset.is_active == True, or_(Asset.user_id == state.context.user_id, Asset.is_public == True), Asset.category.in_(["character", "scene", "prop", "costume"])]
    if state.novel_id:
        filters.append(or_(Asset.novel_id == state.novel_id, Asset.novel_id.is_(None)))
    query = select(Asset).where(and_(*filters)).order_by(desc(Asset.usage_count), desc(Asset.updated_at)).limit(120)
    for asset in (await state.context.db.scalars(query)).all():
        text = f"{asset.name or ''} {asset.description or ''} {' '.join(asset.tags or [])}"
        if ((asset.character_id and asset.character_id in character_ids) or any(name in text for name in names)) and (asset.url or asset.thumbnail_url):
            state.reference_image, state.reference_source = asset.url or asset.thumbnail_url, f"asset_{asset.category}"
            return


async def _load_continuity(state: _PackageState) -> None:
    context, request = state.context, state.context.request
    state.story_context = await load_story_prompt_context(context.db, context.user_id, novel_id=state.novel_id, chapter_id=state.chapter_id)
    project_id = request.project_id or context.lineage.get("project_id")
    state.project = await get_project_for_context(context.db, context.user_id, project_id, strict=False)
    state.story_bible = await get_story_bible_for_context(context.db, context.user_id, story_bible_id=request.story_bible_id, project_id=project_id, novel_id=state.novel_id)
    state.continuity = await build_novel_continuity_package(context.db, context.user_id, novel_id=state.novel_id,
        chapter_id=state.chapter_id, story_bible_id=state.story_bible.id if state.story_bible else request.story_bible_id,
        project_id=state.project.id if state.project else project_id, model_id=request.model, task="shot_video")


def _build_seeds_and_style(state: _PackageState) -> None:
    request, lineage = state.context.request, state.context.lineage
    series = state.continuity.get("novel_series_seed") or derive_stable_seed(["novel_series", state.project.id if state.project else request.project_id or lineage.get("project_id"), state.story_bible.id if state.story_bible else request.story_bible_id, state.novel_id])
    chapter = state.continuity.get("chapter_seed") or derive_stable_seed(["chapter", series, state.chapter_id])
    storyboard = derive_stable_seed(["storyboard", chapter, request.script_id or lineage.get("script_id"), request.storyboard_id or lineage.get("storyboard_id"), request.model])
    shot = request.seed if request.seed is not None else derive_stable_seed(["shot", storyboard, getattr(state.shot, "shot_number", None), request.shot_id or lineage.get("shot_id"), request.model])
    state.seeds = {"series": series, "chapter": chapter, "storyboard": storyboard, "shot": shot}
    board, script = lineage.get("storyboard"), lineage.get("script")
    state.style_lock = {"scope": "novel_series", "series_seed": series, "novel_series_seed": series, "chapter_seed": chapter,
        "storyboard_seed": storyboard, "style": getattr(state.story_bible, "style", None) or state.story_context.get("style") or getattr(board, "style", None) or getattr(script, "style", None) or "统一动漫赛璐璐风格",
        "genre": state.story_context.get("genre") or getattr(board, "genre", None) or getattr(script, "genre", None),
        "story_bible_id": state.story_bible.id if state.story_bible else request.story_bible_id,
        "storyboard_id": request.storyboard_id or lineage.get("storyboard_id"), "chapter_id": state.chapter_id, "novel_id": state.novel_id,
        "constraint": "整部小说共享同一画风、角色视觉DNA、世界观、场景/道具状态机和事件因果；章节和分镜只派生局部节奏，不重置角色形象。"}


def _prompt_context(state: _PackageState) -> dict[str, Any]:
    request = state.context.request
    extra = {"视频时长": request.duration, "分辨率": request.resolution, "整部小说连续性锁": state.continuity.get("prompt_block"),
        "小说级系列种子": state.seeds["series"], "章节连续性种子": state.seeds["chapter"], "分镜派生种子": state.seeds["storyboard"],
        "参考图": state.reference_image, "参考图来源": state.reference_source, "人物角色": _format_refs(state.character_refs),
        "角色视觉DNA锁": _format_visual_locks(state.character_refs), "场景": _format_refs(state.scene_refs), "道具": _format_refs(state.prop_refs),
        "事件": _format_refs(state.event_refs), "环境连续性": state.shot_context["environment_context"], "字幕/对白": state.shot_context["subtitle_text"],
        "小说级风格锁": state.style_lock["constraint"], "资产版本锁": _format_asset_locks(state.asset_locks),
        "角色多视图参考": _format_multiview(state.multiview_refs), "动漫连续性硬约束": build_video_continuity_constraints(state.story_context)}
    for prefix, item in (("分镜", state.context.lineage.get("storyboard")), ("剧本", state.context.lineage.get("script"))):
        if item:
            extra.setdefault(f"{prefix}标题", item.title)
            for attr, label in (("style", "风格"), ("genre", "题材"), ("description", "说明")):
                if getattr(item, attr, None): extra.setdefault(f"{prefix}{label}", getattr(item, attr))
    return {"用户提示词": request.prompt, **extra}


def _prompt_skill_task(request: Any) -> str:
    return "shot_audio_video" if bool(getattr(request, "native_audio", False)) else "shot_video"


async def _compose_prompt(state: _PackageState) -> None:
    request, context = state.context.request, _prompt_context(state)
    task = _prompt_skill_task(request)
    state.prompt_skills = await active_prompt_skill_entries(state.context.db, state.context.user_id, task=task, context=context)
    locks = [{"type": lock.get("category") or "资产", "name": lock.get("entity_name") or lock.get("name") or "Unknown"} for lock in state.asset_locks]
    state.final_prompt = compose_generation_prompt(task=task, shot=state.shot, story_bible=state.story_bible,
        characters=[state.character_by_id[ref["character_id"]] for ref in state.character_refs if ref.get("character_id") in state.character_by_id],
        project=state.project, extra_context=context, locked_assets=locks, skill_blocks=[entry["content"] for entry in state.prompt_skills])


def _metadata(state: _PackageState) -> dict[str, Any]:
    request, lineage, continuity = state.context.request, state.context.lineage, state.continuity
    result = {"task": _prompt_skill_task(request), "story_bible_id": state.story_bible.id if state.story_bible else request.story_bible_id,
        "project_id": state.project.id if state.project else request.project_id or lineage.get("project_id"), "novel_id": state.novel_id,
        "chapter_id": state.chapter_id, "shot_id": request.shot_id or lineage.get("shot_id"), "storyboard_id": request.storyboard_id or lineage.get("storyboard_id"),
        "character_ids": [ref["character_id"] for ref in state.character_refs if ref.get("character_id")],
        "entity_refs": {"characters": state.character_refs, "scenes": state.scene_refs, "props": state.prop_refs, "events": state.event_refs},
        "subtitle_text": state.shot_context["subtitle_text"], "default_model_id": (get_task_default("shot_video") or {}).get("default_model_id"),
        "series_seed": state.seeds["series"], "novel_series_seed": state.seeds["series"], "chapter_seed": state.seeds["chapter"],
        "storyboard_seed": state.seeds["storyboard"], "style_lock": state.style_lock, "prompt_skill_count": len(state.prompt_skills),
        "rendered_prompt_sha256": hashlib.sha256(state.final_prompt.encode("utf-8")).hexdigest(),
        "prompt_skills": [{**{key: entry[key] for key in ("id", "name", "task", "stage", "version")}, "prompt_profile_version_id": entry.get("prompt_profile_version_id")} for entry in state.prompt_skills],
        "character_visual_locks": state.character_refs, "character_multiview_refs": state.multiview_refs,
        "reference_image_source": state.reference_source, "invalid_entity_ref_count": len(state.filtered_refs), "seed": state.seeds["shot"]}
    for key in ("continuity_lock", "previous_chapter_context", "current_chapter_context", "next_chapter_constraint", "previous_chapter_state", "chapter_state_snapshot", "state_machine_version", "state_machine_summary"):
        result[key] = continuity.get(key)
    result.update({"event_timeline_tail": continuity.get("event_timeline_tail") or [], "entity_locks": continuity.get("entity_locks") or {}})
    return result


def _result(state: _PackageState) -> dict[str, Any]:
    context = {"character_refs": state.character_refs, "scene_refs": state.scene_refs, "prop_refs": state.prop_refs,
        "event_refs": state.event_refs, "environment_context": state.shot_context["environment_context"], "subtitle_text": state.shot_context["subtitle_text"],
        "asset_version_locks": state.asset_locks, "character_multiview_refs": state.multiview_refs, "style_lock": state.style_lock,
        "series_seed": state.seeds["series"], "novel_series_seed": state.seeds["series"], "chapter_seed": state.seeds["chapter"],
        "storyboard_seed": state.seeds["storyboard"], "novel_continuity": state.continuity, "reference_image": state.reference_image,
        "reference_image_source": state.reference_source, "filtered_out_entity_refs": state.filtered_refs}
    return {"final_prompt": state.final_prompt, "metadata": _metadata(state), "context": context, "seed": state.seeds["shot"],
            "series_seed": state.seeds["series"], "novel_series_seed": state.seeds["series"], "chapter_seed": state.seeds["chapter"],
            "reference_image": state.reference_image, "reference_image_source": state.reference_source}


async def build_video_consistency_package(context: VideoConsistencyPackageContext) -> dict[str, Any]:
    state = await _load_state(context)
    _resolve_character_refs(state)
    _resolve_entity_refs(state)
    await _load_multiview(state)
    await _resolve_reference(state)
    await _load_continuity(state)
    _build_seeds_and_style(state)
    await _compose_prompt(state)
    return _result(state)
