from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from app.core.time_utils import utc_now
from app.models import Asset, Novel, ProviderAssetBinding, Script, Shot, StoryBible, StoryEntity, Storyboard, Workflow
from app.models.series_production_run import SeriesProductionRun
from app.services.episode_contract_service import lock_episode_contract
from app.services.production_graph_service import append_state_event
from app.services.series_run_orchestrator import (
    SeriesRunPreflightBlocked,
    SeriesRunOrchestrator,
    evaluate_media_preflight,
    mark_run_episode_contracts_superseded,
)
from app.features.series_run_media_preflight.public import _select_assets


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


def _run(*, user_id: str, novel_id: str, status: str = "anchor_ready") -> SeriesProductionRun:
    return SeriesProductionRun(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id,
        series_plan_version="four-chapter-v1", idempotency_key=str(uuid4()),
        status=status, current_episode_number=1, requested_stages=["media"],
        model_bindings={"provider_id": "test.synthetic-provider", "model_id": "test.synthetic-model"},
        budget_policy={}, cost_summary={}, gate_summary={}, run_metadata={},
        episodes=[{"episode_number": 1, "chapter_ids": [], "stage": "shots_ready", "canonical_ids": {}}],
        version=1,
    )


def test_locked_entity_multiview_assets_are_preferred_over_composite_reference() -> None:
    user_id, novel_id, entity_id = str(uuid4()), str(uuid4()), str(uuid4())
    entity = StoryEntity(
        id=entity_id, user_id=user_id, novel_id=novel_id, entity_type="character",
        name="沈岚", is_approved=True, attributes={},
    )
    views = [
        Asset(
            id=f"view-{view_key}", user_id=user_id, novel_id=novel_id,
            entity_id=entity_id, entity_type="character", category="character",
            name=f"沈岚 {view_key}", asset_type="image", url=f"https://cdn.example.com/{view_key}.png",
            version=1, is_active=True, is_final=True, is_locked=True,
            generation_params={"source": "entity_multiview", "status": "succeeded", "view_key": view_key},
        )
        for view_key in ("front", "side", "back")
    ]
    composite = Asset(
        id="legacy-composite", user_id=user_id, novel_id=novel_id, entity_id=entity_id,
        entity_type="character", category="style", name="多角色复合板", asset_type="image",
        url="https://cdn.example.com/composite.png", version=1, is_active=True,
        is_final=True, is_locked=True, generation_params={
            "composite_reference_rule": "single_artifact_dual_role_v1",
            "canonical_roles": ["front", "three_quarter", "full_body", "global_style_board"],
            "role_bindings": [
                {"role": "character_canonical", "entity_id": entity_id},
                {"role": "character_canonical", "entity_id": "another-character"},
                {"role": "global_style_board", "novel_id": novel_id},
            ],
        },
    )
    style = Asset(
        id="style-only", user_id=user_id, novel_id=novel_id, category="style",
        name="系列风格板", asset_type="image", url="https://cdn.example.com/style.png",
        version=1, is_active=True, is_final=True, is_locked=True,
        generation_params={"canonical_roles": ["global_style_board"]},
    )

    selected, missing, unlocked, conflicts = _select_assets(
        [*views, composite, style], [entity], novel_id,
    )

    assert [asset.id for asset in selected] == ["view-front", "view-side", "view-back", "style-only"]
    assert missing == []
    assert unlocked == []
    assert conflicts == []


def test_incomplete_entity_multiview_set_is_not_canonical() -> None:
    user_id, novel_id, entity_id = str(uuid4()), str(uuid4()), str(uuid4())
    entity = StoryEntity(
        id=entity_id, user_id=user_id, novel_id=novel_id, entity_type="character",
        name="沈岚", is_approved=True, attributes={},
    )
    incomplete = [
        Asset(
            id=f"view-{view_key}", user_id=user_id, novel_id=novel_id,
            entity_id=entity_id, entity_type="character", category="character",
            name=f"沈岚 {view_key}", asset_type="image", url=f"https://cdn.example.com/{view_key}.png",
            version=1, is_active=True, is_final=True, is_locked=True,
            generation_params={"source": "entity_multiview", "status": "succeeded", "view_key": view_key},
        )
        for view_key in ("front", "side")
    ]

    selected, missing, _, _ = _select_assets(incomplete, [entity], novel_id)

    assert selected == []
    assert missing == [entity_id, "global_style_board"]


def test_current_run_reference_supersedes_older_composite_reference_candidate() -> None:
    user_id, novel_id, entity_id = str(uuid4()), str(uuid4()), str(uuid4())
    entity = StoryEntity(
        id=entity_id, user_id=user_id, novel_id=novel_id, entity_type="character",
        name="顾清霜", is_approved=True, attributes={},
    )

    def composite(asset_id: str) -> Asset:
        return Asset(
            id=asset_id, user_id=user_id, novel_id=novel_id, category="style",
            name=f"系列复合参考-{asset_id}", asset_type="image",
            url=f"https://cdn.example.com/{asset_id}.png", version=1,
            is_active=True, is_final=True, is_locked=True,
            generation_params={
                "composite_reference_rule": "single_artifact_dual_role_v1",
                "canonical_roles": [
                    "front", "three_quarter", "full_body", "global_style_board",
                ],
                "role_bindings": [
                    {"role": "character_canonical", "entity_id": entity_id},
                    {"role": "global_style_board", "novel_id": novel_id},
                ],
            },
        )

    old_reference = composite("old-reference")
    current_reference = composite("current-reference")

    selected, missing, unlocked, conflicts = _select_assets(
        [old_reference, current_reference],
        [entity],
        novel_id,
        preferred_composite_asset_id=current_reference.id,
    )

    assert [asset.id for asset in selected] == [current_reference.id]
    assert missing == []
    assert unlocked == []
    assert conflicts == []


@pytest.mark.asyncio
async def test_media_preflight_blocks_with_stable_missing_requirement_codes(db_session: AsyncSession) -> None:
    user_id, novel_id = str(uuid4()), str(uuid4())
    db_session.add(Novel(id=novel_id, user_id=user_id, title="缺项小说"))
    run = _run(user_id=user_id, novel_id=novel_id)
    db_session.add(run)
    await db_session.commit()

    result = await evaluate_media_preflight(db_session, run)

    assert result["ready"] is False
    assert set(result["codes"]) >= {
        "story_bible_missing",
        "state_machine_missing",
        "production_entities_missing",
        "canonical_assets_missing",
        "provider_binding_missing",
        "voice_binding_missing",
    }
    with pytest.raises(SeriesRunPreflightBlocked) as exc_info:
        await SeriesRunOrchestrator().enter_media_running(db_session, run)
    assert run.status == "anchor_ready"
    assert exc_info.value.detail["code"] == "series_run_media_preflight_failed"


async def _approved_fixture(db: AsyncSession) -> tuple[SeriesProductionRun, Workflow, StoryEntity]:
    user_id, novel_id = str(uuid4()), str(uuid4())
    db.add(Novel(id=novel_id, user_id=user_id, title="完整小说"))
    db.add(StoryBible(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, title="正式 Bible", style="水墨动画",
        extra_data={
            "production_status": "locked",
            "approval_record": {"approved_by": user_id, "approved_at": "2026-07-11T00:00:00Z"},
            "state_machine": {"status": "approved", "issues": [], "current_state": {}},
        },
    ))
    entity = StoryEntity(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, entity_type="character",
        name="阿青", canonical_name="阿青", is_approved=True,
        attributes={
            "approval_record": {"approved_by": user_id, "approved_at": "2026-07-11T00:00:00Z"},
            "speaking": True,
            "voice_binding": {"voice_id": "voice-aqing", "version": 2, "status": "locked"},
            "visual_dna": {"costume": "青衣"},
            "reference_requirements": {"character_multiview": ["front", "three_quarter", "full_body"]},
        },
    )
    db.add(entity)
    asset = Asset(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, entity_id=entity.id,
        entity_type="character", category="character", name="阿青 canonical", asset_type="image",
        url="https://cdn.example.com/aqing.png", version=3, is_active=True, is_final=True,
        is_locked=True, locked_by=user_id,
        generation_params={"canonical_roles": ["front", "three_quarter", "full_body"], "checksum": "sha256:aqing"},
    )
    style_asset = Asset(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, category="style", name="全局风格板",
        asset_type="image", url="https://cdn.example.com/style.png", version=1,
        is_active=True, is_final=True, is_locked=True, locked_by=user_id,
        generation_params={"canonical_roles": ["global_style_board"], "checksum": "sha256:style"},
    )
    db.add_all([asset, style_asset])
    for value in (asset, style_asset):
        db.add(ProviderAssetBinding(
            id=str(uuid4()), asset_id=value.id, asset_version=value.version,
            provider_id="test.synthetic-provider", model_id="test.synthetic-model", binding_kind="reference_image",
            public_url=value.url, checksum=value.generation_params["checksum"], upload_status="ready",
            verified_at=utc_now(), is_active=True,
        ))
    workflow = Workflow(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, title="第一集", status="pending",
        metadata_={"episode_index": 1},
    )
    db.add(workflow)
    run = _run(user_id=user_id, novel_id=novel_id)
    workflow.metadata_ = {**workflow.metadata_, "series_run_id": run.id}
    run.episodes[0]["canonical_ids"] = {"workflow_id": workflow.id}
    db.add(run)
    await db.commit()
    return run, workflow, entity


async def _add_dialogue_shot(db: AsyncSession, run: SeriesProductionRun, workflow: Workflow, dialogue: str) -> Shot:
    script = Script(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
        title="对白剧本", content=dialogue, status="draft", extra_data={},
    )
    storyboard = Storyboard(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id, title="对白分镜",
        script_id=script.id, content={}, shot_count=1, status="draft",
    )
    shot = Shot(
        id=str(uuid4()), user_id=run.user_id, storyboard_id=storyboard.id,
        shot_number=1, dialogue=dialogue, prompt="对白镜头", extra_data={},
    )
    db.add_all([script, storyboard, shot])
    workflow.storyboard_id = storyboard.id
    await db.commit()
    return shot


@pytest.mark.asyncio
async def test_complete_explicitly_approved_fixture_can_enter_media_running(db_session: AsyncSession) -> None:
    run, workflow, _ = await _approved_fixture(db_session)

    await SeriesRunOrchestrator().enter_media_running(db_session, run)

    assert run.status == "media_running"
    assert run.gate_summary["media_preflight"]["ready"] is True
    contract = workflow.metadata_["episode_contract"]
    assert contract["as_of_facts"]["chapter_id"] == workflow.chapter_id
    assert contract["carry_over_state"] == contract["opening_state"]
    assert contract["asset_version_locks"][0]["asset_version"]
    assert contract["voice_version_locks"][0]["voice_version"] == 2


@pytest.mark.asyncio
async def test_later_approved_fact_marks_downstream_contract_review_required(db_session: AsyncSession) -> None:
    run, workflow, entity = await _approved_fixture(db_session)
    await lock_episode_contract(db_session, run.user_id, workflow.id)

    event = await append_state_event(
        db_session, user_id=run.user_id, novel_id=run.novel_id, entity_id=entity.id,
        episode_index=1, event_type="approved_fact_change", after_state={"costume": "白衣"},
        approval_status="approved", approved_by=run.user_id, commit=False,
    )
    from app.models import Novel
    from app.services.series_production import mark_production_graph_artifact_impact
    novel = await db_session.get(Novel, run.novel_id)
    await mark_production_graph_artifact_impact(
        db_session, user_id=run.user_id, novel=novel, event=event, commit=False
    )
    await db_session.commit()
    await db_session.refresh(workflow)

    assert workflow.metadata_["episode_contract"]["status"] == "superseded_review_required"
    assert workflow.metadata_["episode_contract"]["superseded_by_event_id"] == event.id


@pytest.mark.asyncio
async def test_real_shot_dialogue_requires_known_locked_speaker(db_session: AsyncSession) -> None:
    run, workflow, entity = await _approved_fixture(db_session)
    entity.attributes = {**entity.attributes, "speaking": False}
    await _add_dialogue_shot(db_session, run, workflow, "陌生人：停下。")

    blocked = await evaluate_media_preflight(db_session, run)
    assert "dialogue_speaker_unknown" in blocked["codes"]

    shot = (await db_session.get(Workflow, workflow.id)).storyboard_id
    real_shot = await db_session.scalar(__import__("sqlalchemy").select(Shot).where(Shot.storyboard_id == shot))
    real_shot.dialogue = "阿青：停下。"
    await db_session.commit()
    ready = await evaluate_media_preflight(db_session, run)
    assert ready["ready"] is True
    assert ready["voice_locks"][0]["entity_id"] == entity.id


@pytest.mark.asyncio
async def test_preflight_snapshot_changes_for_asset_voice_and_provider_mutations(db_session: AsyncSession) -> None:
    run, _, entity = await _approved_fixture(db_session)
    first = await evaluate_media_preflight(db_session, run)
    assert first["ready"] is True and first["snapshot_hash"]

    entity.attributes = {**entity.attributes, "voice_binding": {**entity.attributes["voice_binding"], "version": 3}}
    await db_session.flush()
    voice_changed = await evaluate_media_preflight(db_session, run)
    assert voice_changed["snapshot_hash"] != first["snapshot_hash"]

    binding = await db_session.scalar(__import__("sqlalchemy").select(ProviderAssetBinding).limit(1))
    binding.is_active = False
    await db_session.flush()
    provider_changed = await evaluate_media_preflight(db_session, run)
    assert provider_changed["ready"] is False
    assert provider_changed["snapshot_hash"] != voice_changed["snapshot_hash"]


@pytest.mark.asyncio
async def test_lifecycle_hidden_rows_do_not_block_but_candidate_does(db_session: AsyncSession) -> None:
    run, _, _ = await _approved_fixture(db_session)
    candidate = StoryEntity(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id, entity_type="character",
        name="候选", is_approved=False, extra_data={"lifecycle": {"status": "candidate"}},
    )
    db_session.add(candidate)
    await db_session.flush()
    assert "production_entities_unapproved" not in (await evaluate_media_preflight(db_session, run))["codes"]
    metadata = dict(run.run_metadata or {})
    story_locks = dict(metadata.get("story_locks") or {})
    run.run_metadata = {
        **metadata,
        "story_locks": {**story_locks, "required_entity_ids": [candidate.id]},
    }
    await db_session.flush()
    assert "production_entities_unapproved" in (await evaluate_media_preflight(db_session, run))["codes"]
    candidate.extra_data = {"lifecycle": {"status": "rejected"}}
    await db_session.flush()
    assert "production_entities_unapproved" not in (await evaluate_media_preflight(db_session, run))["codes"]
    candidate.extra_data = {"lifecycle": {"status": "archived"}}
    await db_session.flush()
    assert "production_entities_unapproved" not in (await evaluate_media_preflight(db_session, run))["codes"]


@pytest.mark.asyncio
async def test_story_bible_approval_shapes_and_state_machine_severity(db_session: AsyncSession) -> None:
    run, _, _ = await _approved_fixture(db_session)
    bible = await db_session.scalar(__import__("sqlalchemy").select(StoryBible).where(StoryBible.novel_id == run.novel_id))
    base = dict(bible.extra_data)
    bible.extra_data = {**base, "approval_record": None}
    await db_session.flush()
    assert "story_bible_not_approved" in (await evaluate_media_preflight(db_session, run))["codes"]
    bible.extra_data = {**base, "production_status": None}
    await db_session.flush()
    assert "story_bible_not_approved" in (await evaluate_media_preflight(db_session, run))["codes"]
    bible.extra_data = {**base, "state_machine": {"status": "approved", "issues": [{"blocking": False}]}}
    await db_session.flush()
    assert "state_machine_blocking" not in (await evaluate_media_preflight(db_session, run))["codes"]
    bible.extra_data = {**base, "state_machine": {"status": "approved", "issues": [{"message": "unspecified"}]}}
    await db_session.flush()
    assert "state_machine_blocking" in (await evaluate_media_preflight(db_session, run))["codes"]


@pytest.mark.asyncio
async def test_provider_native_reference_is_usable_without_claiming_public_ready(db_session: AsyncSession) -> None:
    run, _, _ = await _approved_fixture(db_session)
    bindings = list((await db_session.scalars(__import__("sqlalchemy").select(ProviderAssetBinding))).all())
    for binding in bindings:
        binding.public_url = None
        binding.provider_asset_id = f"native-{binding.asset_id}"
    await db_session.flush()
    result = await evaluate_media_preflight(db_session, run)
    assert result["ready"] is True
    assert all(item["provider_usable"] for item in result["provider_bindings"])
    assert all("public_ready" not in item for item in result["provider_bindings"])


@pytest.mark.asyncio
async def test_noncritical_prop_not_required_and_duplicate_style_boards_conflict(db_session: AsyncSession) -> None:
    run, _, _ = await _approved_fixture(db_session)
    db_session.add(StoryEntity(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id, entity_type="prop", name="普通杯子",
        is_approved=True, attributes={"approval_record": {"approved_by": run.user_id}},
        extra_data={"lifecycle": {"status": "approved"}},
    ))
    await db_session.flush()
    assert "canonical_assets_missing" not in (await evaluate_media_preflight(db_session, run))["codes"]
    recurring_scene = StoryEntity(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id, entity_type="scene", name="常驻码头",
        is_approved=True,
        attributes={"approval_record": {"approved_by": run.user_id}, "recurring": True},
        extra_data={"lifecycle": {"status": "approved"}},
    )
    db_session.add(recurring_scene)
    await db_session.flush()
    recurring = await evaluate_media_preflight(db_session, run)
    assert "canonical_assets_missing" in recurring["codes"]
    assert recurring_scene.id in next(
        issue["items"] for issue in recurring["issues"] if issue["code"] == "canonical_assets_missing"
    )
    recurring_scene.attributes = {**recurring_scene.attributes, "recurring": False}
    db_session.add(Asset(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id, category="style", name="冲突风格板",
        asset_type="image", version=1, is_active=True, is_final=True, is_locked=True,
        generation_params={"canonical_roles": ["global_style_board"]},
    ))
    await db_session.flush()
    assert "canonical_asset_conflict" in (await evaluate_media_preflight(db_session, run))["codes"]


@pytest.mark.asyncio
async def test_episode_contract_lock_is_idempotent_for_exact_snapshot(db_session: AsyncSession) -> None:
    run, workflow, _ = await _approved_fixture(db_session)
    preflight = await evaluate_media_preflight(db_session, run)
    exact = {**preflight["input_snapshot"], "snapshot_hash": preflight["snapshot_hash"]}

    first = await lock_episode_contract(
        db_session, run.user_id, workflow.id, commit=False, exact_preflight_snapshot=exact
    )
    second = await lock_episode_contract(
        db_session, run.user_id, workflow.id, commit=False, exact_preflight_snapshot=exact
    )

    assert second["contract_id"] == first["contract_id"]
    assert second["asset_version_locks"] == preflight["asset_locks"]
    assert second["voice_version_locks"] == preflight["voice_locks"]
    assert second["provider_bindings"] == preflight["provider_bindings"]


@pytest.mark.asyncio
async def test_multi_episode_contract_lock_rolls_back_all_when_later_episode_fails(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, first_workflow, _ = await _approved_fixture(db_session)
    second = Workflow(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
        title="第二集", status="pending", metadata_={"episode_index": 2},
    )
    db_session.add(second)
    run.episodes = [
        run.episodes[0],
        {"episode_number": 2, "chapter_ids": [], "stage": "shots_ready", "canonical_ids": {"workflow_id": second.id}},
    ]
    await db_session.commit()
    import app.services.series_run_orchestrator as module
    original = module.lock_episode_contract
    calls = 0

    async def _fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("later contract failure")
        return await original(*args, **kwargs)

    monkeypatch.setattr(module, "lock_episode_contract", _fail_second)
    with pytest.raises(RuntimeError, match="later contract failure"):
        await SeriesRunOrchestrator().enter_media_running(db_session, run)

    await db_session.refresh(first_workflow)
    await db_session.refresh(second)
    assert "episode_contract" not in (first_workflow.metadata_ or {})
    assert "episode_contract" not in (second.metadata_ or {})


@pytest.mark.parametrize("mutation", ["asset_unlock", "voice_version_change"])
@pytest.mark.asyncio
async def test_changed_preflight_inputs_mark_all_downstream_episode_contracts(
    db_session: AsyncSession,
    mutation: str,
) -> None:
    run, first, entity = await _approved_fixture(db_session)
    second = Workflow(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
        title="下游第二集", status="pending", metadata_={"episode_index": 2, "series_run_id": run.id},
    )
    db_session.add(second)
    run.episodes = [
        run.episodes[0],
        {"episode_number": 2, "chapter_ids": [], "stage": "shots_ready", "canonical_ids": {"workflow_id": second.id}},
    ]
    await db_session.commit()
    await SeriesRunOrchestrator().enter_media_running(db_session, run)
    old_hash = run.gate_summary["media_preflight"]["snapshot_hash"]

    if mutation == "asset_unlock":
        asset = await db_session.scalar(__import__("sqlalchemy").select(Asset).where(Asset.entity_id == entity.id))
        asset.is_locked = False
    else:
        entity.attributes = {
            **entity.attributes,
            "voice_binding": {**entity.attributes["voice_binding"], "version": 99},
        }
    await db_session.flush()
    fresh = await evaluate_media_preflight(db_session, run)
    assert fresh["snapshot_hash"] != old_hash
    affected = await mark_run_episode_contracts_superseded(
        db_session, run, reason="input_snapshot_changed", fresh_snapshot_hash=fresh["snapshot_hash"]
    )
    await db_session.commit()
    await db_session.refresh(first)
    await db_session.refresh(second)

    assert set(affected) == {first.id, second.id}
    assert first.metadata_["episode_contract"]["status"] == "superseded_review_required"
    assert second.metadata_["episode_contract"]["status"] == "superseded_review_required"


@pytest.mark.asyncio
async def test_snapshot_hash_covers_candidate_state_machine_and_shot_dialogue(db_session: AsyncSession) -> None:
    run, workflow, _ = await _approved_fixture(db_session)
    shot = await _add_dialogue_shot(db_session, run, workflow, "阿青：第一句。")
    baseline = await evaluate_media_preflight(db_session, run)

    candidate = StoryEntity(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id, entity_type="character",
        name="候选乙", extra_data={"lifecycle": {"status": "candidate"}}, is_approved=False,
    )
    db_session.add(candidate)
    await db_session.flush()
    with_candidate = await evaluate_media_preflight(db_session, run)
    assert with_candidate["snapshot_hash"] != baseline["snapshot_hash"]

    bible = await db_session.scalar(__import__("sqlalchemy").select(StoryBible).where(StoryBible.novel_id == run.novel_id))
    bible.extra_data = {
        **bible.extra_data,
        "state_machine": {"status": "approved", "issues": [{"code": "continuity", "blocking": True}]},
    }
    await db_session.flush()
    with_blocker = await evaluate_media_preflight(db_session, run)
    assert with_blocker["snapshot_hash"] != with_candidate["snapshot_hash"]

    shot.dialogue = "阿青：修改后的台词。"
    await db_session.flush()
    changed_dialogue = await evaluate_media_preflight(db_session, run)
    assert changed_dialogue["snapshot_hash"] != with_blocker["snapshot_hash"]
    shot_contract = changed_dialogue["input_snapshot"]["shot_dialogue_contracts"][0]
    assert shot_contract["parsed_speaker"] == "阿青"
    assert shot_contract["resolved_entity_id"]


@pytest.mark.asyncio
async def test_supersede_marker_ignores_foreign_novel_and_other_run_workflows(db_session: AsyncSession) -> None:
    run, owned, _ = await _approved_fixture(db_session)
    other_novel = Novel(id=str(uuid4()), user_id=run.user_id, title="其他小说")
    foreign_novel = Workflow(
        id=str(uuid4()), user_id=run.user_id, novel_id=other_novel.id, title="其他小说工作流",
        metadata_={"series_run_id": run.id, "episode_contract": {"snapshot_hash": "old", "status": "locked"}},
    )
    other_run = Workflow(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id, title="其他run工作流",
        metadata_={"series_run_id": "other-run", "episode_contract": {"snapshot_hash": "old", "status": "locked"}},
    )
    owned.metadata_ = {**owned.metadata_, "series_run_id": run.id, "episode_contract": {"snapshot_hash": "old", "status": "locked"}}
    db_session.add_all([other_novel, foreign_novel, other_run])
    run.episodes = [
        {"canonical_ids": {"workflow_id": owned.id}},
        {"canonical_ids": {"workflow_id": foreign_novel.id}},
        {"canonical_ids": {"workflow_id": other_run.id}},
    ]
    await db_session.flush()

    affected = await mark_run_episode_contracts_superseded(
        db_session, run, reason="input_snapshot_changed", fresh_snapshot_hash="fresh"
    )

    assert affected == [owned.id]
    assert foreign_novel.metadata_["episode_contract"]["status"] == "locked"
    assert other_run.metadata_["episode_contract"]["status"] == "locked"
