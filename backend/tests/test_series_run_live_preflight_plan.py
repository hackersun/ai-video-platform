from __future__ import annotations
from datetime import datetime, timedelta
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import hashlib
import json
import re
import threading
from uuid import uuid4
import pytest
import pytest_asyncio
import httpx
from fastapi import HTTPException
from PIL import Image, ImageDraw
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
import app.models  # noqa: F401
from app.core.database import Base
from app.core.minimax_voice_contract import DEFAULT_MINIMAX_TTS_VOICE
from app.core.time_utils import utc_now
from app.models import Asset, Chapter, LLMConfig, LLMModel, LLMProvider, MediaGenerationJob, Novel, ProviderAssetBinding, QualityEvaluation, Script, Shot, StoryBible, StoryEntity, Storyboard, Workflow
from app.models.live_canary_provider_operation import LiveCanaryProviderOperation
from app.models.series_anchor_generation_submission import SeriesAnchorGenerationSubmission
from app.models.series_production_run import SeriesProductionRun
from app.services.series_run_live_preflight import (
    StoryLockPreparationBlocked,
    build_live_preflight_plan,
    inspect_story_lock_freshness,
    prepare_story_locks,
    persist_voice_selection,
)
from app.services.series_run_reference_preparation import (
    ReferencePreSubmitRejected,
    ReferencePreparationBlocked,
    _fetch_and_verify_image,
    prepare_series_reference,
)
from app.services.series_reference_provider import ReferenceAdapterStageError
from app.services.series_reference_artifact_recovery import PersistedReferenceArtifactAdapter
from app.services.story_entity_lifecycle import APPROVED, get_entity_review_status, set_entity_review_status
from app.services.chapter_fact_timeline import project_entities_as_of_chapter
from app.services.reference_layout_evaluator import evaluate_reference_layout, validate_layout_evidence
from app.api.v1.endpoints.series_runs import AnchorSelectionRequest, DeterministicAcceptanceSetupRequest, GenerateSelectedRequest, PrepareReferenceResponse, _run_shots, generate_selected_series_run_anchors, get_series_run_live_preflight_plan, post_series_run_prepare_reference, post_series_run_prepare_story_locks, put_series_run_anchor_shots, setup_deterministic_acceptance
from app.services.anchor_shot_service import recommend_anchor_shots
from app.services.live_canary_budget import required_tested_at_for_run, validate_model_bindings
from app.services.live_canary_repair_budget import grant_live_canary_repair_extension
from app.features.series_run_story_locks.application.explicit_dialogue_approval import (
    _prepare_explicit_dialogue_facts,
)
@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
@pytest.fixture()
def reference_http_server():
    def png(width: int, height: int) -> bytes:
        buffer = BytesIO()
        image = Image.new("RGB", (width, height), "#e8e2d6")
        draw = ImageDraw.Draw(image)
        split = int(width * 0.60)
        panel_width = split // 3
        for index in range(3):
            x0 = index * panel_width
            draw.rectangle((x0 + 8, 8, x0 + panel_width - 8, height - 8), fill=(220 - index * 8, 230, 235 + index * 5), outline="#203040", width=5)
            cx = x0 + panel_width // 2 + (index - 1) * 12
            draw.ellipse((cx - 55, 120, cx + 55, 230), fill="#d8ad8b", outline="#182838", width=8)
            draw.polygon(((cx - 90, 250), (cx + 90, 250), (cx + 125 - index * 15, 760), (cx - 110 + index * 12, 760)), fill="#243a59", outline="#102030")
            draw.line((cx - 60, 360, cx - 135 + index * 20, 590), fill="#102030", width=22)
            draw.line((cx + 60, 360, cx + 135 - index * 20, 590), fill="#102030", width=22)
            draw.line((cx - 45, 750, cx - 70 + index * 10, 960), fill="#102030", width=25)
            draw.line((cx + 45, 750, cx + 70 - index * 10, 960), fill="#102030", width=25)
        draw.rectangle((split, 0, width - 1, height - 1), fill="#162334", outline="#e0c080", width=6)
        for y in range(60, 620, 45):
            draw.line((split + 35, y, width - 35, y + (y % 90) - 30), fill=(65 + y % 80, 90, 120), width=7)
        swatches = ["#1b2a41", "#406080", "#c08a52", "#e0c9a6", "#7f3448"]
        swatch_width = (width - split - 80) // len(swatches)
        for index, color in enumerate(swatches):
            x0 = split + 40 + index * swatch_width
            draw.rectangle((x0, 700, x0 + swatch_width - 12, 930), fill=color, outline="white", width=4)
        image.save(buffer, "PNG")
        return buffer.getvalue()

    blank_buffer = BytesIO()
    Image.new("RGB", (1536, 1024), "white").save(blank_buffer, "PNG")
    small_buffer = BytesIO()
    Image.new("RGB", (64, 64), "#2060a0").save(small_buffer, "PNG")

    payloads = {
        "/valid.png": (200, "image/png", png(1536, 1024)),
        "/small.png": (200, "image/png", small_buffer.getvalue()),
        "/html": (200, "text/html", b"<html>not an image</html>"),
        "/bad.png": (200, "image/png", b"not-a-decodable-image"),
        "/blank.png": (200, "image/png", blank_buffer.getvalue()),
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status_code, content_type, body = payloads.get(self.path, (404, "text/plain", b"missing"))
            self.send_response(status_code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
def _visual_evidence() -> dict:
    return {
        "source": "trusted_vision_evaluator",
        "evaluator_version": "reference-layout-v1",
        "score": 0.96,
        "character_sheet": {
            "views": ["front", "three_quarter", "full_body"],
            "subject_region": [0.02, 0.05, 0.58, 0.95],
        },
        "style_board": {
            "region": [0.60, 0.05, 0.98, 0.95],
            "palette": ["#2060a0", "#102030", "#e0d0b0"],
        },
    }
def _verified_entity_attrs(entity: StoryEntity, chapter: Chapter) -> dict:
    content = str(chapter.content or "")
    return {**(entity.attributes or {}), "evidence_contract": {"status":"verified",
        "chapter_id":chapter.id, "source_span":[0,1],
        "content_hash":hashlib.sha256(content.encode()).hexdigest(),
        "source_excerpt":content[:1], "parser_version":"deterministic-extraction-v2"}}
async def _fixture(db: AsyncSession, *, dialogue: str = "沈砚：别碰铜铃。") -> SeriesProductionRun:
    user_id, novel_id = str(uuid4()), str(uuid4())
    now = utc_now() - timedelta(hours=1)
    db.add(Novel(
        id=novel_id, user_id=user_id, title="四章锁定测试", description="雾城守灯人",
        extra_data={"visual_style": "二维国风动漫，冷青色光影"}, created_at=now, updated_at=now,
    ))
    chapters = []
    workflows = []
    shots = []
    episodes = []
    for number, content in enumerate((
        "沈砚穿黑色长衣进入钟楼。", "沈砚发现铜铃。", "灯笼在雨中破损。", "沈砚在码头完成守灯仪式。",
    ), 1):
        chapter = Chapter(
            id=str(uuid4()), novel_id=novel_id, user_id=user_id, title=f"第{number}章",
            content=content, chapter_number=number, status="completed", created_at=now, updated_at=now,
        )
        script = Script(id=str(uuid4()), user_id=user_id, novel_id=novel_id, title=f"剧本{number}", content=content, status="draft", extra_data={})
        storyboard = Storyboard(id=str(uuid4()), user_id=user_id, novel_id=novel_id, script_id=script.id, title=f"分镜{number}", content={}, shot_count=1, status="draft")
        shot = Shot(
            id=str(uuid4()), user_id=user_id, storyboard_id=storyboard.id, shot_number=1,
            prompt=content, dialogue=dialogue if number in {1, 4} else "", character_refs=[{"name": "沈砚"}],
            extra_data={"episode_number": number, "event_refs": [f"event-{number}"]},
        )
        workflow = Workflow(
            id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter.id,
            storyboard_id=storyboard.id, script_id=script.id, title=f"工作流{number}", status="pending",
            metadata_={"episode_number": number},
        )
        db.add_all([chapter, script, storyboard, shot, workflow])
        shots.append(shot)
        chapters.append(chapter)
        workflows.append(workflow)
        episodes.append({
            "episode_number": number, "chapter_ids": [chapter.id], "stage": "shots_ready",
            "canonical_ids": {"workflow_id": workflow.id, "shot_ids": [shot.id]},
            "input_hash": f"{chapter.id}:{chapter.updated_at.isoformat()}",
        })
    protagonist = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapters[0].id,
        first_seen_chapter_id=chapters[0].id, entity_type="character", name="沈砚", canonical_name="沈砚",
        description="守灯人", is_approved=True, source="manual",
        attributes={
            "approval_record": {"approved_by": user_id, "approved_at": now.isoformat()},
            "evidence_contract": {"status": "verified", "chapter_id": chapters[0].id,
                                  "source_span": [0, 1], "content_hash": hashlib.sha256(chapters[0].content.encode()).hexdigest(),
                                  "source_excerpt": chapters[0].content[:1],
                                  "parser_version": "deterministic-extraction-v2"},
            "speaking": True, "voice_binding": {"voice_id": "voice-shenyan", "version": 1, "status": "locked"},
            "visual_dna": {"costume": "黑色长衣"}, "reference_requirements": {"character_multiview": ["front", "three_quarter", "full_body"]},
        },
    )
    future_prop = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapters[2].id,
        first_seen_chapter_id=chapters[2].id, entity_type="prop", name="破损灯笼", canonical_name="破损灯笼",
        description="第三章才出现", is_approved=True, source="manual",
        attributes={"approval_record": {"approved_by": user_id, "approved_at": now.isoformat()}, "state": "破损",
                    "evidence_contract": {"status": "verified", "chapter_id": chapters[2].id,
                                          "source_span": [0, 1], "content_hash": hashlib.sha256(chapters[2].content.encode()).hexdigest(),
                                          "source_excerpt": chapters[2].content[:1],
                                          "parser_version": "deterministic-extraction-v2"}},
    )
    rejected_candidate = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapters[3].id,
        first_seen_chapter_id=chapters[3].id,
        entity_type="event", name="守灯仪式", canonical_name="守灯仪式", is_approved=True,
        source="deterministic", attributes={"approval_record":{"approved_by":user_id,"approved_at":now.isoformat()},"evidence_contract":{"status":"verified",
            "chapter_id":chapters[3].id,"source_span":[7,11],
            "content_hash":hashlib.sha256(chapters[3].content.encode()).hexdigest(),
            "source_excerpt":chapters[3].content[7:11],"parser_version":"deterministic-extraction-v2"}},
    )
    rejected_candidate.attributes = {**rejected_candidate.attributes, "approval_record":{"approved_by":user_id,"approved_at":now.isoformat()}}
    set_entity_review_status(rejected_candidate, APPROVED, changed_by=user_id, reason="fixture_manual_review")
    run = SeriesProductionRun(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, series_plan_version="four-v1",
        idempotency_key=str(uuid4()), status="anchor_ready", current_episode_number=4,
        requested_stages=["media"], model_bindings={},
        budget_policy={
            "profile": "isolated_live_canary", "live_canary": True, "max_rmb": "10.00",
            "estimates_rmb": {"image": "1.00", "video": "3.00", "tts": "0.50"},
        },
        cost_summary={"spent_rmb": "0.00", "reserved_rmb": "0.00", "reservations": {}}, gate_summary={},
        run_metadata={"selected_anchor_shot_ids": [episodes[0]["canonical_ids"]["shot_ids"][0], episodes[3]["canonical_ids"]["shot_ids"][0]], "selected_anchor_mode": "smoke"},
        episodes=episodes, created_at=utc_now(), updated_at=utc_now(), version=1,
    )
    updated_episodes=[]
    for episode,workflow,shot in zip(episodes,workflows,shots,strict=True):
        storyboard=await db.get(Storyboard,shot.storyboard_id); script=await db.get(Script,storyboard.script_id)
        tag={"series_run_id":run.id,"episode_number":episode["episode_number"],"input_hash":episode["input_hash"]}
        workflow.metadata_={**(workflow.metadata_ or {}),**tag}; script.extra_data={**(script.extra_data or {}),**tag}
        storyboard.content={**(storyboard.content or {}),**tag}; shot.extra_data={**(shot.extra_data or {}),**tag,
            "chapter_id":episode["chapter_ids"][0]}
        canonical={**episode["canonical_ids"],"script_id":script.id,"storyboard_id":storyboard.id}
        updated_episodes.append({**episode,"canonical_ids":canonical})
    run.episodes=updated_episodes
    for index in (0, 3):
        shots[index].extra_data = {
            **(shots[index].extra_data or {}), "chapter_id": chapters[index].id,
            "entity_refs": {
                "characters": ([{"entity_id": protagonist.id}] if index == 0 else []),
                "scenes": [], "props": [],
                "events": ([{"entity_id": rejected_candidate.id}] if index == 3 else []),
            },
        }
    db.add_all([protagonist, future_prop, rejected_candidate, run])
    await db.flush()
    from app.services.episode_production_service import create_or_resolve_shots_stage
    for index in (0,3):
        await create_or_resolve_shots_stage(db,run=run,episode=updated_episodes[index])
    await db.commit()
    return run
async def _refresh_fixture_production_contracts(db: AsyncSession, run: SeriesProductionRun) -> None:
    selected = set((run.run_metadata or {}).get("selected_anchor_shot_ids") or [])
    for episode in run.episodes or []:
        canonical = episode["canonical_ids"]
        workflow = await db.get(Workflow, canonical["workflow_id"])
        script = await db.get(Script, canonical["script_id"])
        storyboard = await db.get(Storyboard, canonical["storyboard_id"])
        tag = {"series_run_id": run.id, "episode_number": episode["episode_number"],
               "input_hash": episode["input_hash"]}
        workflow.metadata_ = {**(workflow.metadata_ or {}), **tag}
        script.extra_data = {**(script.extra_data or {}), **tag}
        storyboard.content = {**(storyboard.content or {}), **tag}
        for shot_id in canonical.get("shot_ids") or []:
            shot = await db.get(Shot, shot_id)
            if shot and shot.id in selected: shot.extra_data = {**(shot.extra_data or {}), **tag, "chapter_id": episode["chapter_ids"][0]}
    await db.flush()
    from app.features.series_run_story_locks.application.closure_v2_request import refresh_scoped_for_shot
    for episode in run.episodes or []:
        shot_ids = selected.intersection((episode["canonical_ids"].get("shot_ids") or []))
        if not shot_ids:
            continue
        for shot_id in shot_ids:
            shot = await db.get(Shot, shot_id)
            refs = [ref for values in ((shot.extra_data or {}).get("entity_refs") or {}).values() for ref in values]
            entities = [await db.get(StoryEntity, ref.get("entity_id")) for ref in refs]
            complete = refs and all(entity is not None and ((entity.attributes or {}).get("evidence_contract") or {}).get("source_excerpt") is not None for entity in entities)
            if complete:
                try:
                    await refresh_scoped_for_shot(db, run, shot)
                except ValueError:
                    # Invalid/ambiguous fixtures are intentionally preserved so the
                    # Story Lock call under test can prove its fail-closed behavior.
                    continue
    await db.commit()
async def _fresh_bindings(db: AsyncSession, run: SeriesProductionRun, *, voice_id: str = DEFAULT_MINIMAX_TTS_VOICE) -> dict[str, str]:
    now = utc_now()
    ids = {}
    for capability, provider_id, model_type, tags in (
        ("text", "unit-text-provider", "chat", ["chat"]),
        ("image", "unit-image-provider", "image-generation", ["image-generation"]),
        ("tts", "minimax", "tts", ["text-to-speech"]),
        ("video", "unit-video-provider", "video-generation", ["video-generation"]),
    ):
        if await db.get(LLMProvider, provider_id) is None:
            db.add(LLMProvider(id=provider_id, name=provider_id, provider_type="cloud", is_active=True))
        model_id = f"unit-{capability}-model"
        db.add(LLMModel(id=model_id, provider_id=provider_id, model_id=model_id,
                        model_name=model_id, model_type=model_type, capabilities=tags, is_active=True))
        config_id = str(uuid4())
        db.add(LLMConfig(id=config_id, user_id=run.user_id, model_id=model_id, name=f"unit-{capability}",
                         api_key="unit", extra_params=({"voice_id": voice_id} if capability == "tts" else {}),
                         is_active=True, test_status="success", tested_at=now))
        ids[capability] = config_id
    run.model_bindings = {"capabilities": {key: {"config_id": value} for key, value in ids.items()}}
    await db.commit()
    await persist_voice_selection(db, run, config_id=ids["tts"], model_id="unit-tts-model",
                                  voice_id=voice_id, version=1)
    candidates = list((await db.scalars(select(StoryEntity).where(
        StoryEntity.user_id == run.user_id, StoryEntity.novel_id == run.novel_id,
        StoryEntity.entity_type == "character",
    ))).all())
    candidates = [item for item in candidates if item.name == "沈砚" or item.canonical_name == "沈砚"]
    for candidate in candidates:
        candidate.attributes = _verified_entity_attrs(candidate, await db.get(Chapter, candidate.chapter_id))
    await db.flush()
    if candidates:
        selected_ids = set((run.run_metadata or {}).get("selected_anchor_shot_ids") or [])
        selected = list((await db.scalars(select(Shot).where(Shot.id.in_(selected_ids)))).all())
        entities = list((await db.scalars(select(StoryEntity).where(
            StoryEntity.novel_id == run.novel_id,
        ))).all())
        by_id = {item.id: item for item in entities}
        buckets = {"characters": "character", "scenes": "scene", "props": "prop", "events": "event"}
        for shot in selected:
            extra = dict(shot.extra_data or {})
            episode = next(item for item in (run.episodes or []) if shot.id in (item.get("canonical_ids") or {}).get("shot_ids", []))
            chapter_id = str(episode["chapter_ids"][0])
            extra["chapter_id"] = chapter_id
            refs = dict(extra.get("entity_refs") or {})
            local = [item for item in candidates if str(item.chapter_id) == chapter_id]
            if local:
                candidate = sorted(local, key=lambda item: (item.created_at or utc_now(), item.id))[0]
                refs["characters"] = [{"entity_id": candidate.id}]
            for plural, entity_type in buckets.items():
                refs[plural] = [item for item in (refs.get(plural) or [])
                                if (entity := by_id.get(item.get("entity_id"))) is not None
                                and entity.entity_type == entity_type and str(entity.chapter_id) == chapter_id]
            extra["entity_refs"] = refs
            shot.extra_data = extra
    await _refresh_fixture_production_contracts(db, run)
    return ids
async def _explicit_dialogue_source(db: AsyncSession, run: SeriesProductionRun) -> None:
    episodes = [dict(item) for item in run.episodes]
    for index in (0, 3):
        chapter = await db.get(Chapter, episodes[index]["chapter_ids"][0])
        chapter.content = f"沈砚说：“第{index + 1}章明确对白。”"
        chapter.updated_at = utc_now()
        episodes[index]["input_hash"] = f"{chapter.id}:{chapter.updated_at.isoformat()}"
        shot = await db.get(Shot, episodes[index]["canonical_ids"]["shot_ids"][0])
        shot.dialogue = f"沈砚：第{index + 1}章明确对白。"
        shot.extra_data = {**(shot.extra_data or {}), "dialogue_source": {"script_id": "unit", "source_span": [0, len(chapter.content)]},
                           "dialogue_speaker": "沈砚", "parsed_speaker": "沈砚"}
        for entity in (await db.scalars(select(StoryEntity).where(
            StoryEntity.novel_id == run.novel_id, StoryEntity.chapter_id == chapter.id,
        ))).all():
            entity.attributes = {**(entity.attributes or {}), "evidence_contract": {
                "status": "verified", "chapter_id": chapter.id, "source_span": [0, 1],
                "content_hash": hashlib.sha256(chapter.content.encode()).hexdigest(),
                "source_excerpt": chapter.content[:1], "parser_version": "explicit-dialogue-v1",
            }}
    run.episodes = episodes
    await db.commit()


@pytest.mark.asyncio
async def test_native_audio_story_lock_does_not_require_tts_binding(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    await _explicit_dialogue_source(db_session, run)
    await _refresh_fixture_production_contracts(db_session, run)

    result = await prepare_story_locks(db_session, run, native_audio=True)
    repeated = await prepare_story_locks(db_session, run, native_audio=True)
    speaker = await db_session.scalar(select(StoryEntity).where(
        StoryEntity.novel_id == run.novel_id,
        StoryEntity.entity_type == "character",
        StoryEntity.name == "沈砚",
    ))

    assert result["status"] == "locked"
    assert repeated["story_bible_id"] == result["story_bible_id"]
    assert speaker is not None and speaker.is_approved is True
    assert speaker.attributes["speaking"] is True
    assert "voice_binding" not in speaker.attributes

@pytest.mark.asyncio
async def test_explicit_dialogue_rule_atomically_creates_approved_entity_voice_and_enriches_two_anchors(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    novel_id = run.novel_id
    await db_session.execute(delete(StoryEntity).where(StoryEntity.novel_id == run.novel_id))
    await db_session.commit()
    await _explicit_dialogue_source(db_session, run)
    ids = await _fresh_bindings(db_session, run)
    snapshots = await validate_model_bindings(
        db_session, run, ids, required_tested_at=required_tested_at_for_run(run), freshness_seconds=900,
    )
    chapters = list((await db_session.scalars(select(Chapter).where(
        Chapter.novel_id == run.novel_id,
    ).order_by(Chapter.chapter_number))).all())
    await _prepare_explicit_dialogue_facts(db_session, run, chapters, snapshots["tts"])
    created = await db_session.scalar(select(StoryEntity).where(
        StoryEntity.novel_id == run.novel_id, StoryEntity.entity_type == "character",
    ))
    for shot_id in (run.run_metadata or {})["selected_anchor_shot_ids"]:
        shot = await db_session.get(Shot, shot_id)
        shot.extra_data = {**(shot.extra_data or {}), "entity_refs": {
            "characters": [{"entity_id": created.id}], "scenes": [], "props": [], "events": [],
        }}
    await db_session.commit()

    result = await prepare_story_locks(db_session, run)
    repeated = await prepare_story_locks(db_session, run)
    assert result["status"] == "locked"
    assert repeated["idempotent"] is True and repeated["story_bible_id"] == result["story_bible_id"]
    entity = await db_session.scalar(select(StoryEntity).where(StoryEntity.novel_id == run.novel_id))
    assert entity.source == "system" and entity.is_approved is True
    assert entity.attributes["approval_record"]["reason"] == "rule_based_explicit_dialogue_v1"
    assert entity.attributes["voice_binding"]["config_id"] == ids["tts"]
    assert entity.attributes["voice_binding"]["voice_id"] == DEFAULT_MINIMAX_TTS_VOICE
    for index in (0, 3):
        shot = await db_session.get(Shot, run.episodes[index]["canonical_ids"]["shot_ids"][0])
        reference = shot.extra_data["entity_refs"]["characters"][0]
        assert reference["canonical_entity_id"] == entity.id
        assert shot.extra_data["story_lock_lineage"]["story_bible_id"] == result["story_bible_id"]
        assert shot.character_refs[0]["canonical_entity_id"] == entity.id

@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["candidate", "rejected", "archived"])
async def test_explicit_dialogue_never_upgrades_preexisting_non_rule_lifecycle(db_session: AsyncSession, status: str) -> None:
    from app.services.story_entity_lifecycle import set_entity_review_status
    run = await _fixture(db_session)
    novel_id = run.novel_id
    entity = await db_session.scalar(select(StoryEntity).where(
        StoryEntity.novel_id == run.novel_id, StoryEntity.entity_type == "character"))
    entity.source = "manual"
    set_entity_review_status(entity, status, changed_by=run.user_id, reason="review")
    await db_session.commit()
    await _explicit_dialogue_source(db_session, run)
    await _fresh_bindings(db_session, run)

    with pytest.raises(StoryLockPreparationBlocked, match="requires review"):
        await prepare_story_locks(db_session, run)
    assert await db_session.scalar(select(func.count()).select_from(StoryBible).where(StoryBible.novel_id == novel_id)) == 0

@pytest.mark.asyncio
async def test_explicit_dialogue_normalizes_safe_deterministic_duplicates_then_approves_one_canonical(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    await db_session.execute(delete(StoryEntity).where(StoryEntity.novel_id == run.novel_id))
    await db_session.commit()
    await _explicit_dialogue_source(db_session, run)
    for index in reversed(range(4)):
        episode = run.episodes[index]
        db_session.add(StoryEntity(
            id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
            chapter_id=episode["chapter_ids"][0], first_seen_chapter_id=episode["chapter_ids"][0],
            entity_type="character", name="沈砚", canonical_name="沈砚", source="deterministic",
            version=1, description=(["规则识别人物", "规则识别人物动作", "规则识别人物描述", "规则识别人物描述"][index]),
            attributes={"gender": "male"},
            relations=([{"entity_id": "港务长", "type": "ally", "chapter_id": episode["chapter_ids"][0]}] if index == 1 else []),
            state_changes=[],
            tags=(["主角", "人类", "存活"] if index == 0 else
                  ["protagonist", "human", "injured"] if index == 1 else
                  ["lead", "凡人", "死亡"] if index == 2 else ["lead", "凡人"]),
            extra_data={"extraction": {"chapter_index": index + 1}},
        ))
    await db_session.commit()
    run.run_metadata = {**(run.run_metadata or {}), "selected_anchor_shot_ids": [
        run.episodes[0]["canonical_ids"]["shot_ids"][0], run.episodes[3]["canonical_ids"]["shot_ids"][0],
    ]}
    await db_session.commit()
    await _fresh_bindings(db_session, run)

    first = await prepare_story_locks(db_session, run)
    second = await prepare_story_locks(db_session, run)
    rows = list((await db_session.scalars(select(StoryEntity).where(
        StoryEntity.novel_id == run.novel_id, StoryEntity.name == "沈砚",
    ))).all())
    active = [row for row in rows if get_entity_review_status(row) != "archived"]
    merged = [row for row in rows if get_entity_review_status(row) == "archived"]
    assert first["story_bible_id"] == second["story_bible_id"]
    assert len(active) == 1 and get_entity_review_status(active[0]) == "approved"
    assert len(merged) == 4 and {row.chapter_id for row in merged} == {item["chapter_ids"][0] for item in run.episodes}
    assert all(row.extra_data["normalized_merge"]["canonical_entity_id"] == active[0].id and len(row.extra_data["merge_edges"]) == 1 for row in merged)
    selected_shots = [await db_session.get(Shot, shot_id) for shot_id in run.run_metadata["selected_anchor_shot_ids"]]
    assert all((shot.extra_data["entity_refs"]["characters"][0]).get("source_entity_id") != active[0].id
               for shot in selected_shots)
    assert len(active[0].extra_data["entity_normalization"]["merged_entity_ids"]) == 3
    assert active[0].chapter_id == run.episodes[0]["chapter_ids"][0]
    assert active[0].first_seen_chapter_id == run.episodes[0]["chapter_ids"][0]
    assert active[0].attributes["source_chapter_index"] == 1
    assert active[0].attributes["gender"] == "male"
    assert len(active[0].relations) == 1 and [item["state"] for item in active[0].state_changes] == ["alive", "injured", "dead"]
    assert active[0].attributes["role"] == "protagonist" and active[0].attributes["species"] == "human"
    assert active[0].tags == ["role:protagonist", "species:human"]
    chapters = list((await db_session.scalars(select(Chapter).where(Chapter.novel_id == run.novel_id))).all())
    chapter_one = project_entities_as_of_chapter([active[0]], chapters, chapter_number=1, strict=True)[0]
    assert chapter_one.relations == [] and [item["state"] for item in chapter_one.state_changes] == ["alive"]
    tampered_shot = selected_shots[0]
    refs = dict(tampered_shot.extra_data["entity_refs"])
    character_ref = dict(refs["characters"][0])
    character_ref["source_entity_id"] = character_ref["canonical_entity_id"]
    character_ref["evidence"] = {**character_ref["evidence"],
        "source_entity_id": character_ref["canonical_entity_id"]}
    from app.features.series_run_story_locks.domain.scoped_reference import evidence_ref_id
    character_ref["evidence_ref_id"] = evidence_ref_id(character_ref)
    refs["characters"] = [character_ref]
    tampered_shot.extra_data = {**tampered_shot.extra_data, "entity_refs": refs}
    await db_session.commit()
    with pytest.raises(StoryLockPreparationBlocked, match="story_lock_source_invalid"):
        await prepare_story_locks(db_session, run)


@pytest.mark.asyncio
async def test_explicit_dialogue_uses_run_episode_order_when_chapter_numbers_repeat(
    db_session: AsyncSession,
) -> None:
    run = await _fixture(db_session)
    chapters = list((await db_session.scalars(select(Chapter).where(
        Chapter.novel_id == run.novel_id,
    ))).all())
    for chapter in chapters:
        chapter.chapter_number = 1
    await db_session.execute(delete(StoryEntity).where(StoryEntity.novel_id == run.novel_id))
    await db_session.commit()
    await _explicit_dialogue_source(db_session, run)
    episodes = [dict(item) for item in run.episodes]
    final_chapter = await db_session.get(Chapter, episodes[3]["chapter_ids"][0])
    final_chapter.content = "影潮使说：“第四章明确对白。”"
    final_chapter.updated_at = utc_now()
    episodes[3]["input_hash"] = f"{final_chapter.id}:{final_chapter.updated_at.isoformat()}"
    final_shot = await db_session.get(Shot, episodes[3]["canonical_ids"]["shot_ids"][0])
    final_shot.dialogue = "影潮使：第四章明确对白。"
    final_shot.extra_data = {**(final_shot.extra_data or {}),
        "dialogue_speaker": "影潮使", "parsed_speaker": "影潮使"}
    first_shot = await db_session.get(Shot, episodes[0]["canonical_ids"]["shot_ids"][0])
    first_shot.extra_data = {**(first_shot.extra_data or {}),
        "prompt_skill": {"id": "test-shot-skill", "version": 1}}
    run.episodes = episodes
    await db_session.commit()
    created_at = utc_now() - timedelta(minutes=10)
    entity_ids = ["z-first-episode", "y-second-episode", "a-third-episode", "x-fourth-episode"]
    for index, episode in enumerate(run.episodes):
        db_session.add(StoryEntity(
            id=entity_ids[index], user_id=run.user_id, novel_id=run.novel_id,
            chapter_id=episode["chapter_ids"][0], first_seen_chapter_id=episode["chapter_ids"][0],
            entity_type="character", name="沈砚", canonical_name="沈砚", source="deterministic",
            version=1, description="规则识别人物", attributes={"gender": "male"},
            relations=[], state_changes=[], tags=[], extra_data={},
            created_at=created_at + timedelta(seconds=index),
        ))
    await db_session.commit()
    run.run_metadata = {**(run.run_metadata or {}), "selected_anchor_shot_ids": [
        run.episodes[0]["canonical_ids"]["shot_ids"][0],
        run.episodes[3]["canonical_ids"]["shot_ids"][0],
    ]}
    await db_session.commit()
    await _fresh_bindings(db_session, run)

    result = await prepare_story_locks(db_session, run, native_audio=True)
    active = list((await db_session.scalars(select(StoryEntity).where(
        StoryEntity.novel_id == run.novel_id,
        StoryEntity.name == "沈砚",
    ))).all())
    canonical = next(item for item in active if get_entity_review_status(item) != "archived")

    assert result["status"] == "locked"
    assert canonical.chapter_id == run.episodes[0]["chapter_ids"][0]
    assert canonical.attributes["source_chapter_index"] == 1

@pytest.mark.asyncio
async def test_explicit_dialogue_does_not_merge_manual_or_visual_conflicts(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    novel_id = run.novel_id
    await db_session.execute(delete(StoryEntity).where(StoryEntity.novel_id == novel_id))
    await db_session.commit()
    await _explicit_dialogue_source(db_session, run)
    rows = [
        StoryEntity(id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
                    chapter_id=run.episodes[0]["chapter_ids"][0], entity_type="character", name="沈砚",
                    canonical_name="沈砚", source="manual", version=1, description="勇敢少年", attributes={}, extra_data={}),
        StoryEntity(id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
                    chapter_id=run.episodes[1]["chapter_ids"][0], entity_type="character", name="沈砚",
                    canonical_name="沈砚", source="deterministic", version=1, description="冷酷反派",
                    attributes={"visual_dna": {"costume": "冲突红衣"}}, extra_data={}),
    ]
    row_ids = [row.id for row in rows]
    db_session.add_all(rows)
    await db_session.commit()
    await _fresh_bindings(db_session, run)

    with pytest.raises(StoryLockPreparationBlocked, match="explicit_dialogue_character_conflict"):
        await prepare_story_locks(db_session, run)
    assert await db_session.scalar(select(func.count()).select_from(StoryBible).where(StoryBible.novel_id == novel_id)) == 0
    persisted = list((await db_session.scalars(select(StoryEntity).where(StoryEntity.id.in_(row_ids)))).all())
    assert all(get_entity_review_status(row) != "archived" for row in persisted)

@pytest.mark.asyncio
@pytest.mark.parametrize("attribute_key,values", [
    ("visual_dna", [{"costume": "红衣"}, {"costume": "蓝衣"}]),
    ("voice_binding", [{"voice_id": "female-shaonv"}, {"voice_id": "male-qn-jingying"}]),
    ("gender", ["male", "female"]),
    ("role", ["investigator", "smuggler"]),
    ("species", ["human", "spirit"]),
])
async def test_explicit_dialogue_does_not_merge_conflicting_system_identity_attributes(
    db_session: AsyncSession, attribute_key: str, values: list[dict],
) -> None:
    run = await _fixture(db_session)
    novel_id = run.novel_id
    await db_session.execute(delete(StoryEntity).where(StoryEntity.novel_id == novel_id))
    await db_session.commit()
    await _explicit_dialogue_source(db_session, run)
    rows = [StoryEntity(
        id=str(uuid4()), user_id=run.user_id, novel_id=novel_id,
        chapter_id=run.episodes[index]["chapter_ids"][0], entity_type="character",
        name="沈砚", canonical_name="沈砚", source="deterministic", version=1,
        attributes={attribute_key: value}, extra_data={},
    ) for index, value in enumerate(values)]
    row_ids = [row.id for row in rows]
    db_session.add_all(rows)
    await db_session.commit()
    await _fresh_bindings(db_session, run)
    with pytest.raises(StoryLockPreparationBlocked, match="explicit_dialogue_character_conflict"):
        await prepare_story_locks(db_session, run)
    persisted = list((await db_session.scalars(select(StoryEntity).where(StoryEntity.id.in_(row_ids)))).all())
    assert all(get_entity_review_status(row) != "archived" for row in persisted)


@pytest.mark.asyncio
async def test_explicit_dialogue_merges_placeholder_costume_into_concrete_visual_dna(
    db_session: AsyncSession,
) -> None:
    run = await _fixture(db_session)
    await db_session.execute(delete(StoryEntity).where(StoryEntity.novel_id == run.novel_id))
    await db_session.commit()
    await _explicit_dialogue_source(db_session, run)
    shared = {
        "identity_anchor": "沈砚",
        "silhouette": "沈砚 的稳定头身比例和脸型",
        "palette": "依据作品统一色彩",
    }
    rows = [StoryEntity(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
        chapter_id=run.episodes[index]["chapter_ids"][0], entity_type="character",
        name="沈砚", canonical_name="沈砚", source="deterministic", version=1,
        attributes={"visual_dna": {**shared, "costume": costume}}, extra_data={},
    ) for index, costume in enumerate([
        "深蓝旧呢大衣", "依据原文固定服装与标志配饰", "依据原文固定服装与标志配饰",
    ])]
    db_session.add_all(rows)
    await db_session.commit()
    await _fresh_bindings(db_session, run)

    result = await prepare_story_locks(db_session, run, native_audio=True)

    assert result["status"] == "locked"
    active = list((await db_session.scalars(select(StoryEntity).where(
        StoryEntity.novel_id == run.novel_id, StoryEntity.is_approved.is_(True),
    ))).all())
    assert len(active) == 1
    assert active[0].attributes["visual_dna"]["costume"] == "深蓝旧呢大衣"

@pytest.mark.asyncio
async def test_explicit_dialogue_ignores_only_versioned_system_extraction_metadata(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    await db_session.execute(delete(StoryEntity).where(StoryEntity.novel_id == run.novel_id))
    await db_session.commit()
    await _explicit_dialogue_source(db_session, run)
    rows = [StoryEntity(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
        chapter_id=run.episodes[index]["chapter_ids"][0], entity_type="character",
        name="沈砚", canonical_name="沈砚", source="deterministic", version=1,
        evidence=f"chapter-{index + 1}-extraction-evidence", confidence=0.7 + index / 10,
        attributes={
            "extraction_notes": [note], "description_semantics_version": "system_boilerplate_v1",
            "source_kind": "deterministic_rule", "mention_count": index + 1,
            "mention_stats": {"chapter_mentions": index + 1}, "extraction_confidence": 0.8 + index / 10,
            "evidence_contract": {
                "status": "verified", "chapter_id": run.episodes[index]["chapter_ids"][0],
                "source_span": [index, index + 1], "content_hash": f"chapter-{index + 1}-hash",
                "parser_version": "deterministic-extraction-v2",
            },
            "visual_dna": {"hair": "black"},
        }, extra_data={},
    ) for index, note in enumerate(["规则识别人物", "规则识别人物动作", "规则识别人物描述"])]
    expected_evidence = {row.evidence for row in rows}
    db_session.add_all(rows)
    await db_session.commit()
    run.run_metadata = {**(run.run_metadata or {}), "selected_anchor_shot_ids": [
        run.episodes[2]["canonical_ids"]["shot_ids"][0], run.episodes[3]["canonical_ids"]["shot_ids"][0],
    ]}
    await db_session.commit()
    await _fresh_bindings(db_session, run)

    result = await prepare_story_locks(db_session, run)

    assert result["status"] == "locked"
    active = list((await db_session.scalars(select(StoryEntity).where(
        StoryEntity.novel_id == run.novel_id, StoryEntity.is_approved.is_(True),
    ))).all())
    assert len(active) == 1
    history = active[0].attributes["extraction_metadata_history"]
    assert len(history) == 3
    assert {item["source_entity_id"] for item in history} == {row.id for row in rows}
    assert {item["chapter_id"] for item in history} == {row.chapter_id for row in rows}
    assert {item["evidence"] for item in history} == expected_evidence
    assert all(re.fullmatch(r"[0-9a-f]{64}", item["metadata_hash"]) for item in history)
    aggregates = active[0].attributes["extraction_metadata_aggregates"]
    assert aggregates["confidence"]["count"] == 3
    assert aggregates["confidence"]["min"] == pytest.approx(0.7)
    assert aggregates["confidence"]["max"] == pytest.approx(0.9)
    assert aggregates["confidence"]["source_entity_ids"] == sorted(row.id for row in rows)
    assert all(re.fullmatch(r"[0-9a-f]{64}", value) for value in aggregates["confidence"]["value_hashes"])
    assert aggregates["mention_count"]["count"] == 3
    assert aggregates["evidence_contract"]["count"] == 3
    assert len(aggregates["evidence_contract"]["value_hashes"]) == 3
    assert all(item["metadata"]["evidence_contract"]["chapter_id"] == item["chapter_id"] for item in history)
    chapter_mentions = active[0].extra_data["entity_normalization"]["chapter_mentions"]
    assert {item["metadata_hash"] for item in chapter_mentions} == {item["metadata_hash"] for item in history}
    snapshot = json.dumps({"attributes": active[0].attributes, "extra_data": active[0].extra_data}, sort_keys=True)
    repeated = await prepare_story_locks(db_session, run)
    await db_session.refresh(active[0])
    assert repeated["status"] == "locked"
    assert json.dumps({"attributes": active[0].attributes, "extra_data": active[0].extra_data}, sort_keys=True) == snapshot

@pytest.mark.asyncio
async def test_single_deterministic_extraction_candidate_is_normalized_before_rule_approval(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    await db_session.execute(delete(StoryEntity).where(StoryEntity.novel_id == run.novel_id))
    await db_session.commit()
    await _explicit_dialogue_source(db_session, run)
    chapter = await db_session.get(Chapter, run.episodes[0]["chapter_ids"][0])
    from app.services.entity_extraction_service import extract_story_entities
    extracted = next(item for item in extract_story_entities(
        chapter.content, {"character"}, source_chapter_id=chapter.id, source_chapter_index=chapter.chapter_number,
    ) if item["name"] == "沈砚")
    entity = StoryEntity(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
        chapter_id=run.episodes[0]["chapter_ids"][0], entity_type="character",
        name="沈砚", canonical_name="沈砚", source="deterministic", version=1,
        confidence=extracted["confidence"], evidence=extracted["evidence"],
        attributes=extracted["attributes"],
        extra_data={},
    )
    from app.services.story_entity_lifecycle import set_entity_review_status
    set_entity_review_status(entity, "candidate", changed_by=run.user_id, reason="entity_extraction_v2:auto_candidate")
    db_session.add(entity)
    await db_session.commit()
    await _fresh_bindings(db_session, run)

    result = await prepare_story_locks(db_session, run)
    await db_session.refresh(entity)

    assert result["status"] == "locked"
    assert entity.source == "system"
    assert get_entity_review_status(entity) == "approved"
    assert entity.extra_data["explicit_dialogue_rule"]["rule"] == "rule_based_explicit_dialogue_v1"
    assert entity.attributes["voice_binding"]["status"] == "locked"

@pytest.mark.asyncio
@pytest.mark.parametrize("case", [
    "missing_evidence", "wrong_chapter", "wrong_content_hash", "wrong_span", "wrong_substring",
    "wrong_speaker", "wrong_quote", "wrong_evidence_hash", "ambiguous", "unknown_version",
])
async def test_single_untrusted_candidate_remains_blocked_without_partial_story_lock(
    db_session: AsyncSession, case: str,
) -> None:
    run = await _fixture(db_session)
    await db_session.execute(delete(StoryEntity).where(StoryEntity.novel_id == run.novel_id))
    await db_session.commit()
    await _explicit_dialogue_source(db_session, run)
    chapter = await db_session.get(Chapter, run.episodes[0]["chapter_ids"][0])
    from app.services.entity_extraction_service import extract_story_entities
    extracted = next(item for item in extract_story_entities(
        chapter.content, {"character"}, source_chapter_id=chapter.id, source_chapter_index=chapter.chapter_number,
    ) if item["name"] == "沈砚")
    attrs: dict[str, Any] = dict(extracted["attributes"])
    proof = dict(attrs["deterministic_dialogue_evidence"][0])
    extra: dict[str, Any] = {}
    source = "deterministic"
    chapter_id = run.episodes[0]["chapter_ids"][0]
    if case == "missing_evidence": attrs.pop("deterministic_dialogue_evidence")
    if case == "wrong_chapter": proof["chapter_id"] = run.episodes[1]["chapter_ids"][0]
    if case == "wrong_content_hash": proof["content_sha256"] = "0" * 64
    if case == "wrong_span": proof["span_end"] = len(chapter.content) + 1
    if case == "wrong_substring": proof["speaker_text"] = "tampered"
    if case == "wrong_speaker": proof["speaker"] = "他人"
    if case == "wrong_quote": proof["quote_text"] = "tampered"
    if case == "wrong_evidence_hash": proof["evidence_sha256"] = "0" * 64
    if case == "ambiguous": attrs["deterministic_dialogue_evidence"] = [proof, dict(proof)]
    if case == "unknown_version": proof["evidence_version"] = "legacy_unknown"
    if case not in {"missing_evidence", "ambiguous"}: attrs["deterministic_dialogue_evidence"] = [proof]
    entity = StoryEntity(id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
                         chapter_id=chapter_id, entity_type="character", name="沈砚", canonical_name="沈砚",
                         source=source, version=1, evidence="规则识别人物", attributes=attrs, extra_data=extra)
    from app.services.story_entity_lifecycle import set_entity_review_status
    set_entity_review_status(entity, "candidate", changed_by=run.user_id, reason="entity_extraction_v2:auto_candidate")
    novel_id, entity_id = run.novel_id, entity.id
    db_session.add(entity)
    await db_session.commit()
    await _fresh_bindings(db_session, run)

    with pytest.raises(StoryLockPreparationBlocked, match="existing character lifecycle requires review"):
        await prepare_story_locks(db_session, run)
    assert await db_session.scalar(select(func.count()).select_from(StoryBible).where(StoryBible.novel_id == novel_id)) == 0
    persisted = await db_session.get(StoryEntity, entity_id)
    assert persisted is not None and get_entity_review_status(persisted) == "candidate"

@pytest.mark.asyncio
async def test_story_lock_requires_persisted_selected_anchor_entity_closure(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    await db_session.execute(delete(StoryEntity).where(StoryEntity.novel_id == run.novel_id))
    await db_session.commit()
    await _explicit_dialogue_source(db_session, run)
    secret_values = ["港口调查者", "北岬走私者"]
    rows = [StoryEntity(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
        chapter_id=run.episodes[index]["chapter_ids"][0], entity_type="character",
        name="沈砚", canonical_name="沈砚", source="deterministic", version=1,
        attributes={"unknown_business_identity": value}, extra_data={},
    ) for index, value in enumerate(secret_values)]
    db_session.add_all(rows)
    await db_session.commit()
    await _fresh_bindings(db_session, run)
    for shot_id in (run.run_metadata or {})["selected_anchor_shot_ids"]:
        shot = await db_session.get(Shot, shot_id)
        shot.extra_data = {**(shot.extra_data or {}), "entity_refs": {
            "characters": [], "scenes": [], "props": [], "events": [],
        }}
    await db_session.commit()

    with pytest.raises(HTTPException) as raised:
        await post_series_run_prepare_story_locks(run.id, db_session, run.user_id)

    assert raised.value.status_code == 409
    detail = raised.value.detail
    serialized = json.dumps(detail, ensure_ascii=False)
    assert detail["code"] == "story_lock_preparation_blocked"
    assert detail["conflict_fields"]
    assert all(value not in serialized for value in [*secret_values, "沈砚"])

@pytest.mark.asyncio
@pytest.mark.parametrize("category,field,raw_values", [
    ("identity_relation", "relations", ["ally", "enemy"]),
    ("identity_state", "state_changes", ["alive", "dead"]),
    ("identity_tag", "tags", ["protagonist", "antagonist"]),
    ("entity_lifecycle", "source_review_status", ["manual", "rejected"]),
    ("identity_column", "description", ["正文甲", "正文乙"]),
    ("identity_column", "visual_prompt", ["红衣", "蓝衣"]),
    ("voice_binding", "voice_binding", ["voice-secret-a", "voice-secret-b"]),
])
async def test_story_lock_http_conflict_serializer_hashes_every_category_deny_by_default(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, category: str, field: str, raw_values: list[str],
) -> None:
    run = await _fixture(db_session)

    async def fail(*args, **kwargs):
        raise StoryLockPreparationBlocked("explicit_dialogue_character_conflict", conflict_fields=[{
            "category": category, "field": field, "values": raw_values,
        }])

    monkeypatch.setattr("app.api.v1.endpoints.series_runs.prepare_story_locks", fail)
    with pytest.raises(HTTPException) as raised:
        await post_series_run_prepare_story_locks(run.id, db_session, run.user_id)
    serialized = json.dumps(raised.value.detail, ensure_ascii=False)
    hashes = raised.value.detail["conflict_fields"][0]["value_hashes"]
    assert hashes and all(re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes)
    assert all(value not in serialized for value in [*raw_values, "沈砚", "ally", "enemy", "alive", "dead"])

@pytest.mark.asyncio
async def test_story_lock_http_conflict_serializer_fails_closed_on_unserializable_values(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await _fixture(db_session)

    async def fail(*args, **kwargs):
        raise StoryLockPreparationBlocked("must-not-leak", conflict_fields=[{
            "category": "identity_attribute", "field": "secret", "values": [object()],
        }])

    monkeypatch.setattr("app.api.v1.endpoints.series_runs.prepare_story_locks", fail)
    with pytest.raises(HTTPException) as raised:
        await post_series_run_prepare_story_locks(run.id, db_session, run.user_id)
    assert raised.value.detail == {"code": "story_lock_preparation_blocked"}

@pytest.mark.asyncio
@pytest.mark.parametrize("field,values", [
    ("description", ["港口调查者", "北岬走私者"]),
    ("relations", [[{"entity_id": "港务长", "type": "ally"}], [{"entity_id": "港务长", "type": "enemy"}]]),
    ("state_changes", [[{"state": "安全"}], [{"state": "受伤"}]]),
])
async def test_explicit_dialogue_identity_projection_conflicts_rollback_without_partial_merge(
    db_session: AsyncSession, field: str, values: list,
) -> None:
    run = await _fixture(db_session)
    novel_id = run.novel_id
    await db_session.execute(delete(StoryEntity).where(StoryEntity.novel_id == novel_id))
    await db_session.commit()
    await _explicit_dialogue_source(db_session, run)
    chapter_id = run.episodes[0]["chapter_ids"][0]
    rows = []
    for value in values:
        kwargs = {field: value}
        rows.append(StoryEntity(
            id=str(uuid4()), user_id=run.user_id, novel_id=novel_id, chapter_id=chapter_id,
            entity_type="character", name="沈砚", canonical_name="沈砚", source="deterministic",
            version=1, attributes={}, extra_data={}, **kwargs,
        ))
    row_ids = [row.id for row in rows]
    db_session.add_all(rows)
    await db_session.commit()
    await _fresh_bindings(db_session, run)
    with pytest.raises(StoryLockPreparationBlocked, match="explicit_dialogue_character_conflict"):
        await prepare_story_locks(db_session, run)
    persisted = list((await db_session.scalars(select(StoryEntity).where(StoryEntity.id.in_(row_ids)))).all())
    assert all(get_entity_review_status(row) != "archived" for row in persisted)
    assert await db_session.scalar(select(func.count()).select_from(StoryBible).where(StoryBible.novel_id == novel_id)) == 0

@pytest.mark.asyncio
@pytest.mark.parametrize("tags", [
    (["protagonist"], ["antagonist"]),
    (["人类"], ["spirit"]),
    (["alive"], ["死亡"]),
    (["港城侦探"], ["北岬旅人"]),
])
async def test_explicit_dialogue_tag_taxonomy_conflicts_require_review_without_partial_merge(
    db_session: AsyncSession, tags: tuple[list[str], list[str]],
) -> None:
    run = await _fixture(db_session)
    novel_id = run.novel_id
    await db_session.execute(delete(StoryEntity).where(StoryEntity.novel_id == novel_id))
    await db_session.commit()
    await _explicit_dialogue_source(db_session, run)
    chapter_id = run.episodes[0]["chapter_ids"][0]
    rows = [StoryEntity(
        id=str(uuid4()), user_id=run.user_id, novel_id=novel_id, chapter_id=chapter_id,
        entity_type="character", name="沈砚", canonical_name="沈砚", source="deterministic",
        version=1, attributes={}, tags=value, extra_data={},
    ) for value in tags]
    row_ids = [row.id for row in rows]
    db_session.add_all(rows)
    await db_session.commit()
    await _fresh_bindings(db_session, run)
    with pytest.raises(StoryLockPreparationBlocked, match="explicit_dialogue_character_conflict"):
        await prepare_story_locks(db_session, run)
    persisted = list((await db_session.scalars(select(StoryEntity).where(StoryEntity.id.in_(row_ids)))).all())
    assert all(get_entity_review_status(row) != "archived" for row in persisted)

@pytest.mark.asyncio
async def test_explicit_dialogue_role_alias_ambiguity_fails_closed_without_partial_merge(
    db_session: AsyncSession,
) -> None:
    run = await _fixture(db_session)
    novel_id = run.novel_id
    await db_session.execute(delete(StoryEntity).where(StoryEntity.novel_id == novel_id))
    episodes = [dict(item) for item in run.episodes]
    for index in (0, 3):
        chapter = await db_session.get(Chapter, episodes[index]["chapter_ids"][0])
        chapter.content = f"主角说：“第{index + 1}章明确对白。”"
        chapter.updated_at = utc_now()
        episodes[index]["input_hash"] = f"{chapter.id}:{chapter.updated_at.isoformat()}"
        shot = await db_session.get(Shot, episodes[index]["canonical_ids"]["shot_ids"][0])
        shot.dialogue = f"主角：第{index + 1}章明确对白。"
        shot.extra_data = {**(shot.extra_data or {}), "dialogue_speaker": "主角", "parsed_speaker": "主角"}
    run.episodes = episodes
    rows = [StoryEntity(
        id=str(uuid4()), user_id=run.user_id, novel_id=novel_id,
        chapter_id=episodes[index]["chapter_ids"][0], entity_type="character",
        name=f"角色-{index}", canonical_name=f"canonical-{index}", aliases=["主角"],
        source="deterministic", version=1, attributes={}, extra_data={},
    ) for index in (0, 1)]
    row_ids = [row.id for row in rows]
    db_session.add_all(rows)
    await db_session.commit()
    await _fresh_bindings(db_session, run)

    with pytest.raises(StoryLockPreparationBlocked, match="explicit_dialogue_character_conflict"):
        await prepare_story_locks(db_session, run)

    persisted = list((await db_session.scalars(select(StoryEntity).where(StoryEntity.id.in_(row_ids)))).all())
    assert all(get_entity_review_status(row) != "archived" for row in persisted)
    assert await db_session.scalar(
        select(func.count()).select_from(StoryBible).where(StoryBible.novel_id == novel_id)
    ) == 0

@pytest.mark.asyncio
async def test_explicit_dialogue_failure_rolls_back_rule_entity_and_story_bible(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    run = await _fixture(db_session)
    novel_id = run.novel_id
    await _fresh_bindings(db_session, run)

    async def fail(*args, **kwargs):
        raise RuntimeError("atomic failure")
    monkeypatch.setattr("app.features.series_run_story_locks.application.story_transaction.persist_production_closure_v2", fail)
    with pytest.raises(RuntimeError, match="atomic failure"):
        await prepare_story_locks(db_session, run)
    assert await db_session.scalar(select(func.count()).select_from(StoryEntity).where(StoryEntity.novel_id == novel_id)) == 3
    assert await db_session.scalar(select(func.count()).select_from(StoryBible).where(StoryBible.novel_id == novel_id)) == 0

@pytest.mark.asyncio
async def test_manual_approved_entity_is_read_only_and_must_match_fresh_tts_binding(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    await _explicit_dialogue_source(db_session, run)
    ids = await _fresh_bindings(db_session, run)
    entity = await db_session.scalar(select(StoryEntity).where(
        StoryEntity.novel_id == run.novel_id, StoryEntity.entity_type == "character"))
    original_approval = dict(entity.attributes["approval_record"])
    selection = run.run_metadata["voice_selection"]
    entity.attributes = {**entity.attributes, "manual_marker": "preserve", "voice_binding": {
        "voice_id": DEFAULT_MINIMAX_TTS_VOICE, "version": 7, "status": "locked",
        "provider_id": "minimax", "config_id": ids["tts"],
        "db_model_id": selection["db_model_id"], "api_model_id": selection["api_model_id"],
        "tested_at": selection["tested_at"],
    }}
    await db_session.commit()

    await prepare_story_locks(db_session, run)
    await db_session.refresh(entity)
    assert entity.attributes["approval_record"] == original_approval
    assert entity.attributes["manual_marker"] == "preserve"
    assert entity.attributes["voice_binding"]["version"] == 7

@pytest.mark.asyncio
async def test_voice_selection_is_required_and_exposes_only_safe_bound_options_without_writes(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    novel_id = run.novel_id
    await db_session.execute(delete(StoryEntity).where(StoryEntity.novel_id == run.novel_id))
    await db_session.commit()
    await _explicit_dialogue_source(db_session, run)
    await _fresh_bindings(db_session, run)
    run.run_metadata = {key: value for key, value in (run.run_metadata or {}).items() if key != "voice_selection"}
    await db_session.commit()

    plan = await build_live_preflight_plan(db_session, run)
    assert "voice_selection_required" in plan["blocker_codes"]
    assert plan["voice_options"]["config_id"] == ((run.model_bindings["capabilities"])["tts"])["config_id"]
    voice_ids = {item["voice_id"] for item in plan["voice_options"]["options"]}
    assert voice_ids == {"male-qn-qingse"}
    assert "female-shaonv" not in voice_ids
    with pytest.raises(StoryLockPreparationBlocked, match="voice selection"):
        await prepare_story_locks(db_session, run)
    assert await db_session.scalar(select(func.count()).select_from(StoryEntity).where(StoryEntity.novel_id == novel_id)) == 0
    assert await db_session.scalar(select(func.count()).select_from(StoryBible).where(StoryBible.novel_id == novel_id)) == 0

@pytest.mark.asyncio
async def test_voice_selection_rejects_wrong_model_and_non_allowlisted_voice(db_session: AsyncSession) -> None:
    from app.services.live_canary_budget import BindingValidationError
    run = await _fixture(db_session)
    ids = await _fresh_bindings(db_session, run)
    with pytest.raises(BindingValidationError, match="snapshot"):
        await persist_voice_selection(db_session, run, config_id=ids["tts"], model_id="foreign", voice_id="female-shaonv", version=1)
    with pytest.raises(BindingValidationError, match="not allowed"):
        await persist_voice_selection(db_session, run, config_id=ids["tts"], model_id="unit-tts-model", voice_id="not-a-provider-voice", version=1)

@pytest.mark.asyncio
async def test_stale_tts_snapshot_is_reported_without_mutating_locked_lineage(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    await _explicit_dialogue_source(db_session, run)
    ids = await _fresh_bindings(db_session, run)
    old_asset = Asset(id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id, category="reference",
                      name="old reference", asset_type="image", version=3, is_active=True,
                      is_final=True, is_locked=True, generation_params={"status": "locked"})
    old_binding = ProviderAssetBinding(id=str(uuid4()), asset_id=old_asset.id, asset_version=3,
                                       provider_id="unit-provider", model_id="unit-video-api-model",
                                       binding_kind="reference_image", upload_status="ready", is_active=True,
                                       verified_at=utc_now())
    db_session.add_all([old_asset, old_binding])
    metadata = dict(run.run_metadata or {})
    metadata.update(story_locks={"story_bible_id": "old-bible"}, reference_preparation={"asset_id": old_asset.id, "asset_version": 3},
                    anchor_quality_reports={"old-artifact": {"ready": True}})
    run.run_metadata = metadata
    episodes = [dict(item) for item in run.episodes]
    for episode in episodes:
        workflow = await db_session.get(Workflow, episode["canonical_ids"]["workflow_id"])
        workflow.metadata_ = {**(workflow.metadata_ or {}), "episode_contract": {"snapshot_hash": "old-contract", "status": "locked"}}
        shot = await db_session.get(Shot, episode["canonical_ids"]["shot_ids"][0])
        shot.extra_data = {**(shot.extra_data or {}), "story_bible_id": "old-bible", "voice_binding": {"voice_id": "female-shaonv"},
                           "production_context": {"episode_contract_version": "old-contract"}}
    stale = await db_session.get(LLMConfig, ids["tts"])
    stale.tested_at = utc_now() - timedelta(hours=2)
    await db_session.commit()

    plan = await build_live_preflight_plan(db_session, run)
    await db_session.refresh(run)
    assert "model_bindings_not_fresh" in plan["blocker_codes"]
    assert "voice_selection_stale" in plan["blocker_codes"]
    assert run.run_metadata["story_locks"] == {"story_bible_id": "old-bible"}
    assert run.run_metadata["reference_preparation"]["asset_id"] == old_asset.id
    assert run.run_metadata["anchor_quality_reports"] == {"old-artifact": {"ready": True}}
    await db_session.refresh(old_asset)
    await db_session.refresh(old_binding)
    assert old_asset.is_final is True and old_asset.is_locked is True
    assert old_asset.generation_params["status"] == "locked"
    assert old_binding.is_active is True and old_binding.verified_at is not None
    assert old_binding.invalidation_reason is None
    for episode in run.episodes:
        workflow = await db_session.get(Workflow, episode["canonical_ids"]["workflow_id"])
        assert workflow.metadata_["episode_contract"]["status"] == "locked"
        shot = await db_session.get(Shot, episode["canonical_ids"]["shot_ids"][0])
        assert shot.extra_data["story_bible_id"] == "old-bible"
        assert shot.extra_data["voice_binding"]["voice_id"] == "female-shaonv"

@pytest.mark.asyncio
async def test_retested_and_reselected_voice_builds_new_reference_without_reactivating_superseded_asset(
    db_session: AsyncSession, reference_http_server: str,
) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    first_story = await prepare_story_locks(db_session, run)
    old_bible = await db_session.get(StoryBible, first_story["story_bible_id"])
    first = await prepare_series_reference(db_session, run, adapter=_ReferenceAdapter({
        "status": "completed", "public_url": f"{reference_http_server}/valid.png",
        "provider_task_id": "old-reference", "actual_cost_rmb": "0.10", "visual_evidence": _visual_evidence(),
    }), binding_ids=bindings)
    old_asset = await db_session.get(Asset, first["asset_id"])
    old_binding = await db_session.get(ProviderAssetBinding, first["provider_binding_id"])
    tts = await db_session.get(LLMConfig, bindings["tts"])
    tts.tested_at = utc_now() - timedelta(hours=2)
    await db_session.commit()
    assert "voice_selection_stale" in (await build_live_preflight_plan(db_session, run))["blocker_codes"]

    refreshed_at = utc_now()
    for config_id in bindings.values():
        config = await db_session.get(LLMConfig, config_id)
        config.test_status = "success"
        config.tested_at = refreshed_at
    await db_session.commit()
    await persist_voice_selection(db_session, run, config_id=bindings["tts"], model_id=tts.model_id,
                                  voice_id=DEFAULT_MINIMAX_TTS_VOICE, version=2)
    second_story = await prepare_story_locks(db_session, run)
    second = await prepare_series_reference(db_session, run, adapter=_ReferenceAdapter({
        "status": "completed", "public_url": f"{reference_http_server}/valid.png",
        "provider_task_id": "new-reference", "actual_cost_rmb": "0.10", "visual_evidence": _visual_evidence(),
    }), binding_ids=bindings)
    await db_session.refresh(old_asset)
    await db_session.refresh(old_binding)
    await db_session.refresh(old_bible)
    assert second_story["version"] == first_story["version"] + 1 == 2
    assert old_bible.extra_data["production_status"] == "superseded_review_required"
    assert second["asset_id"] != first["asset_id"]
    assert old_asset.is_active is False and old_binding.is_active is False

@pytest.mark.asyncio
async def test_prepare_story_locks_is_idempotent_versioned_and_approved_only(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)

    first = await prepare_story_locks(db_session, run)
    second = await prepare_story_locks(db_session, run)

    assert first["story_bible_id"] == second["story_bible_id"]
    assert first["version"] == second["version"] == 1
    bibles = list((await db_session.scalars(select(StoryBible).where(StoryBible.novel_id == run.novel_id))).all())
    assert len(bibles) == 1
    bible = bibles[0]
    assert bible.extra_data["production_status"] == "locked"
    lock = bible.extra_data["series_story_lock"]
    assert lock["closure_contract_version"] == "required_entity_closure_v2"
    assert lock["subjects"] == first["subjects"] and lock["evidence_edges"] == first["evidence_edges"]
    assert lock["snapshot_hash"] == first["snapshot_hash"]


@pytest.mark.asyncio
async def test_current_entity_extraction_contract_story_lock_is_fresh(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    await prepare_story_locks(db_session, run)

    freshness = await inspect_story_lock_freshness(db_session, run)

    assert freshness["ready"] is True


@pytest.mark.asyncio
async def test_legacy_entity_extraction_contract_story_lock_is_stale(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    result = await prepare_story_locks(db_session, run)
    bible = await db_session.get(StoryBible, result["story_bible_id"])
    run_lock = dict((run.run_metadata or {})["story_locks"])
    run_lock.pop("entity_extraction_contract_version", None)
    run.run_metadata = {**(run.run_metadata or {}), "story_locks": run_lock}
    bible_lock = dict((bible.extra_data or {})["series_story_lock"])
    bible_lock.pop("entity_extraction_contract_version", None)
    bible.extra_data = {**(bible.extra_data or {}), "series_story_lock": bible_lock}
    await db_session.commit()

    freshness = await inspect_story_lock_freshness(db_session, run)

    assert freshness["ready"] is False
    assert freshness["code"] == "story_lock_stale"
    assert freshness["story_blocker_code"] == "entity_extraction_contract_stale"


@pytest.mark.asyncio
async def test_media_running_retry_refreshes_scoped_refs_after_dialogue_changes(
    db_session: AsyncSession,
) -> None:
    run = await _fixture(db_session)
    first = await prepare_story_locks(db_session, run)
    shot_id = (run.run_metadata or {})["selected_anchor_shot_ids"][0]
    shot = await db_session.get(Shot, shot_id)
    old_reference_hash = shot.extra_data["entity_refs"]["characters"][0]["shot_input_sha256"]
    shot.dialogue = f"{shot.dialogue} 新的重试对白"
    run.status = "media_running"
    await db_session.commit()

    second = await prepare_story_locks(db_session, run)
    await db_session.refresh(shot)

    assert second["version"] == first["version"] + 1
    assert shot.extra_data["entity_refs"]["characters"][0]["shot_input_sha256"] != old_reference_hash


@pytest.mark.asyncio
async def test_shots_ready_story_lock_refreshes_scoped_refs_after_entity_review(
    db_session: AsyncSession,
) -> None:
    run = await _fixture(db_session)
    first = await prepare_story_locks(db_session, run)
    shot_id = (run.run_metadata or {})["selected_anchor_shot_ids"][0]
    shot = await db_session.get(Shot, shot_id)
    old_reference_hash = shot.extra_data["entity_refs"]["characters"][0]["shot_input_sha256"]
    shot.dialogue = f"{shot.dialogue} 审核后刷新镜头实体引用"
    metadata = dict(run.run_metadata or {})
    previous_lock = dict(metadata.pop("story_locks"))
    metadata["superseded_story_locks"] = [previous_lock]
    run.run_metadata = metadata
    await db_session.commit()

    second = await prepare_story_locks(db_session, run)
    await db_session.refresh(shot)

    assert second["version"] == first["version"] + 1
    assert shot.extra_data["entity_refs"]["characters"][0]["shot_input_sha256"] != old_reference_hash


@pytest.mark.asyncio
async def test_story_lock_refresh_blocks_when_rejected_entity_is_only_shot_reference(
    db_session: AsyncSession,
) -> None:
    run = await _fixture(db_session)
    first = await prepare_story_locks(db_session, run)
    shot_id = (run.run_metadata or {})["selected_anchor_shot_ids"][1]
    shot = await db_session.get(Shot, shot_id)
    rejected_id = shot.extra_data["entity_refs"]["events"][0]["canonical_entity_id"]
    rejected = await db_session.get(StoryEntity, rejected_id)
    set_entity_review_status(rejected, "rejected", changed_by=run.user_id, reason="manual_review")
    await db_session.commit()

    with pytest.raises(StoryLockPreparationBlocked):
        await prepare_story_locks(db_session, run)
    await db_session.refresh(run)

    assert run.run_metadata["story_locks"]["version"] == first["version"]

@pytest.mark.asyncio
async def test_prepare_story_locks_has_no_future_leakage_in_chapter_snapshots(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)

    result = await prepare_story_locks(db_session, run)
    bible = await db_session.get(StoryBible, result["story_bible_id"])
    lock = bible.extra_data["series_story_lock"]
    future_prop = await db_session.scalar(select(StoryEntity).where(
        StoryEntity.novel_id == run.novel_id, StoryEntity.name == "破损灯笼"))
    assert future_prop.id not in {item["canonical_entity_id"] for item in lock["subjects"]}
    assert all(item["as_of_chapter_id"] != run.episodes[2]["chapter_ids"][0]
               for item in lock["evidence_edges"])

@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["selection", "references", "voice", "model"])
async def test_story_source_snapshot_drift_supersedes_v1_and_rebuilds_v2(
    db_session: AsyncSession, mutation: str,
) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_bindings(db_session, run)
    first = await prepare_story_locks(db_session, run)
    old_bible = await db_session.get(StoryBible, first["story_bible_id"])
    assert first["version"] == 1

    if mutation == "selection":
        selected = []
        for index in (0, 2):
            shot_id = run.episodes[index]["canonical_ids"]["shot_ids"][0]
            shot = await db_session.get(Shot, shot_id)
            entity = await db_session.scalar(select(StoryEntity).where(
                StoryEntity.novel_id == run.novel_id, StoryEntity.chapter_id == run.episodes[index]["chapter_ids"][0]))
            refs = {"characters": [], "scenes": [], "props": [], "events": []}
            refs[{"character":"characters", "prop":"props"}[entity.entity_type]] = [{"entity_id": entity.id}]
            shot.extra_data = {**(shot.extra_data or {}), "chapter_id": run.episodes[index]["chapter_ids"][0],
                               "entity_refs": refs}
            selected.append(shot_id)
        run.run_metadata = {**(run.run_metadata or {}), "selected_anchor_shot_ids": selected,
                            "selected_anchor_mode": "smoke", "anchor_selection_revision": 2}
        await _refresh_fixture_production_contracts(db_session, run)
    elif mutation == "references":
        selected = list((run.run_metadata or {})["selected_anchor_shot_ids"])
        shot = await db_session.get(Shot, selected[-1])
        shot.extra_data = {**shot.extra_data, "entity_refs": {**shot.extra_data["entity_refs"], "props": []}}
        run.run_metadata = {**(run.run_metadata or {}), "anchor_selection_revision": 2}
    elif mutation == "voice":
        await persist_voice_selection(
            db_session, run, config_id=bindings["tts"], model_id="unit-tts-model",
            voice_id=DEFAULT_MINIMAX_TTS_VOICE, version=2)
    else:
        capabilities = {key: dict(value) for key, value in (run.model_bindings or {})["capabilities"].items()}
        capabilities["image"]["tested_at"] = "2099-01-01T00:00:00"
        run.model_bindings = {**(run.model_bindings or {}), "capabilities": capabilities}
    await db_session.commit()

    second = await prepare_story_locks(db_session, run)
    await db_session.refresh(old_bible)
    await db_session.refresh(run)
    changed = mutation in {"selection", "voice"}
    assert second["version"] == (2 if changed else 1)
    assert (second["story_bible_id"] != first["story_bible_id"]) is changed
    assert old_bible.extra_data["production_status"] == ("superseded_review_required" if mutation == "voice" else "locked")
    if changed: assert run.run_metadata["superseded_story_locks"][-1]["story_bible_id"] == first["story_bible_id"]
    assert run.run_metadata["story_locks"]["closure_hash"] == second["closure_hash"]

@pytest.mark.asyncio
async def test_stale_v2_contract_failure_rolls_back_complete_v1_lineage(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, reference_http_server: str,
) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    first = await prepare_story_locks(db_session, run)
    reference = await prepare_series_reference(db_session, run, adapter=_ReferenceAdapter({
        "status": "completed", "public_url": f"{reference_http_server}/valid.png",
        "provider_task_id": "atomic-v1", "actual_cost_rmb": "0.10", "visual_evidence": _visual_evidence(),
    }), binding_ids=bindings)
    run.run_metadata = {**(run.run_metadata or {}), "anchor_quality_reports": {"v1": {"ready": True}}}
    await db_session.commit()
    v1_metadata = json.loads(json.dumps(run.run_metadata))
    v1_episodes = json.loads(json.dumps(run.episodes))
    old_bible = await db_session.get(StoryBible, first["story_bible_id"])
    old_asset = await db_session.get(Asset, reference["asset_id"])
    old_binding = await db_session.get(ProviderAssetBinding, reference["provider_binding_id"])
    workflows = [await db_session.get(Workflow, item["canonical_ids"]["workflow_id"]) for item in run.episodes]
    contract_snapshots = {item.id: json.loads(json.dumps(item.metadata_ or {})) for item in workflows}
    selected_shots = [await db_session.get(Shot, shot_id) for shot_id in run.run_metadata["selected_anchor_shot_ids"]]
    shot_snapshots = {item.id: json.loads(json.dumps(item.extra_data or {})) for item in selected_shots}
    run.run_metadata = {**run.run_metadata, "anchor_selection_revision": 2}
    await db_session.commit()
    v1_metadata["anchor_selection_revision"] = 2

    async def fail_contract(*args, **kwargs):
        raise RuntimeError("injected stale v2 contract failure")

    monkeypatch.setattr(
        "app.features.series_run_story_locks.application.story_transaction.persist_production_closure_v2",
        fail_contract,
    )
    with pytest.raises(RuntimeError, match="stale v2 contract"):
        await prepare_story_locks(db_session, run)

    await db_session.refresh(run)
    await db_session.refresh(old_bible)
    await db_session.refresh(old_asset)
    await db_session.refresh(old_binding)
    assert run.run_metadata == v1_metadata and run.episodes == v1_episodes
    assert old_bible.extra_data["production_status"] == "locked"
    assert len(list((await db_session.scalars(select(StoryBible).where(
        StoryBible.novel_id == run.novel_id,
    ))).all())) == 1
    assert old_asset.is_locked is True and old_asset.is_final is True
    assert old_binding.is_active is True and old_binding.verified_at is not None
    for workflow in workflows:
        await db_session.refresh(workflow)
        assert workflow.metadata_ == contract_snapshots[workflow.id]
    for shot in selected_shots:
        await db_session.refresh(shot)
        assert shot.extra_data == shot_snapshots[shot.id]

@pytest.mark.asyncio
async def test_first_story_lock_rejects_malformed_reference_without_writes(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    novel_id = run.novel_id
    await _fresh_bindings(db_session, run)
    shot_id = (run.run_metadata or {})["selected_anchor_shot_ids"][0]
    shot = await db_session.get(Shot, shot_id)
    shot.extra_data = {**shot.extra_data, "entity_refs": {**shot.extra_data["entity_refs"],
        "characters": ["bad"]}}
    await db_session.commit()

    with pytest.raises(StoryLockPreparationBlocked, match="story_lock_source_invalid"):
        await prepare_story_locks(db_session, run)
    assert await db_session.scalar(select(func.count()).select_from(StoryBible).where(
        StoryBible.novel_id == novel_id)) == 0

@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["no_refs", "malformed_ref", "wrong_type", "missing_shot", "chapter_shape"])
async def test_plain_value_error_source_drift_invalidates_complete_lineage(
    db_session: AsyncSession, mutation: str,
) -> None:
    run = await _fixture(db_session)
    await _fresh_bindings(db_session, run)
    first = await prepare_story_locks(db_session, run)
    run.run_metadata = {**run.run_metadata, "anchor_quality_reports": {"v1": {"ready": True}}}
    await db_session.commit()
    contract_workflow_ids = []
    for episode in run.episodes:
        workflow = await db_session.get(Workflow, episode["canonical_ids"]["workflow_id"])
        if (workflow.metadata_ or {}).get("episode_contract"):
            contract_workflow_ids.append(workflow.id)
    selected = list((run.run_metadata or {})["selected_anchor_shot_ids"])
    shot = await db_session.get(Shot, selected[0])
    if mutation == "no_refs":
        for shot_id in selected:
            row = await db_session.get(Shot, shot_id)
            row.extra_data = {**row.extra_data, "entity_refs": {}}
    elif mutation == "malformed_ref":
        shot.extra_data = {**shot.extra_data, "entity_refs": {**shot.extra_data["entity_refs"], "characters": ["bad"]}}
    elif mutation == "wrong_type":
        prop = await db_session.scalar(select(StoryEntity).where(
            StoryEntity.novel_id == run.novel_id, StoryEntity.entity_type == "prop"))
        shot.extra_data = {**shot.extra_data, "entity_refs": {**shot.extra_data["entity_refs"], "characters": [{"entity_id": prop.id}]}}
    elif mutation == "missing_shot":
        run.run_metadata = {**run.run_metadata, "selected_anchor_shot_ids": [selected[0], str(uuid4())]}
    else:
        episodes = [dict(item) for item in run.episodes]
        episodes[1] = {**episodes[1], "chapter_ids": list(episodes[0]["chapter_ids"])}
        run.episodes = episodes
    await db_session.commit()

    freshness = await inspect_story_lock_freshness(db_session, run, supersede=True)

    await db_session.refresh(run)
    bible = await db_session.get(StoryBible, first["story_bible_id"])
    assert freshness["ready"] is False and freshness["code"] == "story_lock_stale"
    assert "story_locks" not in run.run_metadata
    assert "anchor_quality_reports" not in run.run_metadata
    assert bible.extra_data["production_status"] == "superseded_review_required"
    for workflow_id in contract_workflow_ids:
        workflow = await db_session.get(Workflow, workflow_id)
        assert workflow.metadata_["episode_contract"]["status"] == "superseded"

@pytest.mark.asyncio
async def test_unexpected_freshness_error_propagates_without_lineage_invalidation(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await _fixture(db_session)
    await _fresh_bindings(db_session, run)
    first = await prepare_story_locks(db_session, run)

    async def fail_query(*args, **kwargs):
        raise RuntimeError("injected repository failure")

    monkeypatch.setattr(
        "app.features.series_run_story_locks.application.inspect_freshness.StoryLockRepository.selected_shots",
        fail_query,
    )
    with pytest.raises(RuntimeError, match="repository failure"):
        await inspect_story_lock_freshness(db_session, run, supersede=True)

    await db_session.refresh(run)
    bible = await db_session.get(StoryBible, first["story_bible_id"])
    assert run.run_metadata["story_locks"]["story_bible_id"] == first["story_bible_id"]
    assert bible.extra_data["production_status"] == "locked"

@pytest.mark.asyncio
async def test_story_lock_enriches_selected_episode_contracts_atomically(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    await _fresh_bindings(db_session, run)
    result = await prepare_story_locks(db_session, run)
    selected = set((run.run_metadata or {})["selected_anchor_shot_ids"])
    for episode in run.episodes:
        assert episode["story_bible_id"] == result["story_bible_id"]
        assert episode["closure_contract_version"] == "required_entity_closure_v2"
        for shot_id in episode["canonical_ids"]["shot_ids"]:
            shot = await db_session.get(Shot, shot_id)
            lineage = (shot.extra_data or {}).get("story_lock_lineage") or {}
            assert bool(lineage) is (shot_id in selected)
            if lineage:
                assert lineage["story_bible_id"] == result["story_bible_id"]
                assert lineage["closure_hash"] == result["closure_hash"]

@pytest.mark.asyncio
async def test_story_lock_rolls_back_when_episode_contract_enrichment_fails(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await _fixture(db_session)
    await _fresh_bindings(db_session, run)
    novel_id, run_id = run.novel_id, run.id

    async def fail_contract(*args, **kwargs):
        raise RuntimeError("injected episode contract failure")

    monkeypatch.setattr(
        "app.features.series_run_story_locks.application.story_transaction.persist_production_closure_v2",
        fail_contract,
    )
    with pytest.raises(RuntimeError, match="episode contract"):
        await prepare_story_locks(db_session, run)

    assert not list((await db_session.scalars(
        select(StoryBible).where(StoryBible.novel_id == novel_id)
    )).all())
    persisted_run = await db_session.get(SeriesProductionRun, run_id)
    assert "story_locks" not in (persisted_run.run_metadata or {})
    for episode in persisted_run.episodes:
        assert "story_bible_id" not in episode
        for shot_id in episode["canonical_ids"]["shot_ids"]:
            shot = await db_session.get(Shot, shot_id)
            assert "story_lock_lineage" not in (shot.extra_data or {})

@pytest.mark.asyncio
async def test_prepare_story_locks_rejects_stale_or_non_four_chapter_run_atomically(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    run.status = "superseded_review_required"
    await db_session.commit()

    with pytest.raises(StoryLockPreparationBlocked, match="stale"):
        await prepare_story_locks(db_session, run)

    count = len(list((await db_session.scalars(select(StoryBible).where(StoryBible.novel_id == run.novel_id))).all()))
    assert count == 0

@pytest.mark.asyncio
async def test_live_preflight_plan_uses_trusted_cost_and_dialogue_contracts(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)

    plan = await build_live_preflight_plan(db_session, run)

    assert plan["budget"]["maximum_rmb"] == "10.00"
    assert plan["budget"]["projected_total_rmb"] == "10.00"
    assert [item["capability"] for item in plan["cost_breakdown"]] == ["image", "video", "tts"]
    assert plan["cost_breakdown"][0]["quantity"] == 3
    assert plan["cost_breakdown"][1]["quantity"] == 2
    assert plan["cost_breakdown"][2]["quantity"] == 2
    assert len(plan["anchor_dialogue_contracts"]) == 2
    assert all(item["speaker"] == "沈砚" and item["requires_tts"] for item in plan["anchor_dialogue_contracts"])
    assert "story_bible_missing" in plan["blocker_codes"]


@pytest.mark.asyncio
async def test_native_audio_preflight_reuses_locked_reference_and_skips_tts_cost(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_bindings(db_session, run)
    run.run_metadata = {
        **(run.run_metadata or {}),
        "reference_preparation": {"asset_id": "locked-reference", "asset_version": 1},
    }
    for capability in ("text", "image", "tts"):
        config = await db_session.get(LLMConfig, bindings[capability])
        config.tested_at = utc_now() - timedelta(hours=2)
    await db_session.commit()

    plan = await build_live_preflight_plan(db_session, run, native_audio=True)

    assert [item["capability"] for item in plan["cost_breakdown"]] == ["image", "video"]
    assert plan["cost_breakdown"][0]["quantity"] == 2
    assert plan["budget"]["projected_increment_rmb"] == "8.00"
    assert all(item["requires_tts"] is False for item in plan["anchor_dialogue_contracts"])
    assert all(item["audio_route"] == "video_native_audio" for item in plan["anchor_dialogue_contracts"])
    assert "voice_binding_missing" not in plan["blocker_codes"]
    assert "shot_first_frame_missing" in plan["blocker_codes"]
    assert "model_bindings_not_fresh" in plan["blocker_codes"]


@pytest.mark.asyncio
async def test_representative_preflight_accepts_three_cross_episode_native_audio_anchors(
    db_session: AsyncSession,
) -> None:
    run = await _fixture(db_session)
    shots, _ = await _run_shots(db_session, run)
    selected = [item["shot_id"] for item in recommend_anchor_shots(shots, mode="representative")]
    request = AnchorSelectionRequest(shot_ids=selected, mode="representative")
    run.run_metadata = {
        **(run.run_metadata or {}),
        "selected_anchor_shot_ids": request.shot_ids,
        "selected_anchor_mode": request.mode,
    }
    await db_session.commit()

    plan = await build_live_preflight_plan(db_session, run, native_audio=True)

    assert len(plan["anchor_dialogue_contracts"]) == 3
    assert {item["episode_number"] for item in plan["anchor_dialogue_contracts"]} == {1, 3, 4}
    assert plan["cost_breakdown"][1]["quantity"] == 3
    assert "anchor_coverage_insufficient" not in plan["blocker_codes"]


@pytest.mark.asyncio
async def test_live_preflight_plan_blocks_over_budget_and_unknown_dialogue(db_session: AsyncSession) -> None:
    run = await _fixture(db_session, dialogue="有人低声说道。")
    run.budget_policy = {**run.budget_policy, "estimates_rmb": {"image": "2.00", "video": "4.00", "tts": "1.00"}}
    await db_session.commit()

    plan = await build_live_preflight_plan(db_session, run)

    assert plan["ready"] is False
    assert "projected_budget_exceeded" in plan["blocker_codes"]
    assert "dialogue_speaker_unknown" in plan["blocker_codes"]
    assert all(item["speaker"] is None for item in plan["anchor_dialogue_contracts"])

@pytest.mark.asyncio
async def test_live_preflight_plan_requires_trusted_tts_estimate_for_dialogue(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    estimates = dict(run.budget_policy["estimates_rmb"])
    estimates.pop("tts")
    run.budget_policy = {**run.budget_policy, "estimates_rmb": estimates}
    await db_session.commit()

    plan = await build_live_preflight_plan(db_session, run)

    assert "tts_estimate_missing" in plan["blocker_codes"]
    assert plan["ready"] is False

@pytest.mark.asyncio
async def test_live_preflight_plan_never_uses_a_ceiling_above_wave_one_rmb_ten(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    run.budget_policy = {
        **run.budget_policy,
        "max_rmb": "30.00",
        "estimates_rmb": {"image": "2.00", "video": "4.00", "tts": "1.00"},
    }
    await db_session.commit()

    plan = await build_live_preflight_plan(db_session, run)

    assert plan["budget"]["maximum_rmb"] == "10.00"
    assert "projected_budget_exceeded" in plan["blocker_codes"]
    assert "wave_one_budget_policy_invalid" in plan["blocker_codes"]


@pytest.mark.asyncio
async def test_live_preflight_plan_accepts_one_audited_repair_yuan_above_wave_one(
    db_session: AsyncSession,
) -> None:
    run = await _fixture(db_session)
    run.cost_summary = {"spent_rmb": "7.00", "reserved_rmb": "0.00", "reservations": {}}
    await db_session.commit()
    await grant_live_canary_repair_extension(
        db_session, run, amount=Decimal("1.00"), reason="hair_color_consistency_repair",
        artifact_ids=["stale-reference", "wrong-first-frame"],
    )

    plan = await build_live_preflight_plan(db_session, run)

    assert plan["budget"]["maximum_rmb"] == "11.00"
    assert "wave_one_budget_policy_invalid" not in plan["blocker_codes"]


@pytest.mark.asyncio
async def test_live_preflight_routes_enforce_run_ownership(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)

    with pytest.raises(HTTPException) as get_error:
        await get_series_run_live_preflight_plan(run.id, db_session, "another-user")
    with pytest.raises(HTTPException) as post_error:
        await post_series_run_prepare_story_locks(run.id, db_session, "another-user")

    assert get_error.value.status_code == 404
    assert post_error.value.status_code == 404

@pytest.mark.asyncio
async def test_prepare_story_locks_rolls_back_after_state_machine_failure(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await _fixture(db_session)
    run_id, novel_id = run.id, run.novel_id

    async def fail_after_bible_flush(*args, **kwargs):
        raise RuntimeError("injected state machine failure")

    monkeypatch.setattr("app.features.series_run_story_locks.application.story_transaction.persist_production_closure_v2", fail_after_bible_flush)
    with pytest.raises(RuntimeError, match="injected"):
        await prepare_story_locks(db_session, run)

    assert not list((await db_session.scalars(select(StoryBible).where(StoryBible.novel_id == novel_id))).all())
    persisted_run = await db_session.get(SeriesProductionRun, run_id)
    assert "story_locks" not in (persisted_run.run_metadata or {})

@pytest.mark.asyncio
async def test_deterministic_setup_persists_candidates_without_direct_approval(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DETERMINISTIC_PROVIDER_FAKE", "1")
    monkeypatch.setenv("DETERMINISTIC_REFERENCE_URL", "https://fixtures.example/first-frame.png")
    run = await _fixture(db_session)

    await setup_deterministic_acceptance(
        DeterministicAcceptanceSetupRequest(novel_id=run.novel_id), db_session, run.user_id,
    )

    fixtures = list((await db_session.scalars(select(StoryEntity).where(
        StoryEntity.novel_id == run.novel_id, StoryEntity.source == "deterministic",
    ))).all())
    required_names = {"主角", "连续场景", "连续性道具", "道具被发现", "道具发生变化", "主角完成最终事件"}
    fixtures = [entity for entity in fixtures if entity.name in required_names]
    assert fixtures
    assert all(entity.is_approved is False for entity in fixtures)
    assert all(get_entity_review_status(entity) == "candidate" for entity in fixtures), [
        (entity.name, get_entity_review_status(entity)) for entity in fixtures
    ]
    assert all((entity.attributes or {}).get("evidence_contract", {}).get("status") == "verified" for entity in fixtures)
    shots = list((await db_session.scalars(select(Shot).where(Shot.user_id == run.user_id))).all())
    assert shots
    assert all(shot.image_url == "https://fixtures.example/first-frame.png" for shot in shots)
    assert all(shot.image_status == "succeeded" for shot in shots)

@pytest.mark.asyncio
async def test_anchor_selection_put_is_idempotent_and_only_real_change_increments_revision(
    db_session: AsyncSession,
) -> None:
    run = await _fixture(db_session)
    shots, _ = await _run_shots(db_session, run)
    smoke = [item["shot_id"] for item in recommend_anchor_shots(shots, mode="smoke")]
    run.run_metadata = {**(run.run_metadata or {}), "selected_anchor_shot_ids": smoke,
                        "selected_anchor_mode": "smoke", "anchor_selection_revision": 7}
    await db_session.commit()

    await put_series_run_anchor_shots(
        run.id, AnchorSelectionRequest(shot_ids=smoke, mode="smoke"), db_session, run.user_id,
    )
    await db_session.refresh(run)
    assert run.run_metadata["anchor_selection_revision"] == 7

    await put_series_run_anchor_shots(
        run.id, AnchorSelectionRequest(shot_ids=list(reversed(smoke)), mode="smoke"), db_session, run.user_id,
    )
    await db_session.refresh(run)
    assert run.run_metadata["anchor_selection_revision"] == 8

@pytest.mark.asyncio
@pytest.mark.parametrize(("anchor_mode", "expected_count", "failure_mode"), [
    ("smoke", 2, None), ("full", 6, None), ("full", 6, "recover"), ("full", 6, "unknown"),
])
async def test_deterministic_setup_seeds_normal_approved_facts_then_real_story_lock_succeeds(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, reference_http_server: str,
    anchor_mode: str, expected_count: int, failure_mode: str | None,
) -> None:
    monkeypatch.setenv("DETERMINISTIC_PROVIDER_FAKE", "1")
    run = await _fixture(db_session)
    await db_session.execute(delete(StoryEntity).where(StoryEntity.novel_id == run.novel_id))
    episodes = [dict(item) for item in run.episodes]
    for episode in episodes:
        canonical = dict(episode["canonical_ids"])
        workflow = await db_session.get(Workflow, canonical["workflow_id"])
        canonical["storyboard_id"] = workflow.storyboard_id
        episode["canonical_ids"] = canonical
    run.episodes = episodes
    supporting_character = StoryEntity(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
        chapter_id=run.episodes[1]["chapter_ids"][0], first_seen_chapter_id=run.episodes[1]["chapter_ids"][0],
        entity_type="character", name="配角", canonical_name="配角", source="deterministic",
        is_approved=False, version=1, attributes={},
    )
    db_session.add(supporting_character)
    await db_session.commit()

    setup = await setup_deterministic_acceptance(
        DeterministicAcceptanceSetupRequest(novel_id=run.novel_id), db_session, run.user_id,
    )
    entities_before_lock = list((await db_session.scalars(select(StoryEntity).where(
        StoryEntity.novel_id == run.novel_id,
    ))).all())
    by_name = {entity.name: entity for entity in entities_before_lock}
    required_fixture_names = {"主角", "连续场景", "连续性道具", "主角完成最终事件"}
    assert all(not by_name[name].is_approved for name in required_fixture_names)
    assert all(get_entity_review_status(by_name[name]) == "candidate" for name in required_fixture_names)
    manual_scene = by_name["连续场景"]
    set_entity_review_status(manual_scene, APPROVED, changed_by=run.user_id, reason="manual_review")
    manual_scene.is_approved = True; manual_scene.attributes = {**(manual_scene.attributes or {}), "approval_record":{"approved_by":run.user_id,"approved_at":utc_now().isoformat(),"reason":"manual_review"}}
    all_shots = list((await db_session.scalars(select(Shot).where(
        Shot.user_id == run.user_id,
    ))).all())
    dialogue_anchors = [shot for shot in all_shots if (shot.extra_data or {}).get("deterministic_dialogue_anchor")]
    for shot in all_shots:
        episode_number = int((shot.extra_data or {})["episode_number"])
        chapter_id = run.episodes[episode_number - 1]["chapter_ids"][0]
        event_name = {2:"道具被发现", 3:"道具发生变化", 4:"主角完成最终事件"}.get(episode_number)
        shot.extra_data = {**(shot.extra_data or {}), "deterministic_dialogue_anchor": True, "chapter_id": chapter_id, "entity_refs": {
            "characters": ([{"entity_id": by_name["主角"].id}] if episode_number == 1 else []),
            "scenes": ([{"entity_id": by_name["连续场景"].id}] if episode_number == 1 else []),
            "props": ([{"entity_id": by_name["连续性道具"].id}] if episode_number == 2 else []),
            "events": ([{"entity_id": by_name[event_name].id}] if event_name else []),
        }}
    run.run_metadata = {**(run.run_metadata or {}), "selected_anchor_shot_ids": [shot.id for shot in dialogue_anchors],
                        "selected_anchor_mode": "smoke", "anchor_selection_revision": 1}
    await _refresh_fixture_production_contracts(db_session, run)
    locked = await post_series_run_prepare_story_locks(run.id, db_session, run.user_id)

    assert setup["run_id"] == run.id
    assert locked["status"] == "locked"
    assert locked["closure_contract_version"] == "required_entity_closure_v2"
    assert locked["evidence_edge_count"] == sum(locked["required_counts"].values())
    entities = list((await db_session.scalars(select(StoryEntity).where(StoryEntity.novel_id == run.novel_id))).all())
    assert entities
    production_entities = [entity for entity in entities if entity.is_approved]
    assert manual_scene in production_entities
    assert all(((entity.extra_data or {}).get("lifecycle") or {}).get("status") == "approved" for entity in production_entities)
    await db_session.refresh(supporting_character)
    assert supporting_character.is_approved is False
    assert supporting_character.extra_data["lifecycle"]["status"] == "archived"
    assert supporting_character.extra_data["deterministic_merge"]["canonical_entity_id"]
    protagonist = next(entity for entity in entities if entity.entity_type == "character" and entity.name == "主角")
    assert protagonist.attributes["voice_binding"]["status"] == "locked"
    bible = await db_session.get(StoryBible, locked["story_bible_id"])
    story_lock = bible.extra_data["series_story_lock"]
    assert story_lock["closure_contract_version"] == "required_entity_closure_v2"
    assert len(story_lock["evidence_edges"]) == locked["evidence_edge_count"]
    assert len(dialogue_anchors) == 2
    assert {int((shot.extra_data or {})["episode_number"]) for shot in dialogue_anchors} == {1, 4}
    assert all((shot.extra_data or {}).get("parsed_speaker") == "主角" for shot in dialogue_anchors)
    assert all((shot.extra_data or {})["voice_binding"]["entity_id"] == protagonist.id for shot in dialogue_anchors)

    for config_id in setup["config_ids"].values():
        config = await db_session.get(LLMConfig, config_id)
        config.test_status = "success"
        config.tested_at = utc_now()
    await db_session.commit()
    await db_session.refresh(run)
    await persist_voice_selection(
        db_session, run, config_id=setup["config_ids"]["tts"],
        model_id="deterministic-tts", voice_id="deterministic-protagonist-voice", version=1,
    )
    run.run_metadata = {
        **(run.run_metadata or {}),
        "selected_anchor_shot_ids": [shot.id for shot in dialogue_anchors],
        "selected_anchor_mode": "smoke",
    }
    if anchor_mode == "full":
        run.budget_policy = {
            **(run.budget_policy or {}),
            "estimates_rmb": {"image": "0.10", "video": "0.50", "tts": "0.10", "text": "0.10"},
        }
    await _refresh_fixture_production_contracts(db_session, run)
    locked = await post_series_run_prepare_story_locks(run.id, db_session, run.user_id)
    assert locked["version"] == 2
    monkeypatch.setenv("DETERMINISTIC_REFERENCE_URL", f"{reference_http_server}/valid.png")

    reference = await post_series_run_prepare_reference(run.id, db_session, run.user_id)
    preflight = await __import__(
        "app.services.series_run_orchestrator", fromlist=["evaluate_media_preflight"]
    ).evaluate_media_preflight(db_session, run)

    asset = await db_session.get(Asset, reference["asset_id"])
    character_role_ids = {
        item["entity_id"] for item in asset.generation_params["role_bindings"]
        if item["role"] == "character_canonical"
    }
    approved_character_ids = {entity.id for entity in entities if entity.entity_type == "character" and entity.is_approved}
    assert character_role_ids == approved_character_ids
    assert supporting_character.id not in character_role_ids
    assert preflight["ready"] is True, preflight
    assert preflight["codes"] == []

    current_shots, _ = await _run_shots(db_session, run)
    generation_selected = [item["shot_id"] for item in recommend_anchor_shots(current_shots, mode=anchor_mode)]
    run.run_metadata = {
        **(run.run_metadata or {}), "selected_anchor_shot_ids": generation_selected,
        "selected_anchor_mode": anchor_mode, "anchor_selection_revision": 2,
    }
    for shot_id in generation_selected:
        selected_shot = await db_session.get(Shot, shot_id)
        selected_shot.image_url = f"{reference_http_server}/valid.png"
        selected_shot.image_status = "succeeded"
    await _refresh_fixture_production_contracts(db_session, run)
    await post_series_run_prepare_story_locks(run.id, db_session, run.user_id)
    reference = await post_series_run_prepare_reference(run.id, db_session, run.user_id)
    generation_request = GenerateSelectedRequest(shot_ids=generation_selected, mode=anchor_mode)
    workflow_endpoint = __import__("app.api.v1.endpoints.workflow", fromlist=["_evaluate_and_persist_server_quality"])
    workflow_media = __import__("app.features.workflow_media.public", fromlist=["generate_workflow_media_batch"])
    real_batch = workflow_media.generate_workflow_media_batch
    real_evaluator = workflow_endpoint._evaluate_and_persist_server_quality
    batch_calls: list[tuple[str, tuple[str, ...]]] = []
    evaluator_calls: list[str] = []

    async def batch_spy(command):
        batch_calls.append((command.workflow_id, tuple(command.request.shot_ids or [])))
        return await real_batch(command)

    async def evaluator_spy(db, *, workflow, shot, user_id, **kwargs):
        evaluator_calls.append(shot.id)
        return await real_evaluator(db, workflow=workflow, shot=shot, user_id=user_id, **kwargs)

    monkeypatch.setattr(workflow_media, "generate_workflow_media_batch", batch_spy)
    monkeypatch.setattr(workflow_endpoint, "_evaluate_and_persist_server_quality", evaluator_spy)
    if failure_mode:
        series_endpoint = __import__("app.api.v1.endpoints.series_runs", fromlist=["accept_series_anchor_quality"])
        real_accept = series_endpoint.accept_series_anchor_quality
        accept_calls = 0

        async def fail_third_accept(*args, **kwargs):
            nonlocal accept_calls
            accept_calls += 1
            if accept_calls == 3:
                raise RuntimeError("injected third anchor acceptance failure")
            return await real_accept(*args, **kwargs)

        monkeypatch.setattr(series_endpoint, "accept_series_anchor_quality", fail_third_accept)
        with pytest.raises(RuntimeError, match="third anchor"):
            await generate_selected_series_run_anchors(run.id, generation_request, db_session, run.user_id)
        await db_session.refresh(run)
        assert len((run.run_metadata or {}).get("anchor_quality_reports") or {}) == 2
        submission = await db_session.scalar(select(SeriesAnchorGenerationSubmission).where(
            SeriesAnchorGenerationSubmission.run_id == run.id,
        ))
        assert submission.status == "partial"
        provider_calls_before_retry = list(batch_calls)
        monkeypatch.setattr(series_endpoint, "accept_series_anchor_quality", real_accept)
        if failure_mode == "unknown":
            third_shot_id = generation_selected[2]
            third_job = await db_session.scalar(select(MediaGenerationJob).where(
                MediaGenerationJob.shot_id == third_shot_id,
            ).order_by(MediaGenerationJob.created_at.desc()).limit(1))
            third_job.status = "unknown"
            await db_session.commit()
            with pytest.raises(HTTPException) as unknown_error:
                await generate_selected_series_run_anchors(run.id, generation_request, db_session, run.user_id)
            assert unknown_error.value.detail["code"] == "provider_state_reconciliation_required"
            assert batch_calls == provider_calls_before_retry
            return
    first_generation = await generate_selected_series_run_anchors(run.id, generation_request, db_session, run.user_id)
    first_job_count = int(await db_session.scalar(select(func.count()).select_from(MediaGenerationJob)) or 0)
    first_evaluation_count = int(await db_session.scalar(select(func.count()).select_from(QualityEvaluation)) or 0)
    repeated_generation = await generate_selected_series_run_anchors(run.id, generation_request, db_session, run.user_id)

    assert repeated_generation == first_generation
    assert {shot_id for _, shot_ids in batch_calls for shot_id in shot_ids} == set(generation_selected)
    assert len(batch_calls) == len({item["episode_number"] for item in recommend_anchor_shots(current_shots, mode=anchor_mode)})
    assert evaluator_calls == []  # generic non-bound evaluator is forbidden here
    assert first_job_count == expected_count
    assert first_evaluation_count == expected_count * 6 + (6 if failure_mode == "recover" else 0)
    persisted_evaluations = list((await db_session.scalars(select(QualityEvaluation))).all())
    persisted_media_jobs = list((await db_session.scalars(select(MediaGenerationJob))).all())
    assert {job.shot_id for job in persisted_media_jobs} == set(generation_selected)
    assert all(job.media_type == "audio_video" and job.output_video_url and job.output_audio_url for job in persisted_media_jobs)
    assert all(job.input_assets for job in persisted_media_jobs)
    assert all(
        {item["capability"] for item in (job.extra_data or {}).get("provider_calls") or []}
        == {"reference", "video", "tts"}
        for job in persisted_media_jobs
    )
    assert {row.artifact_id for row in persisted_evaluations} == {job.id for job in persisted_media_jobs}
    if failure_mode == "recover":
        assert batch_calls == provider_calls_before_retry
    else:
        assert all(sum(1 for row in persisted_evaluations if row.artifact_id == job.id) == 6 for job in persisted_media_jobs)
    assert all((row.evidence or {}).get("job_id") for row in persisted_evaluations)
    assert all((row.evidence or {}).get("source") == "deterministic_probe" for row in persisted_evaluations)
    assert all(row.evaluator_version == "anchor-evaluator-v2" for row in persisted_evaluations)
    assert any(float(row.score) != 100.0 for row in persisted_evaluations)
    ordered_results = first_generation["quality_results"]
    assert ordered_results[0]["preceding_artifact_id"] is None
    assert all(
        current["preceding_artifact_id"] == previous["artifact_id"]
        for previous, current in zip(ordered_results, ordered_results[1:])
    )
    assert all((row.evidence or {}).get("canonical_reference_id") == reference["asset_id"] for row in persisted_evaluations)
    assert all((row.evidence or {}).get("as_of_chapter_id") and (row.evidence or {}).get("as_of_chapter_hash") for row in persisted_evaluations)
    await db_session.refresh(run)
    assert len((run.run_metadata or {}).get("anchor_quality_reports") or {}) == expected_count
    assert int(await db_session.scalar(select(func.count()).select_from(MediaGenerationJob)) or 0) == first_job_count
    assert int(await db_session.scalar(select(func.count()).select_from(QualityEvaluation)) or 0) == first_evaluation_count
    submission = await db_session.scalar(select(SeriesAnchorGenerationSubmission).where(SeriesAnchorGenerationSubmission.run_id == run.id))
    submission.status = "pending"
    await db_session.commit()
    with pytest.raises(HTTPException) as busy:
        await generate_selected_series_run_anchors(run.id, generation_request, db_session, run.user_id)
    assert busy.value.status_code == 409
    assert busy.value.detail["code"] == "generation_submission_busy"
    assert int(await db_session.scalar(select(func.count()).select_from(MediaGenerationJob)) or 0) == first_job_count

@pytest.mark.asyncio
async def test_generate_selected_cannot_skip_story_reference_or_task4_gates(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DETERMINISTIC_PROVIDER_FAKE", "1")
    run = await _fixture(db_session)
    shots, _ = await _run_shots(db_session, run)
    recommendations = recommend_anchor_shots(shots, mode="smoke")
    selected = [item["shot_id"] for item in recommendations]
    run.run_metadata = {
        **(run.run_metadata or {}), "selected_anchor_shot_ids": selected,
        "selected_anchor_mode": "smoke", "anchor_selection_revision": 1,
    }
    await db_session.commit()

    with pytest.raises(HTTPException) as blocked:
        await generate_selected_series_run_anchors(
            run.id, GenerateSelectedRequest(shot_ids=selected, mode="smoke"), db_session, run.user_id,
        )

    assert blocked.value.status_code == 409
    assert blocked.value.detail["code"] == "generation_preflight_blocked"
    assert await db_session.scalar(select(MediaGenerationJob.id)) is None
    assert await db_session.scalar(select(QualityEvaluation.id)) is None
    assert await db_session.scalar(select(LiveCanaryProviderOperation.id)) is None
    assert await db_session.scalar(select(SeriesAnchorGenerationSubmission.id)) is None

@pytest.mark.asyncio
async def test_unrelated_approved_character_does_not_expand_required_reference_closure(
    db_session: AsyncSession, reference_http_server: str,
) -> None:
    run = await _fixture(db_session)
    second = StoryEntity(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
        chapter_id=run.episodes[1]["chapter_ids"][0], first_seen_chapter_id=run.episodes[1]["chapter_ids"][0],
        entity_type="character", name="已批准配角", canonical_name="已批准配角", source="manual",
        is_approved=True, version=1,
        attributes={
            "approval_record": {"approved_by": run.user_id, "approved_at": utc_now().isoformat()},
            "visual_dna": {"costume": "浅色长衣"},
            "reference_requirements": {"character_multiview": ["front", "three_quarter", "full_body"]},
        },
        extra_data={"lifecycle": {"status": "approved"}},
    )
    db_session.add(second)
    await db_session.commit()
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)
    plan = await build_live_preflight_plan(db_session, run)
    assert "reference_capacity_exceeded" not in plan["blocker_codes"]
    lock = (run.run_metadata or {})["story_locks"]
    assert second.id not in lock["required_entity_ids"]
    assert await db_session.scalar(select(LiveCanaryProviderOperation.id)) is None
    adapter = _ReferenceAdapter({
        "status": "completed", "public_url": f"{reference_http_server}/valid.png",
        "provider_task_id": "required-closure-only", "actual_cost_rmb": "0.80",
        "width": 1536, "height": 1024,
        "public_url_expires_at": "2100-01-01T00:00:00+00:00",
        "storage_delivery": {
            "delivery_method": "qiniu_object_upload",
            "storage_config_id": "storage-qiniu",
            "object_key": "series-references/required-closure-only.png",
        },
        "visual_evidence": _visual_evidence(),
    })
    await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)
    preflight = await __import__(
        "app.services.series_run_orchestrator", fromlist=["evaluate_media_preflight"]
    ).evaluate_media_preflight(db_session, run)
    assert preflight["ready"] is True, preflight
    assert "canonical_assets_missing" not in preflight["codes"]
async def _fresh_live_bindings(db: AsyncSession, run: SeriesProductionRun) -> dict[str, str]:
    now = utc_now()
    specs = {
        "text": ("chat", ["chat"]),
        "image": ("image-generation", ["text-to-image"]),
        "tts": ("tts", ["text-to-speech"]),
        "video": ("video-generation", ["image-to-video"]),
    }
    result = {}
    for capability, (model_type, capabilities) in specs.items():
        provider = LLMProvider(id="minimax" if capability == "tts" else str(uuid4()), name=f"task9b-{capability}-{uuid4()}", is_active=True)
        model = LLMModel(
            id=str(uuid4()), provider_id=provider.id, model_id=f"task9b-{capability}-api-model",
            model_name=f"Task9b {capability}", model_type=model_type, capabilities=capabilities, is_active=True,
        )
        config = LLMConfig(
            id=str(uuid4()), user_id=run.user_id, model_id=model.id, name=f"Task9b {capability}",
            api_key="opaque-test-value", is_active=True, test_status="success", tested_at=now,
        )
        db.add_all([provider, model, config])
        result[capability] = config.id
    run.model_bindings = {"capabilities": {capability: {"config_id": config_id} for capability, config_id in result.items()}}
    await db.commit()
    await persist_voice_selection(
        db, run, config_id=result["tts"], model_id=(await db.get(LLMConfig, result["tts"])).model_id,
        voice_id=DEFAULT_MINIMAX_TTS_VOICE, version=1,
    )
    return result


class _ReferenceAdapter:
    def __init__(self, result: dict):
        self.result = result
        self.calls = 0
        self.observed_reserved = None
        self.last_prompt = None

    async def generate(self, *, db, run, prompt, image_config_id, operation):
        self.calls += 1
        self.last_prompt = prompt
        await db.refresh(run)
        self.observed_reserved = run.cost_summary["reservations"][operation.reservation_id]["state"]
        return dict(self.result)


@pytest.mark.asyncio
async def test_prepare_reference_prompt_uses_exact_shared_layout_geometry(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)
    adapter = _ReferenceAdapter({"status": "rejected"})

    with pytest.raises(ReferencePreparationBlocked):
        await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)

    assert "3:2" in adapter.last_prompt
    assert "左侧严格占画布 60%" in adapter.last_prompt
    assert "三个等宽面板" in adapter.last_prompt
    assert "右侧严格占画布 40%" in adapter.last_prompt


@pytest.mark.asyncio
async def test_prepare_reference_preserves_native_audio_budget_route(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.series_run_reference_preparation as preparation

    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run, native_audio=True)
    observed: list[bool] = []
    original = preparation.build_live_preflight_plan

    async def capture_native_audio(db, owned_run, *, native_audio=False):
        observed.append(native_audio)
        return await original(db, owned_run, native_audio=native_audio)

    monkeypatch.setattr(preparation, "build_live_preflight_plan", capture_native_audio)
    with pytest.raises(ReferencePreparationBlocked):
        await prepare_series_reference(
            db_session,
            run,
            adapter=_ReferenceAdapter({"status": "rejected"}),
            binding_ids=bindings,
            native_audio=True,
        )

    assert observed == [True]

@pytest.mark.asyncio
async def test_prepare_reference_precommits_budget_then_locks_one_composite_asset_idempotently(
    db_session: AsyncSession, reference_http_server: str,
) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    for capability in ("text", "tts"):
        config = await db_session.get(LLMConfig, bindings[capability])
        config.tested_at = utc_now() - timedelta(hours=2)
    await db_session.commit()
    tested_at_before = {capability: (await db_session.get(LLMConfig, config_id)).tested_at for capability, config_id in bindings.items()}
    await prepare_story_locks(db_session, run)
    adapter = _ReferenceAdapter({
        "status": "completed", "public_url": f"{reference_http_server}/valid.png",
        "provider_task_id": "image-task-1", "actual_cost_rmb": "0.80", "width": 1536, "height": 1024,
        "public_url_expires_at": "2100-01-01T00:00:00+00:00",
        "storage_delivery": {
            "delivery_method": "qiniu_object_upload",
            "storage_config_id": "storage-qiniu",
            "object_key": "series-references/reference.png",
        },
        "visual_evidence": _visual_evidence(),
    })

    first = await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)
    second = await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)
    assert {capability: (await db_session.get(LLMConfig, config_id)).tested_at for capability, config_id in bindings.items()} == tested_at_before

    assert adapter.observed_reserved == "reserved"
    assert adapter.calls == 1
    assert first["asset_id"] == second["asset_id"]
    assert second["idempotent"] is True
    assert first["operation"] == second["operation"]
    assert first["artifact"] == second["artifact"]
    assert first["operation"]["status"] == "reconciled"
    assert first["operation"]["actual_rmb"] == "0.80"
    assert first["artifact"]["checksum"] == first["artifact"]["layout_evidence"]["bytes_sha256"]
    assert first["artifact"]["layout_evidence"]["semantic_claims"] == []
    serialized = PrepareReferenceResponse.model_validate(first).model_dump()
    assert "api_key" not in repr(serialized).lower()
    assert "secret" not in repr(serialized).lower()
    assets = list((await db_session.scalars(select(Asset).where(Asset.novel_id == run.novel_id))).all())
    assert len(assets) == 1
    asset = assets[0]
    assert asset.is_final is True and asset.is_locked is True
    assert asset.category == "style" and asset.entity_id
    assert set(asset.generation_params["canonical_roles"]) >= {"front", "three_quarter", "full_body", "global_style_board"}
    assert {item["role"] for item in asset.generation_params["role_bindings"]} == {"character_canonical", "global_style_board"}
    assert asset.generation_params["evidence"]["operation_id"]
    assert asset.generation_params["evidence"]["public_url_expires_at"] == "2100-01-01T00:00:00+00:00"
    assert asset.generation_params["evidence"]["storage_delivery"]["delivery_method"] == "qiniu_object_upload"
    fetched = httpx.get(f"{reference_http_server}/valid.png").content
    assert asset.generation_params["evidence"]["checksum"] == hashlib.sha256(fetched).hexdigest()
    assert asset.generation_params["evidence"]["layout_evidence"]["layout_score"] >= 0.75
    provider_binding = await db_session.scalar(select(ProviderAssetBinding).where(ProviderAssetBinding.asset_id == asset.id))
    assert provider_binding.provider_id == run.model_bindings["capabilities"]["video"]["provider_id"]
    assert provider_binding.model_id == run.model_bindings["capabilities"]["video"]["api_model_id"]
    assert provider_binding.upload_status == "ready" and provider_binding.verified_at
    assert provider_binding.public_url_expires_at == datetime(2100, 1, 1)
    operation = await db_session.scalar(select(LiveCanaryProviderOperation).where(LiveCanaryProviderOperation.artifact_id == asset.id))
    assert operation.status == "reconciled"
    await db_session.refresh(run)
    assert run.cost_summary["spent_rmb"] == "0.80"
    real_preflight = await __import__(
        "app.services.series_run_orchestrator", fromlist=["evaluate_media_preflight"]
    ).evaluate_media_preflight(db_session, run)
    assert real_preflight["ready"] is True, real_preflight
    assert real_preflight["codes"] == []
    character = await db_session.get(StoryEntity, asset.entity_id)
    character.attributes = {key: value for key, value in (character.attributes or {}).items() if key != "voice_binding"}
    await db_session.commit()
    native_preflight = await __import__(
        "app.services.series_run_orchestrator", fromlist=["evaluate_media_preflight"]
    ).evaluate_media_preflight(db_session, run, native_audio=True)
    assert "voice_binding_missing" not in native_preflight["codes"]


@pytest.mark.asyncio
async def test_media_retry_refreshes_expired_qiniu_reference_without_image_generation(
    db_session: AsyncSession, reference_http_server: str, monkeypatch,
) -> None:
    import app.services.series_run_reference_preparation as preparation

    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)
    adapter = _ReferenceAdapter({
        "status": "completed", "public_url": f"{reference_http_server}/valid.png",
        "provider_task_id": "image-task-refresh", "actual_cost_rmb": "0.80",
        "public_url_expires_at": "2100-01-01T00:00:00+00:00",
        "storage_delivery": {"delivery_method": "qiniu_object_upload", "storage_config_id": "storage-qiniu",
                             "object_key": "series-references/reference.png",
                             "canonical_local_url": "/static/generated/series-references/reference.png"},
        "visual_evidence": _visual_evidence(),
    })
    first = await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)
    asset = await db_session.get(Asset, first["asset_id"])
    binding = await db_session.get(ProviderAssetBinding, first["provider_binding_id"])
    binding.public_url_expires_at = utc_now() - timedelta(minutes=1)
    run.status = "media_running"
    await db_session.commit()

    async def refresh(*_args, **_kwargs):
        return {"provider_url": "https://cdn.example.com/reference.png?e=4102444800",
                "delivery_method": "qiniu_object_upload", "storage_config_id": "storage-qiniu",
                "object_key": "series-references/reference.png", "omitted_reason": None}

    monkeypatch.setattr(preparation, "resolve_provider_media_url", refresh)
    second = await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)

    assert adapter.calls == 1
    assert second["asset_id"] == first["asset_id"]
    assert asset.url.startswith("https://cdn.example.com/reference.png")
    assert binding.public_url_expires_at == datetime(2100, 1, 1)


@pytest.mark.asyncio
async def test_media_retry_rebuilds_reference_after_prior_artifact_was_superseded(
    db_session: AsyncSession, reference_http_server: str,
) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)
    first = await prepare_series_reference(db_session, run, adapter=_ReferenceAdapter({
        "status": "completed", "public_url": f"{reference_http_server}/valid.png",
        "provider_task_id": "old-reference", "actual_cost_rmb": "0.80",
        "visual_evidence": _visual_evidence(),
    }), binding_ids=bindings)
    old_asset = await db_session.get(Asset, first["asset_id"])
    old_asset.is_active = False
    old_asset.generation_params = {**(old_asset.generation_params or {}), "status": "superseded"}
    run.run_metadata = {key: value for key, value in (run.run_metadata or {}).items()
                        if key != "reference_preparation"}
    run.status = "media_running"
    await db_session.commit()

    adapter = _ReferenceAdapter({
        "status": "completed", "public_url": f"{reference_http_server}/valid.png",
        "provider_task_id": "replacement-reference", "actual_cost_rmb": "0.80",
        "visual_evidence": _visual_evidence(),
    })
    replacement = await prepare_series_reference(
        db_session, run, adapter=adapter, binding_ids=bindings,
    )

    assert adapter.calls == 1
    assert replacement["asset_id"] != first["asset_id"]


@pytest.mark.asyncio
async def test_prepare_reference_over_budget_fails_before_operation_or_adapter(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)
    run.cost_summary = {"spent_rmb": "9.50", "reserved_rmb": "0.00", "reservations": {}}
    await db_session.commit()
    adapter = _ReferenceAdapter({"status": "completed", "public_url": "https://cdn.example.com/no.png", "visual_evidence": _visual_evidence()})

    with pytest.raises(ReferencePreparationBlocked, match="budget"):
        await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)

    assert adapter.calls == 0
    assert await db_session.scalar(select(LiveCanaryProviderOperation.id)) is None
    assert await db_session.scalar(select(Asset.id).where(Asset.novel_id == run.novel_id)) is None

@pytest.mark.asyncio
@pytest.mark.parametrize("provider_status", ["rejected", "unknown"])
async def test_prepare_reference_reject_or_unknown_never_creates_canonical_locks(
    db_session: AsyncSession, provider_status: str,
) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)
    adapter = _ReferenceAdapter({"status": provider_status, "provider_task_id": None})

    with pytest.raises(ReferencePreparationBlocked, match=provider_status):
        await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)

    assert await db_session.scalar(select(Asset.id).where(Asset.novel_id == run.novel_id)) is None
    assert await db_session.scalar(select(ProviderAssetBinding.id)) is None
    operation = await db_session.scalar(select(LiveCanaryProviderOperation))
    await db_session.refresh(run)
    if provider_status == "rejected":
        assert operation.status == "confirmed_rejected_before_acceptance"
        assert run.cost_summary["reserved_rmb"] == "0.00"
    else:
        assert operation.status == "unknown_manual_reconcile"
        assert run.cost_summary["reserved_rmb"] == "1.00"
        assert run.budget_policy["blocked"] is True


@pytest.mark.asyncio
async def test_prepare_reference_accepted_without_artifact_retains_id_and_never_resubmits(
    db_session: AsyncSession,
) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)
    adapter = _ReferenceAdapter({"status": "accepted", "provider_task_id": "minimax-generation-1"})

    with pytest.raises(ReferencePreparationBlocked, match="accepted"):
        await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)

    operation = await db_session.scalar(select(LiveCanaryProviderOperation))
    await db_session.refresh(run)
    assert operation.provider_task_id == "minimax-generation-1"
    assert operation.status == "unknown_manual_reconcile"
    assert run.cost_summary["reserved_rmb"] == "1.00"
    assert await db_session.scalar(select(Asset.id).where(Asset.novel_id == run.novel_id)) is None

    with pytest.raises(ReferencePreparationBlocked, match="requires recovery"):
        await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)

    assert adapter.calls == 1


@pytest.mark.asyncio
async def test_prepare_reference_stale_video_binding_fails_before_reservation(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)
    video = await db_session.get(LLMConfig, bindings["video"])
    video.tested_at = utc_now() - timedelta(hours=2)
    await db_session.commit()
    adapter = _ReferenceAdapter({"status": "completed", "public_url": "https://cdn.example.com/no.png", "visual_evidence": _visual_evidence()})

    with pytest.raises(ReferencePreparationBlocked, match="binding"):
        await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)

    assert adapter.calls == 0
    assert await db_session.scalar(select(LiveCanaryProviderOperation.id)) is None

@pytest.mark.asyncio
async def test_prepare_reference_route_enforces_run_ownership_before_adapter_selection(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)

    with pytest.raises(HTTPException) as error:
        await post_series_run_prepare_reference(run.id, db_session, "another-user")

    assert error.value.status_code == 404

@pytest.mark.asyncio
async def test_prepare_reference_unknown_route_returns_safe_operation_without_artifact(db_session: AsyncSession) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)
    with pytest.raises(ReferencePreparationBlocked):
        await prepare_series_reference(
            db_session, run, adapter=_ReferenceAdapter({"status": "unknown"}), binding_ids=bindings,
        )

    with pytest.raises(HTTPException) as caught:
        await post_series_run_prepare_reference(run.id, db_session, run.user_id)

    assert caught.value.status_code == 409
    detail = caught.value.detail
    assert detail["operation"]["status"] == "unknown_manual_reconcile"
    assert "artifact" not in detail
    assert "api_key" not in repr(detail).lower()
    assert "secret" not in repr(detail).lower()

@pytest.mark.asyncio
async def test_prepare_reference_resumes_reconciled_candidate_without_second_provider_call(
    db_session: AsyncSession, reference_http_server: str,
) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)
    adapter = _ReferenceAdapter({
        "status": "completed", "public_url": f"{reference_http_server}/valid.png",
        "provider_task_id": "image-task-resume", "actual_cost_rmb": "1.00",
        "visual_evidence": _visual_evidence(),
    })
    first = await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)
    asset = await db_session.get(Asset, first["asset_id"])
    binding = await db_session.scalar(select(ProviderAssetBinding).where(ProviderAssetBinding.asset_id == asset.id))
    await db_session.delete(binding)
    asset.is_locked = False
    asset.is_final = False
    metadata = dict(run.run_metadata or {})
    metadata.pop("reference_preparation", None)
    run.run_metadata = metadata
    await db_session.commit()

    resumed = await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)

    assert resumed["asset_id"] == asset.id and resumed["resumed"] is True
    assert adapter.calls == 1
    await db_session.refresh(asset)
    assert asset.is_locked and asset.is_final
    assert await db_session.scalar(select(ProviderAssetBinding.id).where(ProviderAssetBinding.asset_id == asset.id))

@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/html", "/bad.png", "/small.png"])
async def test_prepare_reference_rejects_non_image_corrupt_or_too_small_http_artifact(
    db_session: AsyncSession, reference_http_server: str, path: str,
) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)
    adapter = _ReferenceAdapter({
        "status": "completed", "public_url": f"{reference_http_server}{path}",
        "provider_task_id": f"bad-{path}", "visual_evidence": _visual_evidence(),
    })

    with pytest.raises(ReferencePreparationBlocked, match="artifact"):
        await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)

    assert await db_session.scalar(select(Asset.id).where(Asset.novel_id == run.novel_id)) is None
    assert await db_session.scalar(select(ProviderAssetBinding.id)) is None


@pytest.mark.asyncio
async def test_reference_verification_bypasses_broken_environment_proxy(
    reference_http_server: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")

    evidence = await _fetch_and_verify_image(f"{reference_http_server}/valid.png")

    assert evidence["width"] == 1536
    assert evidence["height"] == 1024


@pytest.mark.asyncio
async def test_reference_recovery_reuses_held_operation_without_resubmission(
    db_session: AsyncSession, reference_http_server: str,
) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run, native_audio=True)
    broken = _ReferenceAdapter({
        "status": "completed", "public_url": f"{reference_http_server}/bad.png",
        "provider_task_id": None,
    })
    with pytest.raises(ReferencePreparationBlocked):
        await prepare_series_reference(
            db_session, run, adapter=broken, binding_ids=bindings, native_audio=True,
        )
    operation = await db_session.scalar(select(LiveCanaryProviderOperation))
    assert operation.status == "unknown_manual_reconcile"
    assert operation.recovery_reason == "reference_artifact_unverified"

    recovered = await prepare_series_reference(
        db_session,
        run,
        adapter=_ReferenceAdapter({
            "status": "completed", "public_url": f"{reference_http_server}/valid.png",
            "provider_task_id": f"sync-recovered:{operation.id}",
            "actual_cost_rmb": None,
        }),
        binding_ids=bindings,
        native_audio=True,
        recovery_operation_id=operation.id,
    )

    assert recovered["status"] == "locked"
    assert await db_session.scalar(select(func.count()).select_from(LiveCanaryProviderOperation)) == 1
    await db_session.refresh(run)
    assert run.cost_summary["spent_rmb"] == "1.00"
    assert run.cost_summary["reserved_rmb"] == "0.00"
    assert run.budget_policy.get("blocked") is not True


@pytest.mark.asyncio
async def test_persisted_reference_adapter_republishes_exact_operation_artifact(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.series_reference_artifact_recovery as recovery

    folder = tmp_path / "generated" / "series-references"
    folder.mkdir(parents=True)
    image_path = folder / "reference-operation-1-stable.jpg"
    Image.new("RGB", (1536, 1024), "white").save(image_path, "JPEG")
    observed: list[str] = []

    async def publish(db, user_id, local_url, *, media_type):
        observed.append(local_url)
        return {
            "provider_url": "https://qiniu.example/reference.jpg?e=4102444800&token=redacted",
            "delivery_method": "qiniu_object_upload",
            "storage_config_id": "storage-1",
            "object_key": "generated/series-references/reference-operation-1-stable.jpg",
        }

    monkeypatch.setattr(recovery, "STATIC_ROOT", tmp_path)
    monkeypatch.setattr(recovery, "resolve_provider_media_url", publish)
    result = await PersistedReferenceArtifactAdapter().generate(
        db=db_session if False else object(),
        run=type("Run", (), {"user_id": "user-1"})(),
        prompt="unused", image_config_id="image-1",
        operation=type("Operation", (), {"id": "operation-1"})(),
    )

    assert observed == ["/static/generated/series-references/reference-operation-1-stable.jpg"]
    assert result["status"] == "completed"
    assert result["provider_task_id"] == "sync-recovered:operation-1"

@pytest.mark.asyncio
async def test_prepare_reference_rejects_unfetchable_deterministic_invalid_and_metadata_only(
    db_session: AsyncSession,
) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)
    adapter = _ReferenceAdapter({
        "status": "completed", "public_url": "https://deterministic.invalid/reference.png",
        "provider_task_id": "metadata-only", "width": 1536, "height": 1024,
        "visual_evidence": _visual_evidence(),
    })

    with pytest.raises(ReferencePreparationBlocked, match="artifact"):
        await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)

    assert await db_session.scalar(select(Asset.id).where(Asset.novel_id == run.novel_id)) is None

@pytest.mark.asyncio
async def test_prepare_reference_uses_server_pixels_not_provider_visual_metadata(
    db_session: AsyncSession, reference_http_server: str,
) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)
    adapter = _ReferenceAdapter({
        "status": "completed", "public_url": f"{reference_http_server}/valid.png",
        "provider_task_id": "no-layout-proof", "width": 1536, "height": 1024,
    })

    result = await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)

    asset = await db_session.get(Asset, result["asset_id"])
    assert asset.generation_params["evidence"]["layout_evidence"]["evaluator_version"] == "reference-layout-pixels-v1"

@pytest.mark.asyncio
async def test_provider_forged_visual_evidence_cannot_make_blank_pixels_ready(
    db_session: AsyncSession, reference_http_server: str,
) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)
    adapter = _ReferenceAdapter({
        "status": "completed", "public_url": f"{reference_http_server}/blank.png",
        "provider_task_id": "forged-layout", "visual_evidence": _visual_evidence(),
    })

    with pytest.raises(ReferencePreparationBlocked, match="layout"):
        await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)

    assert await db_session.scalar(select(Asset.id).where(Asset.novel_id == run.novel_id)) is None


@pytest.mark.asyncio
async def test_layout_rejection_persists_allowlisted_scoring_failure(
    db_session: AsyncSession, reference_http_server: str,
) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)
    adapter = _ReferenceAdapter({
        "status": "completed", "public_url": f"{reference_http_server}/blank.png",
        "provider_task_id": "layout-score-failure",
    })

    with pytest.raises(ReferencePreparationBlocked):
        await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)

    await db_session.refresh(run)
    operation = await db_session.scalar(select(LiveCanaryProviderOperation))
    failure = run.run_metadata["reference_failure_evidence"][operation.id]
    assert failure["failure_stage"] == "layout_scoring"
    assert failure["layout_score"] == 0.0
    assert failure["threshold"] == 0.75
    assert failure["evaluator_version"] == "reference-layout-pixels-v1"
    assert set(failure) == {"failure_stage", "layout_score", "threshold", "evaluator_version", "recorded_at"}
    assert "blank.png" not in repr(failure)
    assert adapter.last_prompt not in repr(failure)


def test_server_layout_evidence_is_bound_to_exact_downloaded_bytes(reference_http_server: str) -> None:
    image_bytes = httpx.get(f"{reference_http_server}/valid.png").content
    evidence = evaluate_reference_layout(image_bytes)

    assert evidence["evaluator_version"] == "reference-layout-pixels-v1"
    assert evidence["layout_score"] >= 0.75
    assert len(evidence["character_panels"]) == 3
    assert evidence["style_board"]["significant_palette_colors"] >= 4
    validate_layout_evidence(evidence, expected_bytes_sha256=hashlib.sha256(image_bytes).hexdigest())
    with pytest.raises(ValueError, match="bytes hash"):
        validate_layout_evidence(evidence, expected_bytes_sha256="0" * 64)

@pytest.mark.asyncio
@pytest.mark.parametrize("corrupt", ["NaN", "Infinity", "-1.00", "broken"])
async def test_live_preflight_corrupt_accounting_is_a_hard_blocker(db_session: AsyncSession, corrupt: str) -> None:
    run = await _fixture(db_session)
    run.cost_summary = {"spent_rmb": corrupt, "reserved_rmb": "0.00", "reservations": {}}
    shots, _ = await _run_shots(db_session, run)
    selected = [item["shot_id"] for item in recommend_anchor_shots(shots, mode="smoke")]
    run.run_metadata = {
        **(run.run_metadata or {}), "selected_anchor_shot_ids": selected,
        "selected_anchor_mode": "smoke", "anchor_selection_revision": 1,
    }
    await db_session.commit()

    plan = await build_live_preflight_plan(db_session, run)

    assert "budget_accounting_invalid" in plan["blocker_codes"]
    assert plan["ready"] is False
    with pytest.raises(HTTPException) as blocked:
        await generate_selected_series_run_anchors(
            run.id, GenerateSelectedRequest(shot_ids=selected, mode="smoke"), db_session, run.user_id,
        )
    assert "budget_accounting_invalid" in blocked.value.detail["blocker_codes"]
    assert await db_session.scalar(select(MediaGenerationJob.id)) is None
    assert await db_session.scalar(select(QualityEvaluation.id)) is None
    assert await db_session.scalar(select(LiveCanaryProviderOperation.id)) is None

@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["chapter", "entity", "style", "bible", "run_input"])
async def test_current_source_mutation_is_reported_read_only_by_live_preflight(
    db_session: AsyncSession, reference_http_server: str, mutation: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DETERMINISTIC_PROVIDER_FAKE", "1")
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)
    adapter = _ReferenceAdapter({
        "status": "completed", "public_url": f"{reference_http_server}/valid.png",
        "provider_task_id": f"source-{mutation}", "actual_cost_rmb": "0.80",
        "visual_evidence": _visual_evidence(),
    })
    completed = await prepare_series_reference(db_session, run, adapter=adapter, binding_ids=bindings)
    bible = await db_session.get(StoryBible, run.run_metadata["story_locks"]["story_bible_id"])
    current_shots, _ = await _run_shots(db_session, run)
    selected = [item["shot_id"] for item in recommend_anchor_shots(current_shots, mode="smoke")]
    run.run_metadata = {
        **(run.run_metadata or {}), "selected_anchor_shot_ids": selected,
        "selected_anchor_mode": "smoke", "anchor_selection_revision": 1,
    }
    await db_session.commit()
    if mutation == "chapter":
        chapter = await db_session.get(Chapter, run.episodes[0]["chapter_ids"][0])
        chapter.content += " 内容已变更"
    elif mutation == "entity":
        entity = await db_session.scalar(select(StoryEntity).where(StoryEntity.novel_id == run.novel_id, StoryEntity.entity_type == "character"))
        entity.version += 1
    elif mutation == "style":
        novel = await db_session.get(Novel, run.novel_id)
        novel.extra_data = {**novel.extra_data, "visual_style": "全新风格"}
    elif mutation == "bible":
        bible.style = "被篡改的 Bible 风格"
    else:
        episodes = [dict(item) for item in run.episodes]
        episodes[0] = {**episodes[0], "input_hash": "stale-input"}
        run.episodes = episodes
    await db_session.commit()

    before_run_updated_at = run.updated_at
    first_plan = await get_series_run_live_preflight_plan(run.id, db_session, run.user_id)
    second_plan = await get_series_run_live_preflight_plan(run.id, db_session, run.user_id)

    assert "story_lock_stale" in first_plan["blocker_codes"]
    assert second_plan == first_plan
    await db_session.refresh(bible)
    await db_session.refresh(run)
    assert run.updated_at == before_run_updated_at
    assert bible.extra_data["production_status"] != "superseded_review_required"
    asset = await db_session.get(Asset, completed["asset_id"])
    assert asset.is_locked is True and asset.is_final is True
    binding = await db_session.scalar(select(ProviderAssetBinding).where(ProviderAssetBinding.asset_id == asset.id))
    assert binding.is_active is True
    with pytest.raises(HTTPException) as generation_blocked:
        await generate_selected_series_run_anchors(
            run.id, GenerateSelectedRequest(shot_ids=selected, mode="smoke"), db_session, run.user_id,
        )
    assert generation_blocked.value.status_code == 409
    assert await db_session.scalar(select(MediaGenerationJob.id)) is None
    assert await db_session.scalar(select(QualityEvaluation.id)) is None
    assert await db_session.scalar(select(SeriesAnchorGenerationSubmission.id)) is None


@pytest.mark.asyncio
async def test_live_preflight_sanitizes_internal_exception_messages(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await _fixture(db_session)

    async def fail_with_secret(*args, **kwargs):
        raise RuntimeError("provider-secret-token=do-not-leak")

    monkeypatch.setattr(
        "app.services.series_run_live_preflight.evaluate_media_preflight",
        fail_with_secret,
    )
    plan = await build_live_preflight_plan(db_session, run)

    blocker = next(
        item for item in plan["blockers"]
        if item["code"] == "hard_preflight_unavailable"
    )
    assert blocker["message"] == "媒体预检暂不可用"
    assert "do-not-leak" not in str(plan)

@pytest.mark.asyncio
@pytest.mark.parametrize("exception", [ReferencePreSubmitRejected("invalid request"), TimeoutError("timeout"), ConnectionError("reset")])
async def test_reference_adapter_exception_release_or_retain_is_explicit(
    db_session: AsyncSession, exception: Exception,
) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)

    class RaisingAdapter:
        async def generate(self, **kwargs):
            raise exception

    with pytest.raises(ReferencePreparationBlocked) as caught:
        await prepare_series_reference(db_session, run, adapter=RaisingAdapter(), binding_ids=bindings)

    operation = await db_session.scalar(select(LiveCanaryProviderOperation))
    await db_session.refresh(run)
    if isinstance(exception, ReferencePreSubmitRejected):
        assert operation.status == "confirmed_rejected_before_acceptance"
        assert run.cost_summary["reserved_rmb"] == "0.00"
    else:
        assert operation.status == "unknown_manual_reconcile"
        assert run.cost_summary["reserved_rmb"] == "1.00"
        assert caught.value.operation == {
            "id": operation.id,
            "status": "unknown_manual_reconcile",
            "provider_task_id": None,
            "reservation_id": operation.reservation_id,
            "actual_rmb": None,
            "cost_source": None,
        }
        assert "artifact" not in caught.value.operation
        assert "secret" not in repr(caught.value.operation).lower()


@pytest.mark.asyncio
async def test_reference_adapter_stage_failure_binds_task_and_records_redacted_evidence(
    db_session: AsyncSession,
) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    await prepare_story_locks(db_session, run)

    class QiniuFailureAdapter:
        async def generate(self, **kwargs):
            raise ReferenceAdapterStageError(
                "qiniu_upload", provider_task_id="provider-image-task-1",
                provider_completed=True,
            ) from RuntimeError("https://secret.example/image.png?token=must-not-leak")

    with pytest.raises(ReferencePreparationBlocked) as caught:
        await prepare_series_reference(
            db_session, run, adapter=QiniuFailureAdapter(), binding_ids=bindings,
        )

    operation = await db_session.scalar(select(LiveCanaryProviderOperation))
    await db_session.refresh(run)
    assert operation.status == "unknown_manual_reconcile"
    assert operation.provider_task_id == "provider-image-task-1"
    assert operation.recovery_reason == "reference_adapter_qiniu_upload"
    assert run.cost_summary["reserved_rmb"] == "1.00"
    expected = {
        "schema_version": "reference-adapter-stage-v1",
        "failure_stage": "qiniu_upload",
        "provider_task_id_present": True,
        "provider_completed": True,
        "safe_retry": False,
    }
    failure = caught.value.operation["failure_evidence"]
    assert {key: failure[key] for key in expected} == expected
    assert run.run_metadata["reference_failure_evidence"][operation.id] == failure
    assert "must-not-leak" not in repr(caught.value.operation)
