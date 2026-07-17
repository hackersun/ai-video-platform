from types import SimpleNamespace

import pytest

from app.features.workflow_media.adapters import tts_submission
from app.features.workflow_media.errors import WorkflowMediaError
from app.services.minimax_errors import MiniMaxProviderRejected


def _command() -> SimpleNamespace:
    return SimpleNamespace(
        context=SimpleNamespace(
            db=object(), series_run=object(), workflow=SimpleNamespace(id="workflow-1"),
        ),
        shot=SimpleNamespace(id="shot-1"),
    )


@pytest.mark.asyncio
async def test_explicit_minimax_tts_rejection_releases_reservation_and_returns_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, bool]] = []

    async def prepare(*args, **kwargs):
        return "tts-reservation"

    async def reject(*args, **kwargs):
        raise MiniMaxProviderRejected("TTS", 2054, "voice id not exist")

    async def finish(db, run, reservation_id, *, submission_failed):
        calls.append((reservation_id, submission_failed))

    monkeypatch.setattr(tts_submission, "prepare_live_provider_attempt", prepare)
    monkeypatch.setattr(tts_submission, "_call_provider", reject)
    monkeypatch.setattr(tts_submission, "finish_live_provider_attempt", finish, raising=False)

    with pytest.raises(WorkflowMediaError) as caught:
        await tts_submission._live_provider_result(
            _command(), "tts-job-1", "测试对白", "invalid-voice", 1.0,
        )

    assert caught.value.status_code == 422
    assert caught.value.detail == {
        "code": "tts_provider_rejected",
        "title": "声音生成未受理",
        "message": "当前声线无法用于所选 MiniMax 声音模型，请修改声线并重新测试后，仅重试声音阶段。",
        "stage": "tts_submission",
        "provider_status_code": "2054",
        "operation_status": "confirmed_rejected_before_acceptance",
        "cost_state": "released",
        "safe_retry": True,
        "retry_requires_confirmation": True,
        "retry_scope": "failed_stage",
        "actions": [
            {"code": "edit_voice", "label": "修改声线"},
            {"code": "retest_config", "label": "重新测试声音配置"},
            {"code": "retry_failed_stage", "label": "仅重试声音阶段"},
        ],
    }
    assert calls == [("tts-reservation", True)]


@pytest.mark.asyncio
async def test_unknown_tts_exception_retains_reservation_for_manual_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    released = False

    async def prepare(*args, **kwargs):
        return "tts-reservation"

    async def unknown(*args, **kwargs):
        raise RuntimeError("connection outcome unknown")

    async def finish(*args, **kwargs):
        nonlocal released
        released = True

    monkeypatch.setattr(tts_submission, "prepare_live_provider_attempt", prepare)
    monkeypatch.setattr(tts_submission, "_call_provider", unknown)
    monkeypatch.setattr(tts_submission, "finish_live_provider_attempt", finish, raising=False)

    with pytest.raises(RuntimeError, match="outcome unknown"):
        await tts_submission._live_provider_result(
            _command(), "tts-job-1", "测试对白", "voice-1", 1.0,
        )

    assert released is False
