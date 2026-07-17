from uuid import uuid4

import pytest

from app.models import Shot, StoryEntity, StoryEntityMention
from app.services.series_run_reference_preparation import (
    ReferencePreparationBlocked,
    prepare_series_reference,
)
from app.services.entity_review_service import approve_review_entity
from app.services.story_entity_lifecycle import CANDIDATE, set_entity_review_status
from tests.test_series_run_live_preflight_plan import (
    _ReferenceAdapter,
    _fixture,
    _fresh_live_bindings,
    db_session,
)


@pytest.mark.asyncio
async def test_reference_rejects_unapproved_required_entity_before_provider(db_session) -> None:
    run = await _fixture(db_session)
    bindings = await _fresh_live_bindings(db_session, run)
    selected_shot = await db_session.get(
        Shot, run.run_metadata["selected_anchor_shot_ids"][1],
    )
    refs = (selected_shot.extra_data or {})["entity_refs"]
    entity_id = next(
        item["entity_id"]
        for bucket in ("scenes", "props", "events")
        for item in refs.get(bucket) or []
    )
    entity = await db_session.get(StoryEntity, entity_id)
    entity.is_approved = False
    entity.attributes = {
        key: value for key, value in (entity.attributes or {}).items()
        if key != "approval_record"
    }
    set_entity_review_status(
        entity, CANDIDATE, changed_by=run.user_id, reason="awaiting_explicit_review",
    )
    await db_session.commit()

    from app.features.series_run_story_locks.public import prepare_story_locks
    locked = await prepare_story_locks(db_session, run)
    assert locked["unresolved_entity_ids"] == [entity.id]
    adapter = _ReferenceAdapter({"status": "unknown"})

    with pytest.raises(ReferencePreparationBlocked, match="production_entities_unapproved"):
        await prepare_series_reference(
            db_session, run, adapter=adapter, binding_ids=bindings,
        )

    assert adapter.calls == 0

    db_session.add(StoryEntityMention(
        id=str(uuid4()), user_id=run.user_id, entity_id=entity.id,
        novel_id=run.novel_id, source_type="novel", source_id=run.novel_id,
        mention_text=entity.name, evidence=f"原文明确提及{entity.name}",
        confidence=0.95, extractor="test",
    ))
    await db_session.commit()
    await approve_review_entity(
        db_session, user_id=run.user_id, entity_id=entity.id,
        reason="explicit Story Lock confirmation",
    )
    await db_session.commit()
    confirmed = await prepare_story_locks(db_session, run)
    assert confirmed["unresolved_count"] == 0
    assert confirmed["unresolved_entity_ids"] == []
