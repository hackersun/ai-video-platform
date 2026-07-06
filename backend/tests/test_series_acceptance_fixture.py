from __future__ import annotations

from scripts.create_series_acceptance_fixture import build_fixture_payload


def test_fixture_payload_contains_real_series_context() -> None:
    payload = build_fixture_payload(stamp="unit-test")

    assert payload["novel"]["title"].startswith("Series Studio Acceptance")
    assert len(payload["chapters"]) == 3
    assert payload["series_plan"]["target_episode_count"] == 3
    assert payload["workflow"]["title"].endswith("Episode 1")
    assert payload["workflow"]["novel_id_ref"] == "novel"
    assert payload["workflow"]["chapter_id_ref"] == "chapter-1"
    assert payload["shots"][0]["entity_refs"]["characters"][0]["name"] == "林澈"
    assert payload["assets"][0]["entity_ref"] == "character-main"


def test_fixture_payload_has_acceptance_urls() -> None:
    payload = build_fixture_payload(stamp="unit-test")

    assert payload["acceptance_urls"] == [
        "/novels/{novel_id}",
        "/studio?workflow_id={workflow_id}&novel_id={novel_id}&chapter_id={chapter_id}",
        "/studio/cards?novel_id={novel_id}",
        "/studio/continuity-review?workflow_id={workflow_id}&novel_id={novel_id}&chapter_id={chapter_id}",
        "/studio/shot-review?workflow_id={workflow_id}&novel_id={novel_id}&chapter_id={chapter_id}",
    ]


def test_fixture_payload_without_stamp_is_deterministic() -> None:
    first_payload = build_fixture_payload()
    second_payload = build_fixture_payload()

    assert first_payload == second_payload
    assert first_payload["novel"]["title"] == "Series Studio Acceptance - 星轨少年 - dry-run"
