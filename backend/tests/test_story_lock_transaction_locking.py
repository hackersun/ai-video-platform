from types import SimpleNamespace

import pytest

from app.features.series_run_story_locks.application import story_transaction
from app.features.series_run_story_locks.application.explicit_dialogue_approval import (
    locked_dialogue_entities_statement,
)
from app.features.series_run_story_locks.application.production_scoped_inputs import (
    ProductionScopedRefCommand,
    _ensure_merged_history,
)
from app.features.series_run_story_locks.domain.scoped_reference import sign_history_record
from app.services import episode_shot_stage
from app.services.episode_shot_stage import ShotStageContext, _command


@pytest.mark.asyncio
async def test_media_running_story_lock_retry_is_allowed_after_selected_jobs_finish():
    class Db:
        async def scalar(self, _statement):
            return 0

    run = SimpleNamespace(
        status="media_running", user_id="user-1",
        run_metadata={"selected_anchor_shot_ids": ["shot-1", "shot-2"]},
    )

    await story_transaction._ensure_story_lock_preparation_state(Db(), run)


@pytest.mark.asyncio
async def test_media_running_story_lock_retry_is_blocked_while_selected_job_is_active():
    class Db:
        async def scalar(self, _statement):
            return 1

    run = SimpleNamespace(
        status="media_running", user_id="user-1",
        run_metadata={"selected_anchor_shot_ids": ["shot-1", "shot-2"]},
    )

    with pytest.raises(story_transaction.StoryLockPreparationBlocked, match="selected media jobs are still active"):
        await story_transaction._ensure_story_lock_preparation_state(Db(), run)


def test_media_retry_can_extend_a_verified_merged_reference_history():
    old_history = sign_history_record({
        "owner_user_id": "user-1", "owner_novel_id": "novel-1",
        "owner_entity_type": "character", "canonical_entity_id": "canonical-1",
        "source_entity_id": "source-1", "chapter_id": "chapter-1",
        "evidence_ref_id": "old-evidence", "metadata": {"evidence_contract": {"status": "verified"}},
        "merge_audit": {"canonical_identity_sha256": "identity-1"},
    })
    source = SimpleNamespace(
        id="source-1", entity_type="character",
        extra_data={"merge_edges": [{"source_entity_id": "source-1", "canonical_entity_id": "canonical-1"}]},
    )
    canonical = SimpleNamespace(id="canonical-1", extra_data={"canonical_histories": [old_history]})
    command = ProductionScopedRefCommand(
        run_id="run-1", user_id="user-1", novel_id="novel-1", workflow_id="workflow-1",
        storyboard_id="board-1", shot_id="shot-1", episode_number=1,
        episode_input_hash="episode-hash", chapter_ids=("chapter-1",), chapter_id="chapter-1",
        script_id="script-1", prompt="prompt", dialogue="new dialogue",
        visual_description="visual", source_text="source", shot_text="shot", entity_refs={},
    )

    _ensure_merged_history(
        source, [source, canonical],
        {"evidence_ref_id": "new-evidence", "canonical_identity_sha256": "identity-1", "evidence": {"status": "verified"}},
        {"contract_version": "chapter_evidence_ref_v1", "entity_id": "canonical-1", "evidence_ref_id": "old-evidence"},
        command,
    )

    assert [item["evidence_ref_id"] for item in canonical.extra_data["canonical_histories"]] == [
        "old-evidence", "new-evidence",
    ]


class _Transaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *_args):
        return None


class _LockSpyDb:
    def __init__(self, run, events):
        self.run = run
        self.events = events

    def begin(self):
        return _Transaction()

    async def scalar(self, statement):
        assert statement._for_update_arg is not None
        self.events.append("run_lock")
        return self.run

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_transaction_locks_fresh_run_before_dialogue_normalization(monkeypatch):
    events = []
    run = SimpleNamespace(id="run-1", user_id="user-1", novel_id="novel-1", version=1,
                          episodes=[], run_metadata={})
    db = _LockSpyDb(run, events)

    async def chapters(*_args):
        return []

    async def prepare(*_args, **_kwargs):
        events.append("normalize")

    async def backfill(*_args):
        return None

    async def load(*_args):
        return SimpleNamespace(required_entities=[])

    async def build(*_args, **_kwargs):
        return {"closure_contract_version": "required_entity_closure_v2"}

    async def persist(*_args, **_kwargs):
        return {"status": "locked"}

    monkeypatch.setattr(story_transaction, "_ordered_run_chapters", chapters)
    monkeypatch.setattr(story_transaction, "_backfill_verified_auto_approval_records", backfill)
    monkeypatch.setattr(story_transaction, "_prepare_explicit_dialogue_facts", prepare)
    monkeypatch.setattr(story_transaction, "load_required_context", load)
    monkeypatch.setattr(story_transaction, "build_closure_v2_request", build)
    monkeypatch.setattr(story_transaction, "persist_production_closure_v2", persist)

    await story_transaction.apply_closure_v2_transaction(
        db, run.id, None, 1, user_id=run.user_id, tts_snapshot={"config_id": "tts"})

    assert events == ["run_lock", "normalize"]


def test_dialogue_normalization_entity_query_is_for_update():
    statement = locked_dialogue_entities_statement("user-1", "novel-1")

    assert statement._for_update_arg is not None


@pytest.mark.asyncio
async def test_prepare_preserves_typed_required_entity_blocker(monkeypatch):
    from app.features.series_run_story_locks.domain import ProductionRequiredEntityBlocked

    class Db:
        async def rollback(self):
            return None

    run = SimpleNamespace(
        id="run-1", user_id="user-1", status="shots_ready", version=1,
        model_bindings={},
    )

    async def chapters(*_args):
        return []

    async def fail(*_args, **_kwargs):
        raise ProductionRequiredEntityBlocked(
            code="required_entity_evidence_ambiguous", blocker_category="prop_state",
            field="state", values=("secret",), required_counts={},
        )

    monkeypatch.setattr(story_transaction, "_ordered_run_chapters", chapters)
    monkeypatch.setattr(story_transaction, "apply_closure_v2_transaction", fail)

    with pytest.raises(ProductionRequiredEntityBlocked) as raised:
        await story_transaction.prepare_story_locks(Db(), run)

    assert raised.value.code == "required_entity_evidence_ambiguous"


def test_shot_stage_uses_persisted_second_episode_chapter():
    episode = {"episode_number": 1, "input_hash": "input-1",
               "chapter_ids": ["chapter-1", "chapter-2"]}
    context = ShotStageContext(
        db=SimpleNamespace(),
        run=SimpleNamespace(id="run-1", user_id="user-1", novel_id="novel-1"),
        episode=episode,
        workflow=SimpleNamespace(id="workflow-1"),
        script=SimpleNamespace(id="script-1"),
        storyboard=SimpleNamespace(id="board-1"),
        source_text="source",
    )
    shot = SimpleNamespace(id="shot-1", extra_data={"chapter_id": "chapter-2"},
                           prompt="", dialogue="", visual_description="")

    command = _command(context, shot, {})

    assert command.chapter_id == "chapter-2"


def test_shot_stage_rejects_persisted_chapter_outside_episode():
    episode = {"episode_number": 1, "input_hash": "input-1",
               "chapter_ids": ["chapter-1", "chapter-2"]}
    context = ShotStageContext(
        db=SimpleNamespace(),
        run=SimpleNamespace(id="run-1", user_id="user-1", novel_id="novel-1"),
        episode=episode,
        workflow=SimpleNamespace(id="workflow-1"),
        script=SimpleNamespace(id="script-1"),
        storyboard=SimpleNamespace(id="board-1"),
        source_text="source",
    )
    shot = SimpleNamespace(id="shot-1", extra_data={"chapter_id": "chapter-3"},
                           prompt="", dialogue="", visual_description="")

    with pytest.raises(ValueError, match="outside the production episode"):
        _command(context, shot, {})


@pytest.mark.asyncio
async def test_new_shot_uses_second_chapter_dialogue_for_chapter_and_as_of(monkeypatch):
    calls = []

    class Db:
        def add(self, _value):
            return None

        async def flush(self):
            return None

    async def resolve(*_args, **kwargs):
        calls.append(kwargs["as_of_chapter_id"])
        return {"entity_refs": {"characters": [], "scenes": [], "props": [], "events": []}}

    async def bind(*_args, **_kwargs):
        return SimpleNamespace(rendered_prompt="镜头提示词", evidence={})

    async def execute(*_args, **kwargs):
        return SimpleNamespace(value=kwargs["fallback"](), evidence={"execution_mode": "fallback"})

    monkeypatch.setattr(episode_shot_stage, "resolve_owned_shot_entity_context", resolve)
    monkeypatch.setattr(episode_shot_stage, "bind_series_stage_skill", bind)
    monkeypatch.setattr(episode_shot_stage, "execute_skill_model_or_fallback", execute)
    episode = {"episode_number": 1, "input_hash": "input-1",
               "chapter_ids": ["chapter-1", "chapter-2"]}
    context = ShotStageContext(
        db=Db(),
        run=SimpleNamespace(id="run-1", user_id="user-1", novel_id="novel-1"),
        episode=episode,
        workflow=SimpleNamespace(id="workflow-1"),
        script=SimpleNamespace(id="script-1", extra_data={"dialogue_lines": [{
            "speaker": "沈砚", "spoken_text": "到了", "dialogue": "沈砚：到了",
            "source_span": [0, 8], "chapter_id": "chapter-2",
        }]}),
        storyboard=SimpleNamespace(
            id="board-1", title="第二章场景",
            content={"scene_index": 1, "scene_count": 1, "continuity": {}},
        ),
        source_text="第一章。\n\n沈砚说：“到了”",
    )

    shot = await episode_shot_stage._new_shot(
        context,
        shot_number=1,
        episode_shot_number=1,
        shot_plan={"prompt": "沈砚抵达", "visual_description": "沈砚走入殿中", "dialogue": "幻觉角色：并不存在"},
        dialogue_index=0,
    )

    assert shot.extra_data["chapter_id"] == "chapter-2"
    assert shot.dialogue == "沈砚：到了"
    assert shot.extra_data["dialogue_spoken_text"] == "到了"
    assert calls == ["chapter-2"]
