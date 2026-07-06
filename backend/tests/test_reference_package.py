from __future__ import annotations

import importlib
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - ensure all SQLAlchemy models are registered
from app.core.database import Base
from app.core import model_registry
from app.models import Asset, Shot, StoryEntity


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


def _builder_module():
    try:
        return importlib.import_module("app.services.reference_package_builder")
    except ModuleNotFoundError as exc:
        pytest.fail(f"reference_package_builder module is missing: {exc}")


def _adapter_module():
    try:
        return importlib.import_module("app.services.video_reference_adapter")
    except ModuleNotFoundError as exc:
        pytest.fail(f"video_reference_adapter module is missing: {exc}")


def _seedance_contract_metadata() -> dict[str, Any]:
    return {
        "contract_status": "experimental",
        "contract_model_family": "seedance_2",
        "contract_roles": {
            "image": "reference_image",
            "video": "reference_video",
            "audio": "reference_audio",
        },
        "contract_pricing_status": "unconfirmed",
        "contract_agent_plan_multireference": False,
    }


async def _public_resolver(_db: AsyncSession, _user_id: str, url: str | None) -> dict[str, Any]:
    if url and url.startswith("https://"):
        return {"provider_url": url, "omitted_reason": None}
    return {"provider_url": None, "omitted_reason": "参考资源不是公网 URL"}


async def _cdn_resolver(_db: AsyncSession, _user_id: str, url: str | None) -> str | None:
    if url and url.startswith("/static/"):
        return f"https://cdn.example.com{url}"
    return url if url and url.startswith("https://") else None


def _shot(user_id: str, *, image_url: str | None = None, audio_url: str | None = None) -> Shot:
    return Shot(
        id=f"shot-{uuid4()}",
        user_id=user_id,
        storyboard_id=f"storyboard-{uuid4()}",
        shot_number=2,
        duration=4,
        prompt="孙剑持剑踏入旧山门",
        image_url=image_url,
        audio_url=audio_url,
        character_refs=[
            {"entity_id": "char-main", "name": "孙剑"},
            {"entity_id": "char-side", "name": "林遥"},
        ],
        extra_data={
            "entity_refs": {
                "characters": [
                    {"entity_id": "char-main", "name": "孙剑"},
                    {"entity_id": "char-side", "name": "林遥"},
                ],
                "scenes": [{"entity_id": "scene-gate", "name": "旧山门"}],
                "props": [
                    {"entity_id": "prop-sword", "name": "青锋剑"},
                    {"entity_id": "prop-token", "name": "铜令牌"},
                ],
            }
        },
    )


def _entity(user_id: str, entity_id: str, entity_type: str, name: str) -> StoryEntity:
    return StoryEntity(
        id=entity_id,
        user_id=user_id,
        entity_type=entity_type,
        name=name,
        is_approved=True,
    )


def _asset(
    user_id: str,
    entity_id: str,
    entity_type: str,
    view_key: str,
    name: str,
    *,
    url: str | None = None,
    version: int = 1,
) -> Asset:
    return Asset(
        id=f"asset-{entity_id}-{view_key}-{uuid4()}",
        user_id=user_id,
        category=entity_type,
        asset_type="image",
        entity_id=entity_id,
        entity_type=entity_type,
        name=name,
        url=url or f"https://cdn.example.com/{entity_id}-{view_key}.png",
        is_active=True,
        is_locked=True,
        is_final=True,
        version=version,
        generation_params={"view_key": view_key},
    )


async def _seed_reference_assets(db: AsyncSession, user_id: str) -> None:
    db.add_all(
        [
            _entity(user_id, "char-main", "character", "孙剑"),
            _entity(user_id, "char-side", "character", "林遥"),
            _entity(user_id, "scene-gate", "scene", "旧山门"),
            _entity(user_id, "prop-sword", "prop", "青锋剑"),
            _entity(user_id, "prop-token", "prop", "铜令牌"),
            _asset(user_id, "char-main", "character", "front", "孙剑正面"),
            _asset(user_id, "char-main", "character", "side", "孙剑侧面"),
            _asset(user_id, "char-main", "character", "back", "孙剑背面"),
            _asset(user_id, "scene-gate", "scene", "establishing", "旧山门全景"),
            _asset(user_id, "prop-sword", "prop", "main", "青锋剑主视图"),
            _asset(user_id, "prop-token", "prop", "main", "铜令牌主视图"),
            _asset(user_id, "char-side", "character", "front", "林遥正面"),
        ]
    )
    await db.flush()


def test_reference_limits_from_registry() -> None:
    get_limits = getattr(model_registry, "get_model_reference_limits", None)
    assert callable(get_limits)

    seedance_20 = get_limits("doubao-seedance-2-0-260128")
    assert seedance_20["images"] == 9
    assert seedance_20["videos"] == 3
    assert seedance_20["audios"] == 3
    assert seedance_20["at_reference"] is True
    assert seedance_20["native_audio"] is True

    fast = get_limits("volcano.seedance.2_0_fast")
    assert fast["images"] == 9
    assert fast["at_reference"] is True

    legacy = get_limits("Doubao-Seedance-1.0-pro-fast")
    assert legacy == {
        "images": 1,
        "videos": 0,
        "audios": 0,
        "at_reference": False,
        "native_audio": False,
    }
    assert get_limits("doubao-seedance-2.0-fast") == fast
    assert get_limits("doubao-seedance-2.0-pro") == legacy
    assert get_limits("unknown-video-model") == legacy


@pytest.mark.asyncio
async def test_build_package_prioritizes_protagonist_views(db_session: AsyncSession) -> None:
    builder = _builder_module()
    build_reference_package = getattr(builder, "build_reference_package", None)
    assert callable(build_reference_package)

    user_id = f"user-{uuid4()}"
    shot = _shot(user_id)
    previous_shot = Shot(
        id=f"shot-prev-{uuid4()}",
        user_id=user_id,
        storyboard_id=shot.storyboard_id,
        shot_number=1,
        video_status="succeeded",
        video_url="https://cdn.example.com/previous-shot.mp4",
    )
    db_session.add(previous_shot)
    await _seed_reference_assets(db_session, user_id)

    package = await build_reference_package(
        db_session,
        user_id,
        shot=shot,
        lineage={},
        model_limits={"images": 9, "videos": 3, "audios": 3, "at_reference": True, "native_audio": True},
        resolve_public_url=_public_resolver,
    )

    assert [(item["entity_id"], item["view_key"]) for item in package["images"][:3]] == [
        ("char-main", "front"),
        ("char-main", "side"),
        ("char-main", "back"),
    ]
    assert [(item["entity_type"], item["entity_id"], item["view_key"]) for item in package["images"][3:7]] == [
        ("scene", "scene-gate", "establishing"),
        ("prop", "prop-sword", "main"),
        ("prop", "prop-token", "main"),
        ("character", "char-side", "front"),
    ]
    assert [item["at_index"] for item in package["images"]] == list(range(1, len(package["images"]) + 1))
    assert all(item["url"].startswith("https://cdn.example.com/") for item in package["images"])
    assert package["videos"] == [
        {
            "url": "https://cdn.example.com/previous-shot.mp4",
            "role_tag": "previous_shot",
            "source_shot_id": previous_shot.id,
            "at_index": 1,
        }
    ]
    assert package["at_reference_text"] is not None
    assert package["at_reference_text"].startswith("@图1")
    assert "@图3" in package["at_reference_text"]
    assert "孙剑" in package["at_reference_text"]


@pytest.mark.asyncio
async def test_build_package_truncates_and_records_dropped(db_session: AsyncSession) -> None:
    builder = _builder_module()
    build_reference_package = getattr(builder, "build_reference_package", None)
    assert callable(build_reference_package)

    user_id = f"user-{uuid4()}"
    shot = _shot(user_id)
    await _seed_reference_assets(db_session, user_id)

    package = await build_reference_package(
        db_session,
        user_id,
        shot=shot,
        lineage={},
        model_limits={"images": 4, "videos": 0, "audios": 0, "at_reference": True, "native_audio": False},
        resolve_public_url=_public_resolver,
    )

    assert [(item["entity_id"], item["view_key"]) for item in package["images"]] == [
        ("char-main", "front"),
        ("char-main", "side"),
        ("char-main", "back"),
        ("scene-gate", "establishing"),
    ]
    assert len(package["dropped"]) == 3
    assert all(item["reason"] == "exceeds_model_reference_image_limit" for item in package["dropped"])
    assert [(item["entity_name"], item["view_key"]) for item in package["dropped"]] == [
        ("青锋剑", "main"),
        ("铜令牌", "main"),
        ("林遥", "front"),
    ]


@pytest.mark.asyncio
async def test_single_image_model_unchanged(db_session: AsyncSession) -> None:
    builder = _builder_module()
    build_reference_package = getattr(builder, "build_reference_package", None)
    assert callable(build_reference_package)

    user_id = f"user-{uuid4()}"
    shot = _shot(user_id, image_url="https://cdn.example.com/current-shot-reference.png")
    await _seed_reference_assets(db_session, user_id)

    package = await build_reference_package(
        db_session,
        user_id,
        shot=shot,
        lineage={},
        model_limits={"images": 1, "videos": 0, "audios": 0, "at_reference": False, "native_audio": False},
        resolve_public_url=_public_resolver,
    )

    assert package["images"] == [
        {
            "url": "https://cdn.example.com/current-shot-reference.png",
            "role_tag": "reference_image",
            "entity_type": None,
            "entity_id": None,
            "view_key": None,
            "at_index": 1,
        }
    ]
    assert package["reference_image"] == "https://cdn.example.com/current-shot-reference.png"
    assert package["reference_image_source"] == "shot_image"
    assert package["at_reference_text"] is None
    assert package["dropped"] == []


@pytest.mark.asyncio
async def test_build_package_includes_shot_audio_when_model_allows_audio(db_session: AsyncSession) -> None:
    builder = _builder_module()
    build_reference_package = getattr(builder, "build_reference_package", None)
    assert callable(build_reference_package)

    user_id = f"user-{uuid4()}"
    shot = _shot(
        user_id,
        image_url="https://cdn.example.com/current-shot-reference.png",
        audio_url="https://cdn.example.com/current-shot-dialogue.mp3",
    )
    await _seed_reference_assets(db_session, user_id)
    db_session.add(
        Asset(
            id=f"asset-audio-{uuid4()}",
            user_id=user_id,
            category="voice",
            asset_type="audio",
            name="孙剑锁定声线",
            url="https://cdn.example.com/locked-voice.mp3",
            is_active=True,
            is_locked=True,
            is_final=True,
        )
    )
    await db_session.flush()

    package = await build_reference_package(
        db_session,
        user_id,
        shot=shot,
        lineage={},
        model_limits={"images": 1, "videos": 0, "audios": 1, "at_reference": False, "native_audio": True},
        resolve_public_url=_public_resolver,
    )

    assert [item["url"] for item in package["images"]] == ["https://cdn.example.com/current-shot-reference.png"]
    assert package["audios"] == [
        {
            "url": "https://cdn.example.com/current-shot-dialogue.mp3",
            "role_tag": "shot_audio",
            "source_id": shot.id,
            "at_index": 1,
        }
    ]
    assert package["reference_image"] == "https://cdn.example.com/current-shot-reference.png"
    assert len(package["dropped"]) == 1
    assert package["dropped"][0]["reason"] == "exceeds_model_reference_audio_limit"
    assert package["dropped"][0]["entity_name"] == "孙剑锁定声线"


@pytest.mark.asyncio
async def test_non_public_urls_skipped_unless_resolver_maps_public_url(db_session: AsyncSession) -> None:
    builder = _builder_module()
    build_reference_package = getattr(builder, "build_reference_package", None)
    assert callable(build_reference_package)

    user_id = f"user-{uuid4()}"
    shot = Shot(
        id=f"shot-{uuid4()}",
        user_id=user_id,
        storyboard_id=f"storyboard-{uuid4()}",
        shot_number=1,
        character_refs=[{"entity_id": "char-local", "name": "本地角色"}],
        extra_data={"entity_refs": {"characters": [{"entity_id": "char-local", "name": "本地角色"}]}},
    )
    db_session.add_all(
        [
            _entity(user_id, "char-local", "character", "本地角色"),
            _asset(
                user_id,
                "char-local",
                "character",
                "front",
                "本地角色正面",
                url="/static/generated/images/local-front.png",
            ),
        ]
    )
    await db_session.flush()

    package = await build_reference_package(
        db_session,
        user_id,
        shot=shot,
        lineage={},
        model_limits={"images": 9, "videos": 0, "audios": 0, "at_reference": True, "native_audio": False},
        resolve_public_url=_public_resolver,
    )

    assert package["images"] == []
    assert len(package["dropped"]) == 1
    assert "公网" in package["dropped"][0]["reason"]

    mapped = await build_reference_package(
        db_session,
        user_id,
        shot=shot,
        lineage={},
        model_limits={"images": 9, "videos": 0, "audios": 0, "at_reference": True, "native_audio": False},
        resolve_public_url=_cdn_resolver,
    )

    assert [item["url"] for item in mapped["images"]] == [
        "https://cdn.example.com/static/generated/images/local-front.png"
    ]
    assert mapped["dropped"] == []


def test_provider_content_adapter_submits_multimodal_references() -> None:
    adapter = _adapter_module()
    build_provider_content = getattr(adapter, "build_video_provider_content", None)
    assert callable(build_provider_content)

    result = build_provider_content(
        final_prompt="孙剑踏入旧山门，镜头缓慢推进",
        duration=8,
        resolution="720p",
        provider_image_url="https://cdn.example.com/fallback.png",
        reference_package={
            "images": [
                {"url": "https://cdn.example.com/sunjian-front.png", "role_tag": "protagonist", "at_index": 1},
                {"url": "https://cdn.example.com/sunjian-side.png", "role_tag": "protagonist", "at_index": 2},
            ],
            "videos": [
                {"url": "https://cdn.example.com/previous-shot.mp4", "role_tag": "previous_shot", "at_index": 1}
            ],
            "audios": [
                {"url": "https://cdn.example.com/voice-lock.mp3", "role_tag": "voice_lock", "at_index": 1}
            ],
            "at_reference_text": "@图1为主角孙剑正面形象基准；@图2为主角孙剑侧面形象基准",
        },
        model_limits={"images": 9, "videos": 3, "audios": 3, "at_reference": True, "native_audio": False},
        model_id="doubao-seedance-2-0-260128",
        provider="volcano",
    )

    assert result["mode"] == "multimodal"
    assert [item["type"] for item in result["content"]] == ["image_url", "image_url", "video_url", "audio_url", "text"]
    assert result["content"][0] == {
        "type": "image_url",
        "image_url": {"url": "https://cdn.example.com/sunjian-front.png"},
        "role": "reference_image",
    }
    assert result["content"][2] == {
        "type": "video_url",
        "video_url": {"url": "https://cdn.example.com/previous-shot.mp4"},
        "role": "reference_video",
    }
    assert result["content"][3] == {
        "type": "audio_url",
        "audio_url": {"url": "https://cdn.example.com/voice-lock.mp3"},
        "role": "reference_audio",
    }
    assert result["content"][-1]["text"].startswith("@图1为主角孙剑正面形象基准")
    assert "--duration 8 --resolution 720p --camerafixed false --watermark true" in result["content"][-1]["text"]
    assert result["metadata"] == {
        "mode": "multimodal",
        "image_count": 2,
        "video_count": 1,
        "audio_count": 1,
        **_seedance_contract_metadata(),
    }


def test_provider_content_adapter_keeps_single_image_shape_when_limits_do_not_allow_multimodal() -> None:
    adapter = _adapter_module()
    build_provider_content = getattr(adapter, "build_video_provider_content", None)
    assert callable(build_provider_content)

    result = build_provider_content(
        final_prompt="旧山门外的定场镜头",
        duration=4,
        resolution="480p",
        provider_image_url="https://cdn.example.com/current-shot.png",
        reference_package={
            "images": [
                {"url": "https://cdn.example.com/sunjian-front.png", "role_tag": "protagonist", "at_index": 1},
                {"url": "https://cdn.example.com/sunjian-side.png", "role_tag": "protagonist", "at_index": 2},
            ],
            "videos": [],
            "at_reference_text": "@图1为主角孙剑正面形象基准",
        },
        model_limits={"images": 1, "videos": 0, "audios": 0, "at_reference": False, "native_audio": False},
    )

    assert result["mode"] == "single_image"
    assert result["content"] == [
        {"type": "image_url", "image_url": {"url": "https://cdn.example.com/current-shot.png"}},
        {
            "type": "text",
            "text": "旧山门外的定场镜头 --duration 4 --resolution 480p --camerafixed false --watermark true",
        },
    ]
    assert result["metadata"]["image_count"] == 1
    assert result["metadata"]["video_count"] == 0


def test_provider_content_adapter_allows_audio_with_single_image_limit() -> None:
    adapter = _adapter_module()
    build_provider_content = getattr(adapter, "build_video_provider_content", None)
    assert callable(build_provider_content)

    result = build_provider_content(
        final_prompt="旧山门外的定场镜头",
        duration=4,
        resolution="480p",
        provider_image_url="https://cdn.example.com/current-shot.png",
        reference_package={
            "images": [
                {"url": "https://cdn.example.com/current-shot.png", "role_tag": "reference_image", "at_index": 1},
            ],
            "videos": [],
            "audios": [
                {"url": "https://cdn.example.com/current-shot-dialogue.mp3", "role_tag": "shot_audio", "at_index": 1},
            ],
        },
        model_limits={"images": 1, "videos": 0, "audios": 1, "at_reference": False, "native_audio": True},
        model_id="doubao-seedance-2-0-260128",
        provider="volcano",
    )

    assert result["mode"] == "multimodal"
    assert [item["type"] for item in result["content"]] == ["image_url", "audio_url", "text"]
    assert result["content"][1] == {
        "type": "audio_url",
        "audio_url": {"url": "https://cdn.example.com/current-shot-dialogue.mp3"},
        "role": "reference_audio",
    }
    assert result["metadata"] == {
        "mode": "multimodal",
        "image_count": 1,
        "video_count": 0,
        "audio_count": 1,
        **_seedance_contract_metadata(),
    }


def test_provider_content_adapter_allows_audio_without_image_capacity() -> None:
    adapter = _adapter_module()
    build_provider_content = getattr(adapter, "build_video_provider_content", None)
    assert callable(build_provider_content)

    result = build_provider_content(
        final_prompt="旧山门外只有对白音频参考",
        duration=4,
        resolution="480p",
        provider_image_url="https://cdn.example.com/ignored.png",
        reference_package={
            "images": [],
            "videos": [],
            "audios": [
                {"url": "https://cdn.example.com/current-shot-dialogue.mp3", "role_tag": "shot_audio", "at_index": 1},
            ],
        },
        model_limits={"images": 0, "videos": 0, "audios": 1, "at_reference": False, "native_audio": True},
        model_id="doubao-seedance-2-0-260128",
        provider="volcano",
    )

    assert result["mode"] == "multimodal"
    assert [item["type"] for item in result["content"]] == ["audio_url", "text"]
    assert result["content"][0] == {
        "type": "audio_url",
        "audio_url": {"url": "https://cdn.example.com/current-shot-dialogue.mp3"},
        "role": "reference_audio",
    }
    assert result["metadata"] == {
        "mode": "multimodal",
        "image_count": 0,
        "video_count": 0,
        "audio_count": 1,
        **_seedance_contract_metadata(),
    }


def test_provider_content_adapter_keeps_media_references_without_images() -> None:
    adapter = _adapter_module()
    build_provider_content = getattr(adapter, "build_video_provider_content", None)
    assert callable(build_provider_content)

    result = build_provider_content(
        final_prompt="旧山门内烛火摇动，角色暂未入镜",
        duration=6,
        resolution="720p",
        provider_image_url=None,
        reference_package={
            "images": [],
            "videos": [
                {"url": "https://cdn.example.com/previous-shot.mp4", "role_tag": "previous_shot", "at_index": 1}
            ],
            "audios": [
                {"url": "https://cdn.example.com/voice-lock.mp3", "role_tag": "voice_lock", "at_index": 1}
            ],
        },
        model_limits={"images": 9, "videos": 1, "audios": 1, "at_reference": True, "native_audio": False},
        model_id="doubao-seedance-2-0-260128",
        provider="volcano",
    )

    assert result["mode"] == "multimodal"
    assert [item["type"] for item in result["content"]] == ["video_url", "audio_url", "text"]
    assert result["content"][0] == {
        "type": "video_url",
        "video_url": {"url": "https://cdn.example.com/previous-shot.mp4"},
        "role": "reference_video",
    }
    assert result["content"][1] == {
        "type": "audio_url",
        "audio_url": {"url": "https://cdn.example.com/voice-lock.mp3"},
        "role": "reference_audio",
    }
    assert result["metadata"] == {
        "mode": "multimodal",
        "image_count": 0,
        "video_count": 1,
        "audio_count": 1,
        **_seedance_contract_metadata(),
    }


def test_provider_content_adapter_respects_text_only_model_contract() -> None:
    adapter = _adapter_module()
    build_provider_content = getattr(adapter, "build_video_provider_content", None)
    assert callable(build_provider_content)

    result = build_provider_content(
        final_prompt="纯文字生成镜头，不应发送任何参考图",
        duration=5,
        resolution="720P",
        provider_image_url="https://cdn.example.com/should-not-send.png",
        reference_package={
            "images": [
                {"url": "https://cdn.example.com/sunjian-front.png", "role_tag": "protagonist", "at_index": 1},
            ],
            "videos": [],
            "audios": [],
            "at_reference_text": "@图1为主角孙剑正面形象基准",
        },
        model_limits={"images": 0, "videos": 0, "audios": 0, "at_reference": False, "native_audio": False},
    )

    assert result["mode"] == "text_only"
    assert result["content"] == [
        {
            "type": "text",
            "text": "纯文字生成镜头，不应发送任何参考图 --duration 5 --resolution 720P --camerafixed false --watermark true",
        },
    ]
    assert result["metadata"]["image_count"] == 0


def test_provider_content_records_seedance_contract_status() -> None:
    adapter = _adapter_module()
    build_content = getattr(adapter, "build_video_provider_content")

    result = build_content(
        final_prompt="米粒举起星灯尾巴，照亮雨夜屋顶。",
        duration=4,
        resolution="720p",
        reference_package={
            "images": [{"url": "https://cdn.example.com/mili-front.png"}],
            "videos": [{"url": "https://cdn.example.com/prev-shot.mp4"}],
            "audios": [{"url": "https://cdn.example.com/voice.wav"}],
            "at_reference_text": "@image1 主角定稿图；@video1 上一镜头；@audio1 角色声线。",
        },
        model_limits={"images": 9, "videos": 3, "audios": 3},
        model_id="doubao-seedance-2-0-260128",
        provider="volcano",
    )

    metadata = result["metadata"]
    assert metadata["contract_status"] == "experimental"
    assert metadata["contract_model_family"] == "seedance_2"
    assert metadata["contract_roles"] == {
        "image": "reference_image",
        "video": "reference_video",
        "audio": "reference_audio",
    }
    assert metadata["contract_pricing_status"] == "unconfirmed"


def test_provider_content_without_model_id_does_not_infer_seedance_contract() -> None:
    adapter = _adapter_module()
    build_content = getattr(adapter, "build_video_provider_content")

    result = build_content(
        final_prompt="米粒举起星灯尾巴，照亮雨夜屋顶。",
        duration=4,
        resolution="720p",
        reference_package={
            "images": [{"url": "https://cdn.example.com/mili-front.png"}],
            "videos": [{"url": "https://cdn.example.com/prev-shot.mp4"}],
            "audios": [{"url": "https://cdn.example.com/voice.wav"}],
        },
        model_limits={"images": 9, "videos": 3, "audios": 3},
    )

    assert result["mode"] == "multimodal"
    assert [item["type"] for item in result["content"]] == ["image_url", "video_url", "audio_url", "text"]
    metadata = result["metadata"]
    assert metadata["contract_model_family"] == "legacy"
    assert metadata["contract_status"] == "legacy_single_reference"


def test_non_seedance_contract_limits_keep_registry_multireference_limits() -> None:
    adapter = _adapter_module()
    apply_limits = getattr(adapter, "apply_seedance_contract_limits")
    build_content = getattr(adapter, "build_video_provider_content")

    limits = {"images": 9, "videos": 3, "audios": 2}
    assert apply_limits(
        limits,
        model_id="happyhorse-1.1-r2v",
        provider="alibaba",
    ) == limits

    result = build_content(
        final_prompt="米粒举起星灯尾巴，照亮雨夜屋顶。",
        duration=4,
        resolution="720p",
        reference_package={
            "images": [{"url": "https://cdn.example.com/mili-front.png"}],
            "videos": [{"url": "https://cdn.example.com/prev-shot.mp4"}],
            "audios": [{"url": "https://cdn.example.com/voice.wav"}],
        },
        model_limits=limits,
        model_id="happyhorse-1.1-r2v",
        provider="alibaba",
    )

    assert result["mode"] == "multimodal"
    assert [item["type"] for item in result["content"]] == ["image_url", "video_url", "audio_url", "text"]
    assert result["metadata"]["contract_model_family"] == "legacy"


def test_provider_content_clamps_agent_plan_to_single_reference() -> None:
    adapter = _adapter_module()
    build_content = getattr(adapter, "build_video_provider_content")

    result = build_content(
        final_prompt="米粒举起星灯尾巴，照亮雨夜屋顶。",
        duration=4,
        resolution="720p",
        reference_package={
            "images": [
                {"url": "https://cdn.example.com/mili-front.png"},
                {"url": "https://cdn.example.com/mili-side.png"},
            ],
            "videos": [{"url": "https://cdn.example.com/prev-shot.mp4"}],
            "audios": [{"url": "https://cdn.example.com/voice.wav"}],
        },
        model_limits={"images": 9, "videos": 3, "audios": 3},
        model_id="doubao-seedance-2.0-fast",
        provider="volcano_agent_plan",
    )

    assert result["mode"] == "single_image"
    assert result["content"] == [
        {"type": "image_url", "image_url": {"url": "https://cdn.example.com/mili-front.png"}},
        {
            "type": "text",
            "text": "米粒举起星灯尾巴，照亮雨夜屋顶。 --duration 4 --resolution 720p --camerafixed false --watermark true",
        },
    ]
    metadata = result["metadata"]
    assert metadata["image_count"] == 1
    assert metadata["video_count"] == 0
    assert metadata["audio_count"] == 0
    assert metadata["contract_agent_plan_multireference"] is False
