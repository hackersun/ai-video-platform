from __future__ import annotations

import pytest
from dataclasses import replace
from types import SimpleNamespace
from sqlalchemy.exc import StatementError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.domain import ModelProfileContract, ResolvedModelBinding
from app.features.model_drivers.public import DriverContext
from app.features.model_config.snapshots import (
    ExecutionSnapshotCommand,
    UnsafeSnapshotError,
    create_execution_snapshot,
    load_execution_snapshot,
    sanitize_snapshot_params,
)
from tests.model_binding_test_support import db_session as db_session


def _binding() -> ResolvedModelBinding:
    return ResolvedModelBinding(
        task="shot_video",
        capability="video_generation",
        profile=ModelProfileContract(
            profile_version_id="profile-v1",
            provider_id="provider-v1",
            api_model_id="seedance-v1",
            driver_key="volcano_ark_video_v3",
            capabilities=frozenset({"video_generation"}),
            input_contract={}, output_contract={}, parameter_schema={}, default_params={},
            limits={}, pricing={}, prompt_profile_key=None, contract_version="seedance.v1",
        ),
        connection_id="connection-v1",
        binding_version=3,
        source_scope="series",
        binding_id="binding-v1",
    )


@pytest.mark.asyncio
async def test_execution_snapshot_persists_resolved_immutable_model_evidence(
    db_session: AsyncSession,
) -> None:
    snapshot = await create_execution_snapshot(
        db_session,
        ExecutionSnapshotCommand(
            user_id="user-1", run_id="run-1", job_id="job-1", task="shot_video",
            capability="video_generation", binding=_binding(), recipe_version_id="recipe-v1",
            prompt_profile_version_id="prompt-v1", sanitized_params={
                "duration": 8, "resolution": "720p", "native_audio": True,
                "reference_image_count": 2, "seed": 42,
            },
        ),
    )
    await db_session.commit()

    reloaded = await load_execution_snapshot(db_session, snapshot.id, user_id="user-1")

    assert reloaded is not None
    assert reloaded.profile_version_id == "profile-v1"
    assert reloaded.binding_id == "binding-v1"
    assert reloaded.recipe_version_id == "recipe-v1"
    assert reloaded.sanitized_params == {
        "duration": 8,
        "native_audio": True,
        "reference_image_count": 2,
        "resolution": "720p",
        "seed": 42,
        "resolved_model": {
            "api_model_id": "seedance-v1",
            "contract_version": "seedance.v1",
            "driver_key": "volcano_ark_video_v3",
            "provider_id": "provider-v1",
            "source_scope": "series",
        },
    }
    assert snapshot.checksum == reloaded.checksum


def test_execution_snapshot_rejects_secrets_and_prompt_content() -> None:
    with pytest.raises(UnsafeSnapshotError, match="api_key"):
        sanitize_snapshot_params({"duration": 8, "api_key": "secret"})
    with pytest.raises(UnsafeSnapshotError, match="prompt"):
        sanitize_snapshot_params({"prompt": "private full prompt"})


@pytest.mark.asyncio
async def test_driver_evidence_never_keeps_raw_provider_exception_text() -> None:
    from app.features.model_drivers.domain import DriverExecutionError
    from app.features.model_drivers.executor import _execute_driver_operation

    async def reject():
        raise RuntimeError("provider rejected private prompt: chapter ending secret")

    with pytest.raises(DriverExecutionError) as error:
        await _execute_driver_operation(
            "generation", reject,
            DriverContext(profile=_binding().profile, driver_key="volcano_ark_video_v3", connection_id="conn"),
        )

    assert error.value.sanitized_evidence == {
        "operation": "generation",
        "provider_error_class": "RuntimeError",
        "provider_error_summary": "provider_generation_failed",
    }


@pytest.mark.parametrize(
    "params",
    [
        {"duration": {"prompt": "private full prompt"}},
        {"output_contract": {"Authorization": "Bearer opaque-secret"}},
        {"voice_id": "sk-sensitive-credential"},
    ],
)
def test_execution_snapshot_rejects_nested_or_credential_like_allowlisted_values(params) -> None:
    with pytest.raises(UnsafeSnapshotError):
        sanitize_snapshot_params(params)


@pytest.mark.asyncio
async def test_workflow_video_driver_receives_persisted_snapshot_id(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.features.workflow_media.adapters import video_submission

    binding = replace(_binding(), profile=replace(_binding().profile, driver_key="test_video_driver"))
    generation = SimpleNamespace(
        binding=binding,
        profile=binding.profile,
        recipe_version_id="recipe-v1",
        prompt_profile_version_id="prompt-v1",
        driver_context=DriverContext(
            profile=binding.profile, driver_key=binding.profile.driver_key,
            connection_id=binding.connection_id,
        ),
    )
    command = SimpleNamespace(
        runtime=SimpleNamespace(api_key="test-key", selected_model={"generation_context": generation}),
        prepared=SimpleNamespace(
            video_request=SimpleNamespace(duration=8), video_seed=42,
            final_video_prompt="private prompt must not be saved", dialogue_sync_contract=None,
        ),
        request=SimpleNamespace(resolution="720p", native_audio=True),
        context=SimpleNamespace(db=db_session, user_id="user-1", series_run=None),
    )
    captured = {}

    async def reserve(*_args, **_kwargs):
        return None

    async def execute(_registry, _driver_command, driver_context):
        captured["snapshot_id"] = driver_context.execution_snapshot_id
        return SimpleNamespace(provider_task_id="provider-task")

    monkeypatch.setattr(video_submission, "_reserve", reserve)
    monkeypatch.setattr(video_submission, "execute_generation", execute)
    content = {"content": [], "metadata": {"image_count": 1}}

    snapshot_id = await video_submission._create_execution_snapshot(command, content, "job-1")
    task_id, _reservation, _content = await video_submission._submit_live(
        command, {}, content, "job-1", snapshot_id,
    )

    stored = await load_execution_snapshot(db_session, snapshot_id, user_id="user-1")
    assert task_id == "provider-task"
    assert captured["snapshot_id"] == snapshot_id
    assert stored is not None and "private prompt" not in repr(stored.sanitized_params)


@pytest.mark.asyncio
async def test_workflow_default_ark_video_uses_snapshot_bound_driver(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.features.workflow_media.adapters import video_submission

    binding = _binding()
    generation = SimpleNamespace(
        binding=binding, profile=binding.profile,
        driver_context=DriverContext(
            profile=binding.profile, driver_key="volcano_ark_video_v3",
            connection_id=binding.connection_id,
        ),
    )
    command = SimpleNamespace(
        runtime=SimpleNamespace(api_key="test-key", selected_model={"generation_context": generation}),
        prepared=SimpleNamespace(
            video_request=SimpleNamespace(duration=8), video_seed=None,
            final_video_prompt="private prompt", dialogue_sync_contract=None,
        ),
        request=SimpleNamespace(resolution="720p", native_audio=False),
        context=SimpleNamespace(db=db_session, user_id="user-1", series_run=None),
    )
    captured = {}

    async def reserve(*_args, **_kwargs):
        return None

    async def execute(_registry, _driver_command, driver_context):
        captured["snapshot_id"] = driver_context.execution_snapshot_id
        captured["prompt"] = _driver_command.prompt
        return SimpleNamespace(provider_task_id="ark-task")

    monkeypatch.setattr(video_submission, "_reserve", reserve)
    monkeypatch.setattr(video_submission, "execute_generation", execute)
    snapshot_id = await video_submission._create_execution_snapshot(
        command, {"content": [], "metadata": {}}, "job-ark",
    )
    task_id, _reservation, _content = await video_submission._submit_live(
        command, {"provider_prompt": "provider-safe prompt"}, {"content": []}, "job-ark", snapshot_id,
    )

    assert task_id == "ark-task"
    assert captured["snapshot_id"] == snapshot_id
    assert captured["prompt"] == "provider-safe prompt"


@pytest.mark.asyncio
async def test_workflow_ark_prompt_retry_keeps_execution_snapshot_context(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.features.model_drivers.public import DriverExecutionError
    from app.features.workflow_media.adapters import video_submission

    binding = _binding()
    generation = SimpleNamespace(
        binding=binding, profile=binding.profile,
        driver_context=DriverContext(
            profile=binding.profile, driver_key="volcano_ark_video_v3",
            connection_id=binding.connection_id,
        ),
    )
    command = SimpleNamespace(
        runtime=SimpleNamespace(api_key="test-key", selected_model={"generation_context": generation}),
        prepared=SimpleNamespace(
            video_request=SimpleNamespace(duration=8), video_seed=None,
            final_video_prompt="private prompt", dialogue_sync_contract=None,
            reference_package=None,
        ),
        request=SimpleNamespace(resolution="720p", native_audio=False),
        context=SimpleNamespace(db=db_session, user_id="user-1", series_run=None),
    )
    captured = []

    async def reserve(*_args, **_kwargs):
        return None

    async def execute(_registry, _driver_command, driver_context):
        captured.append(driver_context.execution_snapshot_id)
        if len(captured) == 1:
            raise DriverExecutionError(
                "generation", {}, cause=RuntimeError("InputTextSensitiveContentDetected"),
            )
        return SimpleNamespace(provider_task_id="ark-retry-task")

    monkeypatch.setattr(video_submission, "_reserve", reserve)
    monkeypatch.setattr(video_submission, "execute_generation", execute)
    monkeypatch.setattr(video_submission.video_kernel, "create_ark_client", lambda *_args: object())
    monkeypatch.setattr(
        video_submission, "_build_provider_content",
        lambda *_args: {"content": [], "metadata": {}},
    )
    monkeypatch.setattr(video_submission, "_record_reference_metadata", lambda *_args: None)
    snapshot_id = await video_submission._create_execution_snapshot(
        command, {"content": [], "metadata": {}}, "job-ark-retry",
    )

    task_id, _reservation, _content = await video_submission._submit_live(
        command,
        {"provider_image_url": None, "provider_prompt": "private prompt", "prompt_parameters": {}, "extra_data": {}},
        {"content": []}, "job-ark-retry", snapshot_id,
    )

    assert task_id == "ark-retry-task"
    assert captured == [snapshot_id, snapshot_id]


@pytest.mark.asyncio
async def test_workflow_ark_prompt_retry_maps_wrapped_provider_safety_error(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.features.model_drivers.public import DriverExecutionError
    from app.features.workflow_media.adapters import video_submission
    from app.features.workflow_media.errors import WorkflowMediaError

    binding = _binding()
    generation = SimpleNamespace(
        binding=binding, profile=binding.profile,
        driver_context=DriverContext(
            profile=binding.profile, driver_key="volcano_ark_video_v3",
            connection_id=binding.connection_id,
        ),
    )
    command = SimpleNamespace(
        runtime=SimpleNamespace(api_key="test-key", selected_model={"generation_context": generation}),
        prepared=SimpleNamespace(
            video_request=SimpleNamespace(duration=8), video_seed=None,
            final_video_prompt="private prompt", dialogue_sync_contract=None,
            reference_package=None,
        ),
        request=SimpleNamespace(resolution="720p", native_audio=False),
        context=SimpleNamespace(db=db_session, user_id="user-1", series_run=None),
    )

    async def reserve(*_args, **_kwargs):
        return None

    async def execute(*_args, **_kwargs):
        raise DriverExecutionError(
            "generation", {}, cause=RuntimeError("InputTextSensitiveContentDetected"),
        )

    monkeypatch.setattr(video_submission, "_reserve", reserve)
    monkeypatch.setattr(video_submission, "execute_generation", execute)
    monkeypatch.setattr(video_submission.video_kernel, "create_ark_client", lambda *_args: object())
    monkeypatch.setattr(
        video_submission, "_build_provider_content",
        lambda *_args: {"content": [], "metadata": {}},
    )

    with pytest.raises(WorkflowMediaError) as error:
        await video_submission._submit_live(
            command,
            {"provider_image_url": None, "provider_prompt": "private prompt", "prompt_parameters": {}, "extra_data": {}},
            {"content": []}, "job-ark-retry", "snapshot-ark-retry",
        )

    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_direct_video_driver_receives_persisted_snapshot_id(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.features.video_generation.application import driver_submission

    binding = replace(_binding(), profile=replace(_binding().profile, driver_key="test_video_driver"))
    generation = SimpleNamespace(
        binding=binding,
        profile=binding.profile,
        recipe_version_id="recipe-v1",
        prompt_profile_version_id="prompt-v1",
        driver_context=DriverContext(
            profile=binding.profile, driver_key=binding.profile.driver_key,
            connection_id=binding.connection_id,
        ),
    )
    captured = {}

    async def execute(_registry, _command, driver_context):
        captured["snapshot_id"] = driver_context.execution_snapshot_id
        return SimpleNamespace(provider_task_id="provider-task")

    monkeypatch.setattr(driver_submission, "execute_generation", execute)
    create_kwargs = {"content": [], "duration": 8, "resolution": "720p", "seed": 42}
    snapshot_id = await driver_submission.create_bound_video_execution_snapshot(
        db_session, user_id="user-1", generation_context=generation,
        job_id="job-1", create_kwargs=create_kwargs,
    )
    result = await driver_submission.submit_bound_video_task(
        generation, "private prompt must not be saved", create_kwargs, object(), snapshot_id,
    )

    assert result.id == "provider-task"
    assert captured["snapshot_id"] == snapshot_id
    snapshot = await load_execution_snapshot(db_session, snapshot_id, user_id="user-1")
    assert snapshot.recipe_version_id == "recipe-v1"
    assert snapshot.prompt_profile_version_id == "prompt-v1"


@pytest.mark.asyncio
async def test_image_driver_receives_snapshot_and_returns_safe_trace_id(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.services import image_generation_pipeline

    binding = replace(_binding(), profile=replace(_binding().profile, driver_key="test_image_driver"))
    generation = SimpleNamespace(
        binding=binding, profile=binding.profile,
        recipe_version_id="recipe-v1", prompt_profile_version_id="prompt-v1",
        driver_context=DriverContext(
            profile=binding.profile, driver_key=binding.profile.driver_key,
            connection_id=binding.connection_id,
        ),
    )
    captured = {}

    async def execute(_registry, _command, driver_context):
        captured["snapshot_id"] = driver_context.execution_snapshot_id
        return SimpleNamespace(output={"image_urls": ["https://example.test/image.png"]}, provider_task_id=None)

    monkeypatch.setattr(image_generation_pipeline.driver_kernel, "execute_generation", execute)
    result = await image_generation_pipeline.call_image_generation_provider(
        object(), provider_name="ignored", model_id="ignored", prompt="private prompt",
        generation_context=generation, db=db_session, user_id="user-1", job_id="image-job-1",
    )

    assert result["execution_snapshot_id"] == captured["snapshot_id"]
    snapshot = await load_execution_snapshot(db_session, captured["snapshot_id"], user_id="user-1")
    assert snapshot is not None and snapshot.job_id == "image-job-1"


@pytest.mark.asyncio
async def test_text_adapter_returns_execution_snapshot_trace_id() -> None:
    from app.features.model_drivers.text_execution import TextGenerationServiceAdapter

    class Service:
        async def chat_completion(self, **_kwargs):
            return {"choices": [{"message": {"content": "safe output"}}]}

    response = await TextGenerationServiceAdapter(
        Service(), execution_snapshot_id="snapshot-text-1",
    ).safe_chat_completion(
        model="text-model", messages=[{"role": "user", "content": "private prompt"}],
    )

    assert response["execution_snapshot_id"] == "snapshot-text-1"


@pytest.mark.asyncio
async def test_bound_text_service_creates_distinct_snapshot_for_each_chat_call(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.features.model_drivers import text_execution

    binding = replace(_binding(), capability="text_generation", task="story_generation")
    context = SimpleNamespace(
        binding=binding, recipe_version_id="recipe-v1", prompt_profile_version_id="prompt-v1", base_url=None,
        driver_context=DriverContext(
            profile=binding.profile, driver_key="legacy_text_v1", connection_id=binding.connection_id,
            connection_params={"provider_name": "volcano"},
        ),
        profile=binding.profile,
    )
    async def resolve(*_args, **_kwargs):
        return context

    class Service:
        async def safe_chat_completion(self, **_kwargs):
            return {"choices": [{"message": {"content": "safe output"}}]}

    def create(_context, *, snapshot_factory):
        return text_execution.TextGenerationServiceAdapter(Service(), snapshot_factory=snapshot_factory)

    monkeypatch.setattr(text_execution, "resolve_generation_context", resolve)
    monkeypatch.setattr(text_execution, "create_text_generation_service_from_context", create)
    service, _provider, _model, _base_url = await text_execution.get_user_text_generation_service(
        db_session, "user-1",
    )

    first = await service.safe_chat_completion(model="model", messages=[])
    second = await service.safe_chat_completion(model="model", messages=[])
    first_snapshot = await load_execution_snapshot(db_session, first["execution_snapshot_id"], user_id="user-1")
    second_snapshot = await load_execution_snapshot(db_session, second["execution_snapshot_id"], user_id="user-1")

    assert first["execution_snapshot_id"] != second["execution_snapshot_id"]
    assert first_snapshot.recipe_version_id == second_snapshot.recipe_version_id == "recipe-v1"
    assert first_snapshot.prompt_profile_version_id == second_snapshot.prompt_profile_version_id == "prompt-v1"


@pytest.mark.asyncio
async def test_generate_novel_with_plan_persists_one_snapshot_per_real_chat_request(
    db_session: AsyncSession,
) -> None:
    from sqlalchemy import select

    from app.features.model_drivers import text_execution
    from app.models.model_center import ModelExecutionSnapshot

    binding = replace(_binding(), capability="text_generation", task="story_generation")
    context = SimpleNamespace(
        binding=binding, recipe_version_id="recipe-v1", prompt_profile_version_id="prompt-v1",
    )

    class DashScopeLikeService:
        def __init__(self):
            self._responses = iter(("章节规划", "小说正文"))

        async def chat_completion(self, **_kwargs):
            return {"choices": [{"message": {"content": next(self._responses)}}]}

    adapter = text_execution.TextGenerationServiceAdapter(
        DashScopeLikeService(),
        snapshot_factory=text_execution._text_snapshot_factory(db_session, "user-1", context),
    )
    result = await adapter.generate_novel_with_plan("主题", "dashscope-model")
    snapshots = list((await db_session.scalars(select(ModelExecutionSnapshot).where(
        ModelExecutionSnapshot.user_id == "user-1",
        ModelExecutionSnapshot.task == "story_generation",
    ))).all())

    assert result["plan"] == "章节规划"
    assert result["content"] == "小说正文"
    assert len({snapshot.id for snapshot in snapshots}) == 2
    assert {snapshot.recipe_version_id for snapshot in snapshots} == {"recipe-v1"}
    assert {snapshot.prompt_profile_version_id for snapshot in snapshots} == {"prompt-v1"}


@pytest.mark.asyncio
async def test_execution_snapshot_rows_are_append_only(db_session: AsyncSession) -> None:
    snapshot = await create_execution_snapshot(
        db_session,
        ExecutionSnapshotCommand(
            user_id="user-1", run_id=None, job_id="job-1", task="shot_video",
            capability="video_generation", binding=_binding(), sanitized_params={"duration": 8},
        ),
    )
    await db_session.commit()

    snapshot.sanitized_params = {"duration": 10}
    with pytest.raises((ValueError, StatementError), match="append-only"):
        await db_session.commit()
