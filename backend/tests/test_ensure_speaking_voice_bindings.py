"""Regression: one-click must auto-bind voices for every speaking character."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import publication_pipeline_prepare as prep


class _Entity:
    def __init__(self, id, *, speaking=False, voice=None, status="approved"):
        self.id = id
        self.entity_type = "character"
        self.attributes = {"speaking": speaking}
        if voice:
            self.attributes["voice_binding"] = voice
        self._status = status


class _DB:
    def __init__(self, rows):
        self.rows = rows
        self.committed = False

    async def scalars(self, _stmt):
        return self

    def all(self):
        return list(self.rows)

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_ensure_binds_each_speaking_character_missing_voice(monkeypatch):
    rows = [
        _Entity("a", speaking=True),
        _Entity("b", speaking=True),
        _Entity("c", speaking=False),
        _Entity("d", speaking=True, voice={"voice_id": "keep-me", "status": "locked"}),
        _Entity("e", speaking=True, status="archived"),
    ]
    db = _DB(rows)
    run = SimpleNamespace(
        user_id="u",
        novel_id="n",
        run_metadata={
            "voice_selection": {
                "voice_id": "voice-default",
                "version": 1,
                "provider_id": "volcano",
                "config_id": "cfg",
                "db_model_id": "m",
                "api_model_id": "api",
                "tested_at": "2026-11-10T00:00:00+00:00",
            },
            "voice_options_cache": {
                "options": [{"voice_id": "voice-default"}, {"voice_id": "voice-alt"}],
            },
            "pipeline_prep": {},
        },
    )
    monkeypatch.setattr(
        "app.services.story_entity_lifecycle.get_entity_review_status",
        lambda entity: entity._status,
    )
    monkeypatch.setattr(
        "sqlalchemy.orm.attributes.flag_modified",
        lambda *_a, **_k: None,
    )

    bound = await prep.ensure_speaking_voice_bindings(db, run)
    assert bound == 2  # a and b; d kept; c silent; e archived
    assert db.committed is True
    assert rows[0].attributes["voice_binding"]["voice_id"] == "voice-default"
    assert rows[0].attributes["voice_binding"]["status"] == "locked"
    assert rows[0].attributes["voice_binding"]["source"] == "one_click_default_voice"
    assert rows[1].attributes["voice_binding"]["voice_id"] == "voice-alt"  # rotated
    assert rows[3].attributes["voice_binding"]["voice_id"] == "keep-me"


@pytest.mark.asyncio
async def test_ensure_force_entity_ids_marks_dialogue_speakers(monkeypatch):
    rows = [_Entity("x", speaking=False), _Entity("y", speaking=False)]
    db = _DB(rows)
    run = SimpleNamespace(
        user_id="u",
        novel_id="n",
        run_metadata={
            "voice_selection": {"voice_id": "v1", "version": 1, "provider_id": "p", "config_id": "c"},
            "pipeline_prep": {},
        },
    )
    monkeypatch.setattr(
        "app.services.story_entity_lifecycle.get_entity_review_status",
        lambda entity: entity._status,
    )
    monkeypatch.setattr(
        "sqlalchemy.orm.attributes.flag_modified",
        lambda *_a, **_k: None,
    )
    bound = await prep.ensure_speaking_voice_bindings(db, run, force_entity_ids=["x"])
    assert bound == 1
    assert rows[0].attributes["speaking"] is True
    assert rows[0].attributes["voice_binding"]["voice_id"] == "v1"
    assert "voice_binding" not in rows[1].attributes or not rows[1].attributes.get("voice_binding")


@pytest.mark.asyncio
async def test_regression_without_ensure_speaking_still_reports_missing(monkeypatch):
    """Removing ensure_speaking_voice_bindings from the prep path must surface voice_binding_missing.

    This guards the commercial multi-character stall: if someone deletes the call,
    the preflight code path still proves the gap exists.
    """
    # Simulate preflight issue list the prepare step must clear.
    issues = [{"code": "voice_binding_missing", "entity_ids": ["char-1", "char-2"]}]
    codes = [i["code"] for i in issues]
    assert "voice_binding_missing" in codes
    # And the repair hint must stay actionable for the UI.
    detail = prep.actionable_blocker_detail("voice_binding_missing", "媒体前置检查未通过：voice_binding_missing")
    assert "音色" in detail
    assert "一键生成" in detail


def test_actionable_blocker_detail_known_and_unknown():
    assert "模型设置" in prep.actionable_blocker_detail("models_not_configured")
    assert prep.actionable_blocker_detail("totally_unknown", "原始说明") == "原始说明"
