from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal
from app.models.chapter import Chapter
from app.models.script import Script
from app.models.series_production_run import SeriesProductionRun
from app.models.media_generation_job import MediaGenerationJob
from app.models.shot import Shot
from app.models.storyboard import Storyboard
from app.models.workflow import Workflow
from app.services.series_run_orchestrator import (
    InvalidRunTransition,
    SeriesRunOrchestrator,
    build_production_stage,
    transition_run,
)
from app.api.v1.endpoints.series_runs import CreateSeriesRunRequest, create_series_run
from app.services.episode_production_service import create_script_record
from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def _headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def _series_source(client: TestClient, user_id: str) -> tuple[str, list[str]]:
    response = client.post(
        "/api/v1/novels",
        json={"title": f"四章整书 {uuid4()}", "description": "四章连续故事"},
        headers=_headers(user_id),
    )
    assert response.status_code == 201
    novel_id = response.json()["id"]
    chapter_ids = []
    for number in range(1, 5):
        chapter = client.post(
            "/api/v1/chapters",
            json={
                "novel_id": novel_id,
                "title": f"第{number}章",
                "chapter_number": number,
                "content": f"第{number}章已经验证的正文内容。",
                "status": "completed",
            },
            headers=_headers(user_id),
        )
        assert chapter.status_code == 201
        chapter_ids.append(chapter.json()["id"])
    return novel_id, chapter_ids


def _run_payload(novel_id: str, chapter_ids: list[str], key: str) -> dict:
    return {
        "novel_id": novel_id,
        "series_plan_version": "plan-v1",
        "idempotency_key": key,
        "requested_stages": ["scripts", "storyboards", "shots"],
        "episodes": [
            {"episode_number": number, "chapter_ids": [chapter_id], "input_hash": f"hash-{number}"}
            for number, chapter_id in enumerate(chapter_ids, 1)
        ],
    }


def test_create_is_idempotent_user_isolated_and_validates_episode_sources(client: TestClient) -> None:
    owner = f"series-run-owner-{uuid4()}"
    other = f"series-run-other-{uuid4()}"
    novel_id, chapter_ids = _series_source(client, owner)
    payload = _run_payload(novel_id, chapter_ids, "same-request")

    first = client.post("/api/v1/series-runs", json=payload, headers=_headers(owner))
    second = client.post("/api/v1/series-runs", json=payload, headers=_headers(owner))
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert client.get(f"/api/v1/series-runs/{first.json()['id']}", headers=_headers(other)).status_code == 404

    invalid_numbers = {**payload, "idempotency_key": "bad-numbers", "episodes": [payload["episodes"][1]]}
    assert client.post("/api/v1/series-runs", json=invalid_numbers, headers=_headers(owner)).status_code == 422
    empty_chapters = {**payload, "idempotency_key": "empty", "episodes": [{**payload["episodes"][0], "chapter_ids": []}]}
    assert client.post("/api/v1/series-runs", json=empty_chapters, headers=_headers(owner)).status_code == 422

    other_novel, other_chapters = _series_source(client, owner)
    wrong_chapter = {**payload, "novel_id": novel_id, "idempotency_key": "wrong-chapter"}
    wrong_chapter["episodes"] = [{"episode_number": 1, "chapter_ids": [other_chapters[0]], "input_hash": "x"}]
    assert client.post("/api/v1/series-runs", json=wrong_chapter, headers=_headers(owner)).status_code == 422


def test_execute_async_returns_immediately_and_queues_owned_run(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.v1.endpoints.series_runs as series_endpoint

    user_id = f"series-run-async-{uuid4()}"
    novel_id, chapter_ids = _series_source(client, user_id)
    created = client.post(
        "/api/v1/series-runs",
        json=_run_payload(novel_id, chapter_ids, "async-execute"),
        headers=_headers(user_id),
    )
    queued: list[tuple[str, str]] = []
    monkeypatch.setattr(
        series_endpoint,
        "start_series_run_execution",
        lambda run_id, owner: queued.append((run_id, owner)) or True,
    )

    response = client.post(
        f"/api/v1/series-runs/{created.json()['id']}/execute-async",
        headers=_headers(user_id),
    )

    assert response.status_code == 202
    assert response.json()["execution_status"] == "queued"
    assert queued == [(created.json()["id"], user_id)]


def test_live_canary_policy_is_derived_only_from_server_environment(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = f"trusted-policy-{uuid4()}"
    novel_id, chapter_ids = _series_source(client, user_id)
    payload = _run_payload(novel_id, chapter_ids, "trusted-policy")
    deterministic = client.post(
        "/api/v1/series-runs", json={**payload, "idempotency_key": "deterministic"}, headers=_headers(user_id)
    )
    assert deterministic.status_code == 201
    for name in ("LIVE_CANARY_MAX_RMB", "LIVE_CANARY_IMAGE_ESTIMATE_RMB", "LIVE_CANARY_VIDEO_ESTIMATE_RMB", "LIVE_CANARY_TTS_ESTIMATE_RMB"):
        monkeypatch.delenv(name, raising=False)
    unavailable = client.post(
        f"/api/v1/series-runs/{deterministic.json()['id']}/live-canary/enable", headers=_headers(user_id)
    )
    assert unavailable.status_code == 409
    assert unavailable.json()["detail"]["code"] == "live_canary_unavailable"
    rejected = client.post(
        "/api/v1/series-runs",
        json={**payload, "budget_policy": {"profile": "isolated_live_canary", "max_rmb": "999999"}},
        headers=_headers(user_id),
    )
    assert rejected.status_code == 422

    monkeypatch.setenv("LIVE_CANARY_MAX_RMB", "10")
    monkeypatch.setenv("LIVE_CANARY_IMAGE_ESTIMATE_RMB", "1")
    monkeypatch.setenv("LIVE_CANARY_VIDEO_ESTIMATE_RMB", "2")
    monkeypatch.setenv("LIVE_CANARY_TTS_ESTIMATE_RMB", "0.5")
    enabled = client.post(
        f"/api/v1/series-runs/{deterministic.json()['id']}/live-canary/enable", headers=_headers(user_id)
    )
    assert enabled.status_code == 200
    assert enabled.json()["budget_policy"]["max_rmb"] == "10.00"
    monkeypatch.setenv("LIVE_CANARY_MAX_RMB", "15")
    refreshed = client.post(
        f"/api/v1/series-runs/{deterministic.json()['id']}/live-canary/enable", headers=_headers(user_id)
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["budget_policy"]["max_rmb"] == "15.00"
    created = client.post(
        "/api/v1/series-runs",
        json={**payload, "idempotency_key": "trusted-policy-ok", "budget_policy": {"profile": "isolated_live_canary"}},
        headers=_headers(user_id),
    )
    assert created.status_code == 201
    assert created.json()["budget_policy"] == {
        "profile": "isolated_live_canary", "live_canary": True, "max_rmb": "15.00",
        "estimates_rmb": {"image": "1.00", "video": "2.00", "tts": "0.50"},
    }


@pytest.mark.asyncio
async def test_generate_selected_rejects_stale_bindings_before_provider_and_groups_exact_shots(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.api.v1.endpoints.series_runs as series_endpoint
    import app.features.series_anchor_generation.generation as anchor_generation

    user_id = f"anchor-security-{uuid4()}"
    novel_id, chapter_ids = _series_source(client, user_id)
    created = client.post("/api/v1/series-runs", json=_run_payload(novel_id, chapter_ids, "anchors"), headers=_headers(user_id))
    run_id = created.json()["id"]
    executed = client.post(f"/api/v1/series-runs/{run_id}/execute", headers=_headers(user_id))
    assert executed.status_code == 200
    anchors = client.get(f"/api/v1/series-runs/{run_id}/anchor-shots", headers=_headers(user_id)).json()["smoke"]
    selected = [item["shot_id"] for item in anchors]
    assert len(selected) == 2 and len({item["episode_number"] for item in anchors}) == 2
    saved = client.put(
        f"/api/v1/series-runs/{run_id}/anchor-shots", json={"shot_ids": selected, "mode": "smoke"}, headers=_headers(user_id)
    )
    assert saved.status_code == 200
    assert client.put(
        f"/api/v1/series-runs/{run_id}/anchor-shots", json={"shot_ids": [selected[0]], "mode": "smoke"}, headers=_headers(user_id)
    ).status_code == 422
    assert client.put(
        f"/api/v1/series-runs/{run_id}/anchor-shots", json={"shot_ids": [*selected, "foreign-shot"], "mode": "smoke"}, headers=_headers(user_id)
    ).status_code == 422
    assert client.get(f"/api/v1/series-runs/{run_id}/anchor-shots", headers=_headers("foreign-user")).status_code == 404

    calls: list[tuple[str, list[str], str]] = []

    class Batch:
        def __init__(self, workflow_id, shot_ids): self.workflow_id, self.shot_ids = workflow_id, shot_ids
        def model_dump(self): return {"workflow_id": self.workflow_id, "shot_ids": self.shot_ids}

    async def fake_batch(command):
        workflow_id, request = command.workflow_id, command.request
        db, owner = command.db, command.user_id
        calls.append((workflow_id, list(request.shot_ids or []), request.strategy))
        workflow = await db.get(Workflow, workflow_id)
        contract = (workflow.metadata_ or {}).get("episode_contract") or {}
        for shot_id in request.shot_ids or []:
            shot = await db.get(Shot, shot_id)
            context = (shot.extra_data or {}).get("production_context") or {}
            job_id = str(uuid4())
            db.add(MediaGenerationJob(
                id=job_id, user_id=owner, workflow_id=workflow_id, shot_id=shot_id,
                task_type="shot_audio_video", media_type="audio_video", status="succeeded",
                output_video_url=f"/unit/{job_id}.mp4", output_audio_url=f"/unit/{job_id}.mp3",
                duration_seconds=4, resolution="720p", input_assets=[{"asset_id": "unit-reference"}],
                extra_data={
                    "artifact_id": job_id,
                    "episode_number": context.get("episode_number") or contract.get("episode_index"),
                    "episode_contract_version": context.get("episode_contract_version") or contract.get("contract_id"),
                    "canonical_reference_id": context.get("canonical_reference_id") or contract.get("production_bible_hash"),
                    "canonical_reference_version": context.get("canonical_reference_version") or "unit-v1",
                    "as_of_chapter_id": context.get("as_of_chapter_id") or workflow.chapter_id,
                    "as_of_chapter_hash": context.get("as_of_chapter_hash") or contract.get("snapshot_hash") or "unit-hash",
                    "artifact_completed_at": datetime.now(timezone.utc).isoformat(),
                },
            ))
        await db.flush()
        return Batch(workflow_id, list(request.shot_ids or []))

    monkeypatch.setattr(series_endpoint.workflow_media, "generate_workflow_media_batch", fake_batch)

    async def ready_plan(*_args, **_kwargs):
        return {"ready": True, "blocker_codes": []}

    async def ready_task4(*_args, **_kwargs):
        return {"ready": True, "codes": [], "asset_locks": [], "snapshot_hash": "unit-ready"}

    monkeypatch.setattr(anchor_generation, "build_live_preflight_plan", ready_plan)
    monkeypatch.setattr(anchor_generation, "evaluate_media_preflight", ready_task4)
    async with AsyncSessionLocal() as db:
        run = await db.get(SeriesProductionRun, run_id)
        run.budget_policy = {"profile": "isolated_live_canary", "live_canary": True, "max_rmb": "10.00", "estimates_rmb": {"video": "2.00", "tts": "0.50", "image": "1.00"}}
        run.run_metadata = {
            **(run.run_metadata or {}),
            "story_locks": {"source_hash": "unit-story", "bible_snapshot_hash": "unit-bible"},
            "reference_preparation": {
                "evidence_hash": "unit-reference", "asset_id": "unit-reference-asset", "asset_version": 1,
            },
        }
        await db.commit()
    stale = client.post(
        f"/api/v1/series-runs/{run_id}/generate-selected",
        json={"shot_ids": selected, "mode": "smoke"}, headers=_headers(user_id),
    )
    assert stale.status_code == 409
    assert calls == []

    async def fresh(*_args, **_kwargs): return {}
    monkeypatch.setattr(anchor_generation, "validate_persisted_model_bindings", fresh)
    async with AsyncSessionLocal() as db:
        run = await db.get(SeriesProductionRun, run_id)
        run.model_bindings = {"capabilities": {name: {"config_id": f"config-{name}"} for name in ("text", "image", "tts", "video")}}
        run.status = "media_running"
        for episode in run.episodes or []:
            workflow = await db.get(Workflow, (episode.get("canonical_ids") or {}).get("workflow_id"))
            metadata = dict(workflow.metadata_ or {})
            contract = dict(metadata.get("episode_contract") or {})
            contract.setdefault("snapshot_hash", f"unit-contract-{episode['episode_number']}")
            contract.setdefault("chapter_id", workflow.chapter_id)
            metadata["episode_contract"] = contract
            workflow.metadata_ = metadata
        await db.commit()
    generated = client.post(
        f"/api/v1/series-runs/{run_id}/generate-selected",
        json={"shot_ids": selected, "mode": "smoke"}, headers=_headers(user_id),
    )
    assert generated.status_code == 200, generated.text
    assert [shot for _, group, _ in calls for shot in group] == selected
    assert all(len(group) == 1 for _, group, _ in calls)
    assert {strategy for _, _, strategy in calls} == {"separate_video_tts"}


def test_state_machine_has_explicit_recovery_and_safe_pause_resume() -> None:
    run = SeriesProductionRun(status="created", version=1, run_metadata={})
    with pytest.raises(InvalidRunTransition):
        transition_run(run, "completed")
    transition_run(run, "preflight")
    transition_run(run, "paused")
    transition_run(run, "paused")
    transition_run(run, "preflight")
    transition_run(run, "preflight")
    run.status = "failed"
    transition_run(run, "episodes_building")
    run.status = "blocked"
    transition_run(run, "episodes_building")
    run.status = "paused"
    run.run_metadata = {}
    with pytest.raises(InvalidRunTransition, match="resume target"):
        transition_run(run, "preflight")


@pytest.mark.asyncio
async def test_episode_three_stage_failure_keeps_prior_stages_and_resumes_without_duplicates(client: TestClient) -> None:
    user_id = f"recovery-user-{uuid4()}"
    novel_id, chapter_ids = _series_source(client, user_id)
    created = client.post(
        "/api/v1/series-runs",
        json=_run_payload(novel_id, chapter_ids, "recover-real-rows"),
        headers=_headers(user_id),
    )
    run_id = created.json()["id"]
    calls: Counter[tuple[int, str]] = Counter()
    fail_once = True

    async def fail_storyboard_after_flush(db, run, episode, stage):
        nonlocal fail_once
        number = episode["episode_number"]
        calls[(number, stage)] += 1
        result = await build_production_stage(db, run, episode, stage)
        if number == 3 and stage == "storyboard_ready" and fail_once:
            fail_once = False
            raise RuntimeError("injected episode 3 storyboard failure after flush")
        return result

    async with AsyncSessionLocal() as db:
        run = await db.scalar(select(SeriesProductionRun).where(SeriesProductionRun.id == run_id))
        assert run is not None
        orchestrator = SeriesRunOrchestrator(fail_storyboard_after_flush)
        with pytest.raises(RuntimeError, match="storyboard failure"):
            await orchestrator.execute(db, run)
        await db.refresh(run)
        assert [episode["stage"] for episode in run.episodes] == ["shots_ready", "shots_ready", "script_ready", "created"]
        assert run.episodes[2]["blocker"]
        assert await _canonical_counts(db, run_id) == (3, 3, 2, 2)

        await orchestrator.execute(db, run)
        await db.refresh(run)
        assert calls[(3, "workflow_ready")] == 1
        assert calls[(3, "script_ready")] == 1
        assert calls[(3, "storyboard_ready")] == 2
        assert calls[(3, "shots_ready")] == 1
        assert run.status == "shots_ready"
        assert await _canonical_counts(db, run_id) == (4, 4, 4, 4)
        assert len({episode["canonical_ids"]["workflow_id"] for episode in run.episodes}) == 4


async def _canonical_counts(db, run_id: str) -> tuple[int, int, int, int]:
    workflows = (await db.scalars(select(Workflow))).all()
    scripts = (await db.scalars(select(Script))).all()
    storyboards = (await db.scalars(select(Storyboard))).all()
    shots = (await db.scalars(select(Shot))).all()
    return (
        sum((row.metadata_ or {}).get("series_run_id") == run_id for row in workflows),
        sum((row.extra_data or {}).get("series_run_id") == run_id for row in scripts),
        sum((row.content or {}).get("series_run_id") == run_id for row in storyboards),
        sum((row.extra_data or {}).get("series_run_id") == run_id for row in shots),
    )


@pytest.mark.asyncio
async def test_canonical_resolution_fails_closed_for_stale_hash_foreign_id_and_wrong_lineage(client: TestClient) -> None:
    # Stale hash on a duplicate tagged workflow must fail before metadata advances.
    user_id = f"lineage-user-{uuid4()}"
    novel_id, chapter_ids = _series_source(client, user_id)
    created = client.post("/api/v1/series-runs", json=_run_payload(novel_id, chapter_ids, "lineage"), headers=_headers(user_id))
    run_id = created.json()["id"]
    async with AsyncSessionLocal() as db:
        run = await db.get(SeriesProductionRun, run_id)
        stale = Workflow(
            id=str(uuid4()), user_id=user_id, novel_id=novel_id, chapter_id=chapter_ids[0],
            title="stale", status="pending",
            metadata_={"series_run_id": run_id, "episode_number": 1, "input_hash": "stale-hash"},
        )
        db.add(stale)
        await db.commit()
        with pytest.raises(ValueError, match="input_hash"):
            await SeriesRunOrchestrator().execute(db, run)
        await db.refresh(run)
        assert run.status == "failed"
        assert run.episodes[0]["stage"] == "created"

    # A foreign canonical workflow ID must never be mutated by the script stage.
    owner = f"foreign-owner-{uuid4()}"
    novel_id, chapter_ids = _series_source(client, owner)
    created = client.post("/api/v1/series-runs", json=_run_payload(novel_id, chapter_ids, "foreign"), headers=_headers(owner))
    async with AsyncSessionLocal() as db:
        run = await db.get(SeriesProductionRun, created.json()["id"])
        foreign = Workflow(id=str(uuid4()), user_id="another-owner", title="foreign", status="pending", metadata_={})
        db.add(foreign)
        while run.status != "episodes_building":
            transition_run(run, ("preflight", "planning", "facts_ready", "assets_ready", "episodes_building")[("created", "preflight", "planning", "facts_ready", "assets_ready").index(run.status)])
        episode = dict(run.episodes[0])
        episode.update(stage="workflow_ready", canonical_ids={"workflow_id": foreign.id})
        run.episodes = [episode, *run.episodes[1:]]
        await db.commit()
        with pytest.raises(ValueError, match="workflow"):
            await SeriesRunOrchestrator().execute(db, run)
        await db.refresh(foreign)
        assert foreign.script_id is None
        await db.refresh(run)
        assert run.status == "failed"
        assert run.episodes[0]["stage"] == "workflow_ready"

    # A tagged storyboard linked to a different script must not be resolved.
    chain_user = f"chain-user-{uuid4()}"
    novel_id, chapter_ids = _series_source(client, chain_user)
    created = client.post("/api/v1/series-runs", json=_run_payload(novel_id, chapter_ids, "wrong-chain"), headers=_headers(chain_user))
    async with AsyncSessionLocal() as db:
        run = await db.get(SeriesProductionRun, created.json()["id"])
        while run.status != "episodes_building":
            transition_run(run, ("preflight", "planning", "facts_ready", "assets_ready", "episodes_building")[("created", "preflight", "planning", "facts_ready", "assets_ready").index(run.status)])
        episode = dict(run.episodes[0])
        for stage in ("workflow_ready", "script_ready"):
            additions = await build_production_stage(db, run, episode, stage)
            canonical = dict(episode.get("canonical_ids") or {})
            canonical.update(additions)
            episode.update(stage=stage, canonical_ids=canonical)
            run.episodes = [episode, *run.episodes[1:]]
            await db.commit()
        wrong_script = await create_script_record(
            db, user_id=chain_user, novel_id=novel_id, chapter_id=chapter_ids[0], title="wrong", content="wrong"
        )
        bad_storyboard = Storyboard(
            id=str(uuid4()), user_id=chain_user, novel_id=novel_id, script_id=wrong_script.id,
            title="bad chain", content={"series_run_id": run.id, "episode_number": 1, "input_hash": "hash-1"},
            shot_count=0, status="draft",
        )
        db.add(bad_storyboard)
        await db.commit()
        with pytest.raises(ValueError, match="script"):
            await SeriesRunOrchestrator().execute(db, run)
        await db.refresh(run)
        assert run.status == "failed"
        assert run.episodes[0]["stage"] == "script_ready"
        assert bad_storyboard.script_id == wrong_script.id


@pytest.mark.asyncio
async def test_canonical_workflow_links_cannot_be_overwritten_by_stage_resolution(client: TestClient) -> None:
    user_id = f"link-conflict-{uuid4()}"
    novel_id, chapter_ids = _series_source(client, user_id)
    created = client.post("/api/v1/series-runs", json=_run_payload(novel_id, chapter_ids, "link-conflict"), headers=_headers(user_id))
    async with AsyncSessionLocal() as db:
        run = await db.get(SeriesProductionRun, created.json()["id"])
        while run.status != "episodes_building":
            transition_run(run, ("preflight", "planning", "facts_ready", "assets_ready", "episodes_building")[("created", "preflight", "planning", "facts_ready", "assets_ready").index(run.status)])
        episode = dict(run.episodes[0])
        workflow_ids = await build_production_stage(db, run, episode, "workflow_ready")
        episode.update(stage="workflow_ready", canonical_ids=workflow_ids)
        run.episodes = [episode, *run.episodes[1:]]
        unrelated_script = await create_script_record(
            db, user_id=user_id, novel_id=novel_id, chapter_id=chapter_ids[0], title="occupied", content="occupied"
        )
        workflow = await db.get(Workflow, workflow_ids["workflow_id"])
        workflow.script_id = unrelated_script.id
        await db.commit()
        with pytest.raises(ValueError, match="script link conflict"):
            await SeriesRunOrchestrator().execute(db, run)
        await db.refresh(workflow)
        assert workflow.script_id == unrelated_script.id

    user_id = f"storyboard-link-conflict-{uuid4()}"
    novel_id, chapter_ids = _series_source(client, user_id)
    created = client.post("/api/v1/series-runs", json=_run_payload(novel_id, chapter_ids, "storyboard-link-conflict"), headers=_headers(user_id))
    async with AsyncSessionLocal() as db:
        run = await db.get(SeriesProductionRun, created.json()["id"])
        while run.status != "episodes_building":
            transition_run(run, ("preflight", "planning", "facts_ready", "assets_ready", "episodes_building")[("created", "preflight", "planning", "facts_ready", "assets_ready").index(run.status)])
        episode = dict(run.episodes[0])
        for stage in ("workflow_ready", "script_ready"):
            additions = await build_production_stage(db, run, episode, stage)
            canonical = dict(episode.get("canonical_ids") or {})
            canonical.update(additions)
            episode.update(stage=stage, canonical_ids=canonical)
            run.episodes = [episode, *run.episodes[1:]]
            await db.commit()
        occupied = Storyboard(
            id=str(uuid4()), user_id=user_id, novel_id=novel_id,
            script_id=episode["canonical_ids"]["script_id"], title="occupied", content={}, shot_count=0, status="draft",
        )
        db.add(occupied)
        workflow = await db.get(Workflow, episode["canonical_ids"]["workflow_id"])
        workflow.storyboard_id = occupied.id
        await db.commit()
        with pytest.raises(ValueError, match="storyboard link conflict"):
            await SeriesRunOrchestrator().execute(db, run)
        await db.refresh(workflow)
        assert workflow.storyboard_id == occupied.id


def test_public_execute_builds_real_episode_rows(client: TestClient) -> None:
    user_id = f"execute-user-{uuid4()}"
    novel_id, chapter_ids = _series_source(client, user_id)
    created = client.post(
        "/api/v1/series-runs",
        json=_run_payload(novel_id, chapter_ids, "public-execute"),
        headers=_headers(user_id),
    )
    response = client.post(f"/api/v1/series-runs/{created.json()['id']}/execute", headers=_headers(user_id))
    assert response.status_code == 200
    assert response.json()["status"] == "shots_ready"
    assert all(episode["canonical_ids"]["shot_ids"] for episode in response.json()["episodes"])


@pytest.mark.asyncio
async def test_mapper_version_rejects_stale_run_writer(client: TestClient) -> None:
    user_id = f"stale-user-{uuid4()}"
    novel_id, chapter_ids = _series_source(client, user_id)
    created = client.post(
        "/api/v1/series-runs", json=_run_payload(novel_id, chapter_ids, "stale"), headers=_headers(user_id)
    )
    run_id = created.json()["id"]
    async with AsyncSessionLocal() as first, AsyncSessionLocal() as stale:
        run1 = await first.get(SeriesProductionRun, run_id)
        run2 = await stale.get(SeriesProductionRun, run_id)
        transition_run(run1, "preflight")
        await first.commit()
        transition_run(run2, "preflight")
        with pytest.raises(StaleDataError):
            await stale.commit()


@pytest.mark.asyncio
async def test_idempotency_conflict_rolls_back_and_returns_winner() -> None:
    winner = SeriesProductionRun(
        id="winner", user_id="owner", novel_id="novel", series_plan_version="v1",
        idempotency_key="key", status="created", current_episode_number=0,
        requested_stages=[], model_bindings={}, budget_policy={}, cost_summary={},
        gate_summary={}, run_metadata={}, episodes=[], version=1,
    )

    class ScalarRows:
        def all(self):
            return ["chapter"]

    class ConflictSession:
        def __init__(self):
            self.scalar_calls = 0
            self.rolled_back = False

        async def scalar(self, _statement):
            self.scalar_calls += 1
            return {1: "novel", 2: None, 3: winner}[self.scalar_calls]

        async def scalars(self, _statement):
            return ScalarRows()

        def add(self, _run):
            pass

        async def commit(self):
            raise IntegrityError("insert", {}, Exception("unique"))

        async def rollback(self):
            self.rolled_back = True

    db = ConflictSession()
    request = CreateSeriesRunRequest(
        novel_id="novel", series_plan_version="v1", idempotency_key="key",
        episodes=[{"episode_number": 1, "chapter_ids": ["chapter"], "input_hash": "hash"}],
    )
    response = await create_series_run(request, db=db, user_id="owner")
    assert response.status_code == 200
    assert db.rolled_back is True
    assert b'"id":"winner"' in response.body
