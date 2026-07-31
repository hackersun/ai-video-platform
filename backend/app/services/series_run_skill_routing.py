"""Prompt Skill routing and audit evidence for whole-book production stages."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.prompt_template_router import select_prompt_skill_for_model


class SeriesRunSkillMissing(ValueError):
    """Raised when a required whole-book stage has no active Prompt Skill."""


async def resolve_required_series_run_skill(
    db: AsyncSession,
    *,
    user_id: str,
    task: str,
    stage: str,
    context: dict[str, Any],
    internal_prompt: str,
) -> dict[str, Any]:
    route = await select_prompt_skill_for_model(
        db,
        user_id=user_id,
        task=task,
        stage=stage,
        context=context,
        internal_prompt=internal_prompt,
        template_title="整书生产 Prompt Skill",
        internal_title="整书生产阶段输入",
    )
    if not route.get("used_prompt_skill") or not route.get("prompt_skill_id"):
        raise SeriesRunSkillMissing(f"required Prompt Skill is missing: {task}")
    return route


def skill_audit_evidence(
    route: dict[str, Any], *, execution_mode: str = "deterministic_contract",
) -> dict[str, Any]:
    return {
        "id": route["prompt_skill_id"],
        "name": route.get("prompt_skill_name"),
        "version": route.get("prompt_skill_version"),
        "profile_version_id": route.get("prompt_profile_version_id"),
        "routing_reason": route.get("routing_reason"),
        "execution_mode": execution_mode,
    }


__all__ = [
    "SeriesRunSkillMissing",
    "resolve_required_series_run_skill",
    "skill_audit_evidence",
]
