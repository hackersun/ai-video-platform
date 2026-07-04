from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - ensure all SQLAlchemy models are registered
from app.core.database import Base
from app.models import Chapter, Novel, Script, StoryBible, StoryEntity
from app.services.asset_visual_contract import (
    build_visual_contract_from_story,
    render_contract_prompt_block,
)


@pytest_asyncio.fixture()
async def db_session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture()
async def seeded_story(db_session: AsyncSession) -> dict[str, StoryEntity | str]:
    user_id = f"asset-contract-user-{uuid4()}"
    chapter_id = "chapter-1"
    script_id = "script-1"
    novel = Novel(
        id="novel-1",
        user_id=user_id,
        title="雨巷旧邮局",
        genre="年代悬疑",
        description="1980年代小城雨夜，旧邮局藏着一封没有寄出的信。",
    )
    chapter = Chapter(
        id=chapter_id,
        user_id=user_id,
        novel_id=novel.id,
        title="雨夜来信",
        chapter_number=1,
        content="林澈在雨夜进入旧邮局，裂纹铜铃轻响。",
    )
    script = Script(
        id=script_id,
        user_id=user_id,
        novel_id=novel.id,
        chapter_id=chapter.id,
        title="旧邮局开场",
        description="空间结构和光源说明。",
        content="【场景】旧邮局：左侧正门，右侧木柜台，后墙绿色分拣信箱，门外冷蓝雨光，室内右上方暖黄灯。",
    )
    story_bible = StoryBible(
        id="story-bible-1",
        user_id=user_id,
        novel_id=novel.id,
        title="雨巷旧邮局 Story Bible",
        style="手绘电影感二维动画",
        worldview="1980年代小城，潮湿雨巷、旧邮局和慢节奏邮政系统。",
        negative_prompt="不要现代快递点，不要换成校服",
        scene_rules=[
            {
                "name": "旧邮局",
                "description": "小城邮政所旧址。",
                "scene_dna": {
                    "era": "1980年代小城",
                    "weather": "雨夜",
                    "lighting_direction": "门外冷蓝雨光，室内右上方暖黄灯",
                    "color_palette": "冷蓝雨光与暖黄钨丝灯",
                    "spatial_layout": {
                        "fixed_elements": ["左侧正门", "右侧木柜台", "后墙绿色分拣信箱"],
                        "action_zones": ["门口积水区", "柜台前"],
                        "forbidden_changes": ["不要现代快递点"],
                    },
                },
            }
        ],
        character_rules=[
            {
                "name": "林澈",
                "identity": {
                    "age": "17岁少年",
                    "appearance": "银灰短发，瘦削脸型",
                    "wardrobe": "蓝色工装夹克",
                    "signature_items": ["机械手套"],
                },
            }
        ],
        prop_rules=[
            {
                "name": "裂纹铜铃",
                "prop_dna": {
                    "material": "青铜材质",
                    "scale": "巴掌大小",
                    "fixed_marks": ["裂纹中泛青光", "红绳"],
                },
            }
        ],
    )
    scene = StoryEntity(
        id="scene-old-post-office",
        user_id=user_id,
        novel_id=novel.id,
        chapter_id=chapter.id,
        script_id=script.id,
        entity_type="scene",
        name="旧邮局",
        description="雨夜里的旧邮局。",
        attributes={
            "scene_dna": {
                "era": "1980年代小城",
                "weather": "雨夜",
                "lighting_direction": "门外冷蓝雨光，室内右上方暖黄灯",
                "color_palette": "冷蓝雨光与暖黄钨丝灯",
                "spatial_layout": {
                    "fixed_elements": ["左侧正门", "右侧木柜台", "后墙绿色分拣信箱"],
                    "action_zones": ["门口积水区", "柜台前"],
                    "forbidden_changes": ["不要现代快递点"],
                },
            }
        },
    )
    character = StoryEntity(
        id="character-lin-che",
        user_id=user_id,
        novel_id=novel.id,
        chapter_id=chapter.id,
        script_id=script.id,
        entity_type="character",
        name="林澈",
        description="17岁少年，旧邮局事件的调查者。",
        appearance="银灰短发",
        attributes={
            "identity": {
                "age": "17岁少年",
                "appearance": "银灰短发，瘦削脸型",
                "wardrobe": "蓝色工装夹克",
                "signature_items": ["机械手套"],
            }
        },
    )
    prop = StoryEntity(
        id="prop-cracked-bronze-bell",
        user_id=user_id,
        novel_id=novel.id,
        chapter_id=chapter.id,
        script_id=script.id,
        entity_type="prop",
        name="裂纹铜铃",
        description="巴掌大小的旧铜铃。",
        attributes={
            "prop_dna": {
                "material": "青铜材质",
                "scale": "巴掌大小",
                "fixed_marks": ["裂纹中泛青光", "红绳"],
            }
        },
    )
    db_session.add_all([novel, chapter, script, story_bible, scene, character, prop])
    await db_session.commit()

    return {
        "user_id": user_id,
        "chapter_id": chapter_id,
        "script_id": script_id,
        "scene": scene,
        "character": character,
        "prop": prop,
    }


@pytest.mark.asyncio
async def test_scene_contract_preserves_old_post_office_values(
    db_session: AsyncSession,
    seeded_story: dict[str, StoryEntity | str],
) -> None:
    contract = await build_visual_contract_from_story(
        db_session,
        str(seeded_story["user_id"]),
        entity=seeded_story["scene"],
        style="cinematic-2d",
        chapter_id=str(seeded_story["chapter_id"]),
        script_id=str(seeded_story["script_id"]),
    )

    assert contract["story_scope"]["novel_id"] == "novel-1"
    assert contract["continuity_axes"]["era"] == "1980年代小城"
    assert contract["continuity_axes"]["weather"] == "雨夜"
    assert contract["continuity_axes"]["lighting_direction"] == "门外冷蓝雨光，室内右上方暖黄灯"
    assert "左侧正门" in contract["spatial_layout"]["fixed_elements"]
    assert "右侧木柜台" in contract["spatial_layout"]["fixed_elements"]
    assert "后墙绿色分拣信箱" in contract["spatial_layout"]["fixed_elements"]
    assert "不要现代快递点" in contract["negative_constraints"]

    prompt = render_contract_prompt_block(contract, view_key="establishing", view_label="建立镜头")
    assert "小说关联视觉契约" in prompt
    assert "旧邮局" in prompt
    assert "空间布局" in prompt
    assert "时代：1980年代小城" in prompt
    assert "光源方向：门外冷蓝雨光，室内右上方暖黄灯" in prompt
    assert prompt.endswith("硬规则")


@pytest.mark.asyncio
async def test_character_contract_preserves_lin_che_identity(
    db_session: AsyncSession,
    seeded_story: dict[str, StoryEntity | str],
) -> None:
    contract = await build_visual_contract_from_story(
        db_session,
        str(seeded_story["user_id"]),
        entity=seeded_story["character"],
        style="cinematic-2d",
        chapter_id=str(seeded_story["chapter_id"]),
        script_id=str(seeded_story["script_id"]),
    )

    assert contract["identity"]["age"] == "17岁少年"
    assert "银灰短发" in contract["identity"]["appearance"]
    assert contract["identity"]["wardrobe"] == "蓝色工装夹克"
    assert "机械手套" in contract["identity"]["signature_items"]
    assert "不要换成校服" in contract["context_sources"]["negative_prompt"]


@pytest.mark.asyncio
async def test_prop_contract_preserves_cracked_bronze_bell_dna(
    db_session: AsyncSession,
    seeded_story: dict[str, StoryEntity | str],
) -> None:
    contract = await build_visual_contract_from_story(
        db_session,
        str(seeded_story["user_id"]),
        entity=seeded_story["prop"],
        style="cinematic-2d",
        chapter_id=str(seeded_story["chapter_id"]),
        script_id=str(seeded_story["script_id"]),
    )

    assert contract["prop_dna"]["material"] == "青铜材质"
    assert contract["prop_dna"]["scale"] == "巴掌大小"
    assert "裂纹中泛青光" in contract["prop_dna"]["fixed_marks"]
    assert "红绳" in contract["prop_dna"]["fixed_marks"]
