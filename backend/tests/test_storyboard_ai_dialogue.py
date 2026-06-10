from app.api.v1.endpoints.storyboard_ai import (
    GenerateDialogueRequest,
    extract_json_object,
    normalize_dialogue_payload,
)


def test_extract_json_object_from_fenced_response():
    content = """```json
{"dialogue":"林澈：别碰那枚铜铃。","duration":4}
```"""

    assert extract_json_object(content)["dialogue"] == "林澈：别碰那枚铜铃。"


def test_normalize_dialogue_payload_keeps_script_speaker():
    request = GenerateDialogueRequest(
        scene_description="林澈发现铜铃发光",
        script_content="- 林澈：这枚铜铃在回应我。",
        characters=[{"name": "林澈"}],
        dialogue_mode="extract",
    )

    response = normalize_dialogue_payload(
        {
            "dialogue": "这枚铜铃在回应我。",
            "speaker_name": "林澈",
            "spoken_text": "这枚铜铃在回应我。",
            "duration": 5,
        },
        request,
        request.characters,
    )

    assert response.dialogue == "林澈：这枚铜铃在回应我。"
    assert response.speaker_name == "林澈"
    assert response.spoken_text == "这枚铜铃在回应我。"
    assert response.dialogue_source == "script"
    assert response.warnings == []


def test_normalize_dialogue_payload_warns_placeholder_speaker():
    request = GenerateDialogueRequest(
        scene_description="主角质问黑衣人",
        characters=[{"name": "林澈"}],
        dialogue_mode="rewrite",
    )

    response = normalize_dialogue_payload(
        {
            "dialogue": "角色A：你到底是谁？",
            "duration": 4,
        },
        request,
        request.characters,
    )

    assert response.speaker_name == "角色A"
    assert any("占位名称" in warning for warning in response.warnings)


def test_normalize_dialogue_payload_warns_unknown_speaker():
    request = GenerateDialogueRequest(
        scene_description="林澈发现线索",
        characters=[{"name": "林澈"}],
        dialogue_mode="polish",
    )

    response = normalize_dialogue_payload(
        {
            "dialogue": "陌生人：我知道铜铃的秘密。",
            "duration": 4,
        },
        request,
        request.characters,
    )

    assert response.speaker_name == "陌生人"
    assert any("未在当前镜头角色中找到" in warning for warning in response.warnings)
