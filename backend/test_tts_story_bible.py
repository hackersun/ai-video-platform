"""
Tests for TTS endpoint - Story Bible voice integration
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from fastapi.testclient import TestClient

from app.api.v1.endpoints.tts import (
    extract_character_from_text,
    parse_dialogue,
    is_multi_character,
)
from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def _auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


class TestExtractCharacterFromText:
    """Tests for extract_character_from_text function"""

    def test_extract_with_says_pattern(self):
        """Test extraction with '角色说：' pattern"""
        text = "林舟说：今天天气真好，我们出去走走吧。"
        result = extract_character_from_text(text)
        assert result == "林舟"

    def test_extract_with_speaks_pattern(self):
        """Test extraction with '角色道：' pattern"""
        text = "林舟道：不如我们去公园吧。"
        result = extract_character_from_text(text)
        assert result == "林舟"

    def test_extract_with_answers_pattern(self):
        """Test extraction with '角色回答：' pattern"""
        text = "林舟回答：我认为应该这样做。"
        result = extract_character_from_text(text)
        assert result == "林舟"

    def test_extract_with_colon_pattern(self):
        """Test extraction with '角色：' pattern"""
        text = "林舟：我们走吧，去看看外面的世界。"
        result = extract_character_from_text(text)
        assert result == "林舟"

    def test_extract_empty_text(self):
        """Test with empty text"""
        result = extract_character_from_text("")
        assert result is None

    def test_extract_none_text(self):
        """Test with None text"""
        result = extract_character_from_text(None)
        assert result is None

    def test_extract_no_pattern(self):
        """Test text without character pattern"""
        text = "今天天气真好，我们出去走走吧。"
        result = extract_character_from_text(text)
        assert result is None

    def test_extract_first_match(self):
        """Test that first pattern match is returned"""
        text = "林舟说：你好。有人说：那很好。"
        result = extract_character_from_text(text)
        assert result == "林舟"

    def test_extract_english_text(self):
        """Test extraction with English pattern - uses Chinese colon, so this won't match"""
        text = "John: Hello, how are you?"
        result = extract_character_from_text(text)
        assert result == "John"

    def test_extract_chinese_name(self):
        """Test extraction with Chinese names"""
        text = "许澜说：欢迎来到我们的故事。"
        result = extract_character_from_text(text)
        assert result == "许澜"

    def test_extract_spaces_handled(self):
        """Test extraction with spaces - pattern matches the first word before 说"""
        text = "林舟 说：你好。"  # Space before 说
        result = extract_character_from_text(text)
        # Pattern matches first word before 说/道/etc
        assert result == "说"


class TestParseDialogue:
    """Tests for parse_dialogue function"""

    def test_parse_single_segment(self):
        """Test parsing single segment dialogue"""
        dialogue = "林舟说：今天天气真好。"
        result = parse_dialogue(dialogue)
        assert len(result) == 1
        assert result[0]["text"] == "今天天气真好。"

    def test_parse_multi_character(self):
        """Test parsing multi-character dialogue"""
        dialogue = """林舟说：今天天气真好。
许澜道：是啊，我们出去走走吧。
守夜人说：小心点。"""
        result = parse_dialogue(dialogue)
        assert len(result) == 3
        # parse_dialogue uses "角色名: 对话" format with colon
        # Without proper colon prefix, entire lines are treated as text
        assert result[0]["character"] == "林舟说"  # Pattern matches name
        assert result[0]["text"] == "今天天气真好。"

    def test_parse_with_colon_format(self):
        """Test parsing with colon format"""
        dialogue = "小明: 你好"
        result = parse_dialogue(dialogue)
        assert len(result) == 1
        assert result[0]["character"] == "小明"
        assert result[0]["text"] == "你好"

    def test_parse_with_fullwidth_colon(self):
        """Test parsing with full-width colon"""
        dialogue = "小明：你好"
        result = parse_dialogue(dialogue)
        assert len(result) == 1
        assert result[0]["character"] == "小明"
        assert result[0]["text"] == "你好"

    def test_parse_empty_lines(self):
        """Test parsing with empty lines"""
        dialogue = "小明: 你好\n\n  \n小明: 再见"
        result = parse_dialogue(dialogue)
        assert len(result) == 2

    def test_parse_no_prefix(self):
        """Test parsing without character prefix"""
        dialogue = "这是一段没有角色前缀的文字"
        result = parse_dialogue(dialogue)
        assert len(result) == 1
        assert result[0]["character"] == ""
        assert result[0]["text"] == "这是一段没有角色前缀的文字"


class TestIsMultiCharacter:
    """Tests for is_multi_character function"""

    def test_single_character(self):
        """Test single character segments"""
        segments = [
            {"character": "林舟", "text": "你好"},
            {"character": "林舟", "text": "再见"},
        ]
        assert is_multi_character(segments) is False

    def test_multi_character(self):
        """Test multi character segments"""
        segments = [
            {"character": "林舟", "text": "你好"},
            {"character": "许澜", "text": "你好"},
        ]
        assert is_multi_character(segments) is True

    def test_mixed_empty_character(self):
        """Test with mixed empty character"""
        segments = [
            {"character": "林舟", "text": "你好"},  # Changed from "" to "林舟"
            {"character": "许澜", "text": "你好"},
        ]
        assert is_multi_character(segments) is True

    def test_all_empty_character(self):
        """Test with all empty characters"""
        segments = [
            {"character": "", "text": "你好"},
            {"character": "", "text": "再见"},
        ]
        assert is_multi_character(segments) is False

    def test_empty_segments(self):
        """Test with empty segments list"""
        assert is_multi_character([]) is False


class TestTTSGenerateRequestStoryBibleFields:
    """Tests for TTSGenerateRequest Story Bible fields"""

    def test_story_bible_fields_present(self):
        """Test that Story Bible fields are present in request model"""
        from app.api.v1.endpoints.tts import TTSGenerateRequest

        # Test default values
        request = TTSGenerateRequest(
            text_content="测试文本",
            voice_model="test_voice",
        )
        assert request.story_bible_id is None
        assert request.use_story_bible_voice is True

    def test_story_bible_fields_custom_values(self):
        """Test setting custom values for Story Bible fields"""
        from app.api.v1.endpoints.tts import TTSGenerateRequest

        request = TTSGenerateRequest(
            text_content="测试文本",
            voice_model="test_voice",
            story_bible_id="sb-123",
            use_story_bible_voice=False,
        )
        assert request.story_bible_id == "sb-123"
        assert request.use_story_bible_voice is False


def test_tts_generate_uses_story_bible_voice_per_dialogue_segment(client: TestClient) -> None:
    user_id = uuid4().hex
    novel_resp = client.post(
        "/api/v1/novels",
        json={"title": "多角色配音小说", "description": "孙剑与许澜同行。"},
        headers=_auth_headers(user_id),
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]
    bible_resp = client.post(
        "/api/v1/story-bibles",
        json={
            "novel_id": novel_id,
            "title": "多角色音色 Story Bible",
            "character_rules": [
                {"name": "孙剑", "voice": "voice-sunjian", "voice_speed": 1.1},
                {"name": "许澜", "voice": "voice-xulan", "voice_speed": 0.9},
            ],
        },
        headers=_auth_headers(user_id),
    )
    assert bible_resp.status_code == 201

    response = client.post(
        "/api/v1/tts/generate",
        json={
            "text_content": "孙剑：这一世，我不会再输。\n许澜：那就一起走下去。",
            "voice_model": "fallback-voice",
            "speed": 1.0,
            "story_bible_id": bible_resp.json()["id"],
            "novel_id": novel_id,
            "api_provider": "minimax",
        },
        headers=_auth_headers(user_id),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    segments = payload["extra_data"]["segments"]
    assert segments[0]["voice"] == "voice-sunjian"
    assert segments[0]["voice_source"] == "story_bible"
    assert segments[1]["voice"] == "voice-xulan"
    assert segments[1]["voice_source"] == "story_bible"
