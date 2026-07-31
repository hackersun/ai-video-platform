"""Rebind shot production locks when a canonical series reference is replaced."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models import Asset, Shot
from app.models.series_production_run import SeriesProductionRun


def rebind_shot_reference_context(
    shot: object,
    *,
    superseded_asset_id: str,
    replacement_asset_id: str,
    replacement_asset_version: int,
    rebound_at: str,
) -> bool:
    extra = dict(getattr(shot, "extra_data", None) or {})
    production = dict(extra.get("production_context") or {})
    locks = [dict(item) for item in production.get("asset_version_locks") or []]
    changed = False
    for item in locks:
        if str(item.get("asset_id") or "") != superseded_asset_id:
            continue
        item["asset_id"] = replacement_asset_id
        item["asset_version"] = replacement_asset_version
        item["locked"] = True
        changed = True
    if str(production.get("canonical_reference_id") or "") == superseded_asset_id:
        production["canonical_reference_id"] = replacement_asset_id
        production["canonical_reference_version"] = replacement_asset_version
        changed = True
    if not changed:
        return False
    production["asset_version_locks"] = locks
    production["reference_rebind"] = {
        "superseded_asset_id": superseded_asset_id,
        "replacement_asset_id": replacement_asset_id,
        "replacement_asset_version": replacement_asset_version,
        "rebound_at": rebound_at,
    }
    shot.extra_data = {**extra, "production_context": production}
    return True


async def rebind_run_shots_reference(
    db: AsyncSession,
    run: SeriesProductionRun,
    *,
    superseded_asset_id: str,
    replacement_asset: Asset,
    rebound_at: str,
) -> None:
    shot_ids = list(dict.fromkeys(
        str(shot_id)
        for episode in (run.episodes or [])
        for shot_id in ((episode.get("canonical_ids") or {}).get("shot_ids") or [])
        if shot_id
    ))
    if not shot_ids:
        return
    shots = list((await db.scalars(select(Shot).where(
        Shot.id.in_(shot_ids), Shot.user_id == run.user_id,
    ))).all())
    for shot in shots:
        if rebind_shot_reference_context(
            shot,
            superseded_asset_id=superseded_asset_id,
            replacement_asset_id=str(replacement_asset.id),
            replacement_asset_version=int(replacement_asset.version or 1),
            rebound_at=rebound_at,
        ):
            flag_modified(shot, "extra_data")


__all__ = ["rebind_run_shots_reference", "rebind_shot_reference_context"]
