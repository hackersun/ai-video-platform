"""Owned, idempotent series-run creation application service."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chapter import Chapter
from app.models.novel import Novel
from app.models.series_production_run import SeriesProductionRun
from app.services.live_canary_budget import InvalidAccountingInput, trusted_live_canary_policy

from .errors import SeriesAnchorError


def _scope(*, user_id: str, novel_id: str, plan_version: str, idempotency_key: str) -> tuple[object, ...]:
    return (
        SeriesProductionRun.user_id == user_id,
        SeriesProductionRun.novel_id == novel_id,
        SeriesProductionRun.series_plan_version == plan_version,
        SeriesProductionRun.idempotency_key == idempotency_key,
    )


async def _validate_chapters(
    db: AsyncSession, *, user_id: str, novel_id: str, episodes: list[dict[str, object]],
) -> None:
    requested = [str(chapter_id) for episode in episodes for chapter_id in episode["chapter_ids"]]
    valid = set((await db.scalars(select(Chapter.id).where(
        Chapter.id.in_(requested), Chapter.user_id == user_id, Chapter.novel_id == novel_id,
    ))).all())
    if len(valid) != len(set(requested)) or len(requested) != len(set(requested)):
        raise SeriesAnchorError(422, "episodes contain invalid chapters")


def _new_run(
    *, user_id: str, novel_id: str, plan_version: str, idempotency_key: str,
    requested_stages: list[str], model_bindings: dict, budget_policy: dict,
    episodes: list[dict[str, object]],
) -> SeriesProductionRun:
    stored = [{**episode, "stage": "created", "canonical_ids": {}, "attempt_count": 0, "blocker": None}
              for episode in sorted(episodes, key=lambda item: int(item["episode_number"]))]
    return SeriesProductionRun(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id, series_plan_version=plan_version,
        idempotency_key=idempotency_key, status="created", current_episode_number=0,
        requested_stages=requested_stages, model_bindings=model_bindings,
        budget_policy=budget_policy, cost_summary={}, gate_summary={}, run_metadata={},
        episodes=stored, version=1,
    )


async def create_run(
    db: AsyncSession, *, user_id: str, novel_id: str, plan_version: str,
    idempotency_key: str, requested_stages: list[str], model_bindings: dict,
    requested_budget_policy: dict, episodes: list[dict[str, object]],
) -> tuple[SeriesProductionRun, bool]:
    if await db.scalar(select(Novel.id).where(Novel.id == novel_id, Novel.user_id == user_id)) is None:
        raise SeriesAnchorError(404, "novel not found")
    await _validate_chapters(db, user_id=user_id, novel_id=novel_id, episodes=episodes)
    scope = _scope(user_id=user_id, novel_id=novel_id, plan_version=plan_version, idempotency_key=idempotency_key)
    existing = await db.scalar(select(SeriesProductionRun).where(*scope))
    if existing is not None:
        return existing, False
    try:
        trusted = trusted_live_canary_policy(requested_budget_policy)
    except InvalidAccountingInput as error:
        raise SeriesAnchorError(422, str(error)) from error
    run = _new_run(user_id=user_id, novel_id=novel_id, plan_version=plan_version,
                   idempotency_key=idempotency_key, requested_stages=requested_stages,
                   model_bindings=model_bindings, budget_policy=trusted, episodes=episodes)
    db.add(run)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        winner = await db.scalar(select(SeriesProductionRun).where(*scope))
        if winner is None:
            raise
        return winner, False
    await db.refresh(run)
    return run, True


__all__ = ["create_run"]
