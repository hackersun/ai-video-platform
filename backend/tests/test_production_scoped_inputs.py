"""Focused production owner-chain tests for complete scoped references."""

from __future__ import annotations

import hashlib
import copy
from dataclasses import replace
from uuid import uuid4

import pytest
import pytest_asyncio
import httpx
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base
from app.models import Chapter, Novel, Script, Shot, StoryEntity, Storyboard, Workflow
from app.models.series_production_run import SeriesProductionRun
from app.features.series_run_story_locks.application.production_scoped_inputs import (
    ProductionScopedRefCommand, build_production_scoped_refs,
)
from app.features.series_run_story_locks.domain.scoped_reference import (
    resolve_scoped_reference, sign_history_record, sign_merge_edge,
)
from app.features.series_run_story_locks.application.closure_v2_request import build_closure_v2_request
from app.features.series_run_story_locks.application.closure_versioning import preview_v2_lock
from app.features.series_run_story_locks.public import inspect_story_lock_freshness


@pytest_asyncio.fixture
async def scoped_db(tmp_path) -> AsyncSession:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'scoped-inputs.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session = async_sessionmaker(engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        await session.close(); await engine.dispose()


async def _owner_chain(db: AsyncSession):
    user_id, novel_id, chapter_id = "owner-1", str(uuid4()), str(uuid4())
    content = "沈砚推开城门。"
    novel = Novel(id=novel_id, user_id=user_id, title="四章", status="draft")
    chapter = Chapter(id=chapter_id, novel_id=novel_id, user_id=user_id, title="第一章",
                      content=content, chapter_number=1)
    extra_chapters=[Chapter(id=str(uuid4()),novel_id=novel_id,user_id=user_id,title=f"第{n}章",
        content=f"第{n}章内容",chapter_number=n) for n in range(2,5)]
    run = SeriesProductionRun(id=str(uuid4()), user_id=user_id, novel_id=novel_id,
        series_plan_version="v1", idempotency_key=str(uuid4()), status="shots_ready",
        episodes=[{"episode_number":1,"chapter_ids":[chapter_id],"input_hash":"input-1",
                   "canonical_ids":{"workflow_id":"workflow-1","script_id":"script-1",
                                    "storyboard_id":"board-1"}}, *[
                  {"episode_number":n,"chapter_ids":[extra_chapters[n-2].id],"input_hash":f"input-{n}",
                   "canonical_ids":{}} for n in range(2,5)]])
    workflow = Workflow(id="workflow-1", user_id=user_id, novel_id=novel_id, chapter_id=chapter_id,
        script_id="script-1", storyboard_id="board-1", title="第一集",
        metadata_={"series_run_id":run.id,"episode_number":1,"input_hash":"input-1"})
    script = Script(id="script-1",user_id=user_id,novel_id=novel_id,chapter_id=chapter_id,title="剧本",
        content=content,extra_data={"series_run_id":run.id,"episode_number":1,"input_hash":"input-1"})
    board = Storyboard(id="board-1", user_id=user_id, novel_id=novel_id, script_id="script-1", title="分镜",
        content={"series_run_id":run.id,"episode_number":1,"input_hash":"input-1"})
    evidence = {"status":"verified","chapter_id":chapter_id,"source_span":[0,2],
        "content_hash":hashlib.sha256(content.encode()).hexdigest(),"source_excerpt":content[:2],
        "parser_version":"deterministic-extraction-v2"}
    entity = StoryEntity(id="entity-1",user_id=user_id,novel_id=novel_id,chapter_id=chapter_id,
        first_seen_chapter_id=chapter_id,entity_type="character",name="沈砚",canonical_name="沈砚",
        attributes={"evidence_contract":evidence},extra_data={},is_approved=True)
    db.add_all([novel,chapter,*extra_chapters,run,workflow,script,board,entity]); await db.flush()
    command = ProductionScopedRefCommand(run_id=run.id,user_id=user_id,novel_id=novel_id,
        workflow_id=workflow.id,storyboard_id=board.id,shot_id="shot-new",episode_number=1,
        episode_input_hash="input-1",chapter_ids=(chapter_id,),chapter_id=chapter_id,
        script_id="script-1",prompt=content,dialogue="",visual_description=content,
        source_text=content,shot_text=f"{content} {content}",entity_refs={"characters":[{"entity_id":entity.id}],
            "scenes":[],"props":[],"events":[]})
    return run, command


@pytest.mark.asyncio
async def test_owner_chain_builds_complete_v1_ref_and_resolver_roundtrip(scoped_db):
    _run, command = await _owner_chain(scoped_db)
    result = await build_production_scoped_refs(scoped_db, command)
    ref = result.entity_refs["characters"][0]
    assert ref["contract_version"] == "chapter_evidence_ref_v1"
    resolved = resolve_scoped_reference(ref, result.owned_by_evidence_ref_id[ref["evidence_ref_id"]])
    assert resolved.source_entity_id == "entity-1" and resolved.as_of_chapter_id == command.chapter_id


@pytest.mark.asyncio
async def test_exact_complete_ref_rebuild_is_deterministic(scoped_db):
    _run, command = await _owner_chain(scoped_db)
    first = await build_production_scoped_refs(scoped_db, command)
    second = await build_production_scoped_refs(
        scoped_db, ProductionScopedRefCommand(**{**command.__dict__, "entity_refs": first.entity_refs}),
    )
    assert second.entity_refs == first.entity_refs


@pytest.mark.asyncio
@pytest.mark.parametrize("attack", ["future", "forged", "missing", "cross_owner"])
async def test_invalid_authority_fails_before_any_shot_write(scoped_db, attack):
    _run, command = await _owner_chain(scoped_db)
    entity = await scoped_db.get(StoryEntity, "entity-1")
    if attack == "future": entity.chapter_id = "future-chapter"
    elif attack == "forged": entity.attributes["evidence_contract"]["content_hash"] = "f" * 64
    elif attack == "missing": entity.attributes = {}
    else: entity.user_id = "other-owner"
    await scoped_db.flush()
    with pytest.raises(ValueError):
        await build_production_scoped_refs(scoped_db, command)


async def _persist_scoped_shot(db):
    run, command = await _owner_chain(db)
    scoped = await build_production_scoped_refs(db, command)
    shot = Shot(id=command.shot_id,user_id=command.user_id,storyboard_id=command.storyboard_id,
        shot_number=1,prompt=command.prompt,dialogue=command.dialogue,
        visual_description=command.visual_description,extra_data={"series_run_id":run.id,
            "episode_number":1,"input_hash":command.episode_input_hash,"chapter_id":command.chapter_id,
            "entity_refs":scoped.entity_refs})
    db.add(shot)
    episodes=[dict(item) for item in run.episodes]; canonical=dict(episodes[0]["canonical_ids"]); canonical["shot_ids"]=[shot.id]
    episodes[0]["canonical_ids"]=canonical; run.episodes=episodes
    run.run_metadata={**(run.run_metadata or {}),"selected_anchor_shot_ids":[shot.id]}
    await db.flush()
    return run, shot


@pytest.mark.asyncio
async def test_persisted_scoped_shot_builds_closure_v2_request(scoped_db):
    run, shot = await _persist_scoped_shot(scoped_db)
    request = await build_closure_v2_request(
        scoped_db, run.id, expected_run_version=run.version, user_id=run.user_id,
    )
    preview = preview_v2_lock(request)
    assert request["closure_contract_version"] == "required_entity_closure_v2"
    assert preview["required_counts"] == {"character":1,"scene":0,"prop":0,"event":0}
    assert preview["unrelated_candidate_count"] == 0


@pytest.mark.asyncio
async def test_closure_preserves_explicit_3d_style_from_novel_description(scoped_db):
    run, _shot = await _persist_scoped_shot(scoped_db)
    novel = await scoped_db.get(Novel, run.novel_id)
    novel.extra_data = {}
    novel.genre = "悬疑"
    novel.description = "电影级 3D 科幻悬疑连续短片，统一写实材质与电影光影。"
    await scoped_db.flush()

    request = await build_closure_v2_request(
        scoped_db, run.id, expected_run_version=run.version, user_id=run.user_id,
    )

    assert "3D" in request["drift_factors"]["visual_style"]
    assert request["drift_factors"]["visual_style"] != "悬疑"


@pytest.mark.asyncio
async def test_required_entity_lifecycle_change_drifts_closure_snapshot(scoped_db):
    from app.services.story_entity_lifecycle import ARCHIVED, set_entity_review_status

    run, _shot = await _persist_scoped_shot(scoped_db)
    initial = preview_v2_lock(await build_closure_v2_request(
        scoped_db, run.id, expected_run_version=run.version, user_id=run.user_id,
    ))
    entity = await scoped_db.get(StoryEntity, "entity-1")
    set_entity_review_status(entity, ARCHIVED, changed_by=run.user_id, reason="regression")
    await scoped_db.flush()
    changed = preview_v2_lock(await build_closure_v2_request(
        scoped_db, run.id, expected_run_version=run.version, user_id=run.user_id,
    ))

    assert changed["snapshot_hash"] != initial["snapshot_hash"]


@pytest.mark.asyncio
@pytest.mark.parametrize("attack", ["future","forged","missing","cross_owner"])
async def test_closure_request_revalidates_persisted_refs(scoped_db, attack):
    run, shot = await _persist_scoped_shot(scoped_db)
    refs=copy.deepcopy(shot.extra_data["entity_refs"]); reference=refs["characters"][0]
    if attack == "future": reference["as_of_chapter_id"]="future"
    elif attack == "forged": reference["evidence_ref_id"]="f"*64
    elif attack == "missing": refs["characters"]=[]
    else: shot.user_id="other-owner"
    shot.extra_data={**shot.extra_data,"entity_refs":refs}; await scoped_db.flush()
    with pytest.raises(ValueError):
        await build_closure_v2_request(
            scoped_db, run.id, expected_run_version=run.version, user_id=run.user_id,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("projection", ["episodes","refs","text","chapter","fabricated"])
async def test_detached_caller_projection_cannot_change_fresh_request(scoped_db, projection):
    run, shot = await _persist_scoped_shot(scoped_db); await scoped_db.commit()
    detached_run, detached_shot = copy.deepcopy(run), copy.deepcopy(shot)
    if projection == "episodes": detached_run.episodes=[]
    elif projection == "refs": detached_shot.extra_data={**detached_shot.extra_data,"entity_refs":{}}
    elif projection == "text": detached_shot.prompt="forged"
    elif projection == "chapter": detached_shot.extra_data={**detached_shot.extra_data,"chapter_id":"future"}
    else: detached_shot.id=shot.id; detached_shot.user_id="other"
    request=await build_closure_v2_request(
        scoped_db,run.id,expected_run_version=run.version,user_id=run.user_id)
    assert request["scoped_inputs"][0]["reference"]["shot_id"] == shot.id


@pytest.mark.asyncio
async def test_fresh_run_version_or_owner_drift_fails_without_request(scoped_db):
    run, _shot = await _persist_scoped_shot(scoped_db); await scoped_db.commit()
    with pytest.raises(ValueError,match="version|owner"):
        await build_closure_v2_request(
            scoped_db,run.id,expected_run_version=int(run.version)-1,user_id=run.user_id)
    with pytest.raises(ValueError,match="version|owner"):
        await build_closure_v2_request(
            scoped_db,run.id,expected_run_version=run.version,user_id="other")


@pytest.mark.asyncio
@pytest.mark.parametrize("attack", ["forged","wrongchapter","foreign"])
async def test_existing_shot_validation_failure_never_dirties_or_autoflushes(scoped_db, attack):
    from app.services.episode_production_service import create_or_resolve_shots_stage
    run, shot = await _persist_scoped_shot(scoped_db)
    entity = await scoped_db.get(StoryEntity,"entity-1")
    if attack == "forged":
        attributes=copy.deepcopy(entity.attributes); attributes["evidence_contract"]["content_hash"]="f"*64; entity.attributes=attributes
    elif attack == "wrongchapter": entity.chapter_id="other-chapter"
    else:
        foreign=StoryEntity(id="foreign-1",user_id="other",novel_id="other",chapter_id=entity.chapter_id,
            entity_type="character",name="外部",canonical_name="外部",attributes=copy.deepcopy(entity.attributes),extra_data={})
        scoped_db.add(foreign); refs=copy.deepcopy(shot.extra_data["entity_refs"]); refs["characters"][0]["entity_id"]=foreign.id
        shot.extra_data={**shot.extra_data,"entity_refs":refs}
    await scoped_db.commit()
    before=copy.deepcopy(shot.extra_data)
    with pytest.raises(ValueError):
        await create_or_resolve_shots_stage(scoped_db,run=run,episode=run.episodes[0])
    assert shot.extra_data == before and shot not in scoped_db.dirty
    persisted=await scoped_db.scalar(select(Shot.extra_data).where(Shot.id==shot.id))
    assert persisted == before


@pytest.mark.asyncio
async def test_same_chapter_events_with_shared_evidence_span_are_distinct_valid_refs(scoped_db):
    _run, command = await _owner_chain(scoped_db)
    first = await scoped_db.get(StoryEntity, "entity-1")
    first.entity_type = "event"; first.name = first.canonical_name = "道具被发现"
    second = StoryEntity(id="entity-2",user_id=first.user_id,novel_id=first.novel_id,
        chapter_id=first.chapter_id,first_seen_chapter_id=first.chapter_id,entity_type="event",
        name="守卫开始追捕",canonical_name="守卫开始追捕",attributes=copy.deepcopy(first.attributes),
        extra_data={},is_approved=True)
    scoped_db.add(second); await scoped_db.flush()
    command = replace(command, entity_refs={"characters":[],"scenes":[],"props":[],"events":[
        {"entity_id":first.id},{"entity_id":second.id}]})

    result = await build_production_scoped_refs(scoped_db, command)

    assert {item["canonical_entity_id"] for item in result.entity_refs["events"]} == {first.id, second.id}


@pytest.mark.asyncio
async def test_required_ambiguous_evidence_has_typed_redactable_blocker(scoped_db):
    from app.features.series_run_story_locks.domain.errors import ProductionRequiredEntityBlocked

    _run, command = await _owner_chain(scoped_db)
    entity = await scoped_db.get(StoryEntity, "entity-1")
    attributes = copy.deepcopy(entity.attributes)
    attributes["evidence_contract"] = {
        **attributes["evidence_contract"], "status": "ambiguous",
        "conflicting_values": ["raw-secret-a", "raw-secret-b"],
    }
    entity.attributes = attributes
    await scoped_db.flush()

    with pytest.raises(ProductionRequiredEntityBlocked) as raised:
        await build_production_scoped_refs(scoped_db, command)

    assert raised.value.code == "required_entity_evidence_ambiguous"
    assert raised.value.blocker_category == "identity_state"
    assert raised.value.values == ("raw-secret-a", "raw-secret-b")


async def _post_prepare(db, run):
    from app.api.v1.endpoints.series_runs import router
    from app.core.database import get_db
    from app.core.security import get_current_user_id
    app=FastAPI(); app.include_router(router,prefix="/api/v1")
    async def override_db(): yield db
    app.dependency_overrides[get_db]=override_db
    app.dependency_overrides[get_current_user_id]=lambda: run.user_id
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
        return await client.post(f"/api/v1/series-runs/{run.id}/prepare-story-locks")


@pytest.mark.asyncio
async def test_real_asgi_prepare_persists_v2_and_exact_repeat_reuses(scoped_db):
    from app.models import StoryBible
    run, shot = await _persist_scoped_shot(scoped_db); await scoped_db.commit()
    first=await _post_prepare(scoped_db,run)
    assert first.status_code == 200, first.text
    body=first.json(); assert body["closure_contract_version"]=="required_entity_closure_v2"
    assert body["subjects"] and body["evidence_edges"] and body["required_counts"]["character"]==1
    second=await _post_prepare(scoped_db,run)
    assert second.status_code == 200 and second.json()["idempotent"] is True
    assert second.json()["story_bible_id"] == body["story_bible_id"]
    bibles=list((await scoped_db.scalars(select(StoryBible).where(StoryBible.novel_id==run.novel_id))).all())
    await scoped_db.refresh(shot); await scoped_db.refresh(run)
    assert len(bibles)==1 and run.run_metadata["story_locks"]["closure_contract_version"]=="required_entity_closure_v2"
    assert shot.extra_data["story_lock_lineage"]["snapshot_hash"]==body["snapshot_hash"]


async def _v2_snapshot(db, run_id, shot_id):
    from app.models import StoryBible
    run=await db.get(SeriesProductionRun,run_id); shot=await db.get(Shot,shot_id)
    bibles=list((await db.scalars(select(StoryBible).where(StoryBible.novel_id==run.novel_id)
                                  .order_by(StoryBible.id))).all())
    return {"version":run.version,"metadata":copy.deepcopy(run.run_metadata),
        "episodes":copy.deepcopy(run.episodes),"shot":copy.deepcopy(shot.extra_data),
        "bibles":[(row.id,copy.deepcopy(row.extra_data)) for row in bibles]}


@pytest.mark.asyncio
async def test_existing_v1_is_immutable_and_atomically_superseded(scoped_db):
    from app.models import StoryBible
    run, shot=await _persist_scoped_shot(scoped_db)
    old=StoryBible(id="legacy-v1",user_id=run.user_id,novel_id=run.novel_id,title="Legacy",
        extra_data={"series_story_lock":{"run_id":run.id,"version":1,
            "closure_contract_version":"required_entity_closure_v1","immutable":{"legacy":True}}})
    scoped_db.add(old); run.run_metadata={**run.run_metadata,"story_locks":{"story_bible_id":old.id}}
    await scoped_db.commit()
    response=await _post_prepare(scoped_db,run)
    assert response.status_code==200 and response.json()["story_bible_id"]!=old.id
    await scoped_db.refresh(old); assert old.extra_data["series_story_lock"]["immutable"]=={"legacy":True}
    assert len((await _v2_snapshot(scoped_db,run.id,shot.id))["bibles"])==2


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_at", ["after_supersede","after_bible_insert","after_run_pointer",
                                      "after_episode_contracts","before_commit"])
async def test_production_v2_failpoints_roll_back_full_database(scoped_db, fail_at):
    from app.features.series_run_story_locks.application.story_transaction import apply_closure_v2_transaction
    run, shot=await _persist_scoped_shot(scoped_db); await scoped_db.commit()
    run_id,shot_id,user_id,version=run.id,shot.id,run.user_id,int(run.version)
    before=await _v2_snapshot(scoped_db,run_id,shot_id); await scoped_db.rollback()
    with pytest.raises(RuntimeError,match="injected"):
        await apply_closure_v2_transaction(scoped_db,run_id,None,version,fail_at,user_id=user_id)
    assert await _v2_snapshot(scoped_db,run_id,shot_id)==before


@pytest.mark.asyncio
@pytest.mark.parametrize("attack", ["legacy","missing","forged","future","crossowner"])
async def test_real_asgi_invalid_refs_are_safe_409_and_zero_write(scoped_db, attack):
    run, shot=await _persist_scoped_shot(scoped_db)
    refs=copy.deepcopy(shot.extra_data["entity_refs"]); ref=refs["characters"][0]
    if attack=="legacy": refs["characters"]=[{"entity_id":ref["entity_id"],"entity_type":"character"}]
    elif attack=="missing": refs["characters"]=[]
    elif attack=="forged": ref["evidence_ref_id"]="f"*64
    elif attack=="future": ref["as_of_chapter_id"]=run.episodes[3]["chapter_ids"][0]
    else: shot.user_id="other-owner"
    shot.extra_data={**shot.extra_data,"entity_refs":refs}; await scoped_db.commit()
    run_id,shot_id=run.id,shot.id
    before=await _v2_snapshot(scoped_db,run_id,shot_id)
    response=await _post_prepare(scoped_db,run)
    assert response.status_code==409 and response.json()["detail"]["code"] in {
        "story_lock_source_invalid","anchor_entity_closure_required"}
    assert ref.get("canonical_identity_sha256","") not in response.text
    assert await _v2_snapshot(scoped_db,run_id,shot_id)==before


async def _cross_chapter_local_mentions(db: AsyncSession):
    run, chapter_one = await _owner_chain(db)
    chapter_four_id = run.episodes[3]["chapter_ids"][0]
    chapter_four = await db.get(Chapter, chapter_four_id)
    workflow = Workflow(id="workflow-4",user_id=run.user_id,novel_id=run.novel_id,
        chapter_id=chapter_four_id,script_id="script-4",storyboard_id="board-4",title="第四集",
        metadata_={"series_run_id":run.id,"episode_number":4,"input_hash":"input-4"})
    script = Script(id="script-4",user_id=run.user_id,novel_id=run.novel_id,
        chapter_id=chapter_four_id,title="第四集剧本",content=chapter_four.content,
        extra_data={"series_run_id":run.id,"episode_number":4,"input_hash":"input-4"})
    board = Storyboard(id="board-4",user_id=run.user_id,novel_id=run.novel_id,
        script_id=script.id,title="第四集分镜",
        content={"series_run_id":run.id,"episode_number":4,"input_hash":"input-4"})
    evidence = {"status":"verified","chapter_id":chapter_four_id,"source_span":[0,2],
        "content_hash":hashlib.sha256(chapter_four.content.encode()).hexdigest(),
        "source_excerpt":chapter_four.content[:2],"parser_version":"deterministic-extraction-v2"}
    local = StoryEntity(id="entity-4-local",user_id=run.user_id,novel_id=run.novel_id,
        chapter_id=chapter_four_id,first_seen_chapter_id=chapter_four_id,
        entity_type="character",name="沈砚",canonical_name="沈砚",source="deterministic",
        attributes={"evidence_contract":evidence},extra_data={"lifecycle":{"status":"archived"}},
        is_approved=False)
    db.add_all([workflow,script,board,local]); await db.flush()
    command_four = ProductionScopedRefCommand(run_id=run.id,user_id=run.user_id,novel_id=run.novel_id,
        workflow_id=workflow.id,storyboard_id=board.id,shot_id="shot-four",episode_number=4,
        episode_input_hash="input-4",chapter_ids=(chapter_four_id,),chapter_id=chapter_four_id,
        script_id=script.id,prompt=chapter_four.content,dialogue="",visual_description=chapter_four.content,
        source_text=chapter_four.content,shot_text=f"{chapter_four.content} {chapter_four.content}",
        entity_refs={"characters":[{"entity_id":local.id}],"scenes":[],"props":[],"events":[]})
    provisional = await build_production_scoped_refs(db, command_four)
    ref = provisional.entity_refs["characters"][0]
    history = sign_history_record({"owner_user_id":run.user_id,"owner_novel_id":run.novel_id,
        "owner_entity_type":"character","canonical_entity_id":"entity-1","source_entity_id":local.id,
        "chapter_id":chapter_four_id,"evidence_ref_id":ref["evidence_ref_id"],
        "metadata":{"evidence_contract":copy.deepcopy(ref["evidence"])},"merge_audit":{
            "canonical_identity_sha256":ref["canonical_identity_sha256"]}})
    edge = sign_merge_edge({"source_entity_id":local.id,"canonical_entity_id":"entity-1",
        "user_id":run.user_id,"novel_id":run.novel_id,"entity_type":"character",
        "canonical_identity_sha256":ref["canonical_identity_sha256"]})
    canonical = await db.get(StoryEntity,"entity-1")
    canonical.extra_data={"canonical_histories":[history],"merge_edges":[edge]}; await db.flush()
    refs_one = await build_production_scoped_refs(db, chapter_one)
    refs_four = await build_production_scoped_refs(db, command_four)
    shots=[]
    for command, refs, number in ((chapter_one,refs_one,1),(command_four,refs_four,4)):
        shot=Shot(id=command.shot_id,user_id=run.user_id,storyboard_id=command.storyboard_id,
            shot_number=1,prompt=command.prompt,visual_description=command.visual_description,
            extra_data={"series_run_id":run.id,"episode_number":number,
                "input_hash":command.episode_input_hash,"chapter_id":command.chapter_id,
                "entity_refs":refs.entity_refs})
        db.add(shot); shots.append(shot)
    episodes=[dict(item) for item in run.episodes]
    for index,shot in ((0,shots[0]),(3,shots[1])):
        ids=dict(episodes[index]["canonical_ids"])
        if index==3: ids.update({"workflow_id":workflow.id,"script_id":script.id,"storyboard_id":board.id})
        ids["shot_ids"]=[shot.id]; episodes[index]["canonical_ids"]=ids
    run.episodes=episodes; run.run_metadata={"selected_anchor_shot_ids":[shot.id for shot in shots]}
    await db.flush()
    return run, local, canonical


@pytest.mark.asyncio
async def test_cross_chapter_local_mentions_collapse_to_one_canonical_subject(scoped_db):
    run, local, canonical = await _cross_chapter_local_mentions(scoped_db)
    request = await build_closure_v2_request(scoped_db,run.id,user_id=run.user_id)
    refs=[item["reference"] for item in request["scoped_inputs"]]
    assert {item["source_entity_id"] for item in refs} == {local.id,canonical.id}
    assert {item["entity_id"] for item in refs} == {canonical.id}
    assert len({item["canonical_identity_sha256"] for item in refs}) == 1
    assert request["subjects"] == [{"entity_type":"character","canonical_entity_id":canonical.id,
                                     "canonical_identity_sha256":refs[0]["canonical_identity_sha256"]}]
    assert len(request["evidence_edges"]) == 2


@pytest.mark.asyncio
async def test_cross_chapter_reference_requires_present_local_mention_even_with_signed_history(scoped_db):
    run, local, _canonical = await _cross_chapter_local_mentions(scoped_db)
    await scoped_db.delete(local); await scoped_db.flush()
    with pytest.raises(ValueError,match="local|source|missing|unresolved"):
        await build_closure_v2_request(scoped_db,run.id,user_id=run.user_id)


@pytest.mark.asyncio
async def test_cross_chapter_reference_rejects_ambiguous_local_mentions(scoped_db):
    run, local, _canonical = await _cross_chapter_local_mentions(scoped_db)
    chapter=await scoped_db.get(Chapter,local.chapter_id)
    attributes=copy.deepcopy(local.attributes)
    attributes["evidence_contract"].update({"source_span":[2,4],"source_excerpt":chapter.content[2:4]})
    scoped_db.add(StoryEntity(id="entity-4-duplicate",user_id=local.user_id,novel_id=local.novel_id,
        chapter_id=local.chapter_id,entity_type="character",name="沈砚",canonical_name="沈砚",
        attributes=attributes,extra_data={}))
    await scoped_db.flush()
    with pytest.raises(ValueError,match="ambiguous"):
        await build_closure_v2_request(scoped_db,run.id,user_id=run.user_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("attack",["history","merge"])
async def test_cross_chapter_reference_rejects_forged_history_or_merge_audit(scoped_db,attack):
    run, _local, canonical = await _cross_chapter_local_mentions(scoped_db)
    extra=copy.deepcopy(canonical.extra_data)
    if attack=="history": extra["canonical_histories"][0]["evidence_ref_id"]="f"*64
    else: extra["merge_edges"][0]["merge_audit_sha256"]="f"*64
    canonical.extra_data=extra; await scoped_db.flush()
    with pytest.raises(ValueError,match="history|audit|merge|stale|forged"):
        await build_closure_v2_request(scoped_db,run.id,user_id=run.user_id)


@pytest.mark.asyncio
async def test_cross_chapter_real_post_persists_shared_active_canonical(scoped_db):
    run, local, canonical = await _cross_chapter_local_mentions(scoped_db)
    await scoped_db.commit()
    response=await _post_prepare(scoped_db,run)
    assert response.status_code==200,response.text
    body=response.json()
    assert body["subjects"]==[{"entity_type":"character","canonical_entity_id":canonical.id,
        "canonical_identity_sha256":body["subjects"][0]["canonical_identity_sha256"]}]
    assert len(body["evidence_edges"])==2
    await scoped_db.refresh(local)
    assert local.extra_data["lifecycle"]["status"]=="archived"


@pytest.mark.asyncio
async def test_cross_chapter_real_post_rejects_inactive_canonical_zero_write(scoped_db):
    run, _local, canonical = await _cross_chapter_local_mentions(scoped_db)
    run_id = run.id
    canonical.is_approved=False
    canonical.extra_data={**canonical.extra_data,"lifecycle":{"status":"archived"}}
    await scoped_db.commit()
    before=await _v2_snapshot(scoped_db,run_id,"shot-four")
    response=await _post_prepare(scoped_db,run)
    assert response.status_code==409
    assert await _v2_snapshot(scoped_db,run_id,"shot-four")==before


@pytest.mark.asyncio
async def test_cross_chapter_real_post_requires_signed_history_for_merged_source(scoped_db):
    run, _local, canonical = await _cross_chapter_local_mentions(scoped_db)
    run_id = run.id
    canonical.extra_data={**canonical.extra_data,"canonical_histories":[]}
    await scoped_db.commit()
    before=await _v2_snapshot(scoped_db,run_id,"shot-four")
    response=await _post_prepare(scoped_db,run)
    assert response.status_code==409
    assert await _v2_snapshot(scoped_db,run_id,"shot-four")==before


@pytest.mark.asyncio
async def test_v2_freshness_supersedes_lock_when_required_canonical_is_archived(scoped_db):
    run, _local, canonical = await _cross_chapter_local_mentions(scoped_db)
    await scoped_db.commit()
    response = await _post_prepare(scoped_db, run)
    assert response.status_code == 200, response.text
    canonical.is_approved = False
    canonical.extra_data = {**canonical.extra_data, "lifecycle": {"status": "archived"}}
    await scoped_db.commit()

    freshness = await inspect_story_lock_freshness(scoped_db, run, supersede=True)

    await scoped_db.refresh(run)
    assert freshness["ready"] is False and freshness["code"] == "story_lock_stale"
    assert "story_locks" not in (run.run_metadata or {})
