"""Voice and final-quality lock rules for workflow media."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.workflow_media.errors import WorkflowMediaError
from app.models import Shot, StoryBible, Storyboard, Workflow
from app.models.asset import Asset


@dataclass(frozen=True)
class WorkflowVoiceCommand:
    db: AsyncSession
    user_id: str
    workflow: Workflow
    shot: Shot
    subtitle_text: str
    default_voice: str
    default_speed: float
    requested_story_bible_id: Optional[str] = None
    use_story_bible_voice: bool = True


@dataclass(frozen=True)
class FinalQualityLockCommand:
    db: AsyncSession
    user_id: str
    workflow: Workflow
    shots: List[Shot]
    requested_story_bible_id: Optional[str] = None
    default_voice: Optional[str] = None
    default_speed: float = 1.0
    default_voice_source: str = "provider_default"


@dataclass(frozen=True)
class _VoiceLockCommand:
    db: AsyncSession
    user_id: str
    workflow: Workflow
    shot: Shot
    requested_story_bible_id: Optional[str]
    default_voice: Optional[str]
    default_speed: float
    default_voice_source: str

def _extra(job) -> dict:
    return job.extra_data if isinstance(job.extra_data, dict) else {}

def shot_subtitle_text(shot: Shot) -> str:
    shot_extra = _extra(shot)
    return (shot_extra.get("subtitle_text") or shot_extra.get("subtitle") or shot.dialogue or "").strip()

def uses_legacy_subtitle_only(shot: Shot) -> bool:
    shot_extra = _extra(shot)
    return bool(
        not str(shot_extra.get("subtitle_text") or "").strip()
        and not str(shot.dialogue or "").strip()
        and str(shot_extra.get("subtitle") or "").strip()
    )

def _production_context_for_shot(shot: Shot) -> Dict[str, Any]:
    shot_extra = _extra(shot)
    value = shot_extra.get("production_context")
    return value if isinstance(value, dict) else {}

def clean_character_label(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    value = str(name).strip().strip("「」『』“”\"' ")
    for suffix in ("回答", "低声说", "轻声说", "说道", "说", "道", "问", "喊"):
        if len(value) > len(suffix) and value.endswith(suffix):
            value = value[: -len(suffix)].strip()
            break
    return value or None

def primary_tts_character_name(shot: Shot, subtitle_text: str) -> Optional[str]:
    from app.services.dialogue_parser import extract_character_from_text, parse_dialogue

    character_name = clean_character_label(extract_character_from_text(subtitle_text))
    if character_name:
        return character_name

    for segment in parse_dialogue(subtitle_text):
        character_name = clean_character_label(segment.get("character"))
        if character_name and character_name != "旁白":
            return character_name

    character_refs = shot.character_refs if isinstance(shot.character_refs, list) else []
    for ref in character_refs:
        if isinstance(ref, dict):
            character_name = clean_character_label(
                ref.get("name") or ref.get("canonical_name") or ref.get("character_name")
            )
        else:
            character_name = clean_character_label(ref)
        if character_name:
            return character_name

    shot_extra = _extra(shot)
    entity_refs = shot_extra.get("entity_refs") if isinstance(shot_extra.get("entity_refs"), dict) else {}
    for ref in entity_refs.get("characters") or []:
        if isinstance(ref, dict):
            character_name = clean_character_label(
                ref.get("name") or ref.get("canonical_name") or ref.get("character_name")
            )
        else:
            character_name = clean_character_label(ref)
        if character_name:
            return character_name

    return None

def _story_bible_candidate_ids(workflow: Workflow, shot: Shot, requested_story_bible_id: Optional[str]) -> List[str]:
    candidates: List[str] = []

    def add(value: Optional[str]) -> None:
        if value and value not in candidates:
            candidates.append(str(value))

    add(requested_story_bible_id)
    shot_extra = _extra(shot)
    add(shot_extra.get("story_bible_id"))
    lineage = shot_extra.get("lineage") if isinstance(shot_extra.get("lineage"), dict) else {}
    add(lineage.get("story_bible_id"))
    production_context = _production_context_for_shot(shot)
    add(production_context.get("story_bible_id"))
    workflow_meta = workflow.metadata_ if isinstance(workflow.metadata_, dict) else {}
    add(workflow_meta.get("story_bible_id"))
    return candidates

async def _resolve_story_bible_id_for_workflow_shot(
    db: AsyncSession,
    user_id: str,
    workflow: Workflow,
    shot: Shot,
    requested_story_bible_id: Optional[str] = None,
) -> Optional[str]:
    candidates = _story_bible_candidate_ids(workflow, shot, requested_story_bible_id)

    storyboard_id = workflow.storyboard_id or shot.storyboard_id
    if storyboard_id:
        storyboard_result = await db.execute(
            select(Storyboard).where(Storyboard.id == storyboard_id, Storyboard.user_id == user_id)
        )
        storyboard = storyboard_result.scalar_one_or_none()
        storyboard_content = storyboard.content if storyboard and isinstance(storyboard.content, dict) else {}
        story_bible_id = storyboard_content.get("story_bible_id")
        if story_bible_id and story_bible_id not in candidates:
            candidates.append(str(story_bible_id))

    for story_bible_id in candidates:
        result = await db.execute(
            select(StoryBible.id).where(StoryBible.id == story_bible_id, StoryBible.user_id == user_id).limit(1)
        )
        if result.scalar_one_or_none():
            return story_bible_id

    if workflow.novel_id:
        result = await db.execute(
            select(StoryBible.id)
            .where(StoryBible.user_id == user_id, StoryBible.novel_id == workflow.novel_id)
            .order_by(desc(StoryBible.updated_at))
            .limit(1)
        )
        return result.scalar_one_or_none()
    return None

async def _resolve_user_default_voice_clone(db: AsyncSession, user_id: str) -> Optional[Dict[str, Any]]:
    result = await db.execute(
        select(Asset)
        .where(
            Asset.user_id == user_id,
            Asset.category == "voice",
            Asset.asset_type == "audio",
            Asset.is_active == True,
        )
        .order_by(desc(Asset.created_at))
        .limit(50)
    )
    candidates: List[tuple[int, Asset, Dict[str, Any]]] = []
    for asset in result.scalars().all():
        params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
        voice_id = str(params.get("voice_id") or "").strip()
        if not voice_id:
            continue
        tags = asset.tags if isinstance(asset.tags, list) else []
        style_tags = asset.style_tags if isinstance(asset.style_tags, list) else []
        if "voice_clone" not in tags and "custom_voice" not in style_tags:
            continue
        name = str(asset.name or "").lower()
        rank = 30
        if params.get("is_default") is True or params.get("default") is True:
            rank = 0
        elif voice_id == "sunqinyue-default":
            rank = 1
        elif "默认" in str(asset.name or "") or "default" in name:
            rank = 2
        candidates.append((rank, asset, params))

    if not candidates:
        return None

    _, asset, params = sorted(candidates, key=lambda item: (item[0], str(item[1].created_at or ""), item[1].id))[0]
    return {
        "voice": str(params.get("voice_id")).strip(),
        "voice_source": "user_default_voice_clone",
        "voice_asset_id": asset.id,
        "voice_provider": params.get("provider"),
        "voice_sample_audio_url": asset.url,
    }

async def _apply_user_default_voice_clone(
    db: AsyncSession,
    user_id: str,
    resolved: Dict[str, Any],
    *,
    apply_clone: bool = True,
) -> Dict[str, Any]:
    if resolved.get("voice_source") != "request":
        return resolved
    if not apply_clone:
        resolved["voice_source"] = "provider_default_tts"
        return resolved
    default_clone = await _resolve_user_default_voice_clone(db, user_id)
    if default_clone:
        resolved.update(default_clone)
    return resolved

def _is_narrator_character_name(character_name: Optional[str]) -> bool:
    return str(character_name or "").strip() in {"旁白", "解说", "叙述者", " narrator", "Narrator"}

def _character_rule_name_matches(rule: Dict[str, Any], character_name: str) -> bool:
    names = [
        rule.get("name"),
        rule.get("canonical_name"),
        rule.get("character_name"),
        *(rule.get("aliases") if isinstance(rule.get("aliases"), list) else []),
    ]
    return character_name in {str(name).strip() for name in names if name and str(name).strip()}

def _character_rule_is_main(rule: Dict[str, Any]) -> Optional[bool]:
    if rule.get("is_main") is True or rule.get("main") is True or rule.get("protagonist") is True:
        return True
    role = str(rule.get("role") or rule.get("character_role") or "").strip().lower()
    if role in {"主角", "男主", "女主", "protagonist", "main", "lead", "hero", "heroine"}:
        return True
    if role in {"配角", "反派", "旁白", "supporting", "side", "villain", "narrator"}:
        return False
    return None

async def _is_main_character_for_user_default_voice_clone(
    db: AsyncSession,
    user_id: str,
    story_bible_id: Optional[str],
    character_name: Optional[str],
) -> bool:
    if not character_name or _is_narrator_character_name(character_name) or not story_bible_id:
        return False
    result = await db.execute(
        select(StoryBible).where(StoryBible.id == story_bible_id, StoryBible.user_id == user_id).limit(1)
    )
    story_bible = result.scalar_one_or_none()
    if not story_bible:
        return False
    rules = [rule for rule in (story_bible.character_rules or []) if isinstance(rule, dict)]
    if not rules:
        return False

    explicit_main_exists = any(_character_rule_is_main(rule) is True for rule in rules)
    for index, rule in enumerate(rules):
        if not _character_rule_name_matches(rule, character_name):
            continue
        main_flag = _character_rule_is_main(rule)
        if main_flag is not None:
            return main_flag
        return index == 0 and not explicit_main_exists
    return False

async def resolve_workflow_tts_voice(command: WorkflowVoiceCommand) -> Dict[str, Any]:
    db, user_id = command.db, command.user_id
    workflow, shot = command.workflow, command.shot
    subtitle_text = command.subtitle_text
    default_voice, default_speed = command.default_voice, command.default_speed
    requested_story_bible_id = command.requested_story_bible_id
    use_story_bible_voice = command.use_story_bible_voice
    resolved = {
        "voice": default_voice,
        "speed": default_speed,
        "voice_source": "request",
        "character_name": None,
        "story_bible_id": None,
    }
    if not use_story_bible_voice:
        return resolved

    story_bible_id = await _resolve_story_bible_id_for_workflow_shot(
        db,
        user_id,
        workflow,
        shot,
        requested_story_bible_id=requested_story_bible_id,
    )
    resolved["story_bible_id"] = story_bible_id
    character_name = primary_tts_character_name(shot, subtitle_text)
    resolved["character_name"] = character_name
    apply_user_default_clone = await _is_main_character_for_user_default_voice_clone(
        db,
        user_id,
        story_bible_id,
        character_name,
    )
    if not story_bible_id or not character_name:
        return await _apply_user_default_voice_clone(
            db,
            user_id,
            resolved,
            apply_clone=apply_user_default_clone,
        )

    from app.services.voice_service import get_character_voice_from_story_bible

    voice_config = await get_character_voice_from_story_bible(db, character_name, story_bible_id)
    if not voice_config:
        return await _apply_user_default_voice_clone(
            db,
            user_id,
            resolved,
            apply_clone=apply_user_default_clone,
        )

    story_bible_voice = voice_config.get("voice") or voice_config.get("voice_model")
    if story_bible_voice:
        resolved["voice"] = story_bible_voice
        resolved["voice_source"] = "story_bible"
    if voice_config.get("voice_speed") is not None:
        resolved["speed"] = voice_config.get("voice_speed")
    return await _apply_user_default_voice_clone(
        db,
        user_id,
        resolved,
        apply_clone=apply_user_default_clone,
    )

def provider_compatible_tts_voice(voice: Optional[str], selected_audio_model: Optional[Dict[str, Any]]) -> Optional[str]:
    if (
        selected_audio_model
        and selected_audio_model.get("provider_id") == "volcano"
        and voice == "female-shaonj"
    ):
        return "female_nvsheng"
    return voice

def asset_locks_for_workflow_shot(shot: Shot) -> List[Dict[str, Any]]:
    production_context = _production_context_for_shot(shot)
    locks = production_context.get("asset_version_locks")
    return [dict(item) for item in locks if isinstance(item, dict)] if isinstance(locks, list) else []

async def _voice_lock_snapshot_for_workflow_shot(
    command: _VoiceLockCommand,
) -> Optional[Dict[str, Any]]:
    db, user_id = command.db, command.user_id
    workflow, shot = command.workflow, command.shot
    requested_story_bible_id = command.requested_story_bible_id
    default_voice, default_speed = command.default_voice, command.default_speed
    default_voice_source = command.default_voice_source
    subtitle_text = shot_subtitle_text(shot)
    if not subtitle_text:
        return None
    character_name = primary_tts_character_name(shot, subtitle_text)
    effective_default_voice = None if uses_legacy_subtitle_only(shot) else default_voice
    story_bible_id = await _resolve_story_bible_id_for_workflow_shot(
        db,
        user_id,
        workflow,
        shot,
        requested_story_bible_id=requested_story_bible_id,
    )
    if not character_name or not story_bible_id:
        if not effective_default_voice:
            return None
        return {
            "character_name": character_name,
            "story_bible_id": story_bible_id,
            "voice": effective_default_voice,
            "speed": default_speed,
            "voice_source": default_voice_source,
        }

    from app.services.voice_service import get_character_voice_from_story_bible

    voice_config = await get_character_voice_from_story_bible(db, character_name, story_bible_id)
    if not voice_config:
        if not effective_default_voice:
            return None
        return {
            "character_name": character_name,
            "story_bible_id": story_bible_id,
            "voice": effective_default_voice,
            "speed": default_speed,
            "voice_source": default_voice_source,
        }
    voice = voice_config.get("voice") or voice_config.get("voice_model") or voice_config.get("voice_profile") or voice_config.get("voice_id")
    if not voice:
        if not effective_default_voice:
            return None
        return {
            "character_name": character_name,
            "story_bible_id": story_bible_id,
            "voice": effective_default_voice,
            "speed": default_speed,
            "voice_source": default_voice_source,
        }
    return {
        "character_name": character_name,
        "story_bible_id": story_bible_id,
        "voice": voice,
        "voice_source": "story_bible",
    }

async def build_final_quality_lock_snapshots(
    command: FinalQualityLockCommand,
) -> Dict[str, Dict[str, Any]]:
    db, user_id = command.db, command.user_id
    workflow, shots = command.workflow, command.shots
    snapshots: Dict[str, Dict[str, Any]] = {}
    missing_assets: List[Dict[str, Any]] = []
    missing_voices: List[Dict[str, Any]] = []

    for shot in shots:
        asset_locks = asset_locks_for_workflow_shot(shot)
        voice_lock = await _voice_lock_snapshot_for_workflow_shot(_VoiceLockCommand(
            db, user_id, workflow, shot,
            command.requested_story_bible_id, command.default_voice,
            command.default_speed, command.default_voice_source,
        ))
        snapshots[shot.id] = {
            "asset_version_locks": asset_locks,
            "voice_lock_snapshot": voice_lock,
        }
        if not asset_locks:
            missing_assets.append({"shot_id": shot.id, "shot_number": shot.shot_number})
        dialogue_text = shot_subtitle_text(shot)
        if dialogue_text and not voice_lock:
            missing_voices.append({
                "shot_id": shot.id,
                "shot_number": shot.shot_number,
                "character_name": primary_tts_character_name(shot, dialogue_text),
            })

    if missing_assets or missing_voices:
        raise WorkflowMediaError(422, {
                "code": "final_quality_locks_missing",
                "message": "final_quality 生成前必须锁定镜头资产和相关角色声线",
                "missing_assets": missing_assets,
                "missing_voices": missing_voices,
                "issues": [
                    *[
                        {"code": "asset_lock_missing", **item}
                        for item in missing_assets
                    ],
                    *[
                        {"code": "voice_lock_missing", **item}
                        for item in missing_voices
                    ],
                ],
            },
        )
    return snapshots
