from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.core.database import AsyncSessionLocal
from app.models import StoryEntity
from init_db import init_db


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


def _run(coro):
    return asyncio.run(coro)


def test_canonical_candidate_schema_normalizes_existing_extraction_dicts() -> None:
    from app.services.entity_extraction_schema import CanonicalEntityCandidate

    candidate = CanonicalEntityCandidate.model_validate(
        {
            "entity_type": "character",
            "name": " 林澈 ",
            "description": "黑发少年",
            "aliases": None,
            "attributes": {"visual_dna": {"costume": "深灰风衣"}},
            "evidence": "林澈站在旧邮局门口。",
            "confidence": 92,
            "source": "deterministic",
        }
    )

    assert candidate.entity_type == "character"
    assert candidate.name == "林澈"
    assert candidate.aliases == []
    assert candidate.attributes["visual_dna"]["costume"] == "深灰风衣"


def test_canonical_candidate_schema_rejects_unknown_entity_types() -> None:
    from app.services.entity_extraction_schema import CanonicalEntityCandidate

    with pytest.raises(ValueError):
        CanonicalEntityCandidate.model_validate({"entity_type": "camera", "name": "推镜"})


def test_event_schema_rejects_incomplete_event_shape() -> None:
    from app.services.entity_extraction_schema import CanonicalEntityCandidate

    with pytest.raises(ValueError, match="actor.*action.*object.*outcome"):
        CanonicalEntityCandidate.model_validate({"entity_type": "event", "name": "钟声响起", "evidence": "钟声响起。"})


def test_ai_parser_preserves_complete_event_and_provenance_fields() -> None:
    import json
    from app.api.v1.endpoints.story_bible import _parse_entity_json

    payload = {
        "entity_type": "event", "name": "沈砚打开旧铜铃", "evidence": "沈砚打开旧铜铃，密门显现。",
        "evidence_span": "沈砚打开旧铜铃，密门显现。", "char_start": 4, "char_end": 19,
        "source_chapter_id": "chapter-2", "source_chapter_number": 2,
        "actor": "沈砚", "action": "打开", "object": "旧铜铃", "outcome": "密门显现",
        "extraction_model": "ai-model", "extraction_config": {"temperature": 0}, "review_state": "candidate",
        "current_state": {"door": "open"}, "known_to_characters": ["沈砚"], "introduced_at": 2,
        "future_intent": "第四章重启", "foreshadowing": "铃舌裂纹",
    }

    event = _parse_entity_json(json.dumps([payload], ensure_ascii=False))[0]

    for field in ("actor", "action", "object", "outcome", "source_chapter_id", "source_chapter_number", "char_start", "char_end", "extraction_model", "extraction_config", "review_state", "current_state", "known_to_characters", "introduced_at", "future_intent", "foreshadowing"):
        assert event[field] == payload[field]


def test_normalize_event_preserves_nonempty_ai_event_fields() -> None:
    from app.services.entity_extraction_service import normalize_extracted_entities

    event = normalize_extracted_entities([{
        "entity_type": "event", "name": "钟声异变", "evidence": "钟声异变。",
        "actor": "自定义主体", "action": "自定义动作", "object": "自定义客体", "outcome": "自定义结果",
        "source": "ai",
    }])[0]

    assert {key: event[key] for key in ("actor", "action", "object", "outcome")} == {
        "actor": "自定义主体", "action": "自定义动作", "object": "自定义客体", "outcome": "自定义结果",
    }


@pytest.mark.parametrize(
    ("text", "item", "expected"),
    [
        ("前缀证据句后缀", {"evidence_span": "证据句", "char_start": 2, "char_end": 5}, (2, 5, "verified")),
        ("证据句与证据句", {"evidence_span": "证据句"}, (None, None, "ambiguous")),
        ("前缀证据句后缀", {"evidence_span": "证据句", "char_start": 0, "char_end": 3}, (None, None, "unmatched")),
        ("完全无关文本", {"evidence_span": "证据句"}, (None, None, "unmatched")),
    ],
)
def test_evidence_span_offsets_are_only_kept_when_exact_and_unambiguous(text, item, expected) -> None:
    from app.api.v1.endpoints.story_bible import _validated_evidence_span

    assert _validated_evidence_span(text, item) == expected


def test_schema_rejects_reversed_evidence_offsets() -> None:
    from app.services.entity_extraction_schema import CanonicalEntityCandidate

    with pytest.raises(ValueError, match="char_end"):
        CanonicalEntityCandidate(entity_type="prop", name="铜铃", char_start=8, char_end=2)


def test_mock_ai_metadata_and_custom_event_shape_survive_real_extraction_persistence(monkeypatch) -> None:
    import json
    from app.api.v1.endpoints import story_bible

    text = "前缀沈砚打开旧铜铃，密门显现。后缀"
    span = "沈砚打开旧铜铃，密门显现。"
    start = text.index(span)
    ai_item = {
        "entity_type": "event", "name": "自定义事件名", "evidence": span, "evidence_span": span,
        "char_start": start, "char_end": start + len(span), "actor": "AI主体", "action": "AI动作",
        "object": "AI客体", "outcome": "AI结果", "confidence": 91,
    }

    class FakeService:
        async def safe_chat_completion(self, **kwargs):
            return {"choices": [{"message": {"content": json.dumps([ai_item], ensure_ascii=False)}}]}

    async def fake_config(*args, **kwargs):
        return "key", "provider-x", "model-x", None

    async def fake_prompt(*args, **kwargs):
        return {"prompt": "mock"}

    monkeypatch.setattr(story_bible, "get_user_text_model_config", fake_config)
    monkeypatch.setattr(story_bible, "create_text_generation_service", lambda *args: FakeService())
    monkeypatch.setattr(story_bible, "select_prompt_skill_for_model", fake_prompt)

    async def scenario():
        async with AsyncSessionLocal() as db:
            entities = await story_bible._extract_and_optionally_persist(
                db, f"ai-u-{uuid4().hex}", None, None, None, text, ["event"], True, "config-x"
            )
            return story_bible.build_story_entity_response(entities[0]).model_dump()

    response = _run(scenario())
    assert response["attributes"]["event"] == {"actor": "AI主体", "action": "AI动作", "object": "AI客体", "outcome": "AI结果"}
    provenance = response["extra_data"]["provenance"]
    assert provenance["extraction_model"] == "model-x"
    assert provenance["extraction_config"]["provider_name"] == "provider-x"
    assert provenance["extraction_config"]["model_config_id"] == "config-x"
    assert provenance["char_start"] == start


def test_canonical_candidate_carries_structural_provenance_and_review_state() -> None:
    from app.services.entity_extraction_schema import CanonicalEntityCandidate

    candidate = CanonicalEntityCandidate.model_validate(
        {
            "entity_type": "event",
            "name": "沈砚打开旧铜铃",
            "canonical_name": "沈砚打开旧铜铃",
            "evidence_span": "沈砚打开旧铜铃，密门显现。",
            "source_chapter_id": "chapter-2",
            "source_chapter_index": 2,
            "confidence": 91,
            "extraction_model": "deterministic-v2",
            "extraction_config": {"language": "zh"},
            "review_state": "candidate",
            "actor": "沈砚",
            "action": "打开",
            "object": "旧铜铃",
            "outcome": "密门显现",
        }
    )

    assert candidate.canonical_name == "沈砚打开旧铜铃"
    assert candidate.evidence_span == "沈砚打开旧铜铃，密门显现。"
    assert candidate.source_chapter_index == 2
    assert candidate.extraction_config == {"language": "zh"}
    assert candidate.review_state == "candidate"


def test_quality_rejects_subject_predicate_fragment_for_prop() -> None:
    from app.services.entity_extraction_schema import CanonicalEntityCandidate
    from app.services.entity_quality_service import REJECT_NOISE, score_entity_candidate

    result = score_entity_candidate(
        CanonicalEntityCandidate(
            entity_type="prop",
            name="沈砚在废弃灯",
            evidence="沈砚在废弃灯塔里停住脚步。",
        )
    )

    assert result.auto_decision == REJECT_NOISE
    assert "noise:prop_predicate_phrase" in result.flags


@pytest.mark.parametrize(
    ("entity_type", "name", "evidence"),
    [
        ("prop", "视觉钩", "开场钩子要强，形成下一集钩子。"),
        ("prop", "推镜", "镜头序列：推镜、拉镜。"),
        ("scene", "这一刻重新指向林", "上一章留下的线索，在这一刻重新指向林澈。"),
        ("character", "外门弟子们", "外门弟子们围在门口。"),
    ],
)
def test_quality_service_rejects_known_noise_candidates(entity_type: str, name: str, evidence: str) -> None:
    from app.services.entity_extraction_schema import CanonicalEntityCandidate
    from app.services.entity_quality_service import REJECT_NOISE, score_entity_candidate

    result = score_entity_candidate(
        CanonicalEntityCandidate(entity_type=entity_type, name=name, evidence=evidence, confidence=80)
    )

    assert result.auto_decision == REJECT_NOISE
    assert result.score < 50
    assert result.flags


@pytest.mark.parametrize(
    ("entity_type", "name", "evidence"),
    [
        ("character", "林澈", "林澈站在旧邮局门口，握紧铜铃。"),
        ("scene", "旧邮局", "雨夜的旧邮局亮着暖黄灯。"),
        ("prop", "铜铃", "林澈握紧铜铃，铃声在雨巷里回荡。"),
        ("event", "林澈发现铜铃回声", "林澈发现铜铃回声会模仿他们的声音。"),
    ],
)
def test_quality_service_accepts_evidence_backed_production_candidates(entity_type: str, name: str, evidence: str) -> None:
    from app.services.entity_extraction_schema import CanonicalEntityCandidate
    from app.services.entity_quality_service import AUTO_APPROVE, NEEDS_REVIEW, score_entity_candidate

    event_shape = (
        {"actor": "林澈", "action": "发现", "object": "铜铃回声", "outcome": "回声会模仿他们的声音"}
        if entity_type == "event"
        else {}
    )
    result = score_entity_candidate(
        CanonicalEntityCandidate(entity_type=entity_type, name=name, evidence=evidence, confidence=90, **event_shape)
    )

    assert result.auto_decision in {NEEDS_REVIEW, AUTO_APPROVE}
    assert result.score >= 60
    assert "noise" not in result.flags


def test_quality_annotation_keeps_existing_extraction_shape_and_adds_metadata() -> None:
    from app.services.entity_extraction_service import extract_story_entities_with_quality
    from app.services.entity_quality_service import REJECT_NOISE

    entities = extract_story_entities_with_quality(
        "角色：林澈。场景：旧邮局。道具：铜铃。镜头序列：推镜、拉镜。",
        {"character", "scene", "prop"},
    )

    by_name = {item["name"]: item for item in entities}
    assert by_name["林澈"]["quality"]["auto_decision"] != REJECT_NOISE
    assert by_name["旧邮局"]["quality"]["score"] >= 60
    assert "entity_type" in by_name["铜铃"]
    assert "quality" in by_name["铜铃"]


def test_persisted_story_bible_extraction_stores_quality_metadata() -> None:
    async def scenario() -> StoryEntity:
        from app.api.v1.endpoints.story_bible import _extract_and_optionally_persist

        user_id = f"quality-user-{uuid4().hex[:20]}"
        novel_id = f"quality-novel-{uuid4()}"
        async with AsyncSessionLocal() as db:
            entities = await _extract_and_optionally_persist(
                db,
                user_id,
                novel_id,
                None,
                None,
                "角色：林澈。林澈站在旧邮局门口，握紧铜铃。",
                ["character"],
                persist=True,
            )
            assert len(entities) == 1
            return entities[0]

    entity = _run(scenario())

    quality = entity.extra_data.get("quality") if isinstance(entity.extra_data, dict) else None
    assert quality is not None
    assert quality["score"] >= 60
    assert quality["auto_decision"] in {"needs_review", "auto_approve"}


def test_persisted_story_bible_reextraction_refreshes_quality_metadata() -> None:
    async def scenario() -> dict:
        from app.api.v1.endpoints.story_bible import _extract_and_optionally_persist

        user_id = f"quality-user-{uuid4().hex[:20]}"
        novel_id = f"quality-novel-{uuid4()}"
        async with AsyncSessionLocal() as db:
            first = await _extract_and_optionally_persist(
                db,
                user_id,
                novel_id,
                None,
                None,
                "角色：林澈。",
                ["character"],
                persist=True,
            )
            first_quality = dict((first[0].extra_data or {}).get("quality") or {})

            second = await _extract_and_optionally_persist(
                db,
                user_id,
                novel_id,
                None,
                None,
                "角色：林澈。林澈站在旧邮局门口，握紧铜铃。",
                ["character"],
                persist=True,
            )

            return {
                "first_entity_id": first[0].id,
                "second_entity_id": second[0].id,
                "first_quality": first_quality,
                "second_quality": dict((second[0].extra_data or {}).get("quality") or {}),
            }

    result = _run(scenario())

    assert result["second_entity_id"] == result["first_entity_id"]
    assert result["second_quality"]["score"] >= result["first_quality"].get("score", 0)
    assert result["second_quality"]["auto_decision"] in {"needs_review", "auto_approve"}


def test_candidate_extraction_roundtrip_preserves_fact_semantics_in_response_fields() -> None:
    async def scenario() -> StoryEntity:
        from app.services.entity_review_service import run_candidate_entity_extraction

        token = uuid4().hex
        text = "沈砚打开旧铜铃，密门显现。"
        item = {
            "entity_type": "event", "name": "沈砚打开旧铜铃", "canonical_name": "沈砚打开旧铜铃",
            "description": text, "evidence": text, "evidence_span": text, "char_start": 0, "char_end": len(text),
            "source_chapter_id": f"chapter-{token}", "source_chapter_number": 2,
            "confidence": 91, "source": "ai", "extraction_model": "test-model", "extraction_config": {"temperature": 0},
            "review_state": "candidate", "actor": "沈砚", "action": "打开", "object": "旧铜铃", "outcome": "密门显现",
            "current_state": {"door": "open"}, "known_to_characters": ["沈砚"], "introduced_at": 2, "resolved_at": None,
            "future_intent": "第四章重启", "foreshadowing": "铃舌裂纹",
        }
        async with AsyncSessionLocal() as db:
            result = await run_candidate_entity_extraction(db, user_id=f"u-{token}", novel_id=f"n-{token}", chapter_id=item["source_chapter_id"], source_type="chapter", source_id=item["source_chapter_id"], text=text, entity_types=["event"], candidate_items=[item], persist=True)
            return result["entities"][0]

    entity = _run(scenario())
    assert entity.chapter_id == entity.first_seen_chapter_id
    assert entity.attributes["event"] == {"actor": "沈砚", "action": "打开", "object": "旧铜铃", "outcome": "密门显现"}
    assert entity.attributes["current_state"] == {"door": "open"}
    assert entity.extra_data["provenance"]["char_end"] == len("沈砚打开旧铜铃，密门显现。")
    assert entity.extra_data["future_intent"] == "第四章重启"
