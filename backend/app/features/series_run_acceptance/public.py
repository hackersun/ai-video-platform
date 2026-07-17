"""Seed non-secret deterministic rows through production ownership boundaries."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.features.series_anchor_generation.errors import SeriesAnchorError
from app.features.series_run_story_locks.public import (
    apply_deterministic_voice_binding, deterministic_anchor_entity_refs,
    deterministic_evidence_contract, seed_deterministic_local_mentions,
)
from app.models import Chapter, LLMConfig, LLMModel, LLMProvider, Novel, Shot, StoryEntity, Storyboard
from app.models.series_production_run import SeriesProductionRun
from app.services.deterministic_acceptance_lineage import sync_deterministic_episode_input_hash
from app.services.story_entity_lifecycle import ARCHIVED, CANDIDATE, set_entity_review_status


async def _context(db: AsyncSession, user_id: str, novel_id: str):
    novel = await db.scalar(select(Novel).where(Novel.id == novel_id, Novel.user_id == user_id))
    if novel is None:
        raise SeriesAnchorError(404, "novel not found")
    run = await db.scalar(select(SeriesProductionRun).where(
        SeriesProductionRun.novel_id == novel_id, SeriesProductionRun.user_id == user_id,
    ).order_by(SeriesProductionRun.created_at.desc()).limit(1))
    if run is None:
        raise SeriesAnchorError(409, "create the series run first")
    chapter_ids = [str(value) for episode in sorted(run.episodes or [], key=lambda item: int(item.get("episode_number") or 0))
                   for value in episode.get("chapter_ids") or []]
    chapters = list((await db.scalars(select(Chapter).where(
        Chapter.id.in_(chapter_ids), Chapter.user_id == user_id, Chapter.novel_id == novel_id,
    ))).all())
    by_id = {chapter.id: chapter for chapter in chapters}
    if len(by_id) != len(set(chapter_ids)):
        raise SeriesAnchorError(409, "run chapter sources are incomplete")
    return novel, run, chapter_ids, by_id


def _new_protagonist(user_id: str, novel_id: str, chapter: Chapter) -> StoryEntity:
    entity = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter.id,
        first_seen_chapter_id=chapter.id, entity_type="character", name="主角", canonical_name="主角",
        description="四章故事的已批准主角", version=1, source="deterministic",
        attributes={"source_chapter_id": chapter.id, "source_chapter_index": 1,
            "introduced_at": {"chapter_id": chapter.id, "chapter_number": 1},
            "evidence_contract": deterministic_evidence_contract(chapter), "speaking": True,
            "voice_binding": {"voice_id": "deterministic-protagonist-voice", "version": 1, "status": "locked"},
            "visual_dna": {"costume": "深色长衣", "line_style": "统一二维动漫线稿"},
            "reference_requirements": {"character_multiview": ["front", "three_quarter", "full_body"]}},
    )
    set_entity_review_status(entity, CANDIDATE, changed_by=user_id, reason="deterministic_acceptance_fixture")
    return entity


async def _protagonist(db: AsyncSession, user_id: str, novel_id: str, chapter_ids: list[str], chapters: dict[str, Chapter]):
    protagonist = await db.scalar(select(StoryEntity).where(
        StoryEntity.user_id == user_id, StoryEntity.novel_id == novel_id,
        StoryEntity.source == "deterministic", StoryEntity.name == "主角"))
    if protagonist is None:
        protagonist = _new_protagonist(user_id, novel_id, chapters[chapter_ids[0]])
        db.add(protagonist)
    await db.flush()
    rows = list((await db.scalars(select(StoryEntity).where(
        StoryEntity.user_id == user_id, StoryEntity.novel_id == novel_id,
        StoryEntity.entity_type == "character"))).all())
    approval_at = utc_now().isoformat()
    for character in rows:
        if character.id != protagonist.id and character.name != "主角":
            protagonist.aliases = list(dict.fromkeys([*(protagonist.aliases or []), str(character.name or "")]))
            merge = {"status": "merged_superseded", "canonical_entity_id": protagonist.id, "merged_at": approval_at}
            character.extra_data = {**(character.extra_data or {}), "deterministic_merge": merge, "normalized_merge": dict(merge)}
            character.attributes = {**(character.attributes or {}), "merged_into_entity_id": protagonist.id}
            set_entity_review_status(character, ARCHIVED, changed_by=user_id, reason="merged_into_deterministic_protagonist")
            continue
        attrs = dict(character.attributes or {})
        attrs.pop("approval_record", None)
        attrs.setdefault("source_chapter_id", character.chapter_id or chapter_ids[0])
        attrs.setdefault("source_chapter_index", 1)
        attrs.setdefault("introduced_at", {"chapter_id": attrs["source_chapter_id"], "chapter_number": 1})
        attrs.setdefault("evidence_contract", deterministic_evidence_contract(chapters[str(attrs["source_chapter_id"])]))
        attrs.setdefault("visual_dna", {"costume": "深色长衣", "line_style": "统一二维动漫线稿"})
        attrs.setdefault("reference_requirements", {"character_multiview": ["front", "three_quarter", "full_body"]})
        attrs.update(speaking=True, voice_binding={"voice_id": "deterministic-protagonist-voice", "version": 1, "status": "locked"})
        character.chapter_id, character.first_seen_chapter_id = character.chapter_id or chapter_ids[0], character.first_seen_chapter_id or character.chapter_id
        character.version, character.attributes = int(character.version or 1), attrs
        set_entity_review_status(character, CANDIDATE, changed_by=user_id, reason="deterministic_acceptance_fixture")
    return protagonist


FACTS = (
    ("scene", "连续场景", 1, {"recurring": False, "scene_dna": {"lighting": "冷青电影光"}, "lighting": "冷青电影光"}),
    ("prop", "连续性道具", 2, {"continuity_critical": False, "prop_dna": {"state": "完好"}, "state": "完好"}),
    ("event", "道具被发现", 2, {"sequence": 2, "participants": ["主角"]}),
    ("event", "道具发生变化", 3, {"sequence": 3, "participants": ["主角"], "prop_state_changes": [{"prop": "连续性道具", "from": "完好", "to": "变化"}]}),
    ("event", "主角完成最终事件", 4, {"sequence": 4, "participants": ["主角"]}),
)


async def _fixture_entities(db: AsyncSession, user_id: str, novel_id: str, chapter_ids: list[str], chapters, protagonist):
    entities = {"主角": protagonist}
    for entity_type, name, number, fact_attrs in FACTS:
        chapter_id = chapter_ids[number - 1]
        existing = await db.scalar(select(StoryEntity).where(
            StoryEntity.user_id == user_id, StoryEntity.novel_id == novel_id,
            StoryEntity.source == "deterministic", StoryEntity.entity_type == entity_type, StoryEntity.name == name))
        if existing is None:
            existing = StoryEntity(id=str(uuid4()), user_id=user_id, novel_id=novel_id,
                chapter_id=chapter_id, first_seen_chapter_id=chapter_id, entity_type=entity_type,
                name=name, canonical_name=name, description=f"第{number}章已批准{name}", version=1, source="deterministic",
                attributes={**fact_attrs, "source_chapter_id": chapter_id, "source_chapter_index": number,
                    "introduced_at": {"chapter_id": chapter_id, "chapter_number": number},
                    "evidence_contract": deterministic_evidence_contract(chapters[chapter_id])})
            set_entity_review_status(existing, CANDIDATE, changed_by=user_id, reason="deterministic_acceptance_fixture")
            db.add(existing)
        entities[name] = existing
    await db.flush()
    return entities


def _decorate_shot(shot: Shot, protagonist: StoryEntity, episode: dict, refs: dict) -> None:
    shot.character_refs = [{"character_id": protagonist.id, "entity_id": protagonist.id, "name": "主角"}]
    shot.camera_angle, shot.camera_movement = shot.camera_angle or "medium", shot.camera_movement or "dolly"
    shot.lighting, shot.color_grading = shot.lighting or "cinematic", shot.color_grading or "consistent-anime"
    voice = ({"dialogue_speaker": "主角", "parsed_speaker": "主角",
              "voice_binding": {"entity_id": protagonist.id, "voice_id": "deterministic-protagonist-voice", "version": 1, "status": "locked"}}
             if str(shot.dialogue or "").strip() else {})
    shot.extra_data = {**(shot.extra_data or {}), "input_hash": episode["input_hash"],
        "chapter_id": episode["chapter_ids"][0], "entity_refs": refs, "character_evidence": True,
        "scene_refs": ["连续场景"], "continuity_prop": "连续性道具", "event_refs": ["道具被发现"],
        "event_turning_point": True, "style_evidence": True, "delivery_evidence": True,
        "final_consequence": True, **voice}


def _dialogue_anchor(user_id: str, storyboard_id: str, protagonist: StoryEntity, episode: dict, refs: dict, number: int) -> Shot:
    return Shot(id=str(uuid4()), user_id=user_id, storyboard_id=storyboard_id, shot_number=number,
        duration=4, prompt="主角携带连续性道具进入新场景，事件转折并形成最终后果",
        visual_description="统一动漫风格、角色外观、场景和关键道具", dialogue="主角：继续推进。",
        character_refs=[{"character_id": protagonist.id, "entity_id": protagonist.id, "name": "主角"}],
        camera_angle="close_up", camera_movement="dolly", lighting="cinematic", color_grading="consistent-anime",
        extra_data={"series_run_id": episode["series_run_id"], "episode_number": episode["episode_number"],
            "input_hash": episode["input_hash"], "chapter_id": episode["chapter_ids"][0], "entity_refs": refs,
            "deterministic_dialogue_anchor": True, "dialogue_speaker": "主角", "parsed_speaker": "主角",
            "dialogue_source": {"source": "deterministic_acceptance_fixture", "source_span": [0, 1]},
            "voice_binding": {"entity_id": protagonist.id, "voice_id": "deterministic-protagonist-voice", "version": 1, "status": "locked"},
            "character_evidence": True, "scene_refs": ["连续场景"], "continuity_prop": "连续性道具",
            "event_refs": ["主角完成最终事件" if int(episode["episode_number"]) == 4 else "道具被发现"],
            "event_turning_point": True, "style_evidence": True, "delivery_evidence": True, "final_consequence": True})


async def _episodes(db, run, user_id, chapters, entities, protagonist):
    episodes = [dict(item) for item in run.episodes or []]
    await seed_deterministic_local_mentions(db, user_id=user_id, novel_id=run.novel_id,
        episodes=episodes, chapters_by_id=chapters, fixture_entities=entities)
    for episode in episodes:
        source = [chapters[str(value)] for value in episode.get("chapter_ids") or []]
        episode["input_hash"] = "|".join(f"{item.id}:{item.updated_at.isoformat() if item.updated_at else ''}" for item in source)
        episode["series_run_id"] = run.id
        await sync_deterministic_episode_input_hash(db, run=run, episode=episode, input_hash=episode["input_hash"])
        canonical = dict(episode.get("canonical_ids") or {})
        storyboard_id, shot_ids = canonical.get("storyboard_id"), list(canonical.get("shot_ids") or [])
        if not storyboard_id or not shot_ids:
            continue
        rows = list((await db.scalars(select(Shot).where(Shot.id.in_(shot_ids), Shot.user_id == user_id))).all())
        refs = deterministic_anchor_entity_refs(entities, int(episode.get("episode_number") or 0))
        for shot in rows:
            _decorate_shot(shot, protagonist, episode, refs)
        if int(episode["episode_number"]) in {1, 4} and not any((row.extra_data or {}).get("deterministic_dialogue_anchor") for row in rows):
            extra = _dialogue_anchor(user_id, storyboard_id, protagonist, episode, refs,
                                     max([row.shot_number or 0 for row in rows] or [0]) + 1)
            db.add(extra); shot_ids.append(extra.id)
            board = await db.get(Storyboard, storyboard_id)
            if board is not None: board.shot_count = len(shot_ids)
        canonical["shot_ids"], episode["canonical_ids"] = shot_ids, canonical
        episode.pop("series_run_id", None)
    run.episodes = episodes


async def _configs(db, run, user_id, protagonist):
    provider = await db.get(LLMProvider, "deterministic-acceptance")
    if provider is None:
        provider = LLMProvider(id="deterministic-acceptance", name="deterministic-acceptance", name_cn="确定性验收",
            name_en="Deterministic Acceptance", provider_type="local", is_active=True, is_builtin=True)
        db.add(provider)
    selection = dict((run.run_metadata or {}).get("voice_selection") or {})
    tested_at = str(selection["tested_at"]) if selection.get("provider_id") == provider.id and selection.get("tested_at") else utc_now().isoformat()
    configs, bindings = {}, {}
    for capability in ("text", "image", "tts", "video"):
        model_id = f"deterministic-{capability}"
        model = await db.get(LLMModel, model_id)
        if model is None:
            model = LLMModel(id=model_id, provider_id=provider.id, model_id=model_id,
                model_name=f"Deterministic {capability}", model_type=capability, capabilities=[capability], is_active=True)
            db.add(model)
        config = await db.scalar(select(LLMConfig).where(LLMConfig.user_id == user_id,
            LLMConfig.model_id == model_id, LLMConfig.name == model_id))
        if config is None:
            config = LLMConfig(id=str(uuid4()), user_id=user_id, model_id=model_id, name=model_id, api_key="", is_active=True, test_status="pending")
            db.add(config)
        config.test_status, config.tested_at, config.test_message = "success", datetime.fromisoformat(tested_at).replace(tzinfo=None), "deterministic_config_test_v1"
        config.extra_params = {**(config.extra_params or {}), "test_audit": "deterministic_config_test_v1"}
        configs[capability] = config.id
        bindings[capability] = {"config_id": config.id, "db_model_id": model_id, "api_model_id": model_id,
                                "provider_id": provider.id, "tested_at": tested_at}
    apply_deterministic_voice_binding(protagonist, bindings["tts"], selection)
    run.model_bindings = {"capabilities": bindings, "provider_id": provider.id, "model_id": "deterministic-video"}
    return configs


async def setup_acceptance_fixture(db: AsyncSession, *, user_id: str, novel_id: str) -> dict[str, object]:
    novel, run, chapter_ids, chapters = await _context(db, user_id, novel_id)
    novel.extra_data = {**(novel.extra_data or {}), "visual_style":
                        (novel.extra_data or {}).get("visual_style") or "二维动漫，统一角色线稿、冷青主色与电影光影"}
    protagonist = await _protagonist(db, user_id, novel_id, chapter_ids, chapters)
    entities = await _fixture_entities(db, user_id, novel_id, chapter_ids, chapters, protagonist)
    await _episodes(db, run, user_id, chapters, entities, protagonist)
    configs = await _configs(db, run, user_id, protagonist)
    metadata = {**(run.run_metadata or {}), "deterministic_acceptance": True}
    metadata.pop("selected_anchor_shot_ids", None); metadata.pop("selected_anchor_mode", None)
    run.run_metadata = metadata
    await db.commit()
    return {"run_id": run.id, "config_ids": configs}


__all__ = ["setup_acceptance_fixture"]
