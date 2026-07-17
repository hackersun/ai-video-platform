"""Persistence boundary for Story Lock lineage freshness."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Asset, Chapter, Novel, ProviderAssetBinding, Shot, StoryBible, StoryEntity, Workflow
from app.models.series_production_run import SeriesProductionRun


class StoryLockLineageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def chapters(self, *, ids: list[str], user_id: str, novel_id: str) -> list[Chapter]:
        return list((await self.db.scalars(select(Chapter).where(
            Chapter.id.in_(ids), Chapter.user_id == user_id, Chapter.novel_id == novel_id,
        ))).all())

    async def novel(self, *, novel_id: str, user_id: str) -> Novel | None:
        return await self.db.scalar(select(Novel).where(Novel.id == novel_id, Novel.user_id == user_id))

    async def approved_entities(self, *, novel_id: str, user_id: str) -> list[StoryEntity]:
        rows = list((await self.db.scalars(select(StoryEntity).where(
            StoryEntity.user_id == user_id, StoryEntity.novel_id == novel_id,
            StoryEntity.is_approved.is_(True),
        ))).all())
        return [item for item in rows if bool((item.attributes or {}).get("approval_record"))]

    async def bible(self, bible_id: str) -> StoryBible | None:
        return await self.db.get(StoryBible, bible_id)

    async def reference_asset(self, run: SeriesProductionRun) -> tuple[Asset | None, list[ProviderAssetBinding]]:
        reference = dict((run.run_metadata or {}).get("reference_preparation") or {})
        asset_id, version = str(reference.get("asset_id") or ""), int(reference.get("asset_version") or 0)
        asset = await self.db.scalar(select(Asset).where(
            Asset.id == asset_id, Asset.user_id == run.user_id,
            *([Asset.version == version] if version else []),
        )) if asset_id else None
        bindings = list((await self.db.scalars(select(ProviderAssetBinding).where(
            ProviderAssetBinding.asset_id == asset.id,
            ProviderAssetBinding.asset_version == int(asset.version or 1),
            ProviderAssetBinding.is_active.is_(True),
        ))).all()) if asset is not None else []
        return asset, bindings

    async def workflows_and_shots(self, run: SeriesProductionRun) -> tuple[list[Workflow], list[Shot]]:
        workflow_ids = [str((item.get("canonical_ids") or {}).get("workflow_id"))
                        for item in (run.episodes or []) if (item.get("canonical_ids") or {}).get("workflow_id")]
        workflows = list((await self.db.scalars(select(Workflow).where(
            Workflow.id.in_(workflow_ids), Workflow.user_id == run.user_id,
        ))).all()) if workflow_ids else []
        storyboard_ids = [item.storyboard_id for item in workflows if item.storyboard_id]
        shots = list((await self.db.scalars(select(Shot).where(
            Shot.user_id == run.user_id, Shot.storyboard_id.in_(storyboard_ids),
        ))).all()) if storyboard_ids else []
        return workflows, shots

    async def commit(self) -> None:
        await self.db.commit()
