from app.api.v1.endpoints.storyboards import (
    build_dialogue_metadata,
    extract_dialogue_speaker,
    strip_dialogue_speaker,
)
from app.services.storyboard_template_service import build_template_shots


def test_extract_dialogue_speaker_and_spoken_text():
    dialogue = "林澈：这道光，在回应我。"

    assert extract_dialogue_speaker(dialogue) == "林澈"
    assert strip_dialogue_speaker(dialogue) == "这道光，在回应我。"


def test_build_dialogue_metadata_resolves_character_ref():
    metadata = build_dialogue_metadata(
        {"dialogue": "林澈：这道光，在回应我。"},
        [{"name": "林澈", "entity_id": "entity-1", "character_id": "char-1", "voice": "voice-a"}],
        dialogue_source="script",
    )

    assert metadata["dialogue_speaker"] == "林澈"
    assert metadata["dialogue_spoken_text"] == "这道光，在回应我。"
    assert metadata["dialogue_source"] == "script"
    assert metadata["speaker_entity_id"] == "entity-1"
    assert metadata["speaker_character_id"] == "char-1"
    assert metadata["speaker_voice"] == "voice-a"


def test_template_shots_include_dialogue_metadata():
    template = {
        "id": "dialogue-template",
        "name": "对白模板",
        "description": "测试模板",
        "shots": [
            {
                "duration": 4,
                "shot_type": "dialogue",
                "camera_angle": "medium",
                "camera_movement": "static",
                "emotion": "tense",
                "lighting": "natural",
                "color_grading": "cinematic",
                "visual_focus": "主角确认线索",
                "dialogue_role": "角色",
            }
        ],
    }

    shots = build_template_shots(
        template=template,
        source_title="第一章",
        source_content="林澈在雨夜发现铜铃异常。",
        story_context={"characters": [{"name": "林澈"}], "props": [{"name": "铜铃"}]},
    )

    assert shots[0]["dialogue"].startswith("林澈：")
    assert shots[0]["extra_data"]["dialogue_speaker"] == "林澈"
    assert shots[0]["extra_data"]["dialogue_source"] == "template_story_beat"
