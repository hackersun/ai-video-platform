"""Select one locked composite anchor for single-image video models."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset
from app.services.entity_ref_normalizer import normalize_entity_refs


def _locked_ids(shot: Any) -> list[str]:
    extra = shot.extra_data if isinstance(getattr(shot, "extra_data", None), dict) else {}
    production = extra.get("production_context") if isinstance(extra.get("production_context"), dict) else {}
    return list(dict.fromkeys(
        str(item.get("asset_id")) for item in (production.get("asset_version_locks") or [])
        if isinstance(item, dict) and item.get("asset_id") and item.get("locked") is not False
    ))


def _shot_character_ids(shot: Any) -> set[str]:
    extra = shot.extra_data if isinstance(getattr(shot, "extra_data", None), dict) else {}
    refs = normalize_entity_refs(extra.get("entity_refs")).get("characters") or []
    refs = [*(getattr(shot, "character_refs", None) or []), *refs]
    return {
        str(ref.get("canonical_entity_id") or ref.get("entity_id") or ref.get("character_id"))
        for ref in refs if isinstance(ref, dict)
        and (ref.get("canonical_entity_id") or ref.get("entity_id") or ref.get("character_id"))
    }


def _covers_shot(asset: Asset, character_ids: set[str]) -> bool:
    params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
    if params.get("composite_reference_rule") != "single_artifact_dual_role_v1":
        return False
    bound = {
        str(item.get("entity_id")) for item in (params.get("role_bindings") or [])
        if isinstance(item, dict) and item.get("role") == "character_canonical" and item.get("entity_id")
    }
    return bool(bound and (not character_ids or character_ids.issubset(bound)))


async def find_locked_composite_anchor(
    db: AsyncSession, *, user_id: str, shot: Any,
) -> Asset | None:
    asset_ids = _locked_ids(shot)
    if not asset_ids:
        return None
    assets = list((await db.scalars(select(Asset).where(
        Asset.id.in_(asset_ids), Asset.user_id == user_id,
        Asset.is_active.is_(True), Asset.is_locked.is_(True),
    ))).all())
    by_id = {asset.id: asset for asset in assets}
    character_ids = _shot_character_ids(shot)
    return next((
        asset for asset_id in asset_ids
        if (asset := by_id.get(asset_id)) is not None
        and (asset.url or asset.thumbnail_url) and _covers_shot(asset, character_ids)
    ), None)


__all__ = ["find_locked_composite_anchor"]
