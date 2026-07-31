from types import SimpleNamespace

import pytest

from app.features.workflow_media.application import voice_locks


@pytest.mark.asyncio
async def test_native_audio_final_quality_requires_assets_but_not_tts_voice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shot = SimpleNamespace(
        id="shot-native-audio",
        shot_number=1,
        dialogue="苏澜：北塔熄灭了。",
        character_refs=[],
        extra_data={
            "production_context": {
                "asset_version_locks": [
                    {"asset_id": "reference-board", "version": 1},
                ],
            },
        },
    )

    async def no_tts_voice_lock(_command):
        return None

    monkeypatch.setattr(
        voice_locks, "_voice_lock_snapshot_for_workflow_shot", no_tts_voice_lock,
    )

    snapshots = await voice_locks.build_final_quality_lock_snapshots(
        voice_locks.FinalQualityLockCommand(
            db=SimpleNamespace(),
            user_id="user-native-audio",
            workflow=SimpleNamespace(id="workflow-native-audio"),
            shots=[shot],
            require_voice_locks=False,
        ),
    )

    assert snapshots[shot.id]["asset_version_locks"] == [
        {"asset_id": "reference-board", "version": 1},
    ]
    assert snapshots[shot.id]["voice_lock_snapshot"] is None


@pytest.mark.asyncio
async def test_tts_final_quality_still_requires_dialogue_voice_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shot = SimpleNamespace(
        id="shot-tts",
        shot_number=2,
        dialogue="苏澜：守住星灯。",
        character_refs=[],
        extra_data={
            "production_context": {
                "asset_version_locks": [
                    {"asset_id": "reference-board", "version": 1},
                ],
            },
        },
    )

    async def no_tts_voice_lock(_command):
        return None

    monkeypatch.setattr(
        voice_locks, "_voice_lock_snapshot_for_workflow_shot", no_tts_voice_lock,
    )

    with pytest.raises(voice_locks.WorkflowMediaError) as caught:
        await voice_locks.build_final_quality_lock_snapshots(
            voice_locks.FinalQualityLockCommand(
                db=SimpleNamespace(),
                user_id="user-tts",
                workflow=SimpleNamespace(id="workflow-tts"),
                shots=[shot],
            ),
        )

    assert caught.value.detail["code"] == "final_quality_locks_missing"
    assert caught.value.detail["missing_voices"][0]["shot_id"] == shot.id
