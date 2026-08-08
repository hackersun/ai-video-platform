from types import SimpleNamespace

import pytest

from app.services.shot_reference_input_service import (
    ShotReferenceInputError,
    locked_asset_ids,
    resolve_shot_reference_images,
)
from app.services.series_run_reference_preparation import reference_visual_contract_hash
from app.models.asset import Asset


def test_locked_asset_ids_are_stable_and_deduplicated() -> None:
    shot = SimpleNamespace(extra_data={"production_context": {"asset_version_locks": [
        {"asset_id": "asset-1", "locked": True},
        {"asset_id": "asset-1", "locked": True},
        {"asset_id": "asset-2", "locked": True},
    ]}})

    assert locked_asset_ids(shot) == ["asset-1", "asset-2"]


@pytest.mark.asyncio
async def test_locked_asset_is_refreshed_to_provider_accessible_reference(monkeypatch) -> None:
    shot = SimpleNamespace(extra_data={"production_context": {"asset_version_locks": [
        {"asset_id": "asset-1", "locked": True},
    ]}})
    asset = SimpleNamespace(
        id="asset-1", url="https://expired.example.test/reference.jpg", thumbnail_url=None,
        generation_params={"evidence": {"storage_delivery": {
            "canonical_local_url": "/static/generated/reference.jpg",
        }}},
    )

    class Result:
        def all(self):
            return [asset]

    class DB:
        async def scalars(self, _query):
            return Result()

    async def resolve(_db, _user_id, canonical_url, **_kwargs):
        assert canonical_url == "/static/generated/reference.jpg"
        return {"provider_url": "https://cdn.example.test/fresh-reference.jpg"}

    monkeypatch.setattr("app.services.shot_reference_input_service.resolve_original_image", resolve)

    assert await resolve_shot_reference_images(DB(), "user-1", shot, required=True) == [
        "https://cdn.example.test/fresh-reference.jpg",
    ]


@pytest.mark.asyncio
async def test_local_locked_asset_is_registered_before_being_sent_to_provider(monkeypatch) -> None:
    shot = SimpleNamespace(id="shot-1", character_refs=[], extra_data={"production_context": {
        "asset_version_locks": [{"asset_id": "asset-1", "locked": True}],
    }})
    asset = Asset(
        id="asset-1", user_id="user-1", category="character", name="角色三视图",
        asset_type="image", url="/static/generated/images/ref.jpg",
        project_id="project-1", generation_params={}, is_active=True,
    )

    class Result:
        def all(self): return [asset]

    class DB:
        async def scalars(self, _query): return Result()

    registered = {}

    async def resolve(_db, _user_id, canonical_url, **kwargs):
        kwargs["canonical_url"] = canonical_url
        registered.update(kwargs)
        return {
            "provider_url": "https://private.test/ref.jpg?e=1900000000&token=hidden",
            "delivery_method": "qiniu_object_upload", "storage_config_id": "storage-1",
            "object_key": "private/original/user-1/ref.jpg",
        }

    monkeypatch.setattr("app.services.shot_reference_input_service.resolve_original_image", resolve)

    result = await resolve_shot_reference_images(DB(), "user-1", shot, required=True)

    assert result == ["https://private.test/ref.jpg?e=1900000000&token=hidden"]
    assert registered["canonical_url"] == "/static/generated/images/ref.jpg"
    assert registered["project_id"] == "project-1"


@pytest.mark.asyncio
async def test_live_run_reference_is_used_before_shot_media_context_is_activated(monkeypatch) -> None:
    shot = SimpleNamespace(id="shot-1", character_refs=[], extra_data={})
    asset = SimpleNamespace(
        id="series-reference-1", url="https://cdn.example.test/reference.jpg", thumbnail_url=None,
        generation_params={},
    )

    class Result:
        def all(self): return [asset]

    class DB:
        async def scalars(self, _query): return Result()

    async def resolve(*_args, **_kwargs):
        return {"provider_url": "https://cdn.example.test/reference.jpg"}

    monkeypatch.setattr("app.services.shot_reference_input_service.resolve_original_image", resolve)
    result = await resolve_shot_reference_images(
        DB(), "user-1", shot, required=True,
        fallback_asset_ids=["series-reference-1"],
    )
    assert result == ["https://cdn.example.test/reference.jpg"]


@pytest.mark.asyncio
async def test_manual_repair_can_add_same_novel_shot_identity_reference(monkeypatch) -> None:
    shot = SimpleNamespace(id="shot-1", user_id="user-1", image_url=None, extra_data={})
    reference_shot = SimpleNamespace(
        id="shot-2", user_id="user-1", image_status="succeeded",
        image_url="/static/generated/shot-2.jpg", extra_data={},
    )
    asset = SimpleNamespace(
        id="series-reference-1", url="/static/generated/reference.jpg", thumbnail_url=None,
        generation_params={},
    )

    class Result:
        def __init__(self, rows): self.rows = rows
        def all(self): return self.rows

    class DB:
        calls = 0
        async def scalars(self, _query):
            self.calls += 1
            return Result([asset] if self.calls == 1 else [reference_shot])

    async def resolve_registered(_db, _user_id, canonical_url, **_kwargs):
        return {"provider_url": f"https://cdn.example.test/{canonical_url.rsplit('/', 1)[-1]}"}

    monkeypatch.setattr("app.services.shot_reference_input_service.resolve_original_image", resolve_registered)
    async def same_novel(*_args, **_kwargs): return True
    monkeypatch.setattr("app.services.shot_reference_input_service._same_novel", same_novel)
    result = await resolve_shot_reference_images(
        DB(), "user-1", shot, required=True,
        fallback_asset_ids=["series-reference-1"],
        continuity_reference_shot_id="shot-2",
    )
    assert result == [
        "https://cdn.example.test/shot-2.jpg",
        "https://cdn.example.test/reference.jpg",
    ]


@pytest.mark.asyncio
async def test_locked_reference_delivery_fails_closed(monkeypatch) -> None:
    shot = SimpleNamespace(extra_data={"production_context": {"asset_version_locks": [
        {"asset_id": "asset-1", "locked": True},
    ]}})
    asset = SimpleNamespace(id="asset-1", url=None, thumbnail_url=None, generation_params={})

    class Result:
        def all(self):
            return [asset]

    class DB:
        async def scalars(self, _query):
            return Result()

    with pytest.raises(ShotReferenceInputError) as error:
        await resolve_shot_reference_images(DB(), "user-1", shot, required=True)

    assert error.value.detail["code"] == "shot_reference_image_unavailable"


@pytest.mark.asyncio
async def test_locked_reference_with_stale_character_wardrobe_fails_before_provider(monkeypatch) -> None:
    shot = SimpleNamespace(
        id="shot-1",
        character_refs=[{"canonical_entity_id": "character-shen"}],
        extra_data={"production_context": {"asset_version_locks": [
            {"asset_id": "asset-1", "locked": True},
        ]}},
    )
    asset = SimpleNamespace(
        id="asset-1", url="https://cdn.example.test/reference.jpg", thumbnail_url=None,
        generation_params={"evidence": {"visual_contract_hash": "old-contract"}},
    )
    character = SimpleNamespace(
        id="character-shen",
        attributes={"visual_dna": {"costume": "深蓝旧呢大衣"}},
    )

    class Result:
        def __init__(self, rows): self.rows = rows
        def all(self): return self.rows

    class DB:
        calls = 0
        async def scalars(self, _query):
            self.calls += 1
            return Result([asset] if self.calls == 1 else [character])

    with pytest.raises(ShotReferenceInputError) as error:
        await resolve_shot_reference_images(DB(), "user-1", shot, required=True)

    assert error.value.detail["code"] == "shot_reference_visual_contract_stale"
    assert error.value.detail["repair_action"] == "regenerate_locked_reference"


@pytest.mark.asyncio
async def test_single_character_shot_uses_only_its_locked_multiview_and_style(monkeypatch) -> None:
    def view(asset_id: str, entity_id: str, key: str):
        return SimpleNamespace(
            id=asset_id, entity_id=entity_id, entity_type="character", category="character",
            url=f"https://cdn.example.test/{asset_id}.jpg", thumbnail_url=None,
            generation_params={"source": "entity_multiview", "status": "succeeded", "view_key": key},
        )

    assets = [
        *(view(f"one-{key}", "character-one", key) for key in ("front", "side", "back")),
        *(view(f"two-{key}", "character-two", key) for key in ("front", "side", "back")),
        SimpleNamespace(
            id="style", entity_id=None, entity_type=None, category="style",
            url="https://cdn.example.test/style.jpg", thumbnail_url=None,
            generation_params={"canonical_roles": ["global_style_board"]},
        ),
    ]
    shot = SimpleNamespace(
        id="shot-1", character_refs=[{"canonical_entity_id": "character-one"}],
        extra_data={"production_context": {"asset_version_locks": [
            {"asset_id": asset.id, "locked": True} for asset in assets
        ]}},
    )

    class Result:
        def all(self): return assets

    class DB:
        async def scalars(self, _query): return Result()

    async def resolve(_db, _user_id, canonical_url, **_kwargs):
        return {"provider_url": canonical_url}

    monkeypatch.setattr("app.services.shot_reference_input_service.resolve_original_image", resolve)

    result = await resolve_shot_reference_images(DB(), "user-1", shot, required=True)

    assert result == [
        "https://cdn.example.test/one-front.jpg",
        "https://cdn.example.test/one-side.jpg",
        "https://cdn.example.test/one-back.jpg",
        "https://cdn.example.test/style.jpg",
    ]


@pytest.mark.asyncio
async def test_multi_character_composite_is_ambiguous_for_single_character_shot(monkeypatch) -> None:
    character_one = SimpleNamespace(id="character-one", attributes={"visual_dna": {"costume": "霜蓝法袍"}})
    character_two = SimpleNamespace(id="character-two", attributes={"visual_dna": {"costume": "玄黑剑服"}})
    asset = SimpleNamespace(
        id="asset-1", entity_id="character-one", entity_type="character", category="style",
        url="https://cdn.example.test/reference.jpg", thumbnail_url=None,
        generation_params={
            "composite_reference_rule": "single_artifact_dual_role_v1",
            "role_bindings": [
                {"role": "character_canonical", "entity_id": "character-one"},
                {"role": "character_canonical", "entity_id": "character-two"},
            ],
            "evidence": {"visual_contract_hash": reference_visual_contract_hash([character_one, character_two])},
        },
    )
    shot = SimpleNamespace(
        id="shot-1", character_refs=[{"canonical_entity_id": "character-one"}],
        extra_data={"production_context": {"asset_version_locks": [{"asset_id": "asset-1", "locked": True}]}},
    )

    class Result:
        def __init__(self, rows): self.rows = rows
        def all(self): return self.rows

    class DB:
        calls = 0
        async def scalars(self, _query):
            self.calls += 1
            return Result([asset] if self.calls == 1 else [character_one, character_two])

    async def resolve(*_args, **_kwargs): return {"provider_url": asset.url}
    monkeypatch.setattr("app.services.shot_reference_input_service.resolve_original_image", resolve)
    with pytest.raises(ShotReferenceInputError) as error:
        await resolve_shot_reference_images(DB(), "user-1", shot, required=True)

    assert error.value.detail["code"] == "shot_reference_character_ambiguous"
    assert error.value.detail["repair_action"] == "generate_and_lock_character_multiview"


@pytest.mark.asyncio
async def test_multi_character_composite_is_allowed_when_shot_contract_names_every_bound_character(monkeypatch) -> None:
    character_one = SimpleNamespace(
        id="character-one", name="沈砚", canonical_name="沈砚",
        appearance="黑发蓝袍", attributes={"visual_dna": {"costume": "蓝袍"}},
    )
    character_two = SimpleNamespace(
        id="character-two", name="洛青璃", canonical_name="洛青璃",
        appearance="银蓝发白袍", attributes={"visual_dna": {"costume": "白袍"}},
    )
    asset = SimpleNamespace(
        id="asset-1", entity_id="character-one", entity_type="character", category="style",
        url="https://cdn.example.test/reference.jpg", thumbnail_url=None,
        generation_params={
            "composite_reference_rule": "single_artifact_dual_role_v1",
            "role_bindings": [
                {"role": "character_canonical", "entity_id": "character-one"},
                {"role": "character_canonical", "entity_id": "character-two"},
            ],
            "evidence": {"visual_contract_hash": reference_visual_contract_hash([character_one, character_two])},
        },
    )
    shot = SimpleNamespace(
        id="shot-1",
        character_refs=[{"canonical_entity_id": "character-one"}],
        character_prompt="沈砚与洛青璃并肩迎敌；两人的发色、服装和武器保持锁定设定。",
        prompt="", visual_description="",
        extra_data={"production_context": {"asset_version_locks": [{"asset_id": "asset-1", "locked": True}]}},
    )

    class Result:
        def __init__(self, rows): self.rows = rows
        def all(self): return self.rows

    class DB:
        calls = 0
        async def scalars(self, _query):
            self.calls += 1
            return Result([asset] if self.calls == 1 else [character_one, character_two])

    async def resolve(*_args, **_kwargs): return {"provider_url": asset.url}
    monkeypatch.setattr("app.services.shot_reference_input_service.resolve_original_image", resolve)

    result = await resolve_shot_reference_images(DB(), "user-1", shot, required=True)

    assert result == [asset.url]
