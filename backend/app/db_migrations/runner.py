"""Small facade for schema upgrades that live outside the legacy init module."""

from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db_migrations.live_canary_provider_operations import (
    add_artifact_id,
    add_artifact_id_async,
)
from app.db_migrations.model_center import add_model_center_links, add_model_center_links_async


def register_production_models() -> None:
    """Register production models with shared metadata before create_all."""
    from app.models.entity_extraction_run import EntityExtractionRun
    from app.models.entity_feedback import EntityFeedback
    from app.models.live_canary_provider_operation import LiveCanaryProviderOperation
    from app.models.model_center import (
        ModelBinding,
        ModelCertificationRun,
        ModelConfigAuditEvent,
        ModelConnection,
        ModelExecutionSnapshot,
        ModelProfile,
        ModelProfileVersion,
        ModelProvider,
        ProductionRecipeVersion,
    )
    from app.models.production_state_event import ProductionStateEvent
    from app.models.provider_asset_binding import ProviderAssetBinding
    from app.models.quality_evaluation import QualityEvaluation
    from app.models.series_production_run import SeriesProductionRun
    from app.models.story_entity_mention import StoryEntityMention

    _ = (
        EntityExtractionRun,
        EntityFeedback,
        LiveCanaryProviderOperation,
        ModelBinding,
        ModelCertificationRun,
        ModelConfigAuditEvent,
        ModelConnection,
        ModelExecutionSnapshot,
        ModelProfile,
        ModelProfileVersion,
        ModelProvider,
        ProductionRecipeVersion,
        ProductionStateEvent,
        ProviderAssetBinding,
        QualityEvaluation,
        SeriesProductionRun,
        StoryEntityMention,
    )


def run_schema_migrations(engine: Engine) -> None:
    """Run focused synchronous schema upgrades."""
    add_artifact_id(engine)
    add_model_center_links(engine)


async def run_schema_migrations_async(engine: AsyncEngine) -> None:
    """Run focused asynchronous schema upgrades."""
    await add_artifact_id_async(engine)
    await add_model_center_links_async(engine)
