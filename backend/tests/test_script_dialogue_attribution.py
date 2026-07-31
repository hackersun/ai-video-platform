from app.api.v1.endpoints.scripts import (
    extract_chapter_dialogue_lines,
    extract_chapter_dialogue_speakers,
)


def test_speech_attribution_verb_is_not_treated_as_a_character() -> None:
    content = "顾言接回能量核心，喊道：‘能源接通，苏澜，点灯！’"

    assert extract_chapter_dialogue_speakers(content, ["顾言", "苏澜"]) == ["顾言", "苏澜"]
    assert extract_chapter_dialogue_lines(content, ["顾言", "苏澜"]) == [
        {"speaker": "顾言", "text": "能源接通，苏澜，点灯"},
    ]
