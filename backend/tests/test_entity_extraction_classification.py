from app.services.entity_extraction_service import extract_story_entities


def _names_by_type(entities):
    grouped = {}
    for entity in entities:
        grouped.setdefault(entity["entity_type"], set()).add(entity["name"])
    return grouped


def test_deterministic_extraction_classifies_characters_scenes_and_props():
    text = "沈月璃在青阳宗外门石屋醒来，旧铜钩悬在门梁上。外门弟子们围在门口，王执事低声道：“别碰铜钩。”"

    entities = extract_story_entities(text, {"character", "scene", "prop"})

    by_type = _names_by_type(entities)
    assert {"沈月璃", "王执事"}.issubset(by_type.get("character", set()))
    assert "青阳宗外门石屋" in by_type.get("scene", set())
    assert "旧铜钩" in by_type.get("prop", set())
    assert "外门弟子们" not in by_type.get("character", set())
    assert "青阳宗外门石屋" not in by_type.get("character", set())
    assert "旧铜钩" not in by_type.get("character", set())


def test_ai_entity_json_is_normalized_before_persistence():
    from app.api.v1.endpoints.story_bible import _parse_entity_json

    content = """
    [
      {"entity_type": "character", "name": "青阳宗外门石屋", "description": "沈月璃醒来的地点"},
      {"entity_type": "scene", "name": "沈月璃", "description": "少女主角，在石屋醒来并行动"},
      {"entity_type": "character", "name": "外门弟子们", "description": "围在门口的群体背景"},
      {"entity_type": "prop", "name": "王执事", "description": "低声说话的执事"},
      {"entity_type": "scene", "name": "旧铜钩", "description": "悬在门梁上的旧铜钩"}
    ]
    """

    entities = _parse_entity_json(content)

    by_type = _names_by_type(entities)
    assert "沈月璃" in by_type.get("character", set())
    assert "王执事" in by_type.get("character", set())
    assert "青阳宗外门石屋" in by_type.get("scene", set())
    assert "旧铜钩" in by_type.get("prop", set())
    assert "外门弟子们" not in by_type.get("character", set())
