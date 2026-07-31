from __future__ import annotations

from hashlib import sha256
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.prompt_template_router import select_prompt_skill_for_model

from .domain import BoundSeriesStageSkill, SeriesStageSkillMissing


async def bind_series_stage_skill(
    db: AsyncSession, *, user_id: str, task: str, stage: str,
    context: dict[str, Any], internal_prompt: str, artifact_type: str,
    artifact_id: str | None = None,
    execution_mode: str = "deterministic_skill_contract",
    provider_name: str | None = None, model_id: str | None = None,
    output_contract: str | None = None,
) -> BoundSeriesStageSkill:
    route = await select_prompt_skill_for_model(
        db, user_id=user_id, task=task, stage=stage, context=context,
        internal_prompt=internal_prompt, provider_name=provider_name,
        model_id=model_id, output_contract=output_contract,
        template_title="整书生产 Prompt Skill", internal_title="整书生产阶段输入",
    )
    rendered = str(route.get("prompt") or "").strip()
    if not route.get("used_prompt_skill") or not route.get("prompt_skill_id") or not rendered:
        raise SeriesStageSkillMissing(f"required Prompt Skill is missing: {task}")
    evidence = {
        "id": route["prompt_skill_id"], "name": route.get("prompt_skill_name"),
        "version": route.get("prompt_skill_version"), "task": task, "stage": stage,
        "profile_version_id": route.get("prompt_profile_version_id"),
        "routing_reason": route.get("routing_reason"), "execution_mode": execution_mode,
        "rendered_prompt_sha256": sha256(rendered.encode("utf-8")).hexdigest(),
        "artifact_type": artifact_type, "artifact_id": artifact_id,
    }
    return BoundSeriesStageSkill(rendered_prompt=rendered, evidence=evidence)
