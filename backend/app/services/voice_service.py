"""
Story Bible Voice Service
从Story Bible获取角色音色配置
"""

from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StoryBible


async def get_character_voice_from_story_bible(
    db: AsyncSession,
    character_name: str,
    story_bible_id: str
) -> Optional[Dict[str, Any]]:
    """
    从Story Bible获取角色音色配置

    Args:
        db: 数据库会话
        character_name: 角色名称
        story_bible_id: Story Bible ID

    Returns:
        音色配置字典，包含voice, voice_model, voice_speed, voice_pitch, voice_volume
        如果未找到则返回None
    """
    result = await db.execute(
        select(StoryBible).where(StoryBible.id == story_bible_id)
    )
    story_bible = result.scalar_one_or_none()
    if not story_bible:
        return None

    character_rules = story_bible.character_rules or []
    for rule in character_rules:
        if rule.get("name") == character_name:
            return {
                "voice": rule.get("voice"),
                "voice_model": rule.get("voice_model"),
                "voice_speed": rule.get("voice_speed", 1.0),
                "voice_pitch": rule.get("voice_pitch"),
                "voice_volume": rule.get("voice_volume", 1.0),
            }
    return None


async def get_all_character_voices(
    db: AsyncSession,
    story_bible_id: str
) -> Dict[str, Dict[str, Any]]:
    """
    获取Story Bible中所有角色的音色配置

    Args:
        db: 数据库会话
        story_bible_id: Story Bible ID

    Returns:
        角色名称到音色配置的映射字典
    """
    voices = {}
    result = await db.execute(
        select(StoryBible).where(StoryBible.id == story_bible_id)
    )
    story_bible = result.scalar_one_or_none()
    if not story_bible:
        return voices

    character_rules = story_bible.character_rules or []
    for rule in character_rules:
        name = rule.get("name")
        if name:
            voices[name] = {
                "voice": rule.get("voice"),
                "voice_model": rule.get("voice_model"),
                "voice_speed": rule.get("voice_speed", 1.0),
            }
    return voices