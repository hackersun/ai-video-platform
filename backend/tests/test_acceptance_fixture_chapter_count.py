from types import SimpleNamespace

import pytest

from app.features.series_run_story_locks.application.deterministic_acceptance import (
    deterministic_anchor_entity_refs, fixture_chapter_position,
)

NAMES = ["主角", "连续场景", "连续性道具", "道具被发现", "道具发生变化", "主角完成最终事件"]
ENTITIES = {name: SimpleNamespace(id=f"id-{name}") for name in NAMES}


@pytest.mark.parametrize("total", [1, 2, 3, 4, 6])
def test_fixture_positions_stay_in_range(total):
    positions = [fixture_chapter_position(slot, total) for slot in (1, 2, 3, 4)]
    assert all(1 <= p <= total for p in positions)
    assert positions[0] == 1 and positions[3] == total
    assert positions == sorted(positions)


def test_four_chapter_mapping_unchanged():
    assert [fixture_chapter_position(s, 4) for s in (1, 2, 3, 4)] == [1, 2, 3, 4]


@pytest.mark.parametrize("total", [1, 2, 4])
def test_every_event_referenced_exactly_once(total):
    seen = []
    for ep in range(1, total + 1):
        refs = deterministic_anchor_entity_refs(ENTITIES, ep, total)
        seen += [r["entity_id"] for r in refs["events"]]
    assert sorted(seen) == sorted(f"id-{n}" for n in NAMES[3:])
    last = deterministic_anchor_entity_refs(ENTITIES, total, total)
    assert {"entity_id": "id-主角完成最终事件"} in last["events"]
    assert last["props"]
