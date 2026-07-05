"""
Tests for voice_service.py
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.voice_service import (
    get_character_voice_from_story_bible,
    get_all_character_voices,
)


class MockStoryBible:
    """Mock StoryBible model for testing"""
    def __init__(self, id: str, character_rules: list):
        self.id = id
        self.character_rules = character_rules


class MockResult:
    """Mock query result"""
    def __init__(self, story_bible):
        self._story_bible = story_bible

    def scalar_one_or_none(self):
        return self._story_bible


class MockSession:
    """Mock AsyncSession"""
    def __init__(self, story_bible=None):
        self._story_bible = story_bible

    async def execute(self, query):
        return MockResult(self._story_bible)


@pytest.mark.asyncio
async def test_get_character_voice_found():
    """Test getting voice config for an existing character"""
    story_bible = MockStoryBible(
        id="sb-001",
        character_rules=[
            {
                "name": "林舟",
                "voice": "male_youth",
                "voice_model": "doubao-tts",
                "voice_speed": 1.1,
                "voice_pitch": 0.9,
                "voice_volume": 0.8,
            },
            {
                "name": "许澜",
                "voice": "female_mature",
                "voice_model": "doubao-tts",
            },
        ],
    )
    db = MockSession(story_bible)

    result = await get_character_voice_from_story_bible(db, "林舟", "sb-001")

    assert result is not None
    assert result["voice"] == "male_youth"
    assert result["voice_model"] == "doubao-tts"
    assert result["voice_speed"] == 1.1
    assert result["voice_pitch"] == 0.9
    assert result["voice_volume"] == 0.8


@pytest.mark.asyncio
async def test_get_character_voice_not_found():
    """Test getting voice config for non-existent character"""
    story_bible = MockStoryBible(
        id="sb-001",
        character_rules=[
            {"name": "林舟", "voice": "male_youth"},
        ],
    )
    db = MockSession(story_bible)

    result = await get_character_voice_from_story_bible(db, "不存在", "sb-001")

    assert result is None


@pytest.mark.asyncio
async def test_get_character_voice_matches_entity_id():
    """Test getting voice config by StoryEntity id when names diverge"""
    story_bible = MockStoryBible(
        id="sb-001",
        character_rules=[
            {"entity_id": "entity-linzhou", "name": "旧名", "voice": "male_youth"},
        ],
    )
    db = MockSession(story_bible)

    result = await get_character_voice_from_story_bible(
        db,
        "林舟",
        "sb-001",
        entity_id="entity-linzhou",
    )

    assert result is not None
    assert result["voice"] == "male_youth"


@pytest.mark.asyncio
async def test_get_character_voice_matches_alias_or_canonical_name():
    """Test getting voice config by alias/canonical name"""
    story_bible = MockStoryBible(
        id="sb-001",
        character_rules=[
            {"name": "沈砚", "aliases": ["雾港青年"], "voice": "calm_male"},
            {"canonical_name": "林舟", "voice": "male_youth"},
        ],
    )
    db = MockSession(story_bible)

    alias_result = await get_character_voice_from_story_bible(
        db,
        "阿砚",
        "sb-001",
        aliases=["雾港青年"],
    )
    canonical_result = await get_character_voice_from_story_bible(
        db,
        "小舟",
        "sb-001",
        canonical_name="林舟",
    )

    assert alias_result is not None
    assert alias_result["voice"] == "calm_male"
    assert canonical_result is not None
    assert canonical_result["voice"] == "male_youth"


@pytest.mark.asyncio
async def test_get_character_voice_no_story_bible():
    """Test when story bible does not exist"""
    db = MockSession(None)

    result = await get_character_voice_from_story_bible(db, "林舟", "nonexistent-id")

    assert result is None


@pytest.mark.asyncio
async def test_get_character_voice_defaults():
    """Test default values when optional fields are missing"""
    story_bible = MockStoryBible(
        id="sb-001",
        character_rules=[
            {
                "name": "林舟",
                "voice": "male_youth",
                # voice_model, voice_speed, voice_pitch, voice_volume not set
            },
        ],
    )
    db = MockSession(story_bible)

    result = await get_character_voice_from_story_bible(db, "林舟", "sb-001")

    assert result["voice"] == "male_youth"
    assert result["voice_model"] is None
    assert result["voice_speed"] == 1.0  # default
    assert result["voice_pitch"] is None
    assert result["voice_volume"] == 1.0  # default


@pytest.mark.asyncio
async def test_get_character_voice_empty_rules():
    """Test when character_rules is empty"""
    story_bible = MockStoryBible(
        id="sb-001",
        character_rules=[],
    )
    db = MockSession(story_bible)

    result = await get_character_voice_from_story_bible(db, "林舟", "sb-001")

    assert result is None


@pytest.mark.asyncio
async def test_get_character_voice_none_rules():
    """Test when character_rules is None"""
    story_bible = MockStoryBible(
        id="sb-001",
        character_rules=None,
    )
    db = MockSession(story_bible)

    result = await get_character_voice_from_story_bible(db, "林舟", "sb-001")

    assert result is None


@pytest.mark.asyncio
async def test_get_all_character_voices():
    """Test getting all character voices from story bible"""
    story_bible = MockStoryBible(
        id="sb-001",
        character_rules=[
            {"name": "林舟", "voice": "male_youth", "voice_model": "doubao-tts", "voice_speed": 1.1},
            {"name": "许澜", "voice": "female_mature", "voice_model": "doubao-tts", "voice_speed": 1.0},
            {"name": "守夜人", "voice": "male_deep"},
        ],
    )
    db = MockSession(story_bible)

    result = await get_all_character_voices(db, "sb-001")

    assert len(result) == 3
    assert result["林舟"]["voice"] == "male_youth"
    assert result["林舟"]["voice_speed"] == 1.1
    assert result["许澜"]["voice"] == "female_mature"
    assert result["守夜人"]["voice"] == "male_deep"


@pytest.mark.asyncio
async def test_get_all_character_voices_empty():
    """Test getting all voices when no characters"""
    story_bible = MockStoryBible(
        id="sb-001",
        character_rules=[],
    )
    db = MockSession(story_bible)

    result = await get_all_character_voices(db, "sb-001")

    assert result == {}


@pytest.mark.asyncio
async def test_get_all_character_voices_no_story_bible():
    """Test getting all voices when story bible not found"""
    db = MockSession(None)

    result = await get_all_character_voices(db, "nonexistent-id")

    assert result == {}
