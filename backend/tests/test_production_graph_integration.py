from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from fastapi import HTTPException

from app.models import (
    Chapter,
    MediaGenerationJob,
    Novel,
    Publication,
    Script,
    Shot,
    StoryBible,
    Storyboard,
    SynthesisJob,
    TTSJob,
    VideoJob,
    Workflow,
)
from app.services.production_graph_service import append_state_event
from app.services.studio_snapshot import build_studio_snapshot


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_studio_snapshot_exposes_story_order_and_production_revision_order(db_session: AsyncSession) -> None:
    user_id = f"graph-user-{uuid4()}"
    novel_id = f"graph-novel-{uuid4()}"
    workflow_id = f"graph-workflow-{uuid4()}"
    db_session.add(Novel(id=novel_id, user_id=user_id, title="双时间线"))
    db_session.add(Workflow(id=workflow_id, user_id=user_id, novel_id=novel_id, title="第三集", status="running"))
    await db_session.commit()

    later_story_first_revision = await append_state_event(
        db_session,
        user_id=user_id,
        novel_id=novel_id,
        episode_index=3,
        entity_id="prop-bell",
        event_type="prop_owner_changed",
        story_time={"episode_index": 3, "sequence": 1},
        production_time={"stage": "script", "revision": 1},
        before_state={},
        after_state={"owner": "character-lin"},
        approval_status="approved",
    )
    earlier_story_second_revision = await append_state_event(
        db_session,
        user_id=user_id,
        novel_id=novel_id,
        episode_index=2,
        entity_id="prop-bell",
        event_type="prop_owner_changed",
        story_time={"episode_index": 2, "sequence": 1},
        production_time={"stage": "review", "revision": 2},
        before_state={},
        after_state={"owner": "character-shen"},
        approval_status="approved",
    )

    snapshot = await build_studio_snapshot(db_session, user_id, workflow_id)
    graph = snapshot["production_graph"]

    assert [item["id"] for item in graph["story_order"]] == [
        earlier_story_second_revision.id,
        later_story_first_revision.id,
    ]
    assert [item["id"] for item in graph["production_revisions"]] == [
        later_story_first_revision.id,
        earlier_story_second_revision.id,
    ]
    assert graph["version"] == 2
    assert graph["hash"] == earlier_story_second_revision.event_hash
    assert [item["id"] for item in snapshot["stage_gate"]["stages"]] == [
        "facts", "assets", "episode_contract", "draft", "review", "final", "render", "publish"
    ]
    assert snapshot["stage_gate"]["recommended_action"] == snapshot["guidance"]["next_action"]


@pytest.mark.asyncio
async def test_production_graph_endpoints_enforce_ownership_and_expose_projection_and_impact(
    db_session: AsyncSession,
) -> None:
    from app.api.v1.endpoints.story_bible import (
        ProductionGraphEventAppendRequest,
        append_production_graph_event,
        get_production_graph_event_impact,
        get_production_graph_projection,
        list_production_graph_events,
    )

    user_id = f"graph-user-{uuid4()}"
    other_user_id = f"graph-user-{uuid4()}"
    novel_id = f"graph-novel-{uuid4()}"
    db_session.add(Novel(id=novel_id, user_id=user_id, title="图谱 API"))
    await db_session.commit()
    request = ProductionGraphEventAppendRequest(
        novel_id=novel_id,
        episode_index=2,
        entity_id="prop-bell",
        event_type="prop_owner_changed",
        story_time={"episode_index": 2, "sequence": 1},
        production_time={"stage": "review"},
        before_state={},
        after_state={"owner": "character-lin"},
        evidence={"quote": "铜铃交给林澈"},
        approval_status="approved",
    )

    with pytest.raises(HTTPException) as exc_info:
        await append_production_graph_event(request, db_session, other_user_id)
    assert exc_info.value.status_code == 404

    created = await append_production_graph_event(request, db_session, user_id)
    listed = await list_production_graph_events(novel_id, None, db_session, user_id)
    projected = await get_production_graph_projection(novel_id, None, db_session, user_id)
    impact = await get_production_graph_event_impact(created["id"], novel_id, db_session, user_id)

    assert [item["id"] for item in listed["items"]] == [created["id"]]
    assert projected["state"]["entities"]["prop-bell"]["owner"] == "character-lin"
    assert impact["affected_episode_indices"] == [2]

    with pytest.raises(HTTPException) as exc_info:
        await list_production_graph_events(novel_id, None, db_session, other_user_id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_approved_append_rolls_back_when_impact_marking_fails(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.endpoints import story_bible
    from app.api.v1.endpoints.story_bible import ProductionGraphEventAppendRequest
    from app.models import ProductionStateEvent

    user_id = f"graph-atomic-{uuid4()}"
    novel_id = f"graph-novel-{uuid4()}"
    db_session.add(Novel(id=novel_id, user_id=user_id, title="原子图谱"))
    await db_session.commit()

    async def fail_mark(*_args, **_kwargs):
        raise RuntimeError("impact marker failed")

    monkeypatch.setattr(story_bible, "mark_production_graph_artifact_impact", fail_mark)
    request = ProductionGraphEventAppendRequest(
        novel_id=novel_id,
        episode_index=1,
        entity_id="prop-bell",
        event_type="prop_owner_changed",
        after_state={"owner": "character-lin"},
        approval_status="approved",
    )

    with pytest.raises(RuntimeError, match="impact marker failed"):
        await story_bible.append_production_graph_event(request, db_session, user_id)

    result = await db_session.execute(
        select(ProductionStateEvent).where(ProductionStateEvent.novel_id == novel_id)
    )
    assert result.scalars().all() == []

@pytest.mark.asyncio
async def test_production_bible_state_machine_and_series_plan_consume_graph_snapshots(
    db_session: AsyncSession,
) -> None:
    from app.services.production_bible import build_production_bible_summary
    from app.services.series_production import build_series_plan
    from app.services.story_state_machine import build_story_state_machine

    user_id = f"graph-user-{uuid4()}"
    novel_id = f"graph-novel-{uuid4()}"
    chapter_id = f"graph-chapter-{uuid4()}"
    bible_id = f"graph-bible-{uuid4()}"
    db_session.add(Novel(id=novel_id, user_id=user_id, title="图谱消费者"))
    db_session.add(Chapter(id=chapter_id, user_id=user_id, novel_id=novel_id, title="第一章", chapter_number=1, content="铜铃易主。"))
    db_session.add(StoryBible(id=bible_id, user_id=user_id, novel_id=novel_id, title="图谱圣经", style="动漫"))
    await db_session.commit()
    event = await append_state_event(
        db_session,
        user_id=user_id,
        novel_id=novel_id,
        chapter_id=chapter_id,
        episode_index=1,
        entity_id="prop-bell",
        event_type="prop_owner_changed",
        story_time={"episode_index": 1, "sequence": 1},
        production_time={"stage": "script"},
        before_state={},
        after_state={"owner": "character-lin"},
        approval_status="approved",
    )

    bible = await build_production_bible_summary(db_session, user_id, novel_id)
    state_machine = await build_story_state_machine(
        db_session,
        user_id,
        story_bible_id=bible_id,
        novel_id=novel_id,
        persist=False,
    )
    plan = await build_series_plan(
        db_session,
        user_id,
        novel_id=novel_id,
        target_episode_count=1,
        persist=False,
    )

    assert bible["production_graph"]["through_version"] == 1
    assert state_machine["production_graph"]["through_version"] == 1
    assert plan["episodes"][0]["production_graph"]["status"] == "ready"
    assert plan["episodes"][0]["production_graph"]["relevant_event_ids"] == [event.id]
    assert plan["episodes"][0]["production_graph"]["expected_closing_state"]["entities"]["prop-bell"]["owner"] == "character-lin"


@pytest.mark.asyncio
async def test_approved_impact_marks_concrete_lineage_and_supersedes_publication_metadata(db_session: AsyncSession) -> None:
    from app.api.v1.endpoints.story_bible import ProductionGraphEventAppendRequest, append_production_graph_event
    from app.services.publication_readiness import evaluate_publication_readiness

    user_id = f"graph-user-{uuid4()}"
    novel_id = f"graph-novel-{uuid4()}"
    chapter_id = f"graph-chapter-{uuid4()}"
    script_id = f"graph-script-{uuid4()}"
    storyboard_id = f"graph-board-{uuid4()}"
    workflow_id = f"graph-workflow-{uuid4()}"
    shot_id = f"graph-shot-{uuid4()}"
    chapter3_id = f"graph-chapter-{uuid4()}"
    script3_id = f"graph-script-{uuid4()}"
    storyboard3_id = f"graph-board-{uuid4()}"
    workflow3_id = f"graph-workflow-{uuid4()}"
    shot3_id = f"graph-shot-{uuid4()}"
    synthesis_id = f"graph-synthesis-{uuid4()}"
    novel = Novel(
        id=novel_id,
        user_id=user_id,
        title="影响链路",
        extra_data={"series_plan": {"episodes": [
            {"episode_index": 2, "chapter_ids": [chapter_id], "workflow_id": workflow_id},
            {"episode_index": 3, "chapter_ids": [chapter3_id], "workflow_id": workflow3_id},
        ]}},
    )
    db_session.add_all([
        novel,
        Chapter(id=chapter_id, user_id=user_id, novel_id=novel_id, title="第二章", chapter_number=2),
        Chapter(id=chapter3_id, user_id=user_id, novel_id=novel_id, title="第三章", chapter_number=3),
        Script(id=script_id, user_id=user_id, novel_id=novel_id, chapter_id=chapter_id, title="第二集"),
        Storyboard(id=storyboard_id, user_id=user_id, novel_id=novel_id, script_id=script_id, title="第二集分镜"),
        Script(id=script3_id, user_id=user_id, novel_id=novel_id, chapter_id=chapter3_id, title="第三集"),
        Storyboard(id=storyboard3_id, user_id=user_id, novel_id=novel_id, script_id=script3_id, title="第三集分镜"),
        Workflow(id=workflow_id, user_id=user_id, novel_id=novel_id, chapter_id=chapter_id, script_id=script_id, storyboard_id=storyboard_id, title="第二集", status="running", metadata_={"episode_index": 2, "episode_contract": {"contract_id": "contract-2"}}),
        Workflow(id=workflow3_id, user_id=user_id, novel_id=novel_id, chapter_id=chapter3_id, script_id=script3_id, storyboard_id=storyboard3_id, title="第三集", status="running", metadata_={"episode_index": 3, "episode_contract": {"contract_id": "contract-3"}}),
        Shot(id=shot_id, user_id=user_id, storyboard_id=storyboard_id, shot_number=1, extra_data={"entity_refs": {"props": [{"entity_id": "prop-bell"}]}, "production_context": {}}),
        Shot(id=shot3_id, user_id=user_id, storyboard_id=storyboard3_id, shot_number=1, extra_data={"entity_refs": {"props": [{"entity_id": "prop-bell"}]}, "production_context": {}}),
        VideoJob(id=f"video-{uuid4()}", user_id=user_id, workflow_id=workflow_id, title="视频", extra_data={}),
        TTSJob(id=f"tts-{uuid4()}", user_id=user_id, workflow_id=workflow_id, shot_id=shot_id, text="对白", extra_data={}),
        MediaGenerationJob(id=f"media-{uuid4()}", user_id=user_id, workflow_id=workflow_id, novel_id=novel_id, chapter_id=chapter_id, shot_id=shot_id, task_type="video", media_type="video", extra_data={}),
        SynthesisJob(id=synthesis_id, user_id=user_id, workflow_id=workflow_id, title="合成", video_url="shot.mp4", extra_data={"render_status": "rendered"}),
        Publication(id=f"publication-{uuid4()}", user_id=user_id, synthesis_job_id=synthesis_id, title="已发布第二集", status="published", video_url="https://cdn.example.com/final.mp4", publication_metadata={"render_status": "rendered", "output_kind": "final_video"}),
    ])
    await db_session.commit()

    created = await append_production_graph_event(
        ProductionGraphEventAppendRequest(
            novel_id=novel_id,
            chapter_id=chapter_id,
            episode_index=2,
            entity_id="prop-bell",
            event_type="prop_owner_changed",
            story_time={"episode_index": 2},
            production_time={"stage": "review"},
            after_state={"owner": "character-lin"},
            approval_status="approved",
        ),
        db_session,
        user_id,
    )
    impact = created["impact"]
    assert impact["affected_episode_indices"] == [2, 3]
    assert impact["affected_episode_contract_ids"] == ["contract-2", "contract-3"]
    assert impact["affected_shot_ids"] == [shot_id, shot3_id]
    assert {item["id"] for item in impact["affected_shots"]} == {shot_id, shot3_id}
    assert len(impact["affected_job_ids"]["video"]) == 1
    assert len(impact["affected_job_ids"]["tts"]) == 1
    assert len(impact["affected_job_ids"]["media"]) == 1
    assert impact["affected_job_ids"]["synthesis"] == [synthesis_id]

    shot = await db_session.get(Shot, shot_id)
    publication = (await db_session.execute(select(Publication).where(Publication.synthesis_job_id == synthesis_id))).scalar_one()
    assert shot.extra_data["needs_review"] is True
    assert shot.extra_data["production_context"]["review_state"] == "changes_requested"
    assert publication.status == "published"
    assert publication.publication_metadata["production_graph_status"] == "superseded_review_required"
    marked_at = publication.publication_metadata["marked_at"]

    from app.api.v1.endpoints.story_bible import get_production_graph_event_impact
    read_only_impact = await get_production_graph_event_impact(created["id"], novel_id, db_session, user_id)
    await db_session.refresh(publication)
    assert read_only_impact["affected_shot_ids"] == [shot_id, shot3_id]
    assert publication.publication_metadata["marked_at"] == marked_at

    snapshot = await build_studio_snapshot(db_session, user_id, workflow_id)
    source_item = next(item for item in snapshot["production_graph"]["production_revisions"] if item["id"] == created["id"])
    assert {item["id"] for item in source_item["affected_shots"]} == {shot_id, shot3_id}
    assert all("shot_id=" in item["review_url"] for item in source_item["affected_shots"])
    readiness = evaluate_publication_readiness(publication.video_url, publication.publication_metadata)
    assert readiness["is_publishable"] is False
    assert any(item["code"] == "production_graph_superseded" for item in readiness["publication_blockers"])


@pytest.mark.asyncio
async def test_studio_snapshot_uses_newest_100_events_and_canonical_tip_hash(db_session: AsyncSession) -> None:
    user_id = f"graph-user-{uuid4()}"
    novel_id = f"graph-novel-{uuid4()}"
    workflow_id = f"graph-workflow-{uuid4()}"
    db_session.add(Novel(id=novel_id, user_id=user_id, title="101 修订"))
    db_session.add(Workflow(id=workflow_id, user_id=user_id, novel_id=novel_id, title="工作流", status="running"))
    await db_session.commit()
    last = None
    for version in range(1, 102):
        last = await append_state_event(
            db_session,
            user_id=user_id,
            novel_id=novel_id,
            episode_index=version,
            event_type="weather_changed",
            story_time={"episode_index": version},
            after_state={"weather": f"weather-{version}"},
            approval_status="approved",
        )
    snapshot = await build_studio_snapshot(db_session, user_id, workflow_id)
    graph = snapshot["production_graph"]
    assert graph["version"] == 101
    assert graph["hash"] == last.event_hash
    assert len(graph["production_revisions"]) == 100
    assert graph["production_revisions"][0]["production_version"] == 2
    assert graph["production_revisions"][-1]["production_version"] == 101
