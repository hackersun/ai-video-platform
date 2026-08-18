"""Additive projection of selected shared providers into Model Center."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.backfill import BackfillReport, _backfill_model, _backfill_provider
from app.features.model_config.catalog import is_product_visible_model, is_product_visible_provider
from app.models.llm_config import LLMModel, LLMProvider


async def backfill_provider_catalog(
    db: AsyncSession, *, provider_ids: set[str], apply: bool = True,
) -> BackfillReport:
    """Project selected providers and models without reading user-owned rows."""
    report = BackfillReport()
    providers = [
        provider for provider in (await db.scalars(
            select(LLMProvider).where(LLMProvider.id.in_(provider_ids))
        )).all()
        if is_product_visible_provider(provider)
    ]
    models = [
        model for model in (await db.scalars(
            select(LLMModel).where(LLMModel.provider_id.in_(provider_ids))
        )).all()
        if is_product_visible_model(model)
    ]
    canonical_provider_ids: dict[str, str] = {}
    for provider in providers:
        canonical_provider_ids[provider.id] = await _backfill_provider(db, provider, report, apply)
    pending_versions: dict[tuple[str, str], tuple[str, str, str]] = {}
    providers_by_id = {provider.id: provider for provider in providers}
    for model in models:
        provider = providers_by_id.get(model.provider_id)
        if provider is not None:
            await _backfill_model(
                db, model, provider, canonical_provider_ids[provider.id], report, apply, pending_versions,
            )
    if apply:
        await db.flush()
    return report


__all__ = ["backfill_provider_catalog"]
