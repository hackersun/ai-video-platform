from types import SimpleNamespace

import pytest

from app.features.series_anchor_generation.generation import _shot_input_fingerprint
from app.features.workflow_media.application.live_provider_attempts import (
    resolve_live_series_run_for_shot,
)
from app.services.shot_image_delivery import (
    is_live_ready_shot_image,
    persist_shot_image_publicly,
    should_refresh_shot_entity_refs,
    should_use_dev_shot_image_fallback,
)


def test_shot_input_fingerprint_ignores_generated_first_frame() -> None:
    shot = SimpleNamespace(
        id="shot-1", prompt="prompt", visual_description="visual",
        dialogue="line", image_url=None, extra_data={"subtitle_text": "line"},
    )
    before = _shot_input_fingerprint(shot)
    shot.image_url = "/static/generated/images/shot-1.jpg"
    assert _shot_input_fingerprint(shot) == before
    shot.dialogue = "changed"
    assert _shot_input_fingerprint(shot) != before


@pytest.mark.asyncio
async def test_shots_ready_run_is_live_context_for_first_frame_accounting() -> None:
    run = SimpleNamespace(
        id="run-1", user_id="user-1", novel_id="novel-1", status="shots_ready",
        budget_policy={"live_canary": True},
        episodes=[{"canonical_ids": {"workflow_id": "workflow-1", "shot_ids": ["shot-1"]}}],
    )
    shot = SimpleNamespace(id="shot-1", storyboard_id="board-1")
    board = SimpleNamespace(id="board-1", novel_id="novel-1")
    workflow = SimpleNamespace(id="workflow-1", storyboard_id="board-1")

    class Scalars:
        def all(self):
            return [run]

    class DB:
        async def scalars(self, _query):
            return Scalars()

        async def get(self, _model, _value):
            return board

        async def scalar(self, _query):
            return workflow

    resolved = await resolve_live_series_run_for_shot(DB(), user_id="user-1", shot=shot)
    assert resolved is run


@pytest.mark.asyncio
async def test_persist_shot_image_uses_public_storage_delivery(monkeypatch) -> None:
    persistence = {}

    async def persist(*args, **kwargs):
        persistence.update(kwargs)
        return "/static/generated/images/shot.jpg"

    async def deliver(db, user_id, source_url, **kwargs):
        return {"provider_url": "https://cdn.example.com/static/generated/images/shot.jpg",
                "image_url_sent": True, "delivery_method": "qiniu_object_upload",
                "storage_config_id": "qiniu"}

    monkeypatch.setattr("app.services.shot_image_delivery.persist_remote_media_url", persist)
    monkeypatch.setattr("app.services.shot_image_delivery.resolve_provider_media_url", deliver)
    result = await persist_shot_image_publicly(object(), user_id="user", source_url="https://provider/shot.jpg",
                                               shot_id="shot-1")
    assert result.public_url == "https://cdn.example.com/static/generated/images/shot.jpg"
    assert result.storage_url == "/static/generated/images/shot.jpg"
    assert result.delivery["delivery_method"] == "qiniu_object_upload"
    assert persistence["image_max_dimension"] >= 1024


def test_live_shot_image_never_accepts_or_falls_back_to_dev_placeholder() -> None:
    assert is_live_ready_shot_image("/static/generated/images/shot.jpg") is True
    assert is_live_ready_shot_image("https://cdn.example.com/shot.jpg") is True
    assert is_live_ready_shot_image("/static/dev/image-shot.png") is False
    assert should_use_dev_shot_image_fallback(live_run=object(), model_config_id=None) is False
    assert should_use_dev_shot_image_fallback(live_run=None, model_config_id="config-1") is False
    assert should_use_dev_shot_image_fallback(live_run=None, model_config_id=None) is True


def test_locked_live_shot_does_not_rewrite_entity_references_during_image_generation() -> None:
    assert should_refresh_shot_entity_refs(live_run=object()) is False
    assert should_refresh_shot_entity_refs(live_run=None) is True
