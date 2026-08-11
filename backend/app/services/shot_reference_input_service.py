"""Resolve locked series assets into provider-safe shot image references."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, Shot, StoryEntity, Storyboard
from app.features.private_media.integration import resolve_original_image
from app.services.series_run_reference_preparation import reference_visual_contract_hash


class ShotReferenceInputError(ValueError):
    def __init__(self, detail: dict[str, Any]) -> None:
        super().__init__(str(detail.get("message") or detail.get("code")))
        self.detail = detail


def locked_asset_ids(shot: object) -> list[str]:
    extra = getattr(shot, "extra_data", None)
    production = (extra if isinstance(extra, dict) else {}).get("production_context") or {}
    locks = production.get("asset_version_locks") if isinstance(production, dict) else []
    return list(dict.fromkeys(
        str(item.get("asset_id"))
        for item in (locks or [])
        if isinstance(item, dict) and item.get("asset_id") and item.get("locked") is not False
    ))


def _canonical_source(asset: Asset) -> str:
    params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
    evidence = params.get("evidence") if isinstance(params.get("evidence"), dict) else {}
    delivery = evidence.get("storage_delivery") if isinstance(evidence.get("storage_delivery"), dict) else {}
    return str(delivery.get("canonical_local_url") or asset.url or asset.thumbnail_url or "").strip()


def _unavailable(shot: object, message: str) -> ShotReferenceInputError:
    return ShotReferenceInputError({
        "code": "shot_reference_image_unavailable",
        "message": message,
        "shot_id": str(getattr(shot, "id", "") or ""),
        "repair_action": "refresh_or_regenerate_locked_reference",
    })


def _character_entity_ids(shot: object) -> list[str]:
    refs = getattr(shot, "character_refs", None) or []
    return list(dict.fromkeys(
        str(ref.get("canonical_entity_id") or ref.get("entity_id"))
        for ref in refs if isinstance(ref, dict) and (ref.get("canonical_entity_id") or ref.get("entity_id"))
    ))


def _asset_character_ids(asset: Asset) -> list[str]:
    params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
    bindings = params.get("role_bindings") if isinstance(params.get("role_bindings"), list) else []
    bound = [
        str(item.get("entity_id"))
        for item in bindings
        if isinstance(item, dict) and item.get("role") == "character_canonical" and item.get("entity_id")
    ]
    entity_id = str(getattr(asset, "entity_id", "") or "")
    entity_type = str(getattr(asset, "entity_type", "") or "")
    if entity_id and entity_type == "character":
        bound.append(entity_id)
    return list(dict.fromkeys(bound))


def _is_entity_multiview(asset: Asset) -> bool:
    params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
    return params.get("source") == "entity_multiview" and bool(_asset_character_ids(asset))


def _is_style_only(asset: Asset) -> bool:
    params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
    roles = set(params.get("canonical_roles") or [])
    return "global_style_board" in roles and not _asset_character_ids(asset)


def _assets_for_shot(
    shot: object, assets: list[Asset], *, character_entity_ids: list[str] | None = None,
) -> list[Asset]:
    shot_ids = set(character_entity_ids or _character_entity_ids(shot))
    if not shot_ids:
        return assets
    individual = [
        asset for asset in assets
        if _is_entity_multiview(asset) and set(_asset_character_ids(asset)).intersection(shot_ids)
    ]
    covered = {entity_id for asset in individual for entity_id in _asset_character_ids(asset)}
    if shot_ids.issubset(covered):
        return [*individual, *[asset for asset in assets if _is_style_only(asset)]]
    selected: list[Asset] = []
    for asset in assets:
        bound = set(_asset_character_ids(asset))
        params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
        if params.get("composite_reference_rule") == "single_artifact_dual_role_v1" and bound:
            if not bound.issubset(shot_ids):
                raise ShotReferenceInputError({
                    "code": "shot_reference_character_ambiguous",
                    "message": "当前参考板包含本镜头未出场的其他角色，无法保证人物身份一致；请先生成并锁定该角色三视图。",
                    "shot_id": str(getattr(shot, "id", "") or ""),
                    "repair_action": "generate_and_lock_character_multiview",
                    "shot_character_entity_ids": sorted(shot_ids),
                    "reference_character_entity_ids": sorted(bound),
                })
            selected.append(asset)
        elif not bound or bound.intersection(shot_ids):
            selected.append(asset)
    return selected


async def _explicit_composite_character_ids(
    db: AsyncSession, shot: object, assets: list[Asset], shot_ids: list[str],
) -> list[str]:
    bound_ids = {
        entity_id
        for asset in assets
        if (asset.generation_params or {}).get("composite_reference_rule") == "single_artifact_dual_role_v1"
        for entity_id in _asset_character_ids(asset)
    }
    current = set(shot_ids)
    missing = bound_ids - current
    if not missing:
        return shot_ids
    text = "\n".join(str(getattr(shot, field, "") or "") for field in (
        "character_prompt", "prompt", "visual_description",
    ))
    if not text.strip():
        return shot_ids
    entities = list((await db.scalars(select(StoryEntity).where(StoryEntity.id.in_(missing)))).all())
    for entity in entities:
        names = {
            str(getattr(entity, "name", "") or "").strip(),
            str(getattr(entity, "canonical_name", "") or "").strip(),
        }
        if any(len(name) >= 2 and name in text for name in names):
            current.add(str(entity.id))
    return [*shot_ids, *sorted(current - set(shot_ids))]


async def _verify_visual_contract(db: AsyncSession, shot: object, assets: list[Asset]) -> None:
    shot_entity_ids = _character_entity_ids(shot)
    guarded = [asset for asset in assets if (
        (asset.generation_params or {}).get("composite_reference_rule")
        or ((asset.generation_params or {}).get("evidence") or {}).get("visual_contract_hash")
    )]
    if not shot_entity_ids or not guarded:
        return
    contract_ids_by_asset: dict[str, list[str]] = {}
    all_entity_ids: set[str] = set()
    for asset in guarded:
        params = asset.generation_params or {}
        contract_ids = list(dict.fromkeys(
            str(item.get("entity_id")) for item in (params.get("role_bindings") or [])
            if isinstance(item, dict) and item.get("role") == "character_canonical" and item.get("entity_id")
        )) or shot_entity_ids
        contract_ids_by_asset[str(asset.id)] = contract_ids
        all_entity_ids.update(contract_ids)
    characters = list((await db.scalars(select(StoryEntity).where(StoryEntity.id.in_(all_entity_ids)))).all())
    character_by_id = {str(character.id): character for character in characters}
    for asset in guarded:
        contract_ids = contract_ids_by_asset[str(asset.id)]
        contract_characters = [character_by_id[item] for item in contract_ids if item in character_by_id]
        expected = reference_visual_contract_hash(contract_characters) if len(contract_characters) == len(contract_ids) else ""
        evidence = (asset.generation_params or {}).get("evidence") or {}
        if not set(shot_entity_ids).issubset(contract_ids) or not expected or evidence.get("visual_contract_hash") != expected:
            raise ShotReferenceInputError({
                "code": "shot_reference_visual_contract_stale",
                "message": "统一角色参考资产与当前锁定服装不一致，请重新生成参考设定板后再生成镜头。",
                "shot_id": str(getattr(shot, "id", "") or ""),
                "repair_action": "regenerate_locked_reference",
            })


async def resolve_shot_reference_images(
    db: AsyncSession, user_id: str, shot: object, *, required: bool = False,
    fallback_asset_ids: list[str] | None = None,
    continuity_reference_shot_id: str | None = None,
) -> list[str]:
    asset_ids = locked_asset_ids(shot) or list(dict.fromkeys(fallback_asset_ids or []))
    if not asset_ids:
        if required:
            raise _unavailable(shot, "当前镜头没有已锁定的统一角色参考资产，请先重新生成并锁定参考图。")
        return []
    assets = list((await db.scalars(select(Asset).where(
        Asset.id.in_(asset_ids), Asset.user_id == user_id, Asset.is_active.is_(True),
    ))).all())
    by_id = {str(asset.id): asset for asset in assets}
    if set(by_id) != set(asset_ids):
        raise _unavailable(shot, "镜头锁定的参考资产已失效或不属于当前用户，请刷新参考资产后重试。")
    ordered_assets = [by_id[asset_id] for asset_id in asset_ids]
    shot_character_ids = _character_entity_ids(shot)
    shot_character_ids = await _explicit_composite_character_ids(
        db, shot, ordered_assets, shot_character_ids,
    )
    selected_assets = _assets_for_shot(
        shot, ordered_assets, character_entity_ids=shot_character_ids,
    )
    if required and not selected_assets:
        raise _unavailable(shot, "当前镜头没有可复用的角色三视图，请先在资产工作台生成并锁定角色资产。")
    await _verify_visual_contract(db, shot, selected_assets)
    urls: list[str] = []
    for asset in selected_assets:
        source = _canonical_source(asset)
        delivery = await resolve_original_image(db, user_id, source, project_id=getattr(asset, "project_id", None))
        url = str(delivery.get("provider_url") or "").strip()
        if not url:
            raise _unavailable(shot, "统一角色参考资产无法生成供应商可访问地址，请检查七牛映射后重试。")
        if url not in urls:
            urls.append(url)
    if continuity_reference_shot_id:
        candidates = list((await db.scalars(select(Shot).where(
            Shot.id == continuity_reference_shot_id,
            Shot.user_id == user_id,
        ))).all())
        candidate = candidates[0] if candidates else None
        if (
            candidate is None
            or candidate.image_status != "succeeded"
            or not candidate.image_url
            or not await _same_novel(db, user_id, shot, candidate)
        ):
            raise _unavailable(shot, "选作人物延续参考的镜头不可用或不属于当前小说，请重新选择后重试。")
        delivery = await resolve_original_image(db, user_id, candidate.image_url)
        continuity_url = str(delivery.get("provider_url") or "").strip()
        if not continuity_url:
            raise _unavailable(shot, "人物延续参考图无法生成供应商可访问地址，请检查七牛映射后重试。")
        if continuity_url not in urls:
            urls.insert(0, continuity_url)
    return urls


async def _same_novel(db: AsyncSession, user_id: str, shot: object, candidate: Shot) -> bool:
    board_ids = [str(getattr(item, "storyboard_id", "") or "") for item in (shot, candidate)]
    if not all(board_ids):
        return False
    boards = list((await db.scalars(select(Storyboard).where(
        Storyboard.id.in_(board_ids), Storyboard.user_id == user_id,
    ))).all())
    novel_ids = {str(board.novel_id or "") for board in boards}
    return len(boards) == 2 and len(novel_ids) == 1 and "" not in novel_ids


__all__ = ["ShotReferenceInputError", "locked_asset_ids", "resolve_shot_reference_images"]
