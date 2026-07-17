"""SQLAlchemy queries used by workflow-media application services."""

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Shot, Workflow
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.series_production_run import SeriesProductionRun


async def get_workflow(
    db: AsyncSession, workflow_id: str, user_id: str,
) -> Optional[Workflow]:
    return await db.scalar(select(Workflow).where(
        Workflow.id == workflow_id,
        Workflow.user_id == user_id,
    ))


async def get_series_run(
    db: AsyncSession, series_run_id: str, user_id: str, novel_id: str,
) -> Optional[SeriesProductionRun]:
    return await db.scalar(select(SeriesProductionRun).where(
        SeriesProductionRun.id == series_run_id,
        SeriesProductionRun.user_id == user_id,
        SeriesProductionRun.novel_id == novel_id,
    ))


async def list_shots(
    db: AsyncSession,
    user_id: str,
    storyboard_id: Optional[str],
    shot_ids: Optional[Sequence[str]],
) -> list[Shot]:
    query = select(Shot).where(Shot.user_id == user_id)
    if shot_ids:
        query = query.where(Shot.id.in_(shot_ids))
    elif storyboard_id:
        query = query.where(Shot.storyboard_id == storyboard_id)
    result = await db.execute(query.order_by(Shot.shot_number))
    return list(result.scalars().all())


async def get_video_model_config(
    db: AsyncSession, user_id: str, config_id: str,
) -> Optional[tuple[LLMConfig, LLMModel, LLMProvider]]:
    result = await db.execute(
        select(LLMConfig, LLMModel, LLMProvider)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
        .where(
            LLMConfig.id == config_id,
            LLMConfig.user_id == user_id,
            LLMConfig.is_active == True,
            LLMModel.is_active == True,
            LLMProvider.is_active == True,
        )
        .limit(1)
    )
    row = result.first()
    return (row[0], row[1], row[2]) if row else None
