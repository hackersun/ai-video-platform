from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.core.time_utils import utc_now
from app.features.workflow_media.public import (
    WorkflowMediaBatchRequest,
    WorkflowMediaBatchResponse,
    WorkflowMediaError,
)
from app.models import (
    MediaGenerationJob,
    LLMConfig,
    LLMModel,
    LLMProvider,
    LiveCanaryProviderOperation,
    Novel,
    Script,
    Shot,
    Storyboard,
    SubtitleTrack,
    TTSJob,
    VideoJob,
    Workflow,
)
from app.models.series_production_run import SeriesProductionRun
from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.delenv("DETERMINISTIC_PROVIDER_FAKE", raising=False)
    with TestClient(app) as test_client:
        yield test_client


def _headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def test_workflow_uses_transport_neutral_dialogue_parser_owner() -> None:
    source = (Path(__file__).parents[1] / "app/api/v1/endpoints/workflow.py").read_text()
    assert "from app.services.dialogue_parser import parse_dialogue" in source
    assert "from app.api.v1.endpoints.tts import parse_dialogue" not in source


async def _seed_workflow(*, shot_count: int = 1, image_url: str | None = None) -> dict[str, object]:
    ids = {name: str(uuid4()) for name in ("user", "novel", "script", "storyboard", "workflow")}
    shot_ids = [str(uuid4()) for _ in range(shot_count)]
    async with AsyncSessionLocal() as db:
        db.add(Novel(id=ids["novel"], user_id=ids["user"], title="media contract novel"))
        db.add(Script(
            id=ids["script"], user_id=ids["user"], novel_id=ids["novel"],
            title="media contract script", content="contract",
        ))
        db.add(Storyboard(
            id=ids["storyboard"], user_id=ids["user"], novel_id=ids["novel"],
            script_id=ids["script"], title="media contract board", content={},
        ))
        for index, shot_id in enumerate(shot_ids, 1):
            db.add(Shot(
                id=shot_id, user_id=ids["user"], storyboard_id=ids["storyboard"],
                shot_number=index, duration=4, prompt=f"contract shot {index}",
                dialogue=f"line {index}", visual_description=f"visual {index}", extra_data={},
                image_url=image_url,
            ))
        db.add(Workflow(
            id=ids["workflow"], user_id=ids["user"], novel_id=ids["novel"],
            script_id=ids["script"], storyboard_id=ids["storyboard"],
            title="media contract workflow", status="active", current_step=1,
            completed_steps=[], video_job_ids=[], tts_job_ids=[], synthesis_job_ids=[], metadata_={},
        ))
        await db.commit()
    return {**ids, "shot_ids": shot_ids}


async def _seed_video_config(user_id: str) -> str:
    provider_id, model_id, config_id = (str(uuid4()) for _ in range(3))
    async with AsyncSessionLocal() as db:
        provider = await db.scalar(select(LLMProvider).where(LLMProvider.name == "volcano"))
        if provider is None:
            provider = LLMProvider(id=provider_id, name="volcano", is_active=True)
            db.add(provider)
        db.add(LLMModel(
            id=model_id, provider_id=provider.id, model_id=f"contract-video-api-{uuid4()}",
            model_name="contract video", model_type="video", capabilities=["text-to-video", "image-to-video"],
            is_active=True,
        ))
        db.add(LLMConfig(
            id=config_id, user_id=user_id, model_id=model_id, name="contract video",
            api_key="opaque-test-key", is_active=True, test_status="success", tested_at=utc_now(),
        ))
        await db.commit()
    return config_id


async def _attach_live_run(seed: dict[str, object], video_config_id: str) -> str:
    run_id = str(uuid4())
    bindings = {"video": video_config_id}
    async with AsyncSessionLocal() as db:
        for capability, model_type, capabilities in (
            ("text", "chat", ["chat"]),
            ("image", "image-generation", ["text-to-image"]),
            ("tts", "tts", ["text-to-speech"]),
        ):
            provider_id, model_id, config_id = (str(uuid4()) for _ in range(3))
            db.add(LLMProvider(id=provider_id, name=f"contract-{capability}", is_active=True))
            db.add(LLMModel(
                id=model_id, provider_id=provider_id, model_id=f"contract-{capability}-api",
                model_name=capability, model_type=model_type, capabilities=capabilities, is_active=True,
            ))
            db.add(LLMConfig(
                id=config_id, user_id=seed["user"], model_id=model_id, name=capability,
                api_key="opaque", is_active=True, test_status="success", tested_at=utc_now(),
            ))
            bindings[capability] = config_id
        run = SeriesProductionRun(
            id=run_id, user_id=seed["user"], novel_id=seed["novel"], series_plan_version="v1",
            idempotency_key=str(uuid4()), status="media_running", requested_stages=["media"],
            model_bindings={"capabilities": {key: {"config_id": value} for key, value in bindings.items()}},
            budget_policy={"live_canary": True, "max_rmb": "10.00", "estimates_rmb": {"video": "2.00"}},
            cost_summary={}, gate_summary={"media_preflight": {"ready": True, "snapshot_hash": "contract"}},
            run_metadata={}, episodes=[], version=1, created_at=utc_now() - timedelta(seconds=2),
        )
        workflow = await db.get(Workflow, seed["workflow"])
        workflow.metadata_ = {"series_run_id": run_id}
        db.add(run)
        await db.commit()
    return run_id


async def _direct_snapshot(seed: dict[str, object]) -> dict[str, object]:
    workflow_id = str(seed["workflow"])
    shot_ids = list(seed["shot_ids"])
    async with AsyncSessionLocal() as db:
        workflow = await db.get(Workflow, workflow_id)
        jobs = list((await db.scalars(select(MediaGenerationJob).where(
            MediaGenerationJob.workflow_id == workflow_id,
        ).order_by(MediaGenerationJob.shot_id))).all())
        tracks = list((await db.scalars(select(SubtitleTrack).where(
            SubtitleTrack.workflow_id == workflow_id,
        ).order_by(SubtitleTrack.shot_id))).all())
        shots = list((await db.scalars(select(Shot).where(Shot.id.in_(shot_ids)).order_by(Shot.shot_number))).all())
        return {
            "workflow": {
                "current_step": workflow.current_step,
                "completed_steps": workflow.completed_steps,
                "latest_media_batch_strategy": workflow.metadata_.get("latest_media_batch_strategy"),
                "latest_media_batch_count": workflow.metadata_.get("latest_media_batch_count"),
                "media_job_ids": workflow.metadata_.get("media_job_ids"),
                "subtitle_track_ids": workflow.metadata_.get("subtitle_track_ids"),
            },
            "jobs": [{
                "id": job.id, "shot_id": job.shot_id, "status": job.status,
                "media_type": job.media_type, "video": bool(job.output_video_url),
                "audio": bool(job.output_audio_url), "subtitle_track_id": job.subtitle_track_id,
            } for job in jobs],
            "tracks": [{"id": track.id, "shot_id": track.shot_id, "source": track.source} for track in tracks],
            "shots": [{
                "id": shot.id, "video_status": shot.video_status, "audio_status": shot.audio_status,
                "latest_media_job_id": shot.extra_data.get("latest_media_job_id"),
                "latest_subtitle_track_id": shot.extra_data.get("latest_subtitle_track_id"),
            } for shot in shots],
        }


def test_direct_batch_locks_response_and_persistence_contract(client: TestClient) -> None:
    seed = asyncio.run(_seed_workflow(shot_count=2))
    response = client.post(
        f"/api/v1/workflow/{seed['workflow']}/generate-media-batch",
        json={"strategy": "direct_av_first", "resolution": "720p"},
        headers=_headers(str(seed["user"])),
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "workflow_id": seed["workflow"], "strategy": "direct_av_first",
        "production_strategy": None, "created_count": 2,
        "video_job_ids": [], "tts_job_ids": [], "tts_voice_lock_count": 0,
        "media_job_ids": body["media_job_ids"], "subtitle_track_ids": body["subtitle_track_ids"],
        "pending_video_job_ids": [], "pending_tts_job_ids": [],
        "ready_for_concatenate": True, "message": "音视频草稿已生成",
    }
    assert len(body["media_job_ids"]) == len(set(body["media_job_ids"])) == 2
    assert len(body["subtitle_track_ids"]) == len(set(body["subtitle_track_ids"])) == 2

    snapshot = asyncio.run(_direct_snapshot(seed))
    assert snapshot["workflow"] == {
        "current_step": 7, "completed_steps": [7, 8],
        "latest_media_batch_strategy": "direct_av_first", "latest_media_batch_count": 2,
        "media_job_ids": body["media_job_ids"], "subtitle_track_ids": body["subtitle_track_ids"],
    }
    assert {item["id"] for item in snapshot["jobs"]} == set(body["media_job_ids"])
    assert all(item["status"] == "succeeded" and item["media_type"] == "audio_video" for item in snapshot["jobs"])
    assert all(item["video"] and item["audio"] and item["subtitle_track_id"] for item in snapshot["jobs"])
    assert {item["id"] for item in snapshot["tracks"]} == set(body["subtitle_track_ids"])
    assert all(item["source"] == "direct_av_model" for item in snapshot["tracks"])
    assert all(item["video_status"] == "succeeded" and item["audio_status"] == "succeeded" for item in snapshot["shots"])


def test_direct_batch_rejects_dev_placeholder_when_real_video_is_required(client: TestClient) -> None:
    seed = asyncio.run(_seed_workflow())
    response = client.post(
        f"/api/v1/workflow/{seed['workflow']}/generate-media-batch",
        json={"strategy": "direct_av_first", "require_real_video": True},
        headers=_headers(str(seed["user"])),
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "直生音视频真实供应商适配尚未配置；请改用视频+声音分步生成策略"
    }
    snapshot = asyncio.run(_direct_snapshot(seed))
    assert snapshot["jobs"] == []
    assert snapshot["tracks"] == []
    assert snapshot["workflow"] == {
        "current_step": 1,
        "completed_steps": [],
        "latest_media_batch_strategy": None,
        "latest_media_batch_count": None,
        "media_job_ids": None,
        "subtitle_track_ids": None,
    }


@pytest.mark.asyncio
async def test_required_legacy_single_reference_builds_bound_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.features.workflow_media.application import prepare_separate_media

    built: list[str] = []

    async def build_package(*args, **kwargs):
        built.append(kwargs["shot"].id)
        return {"images": [{"url": "https://media.example/reference.png"}]}

    async def bind_package(db, package, **kwargs):
        return {**package, "reference_image": package["images"][0]["url"]}

    monkeypatch.setattr(prepare_separate_media, "supports_reference_package", lambda limits: False)
    monkeypatch.setattr(prepare_separate_media, "build_reference_package", build_package)
    monkeypatch.setattr(prepare_separate_media, "bind_reference_package", bind_package)
    command = SimpleNamespace(
        context=SimpleNamespace(db=object(), user_id="user-1"),
        request=SimpleNamespace(require_provider_reference_image=True),
    )
    values = {
        "limits": {"images": 1}, "quality_references": {},
        "provider": "volcano", "model_id": "seedance-1.5",
        "video_request": SimpleNamespace(model="seedance-1.5"),
    }

    result = await prepare_separate_media._reference_for_shot(
        command, values, SimpleNamespace(id="shot-1"), {"shot_id": "shot-1"},
    )

    assert built == ["shot-1"]
    assert result["reference_image"] == "https://media.example/reference.png"


@pytest.mark.parametrize(
    ("workflow_id", "payload", "expected_status", "expected_detail"),
    [
        ("missing", {"strategy": "direct_av_first"}, 404, "工作流不存在"),
    ],
)
def test_batch_locks_owned_workflow_error(
    client: TestClient, workflow_id: str, payload: dict[str, object],
    expected_status: int, expected_detail: str,
) -> None:
    response = client.post(
        f"/api/v1/workflow/{workflow_id}/generate-media-batch", json=payload,
        headers=_headers(str(uuid4())),
    )
    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}


def test_batch_locks_validation_and_missing_shot_errors(client: TestClient) -> None:
    seed = asyncio.run(_seed_workflow(shot_count=0))
    url = f"/api/v1/workflow/{seed['workflow']}/generate-media-batch"
    headers = _headers(str(seed["user"]))
    invalid = client.post(url, json={"strategy": "unknown"}, headers=headers)
    assert invalid.status_code == 422
    assert invalid.json() == {"detail": "当前仅支持 direct_av_first 或 separate_video_tts 策略"}
    missing = client.post(url, json={"strategy": "direct_av_first"}, headers=headers)
    assert missing.status_code == 422
    assert missing.json() == {"detail": "没有可生成的镜头"}


def test_direct_batch_rolls_back_all_rows_when_second_shot_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = asyncio.run(_seed_workflow(shot_count=2))
    from app.features.workflow_media.application import direct_av

    calls = 0

    def _fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected media failure")
        return None

    monkeypatch.setenv("DETERMINISTIC_PROVIDER_FAKE", "1")
    monkeypatch.setattr(direct_av, "deterministic_media_provider_artifacts", _fail_second)
    with pytest.raises(RuntimeError, match="injected media failure"):
        client.post(
            f"/api/v1/workflow/{seed['workflow']}/generate-media-batch",
            json={"strategy": "direct_av_first"}, headers=_headers(str(seed["user"])),
        )

    async def _counts() -> tuple[int, int, int, dict[str, object]]:
        async with AsyncSessionLocal() as db:
            jobs = await db.scalar(select(func.count()).select_from(MediaGenerationJob).where(
                MediaGenerationJob.workflow_id == seed["workflow"],
            ))
            tracks = await db.scalar(select(func.count()).select_from(SubtitleTrack).where(
                SubtitleTrack.workflow_id == seed["workflow"],
            ))
            changed = await db.scalar(select(func.count()).select_from(Shot).where(
                Shot.id.in_(seed["shot_ids"]), Shot.video_status == "succeeded",
            ))
            workflow = await db.get(Workflow, seed["workflow"])
            return jobs, tracks, changed, workflow.metadata_

    assert asyncio.run(_counts()) == (0, 0, 0, {})


@pytest.mark.parametrize(("audio_mode", "expected_tts"), [("model_audio", 1), ("none", 0)])
def test_separate_batch_locks_completed_and_no_tts_contract(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, audio_mode: str, expected_tts: int,
) -> None:
    seed = asyncio.run(_seed_workflow())
    monkeypatch.setenv("DETERMINISTIC_PROVIDER_FAKE", "1")
    response = client.post(
        f"/api/v1/workflow/{seed['workflow']}/generate-media-batch",
        json={"strategy": "separate_video_tts", "audio_mode": audio_mode},
        headers=_headers(str(seed["user"])),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created_count"] == 1
    assert len(body["video_job_ids"]) == 1
    assert len(body["tts_job_ids"]) == expected_tts
    assert body["media_job_ids"] == []
    assert body["pending_video_job_ids"] == []
    assert body["pending_tts_job_ids"] == []
    assert body["ready_for_concatenate"] is True
    assert body["message"] == "视频和声音任务已创建"

    async def _snapshot() -> tuple[list[tuple[str, str]], list[tuple[str, str]], dict[str, object]]:
        async with AsyncSessionLocal() as db:
            videos = list((await db.scalars(select(VideoJob).where(
                VideoJob.workflow_id == seed["workflow"],
            ))).all())
            voices = list((await db.scalars(select(TTSJob).where(
                TTSJob.workflow_id == seed["workflow"],
            ))).all())
            workflow = await db.get(Workflow, seed["workflow"])
            return (
                [(job.id, job.status) for job in videos],
                [(job.id, job.status) for job in voices],
                workflow.metadata_,
            )

    videos, voices, metadata = asyncio.run(_snapshot())
    assert videos == [(body["video_job_ids"][0], "succeeded")]
    assert voices == [(job_id, "succeeded") for job_id in body["tts_job_ids"]]
    assert metadata["latest_video_job_ids"] == body["video_job_ids"]
    assert metadata["latest_tts_job_ids"] == body["tts_job_ids"]


def test_separate_batch_locks_prompt_fallback_and_local_reference_omission(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = asyncio.run(_seed_workflow(image_url="/static/generated/contract-local.png"))
    config_id = asyncio.run(_seed_video_config(str(seed["user"])))
    calls: list[dict[str, object]] = []

    class _Tasks:
        @staticmethod
        def create(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("InputTextSensitiveContentDetected")

            class _Result:
                id = "contract-provider-task"

            return _Result()

    class _Client:
        class content_generation:
            tasks = _Tasks()

    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", lambda *_args: _Client())
    response = client.post(
        f"/api/v1/workflow/{seed['workflow']}/generate-media-batch",
        json={
            "strategy": "separate_video_tts", "audio_mode": "none",
            "model_config_id": config_id,
        },
        headers=_headers(str(seed["user"])),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(calls) == 2
    assert all(item["type"] != "image_url" for item in calls[0]["content"])
    assert "Anime cinematic shot" in calls[1]["content"][-1]["text"]

    async def _job() -> VideoJob:
        async with AsyncSessionLocal() as db:
            return await db.get(VideoJob, body["video_job_ids"][0])

    job = asyncio.run(_job())
    parameters = job.extra_data["prompt_parameters"]
    assert job.image_url == "/static/generated/contract-local.png"
    assert parameters["image_url_sent"] is False
    assert "公网" in parameters["image_url_omitted_reason"]
    assert parameters["provider_prompt_safety_retry"] is True
    assert job.task_id == "contract-provider-task"


def test_live_canary_zero_retries_stops_after_sensitive_prompt_rejection(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = asyncio.run(_seed_workflow())
    config_id = asyncio.run(_seed_video_config(str(seed["user"])))
    calls: list[dict[str, object]] = []

    class _Tasks:
        @staticmethod
        def create(**kwargs):
            calls.append(kwargs)
            raise RuntimeError("InputTextSensitiveContentDetected")

    class _Client:
        class content_generation:
            tasks = _Tasks()

    monkeypatch.setenv("LIVE_CANARY_PROVIDER_RETRIES", "0")
    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", lambda *_args: _Client())
    response = client.post(
        f"/api/v1/workflow/{seed['workflow']}/generate-media-batch",
        json={"strategy": "separate_video_tts", "audio_mode": "none", "model_config_id": config_id},
        headers=_headers(str(seed["user"])),
    )
    assert response.status_code == 422
    assert len(calls) == 1


def test_live_provider_unknown_submission_precommits_budget_without_job(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = asyncio.run(_seed_workflow())
    config_id = asyncio.run(_seed_video_config(str(seed["user"])))
    run_id = asyncio.run(_attach_live_run(seed, config_id))

    class _Tasks:
        @staticmethod
        def create(**_kwargs):
            raise RuntimeError("connection outcome unknown")

    class _Client:
        class content_generation:
            tasks = _Tasks()

    async def _ready(*_args, **_kwargs):
        return {"ready": True, "snapshot_hash": "contract", "issues": []}

    monkeypatch.setattr("app.features.video_generation.public.create_ark_client", lambda *_args: _Client())
    monkeypatch.setattr("app.features.workflow_media.application.load_context.evaluate_media_preflight", _ready)
    with pytest.raises(RuntimeError, match="outcome unknown"):
        client.post(
            f"/api/v1/workflow/{seed['workflow']}/generate-media-batch",
            json={"strategy": "separate_video_tts", "audio_mode": "none", "model_config_id": config_id},
            headers=_headers(str(seed["user"])),
        )

    async def _snapshot() -> tuple[int, str, str, int]:
        async with AsyncSessionLocal() as db:
            run = await db.get(SeriesProductionRun, run_id)
            operation = await db.scalar(select(LiveCanaryProviderOperation).where(
                LiveCanaryProviderOperation.run_id == run_id,
            ))
            jobs = await db.scalar(select(func.count()).select_from(VideoJob).where(
                VideoJob.workflow_id == seed["workflow"],
            ))
            return len(run.cost_summary["reservations"]), run.cost_summary["reserved_rmb"], operation.status, jobs

    assert asyncio.run(_snapshot()) == (1, "2.00", "reserved", 0)


@pytest.mark.asyncio
async def test_series_workflow_preflight_uses_the_requested_native_audio_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.features.workflow_media.application.load_context as load_context

    observed: list[bool] = []
    series_run = SimpleNamespace(
        status="media_running",
        gate_summary={"media_preflight": {"ready": True, "snapshot_hash": "native-snapshot"}},
    )

    async def get_series_run(*_args, **_kwargs):
        return series_run

    async def evaluate(*_args, native_audio: bool = False, **_kwargs):
        observed.append(native_audio)
        return {"ready": True, "snapshot_hash": "native-snapshot", "issues": []}

    monkeypatch.setattr(load_context.repository, "get_series_run", get_series_run)
    monkeypatch.setattr(load_context, "evaluate_media_preflight", evaluate)

    result = await load_context._validate_series_run(
        SimpleNamespace(), "user-1",
        SimpleNamespace(metadata_={"series_run_id": "run-1"}, novel_id="novel-1"),
        native_audio=True,
    )

    assert result is series_run
    assert observed == [True]


def test_openapi_locks_workflow_media_schema_contract(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/workflow/{workflow_id}/generate-media-batch"]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/WorkflowMediaBatchRequest"
    }
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/WorkflowMediaBatchResponse"
    }
    request = schema["components"]["schemas"]["WorkflowMediaBatchRequest"]
    response = schema["components"]["schemas"]["WorkflowMediaBatchResponse"]
    assert list(request["properties"]) == [
        "production_strategy", "strategy", "shot_ids", "duration_seconds", "resolution",
        "subtitle_mode", "audio_mode", "native_audio", "model_config_id", "audio_model_config_id", "voice_model",
        "speed", "story_bible_id", "use_story_bible_voice", "require_real_video",
        "require_provider_reference_image",
    ]
    assert request["properties"]["strategy"]["default"] == "direct_av_first"
    duration = request["properties"]["duration_seconds"]["anyOf"][0]
    assert duration["maximum"] == 60
    assert duration["minimum"] == 1
    assert response["required"] == [
        "workflow_id", "strategy", "created_count", "media_job_ids", "subtitle_track_ids", "message",
    ]

    baseline_path = Path(__file__).parent / "fixtures" / "workflow_media_openapi_baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    payload = {
        "request": request,
        "response": response,
        "operation": {field: operation[field] for field in baseline["payload"]["operation_fields"]},
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(canonical.encode()).hexdigest() == baseline["sha256"]


def test_public_contract_is_transport_neutral_and_preserves_error_payload() -> None:
    import app.api.v1.endpoints.workflow as workflow_endpoint

    assert workflow_endpoint.WorkflowMediaBatchRequest is WorkflowMediaBatchRequest
    assert workflow_endpoint.WorkflowMediaBatchResponse is WorkflowMediaBatchResponse
    detail = {"code": "media_blocked", "issues": [{"code": "stale"}]}
    error = WorkflowMediaError(409, detail)
    assert error.status_code == 409
    assert error.detail is detail


def test_generic_character_ref_does_not_guess_between_multiple_novel_characters() -> None:
    from types import SimpleNamespace
    from app.features.video_generation.public import lookup_character_by_name

    characters = [
        SimpleNamespace(id="one", name="沈砚", novel_id="novel", tags=[]),
        SimpleNamespace(id="two", name="林澈", novel_id="novel", tags=[]),
    ]
    assert lookup_character_by_name(characters, "主角", "novel", None) is None
