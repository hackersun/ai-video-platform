from __future__ import annotations

import pytest
from dataclasses import replace
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
async def test_workflow_video_driver_receives_persisted_snapshot_id(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.features.workflow_media.adapters import video_submission

    binding = replace(_binding(), profile=replace(_binding().profile, driver_key="test_video_driver"))
    generation = SimpleNamespace(
        binding=binding,
        profile=binding.profile,
        driver_context=DriverContext(
            profile=binding.profile, driver_key=binding.profile.driver_key,
            connection_id=binding.connection_id,
        ),
    )
    command = SimpleNamespace(
        runtime=SimpleNamespace(selected_model={"generation_context": generation}),
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
async def test_direct_video_driver_receives_persisted_snapshot_id(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.features.video_generation.application import driver_submission

    binding = replace(_binding(), profile=replace(_binding().profile, driver_key="test_video_driver"))
    generation = SimpleNamespace(
        binding=binding,
        profile=binding.profile,
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
