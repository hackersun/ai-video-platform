"""Model-aware Prompt Skill routing.

Routing metadata is stored in ``PromptSkill.variables.routing`` to keep the
first rollout backwards-compatible with existing Prompt Skill rows.
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PromptSkill
from app.features.model_execution_contract import resolve_model_execution_contract
from app.services.default_prompt_skills import ensure_standard_prompt_skills
from app.services.prompt_skill_service import render_prompt_skill


def _json_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    return []


def _routing(skill: PromptSkill) -> dict[str, Any]:
    variables = _json_dict(skill.variables)
    return _json_dict(variables.get("routing"))


def _matches_filter(value: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    normalized = (value or "").lower()
    return any(fnmatchcase(normalized, pattern.lower()) for pattern in patterns)


def _capabilities_match(model_capabilities: set[str], required: list[str]) -> bool:
    return all(item in model_capabilities for item in required)


def _routing_score(
    routing: dict[str, Any],
    *,
    provider_name: str,
    model_id: str,
    model_capabilities: set[str],
    output_contract: Optional[str],
) -> Optional[tuple[int, str, Optional[str]]]:
    provider_filter = _string_list(routing.get("provider_filter"))
    model_filter = _string_list(routing.get("model_filter"))
    capability_filter = _string_list(routing.get("capability_filter"))
    expected_contract = str(routing.get("output_contract") or "").strip() or None

    if provider_filter and not _matches_filter(provider_name, provider_filter):
        return None
    if model_filter and not _matches_filter(model_id, model_filter):
        return None
    if capability_filter and not _capabilities_match(model_capabilities, capability_filter):
        return None
    if expected_contract and output_contract and expected_contract != output_contract:
        return None

    score = 0
    if provider_filter:
        score += 40
    if model_filter:
        score += 35
    if capability_filter:
        score += 15
    if expected_contract:
        score += 10

    if provider_filter and model_filter and expected_contract:
        reason = "provider_model_contract_match"
    elif model_filter and expected_contract:
        reason = "model_contract_match"
    elif provider_filter:
        reason = "provider_match"
    elif expected_contract:
        reason = "output_contract_match"
    else:
        reason = "task_only_template"

    fallback = "task_only_template" if score == 0 else None
    return score, reason, fallback


def _quality_sort_values(skill: PromptSkill, routing: dict[str, Any]) -> tuple[float, float, float, int, int]:
    return (
        float(routing.get("quality_score") or 0),
        -float(routing.get("garbage_rate") or 0),
        float(routing.get("parse_success_rate") or 0),
        -int(skill.priority or 100),
        int(skill.version or 1),
    )


def _model_contract_evidence(provider: str, model: str, capability: str | None, task: str) -> dict:
    resolved_capability = capability or (
        "image" if task in {"character_image", "scene_reference_image", "prop_image"} else "text"
    )
    contract = resolve_model_execution_contract(provider, model, resolved_capability)
    return {
        "model_contract_version": contract.contract_version,
        "prompt_profile": contract.prompt_profile,
        "model_verification_status": contract.verification_status,
    }


async def select_prompt_skill_for_model(
    db: AsyncSession,
    *,
    user_id: str,
    task: str,
    provider_name: Optional[str] = None,
    model_id: Optional[str] = None,
    model_capabilities: Optional[list[str]] = None,
    capability: Optional[str] = None,
    output_contract: Optional[str] = None,
    stage: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
    internal_prompt: str = "",
    template_title: str = "模型适配提示词模板",
    internal_title: str = "内部任务提示词",
) -> dict[str, Any]:
    """Select and render the best Prompt Skill for a provider/model request."""
    await ensure_standard_prompt_skills(db)
    query = select(PromptSkill).where(
        PromptSkill.task == task,
        PromptSkill.is_active == True,
        or_(PromptSkill.user_id == user_id, PromptSkill.is_builtin == True),
    )
    if stage:
        query = query.where(or_(PromptSkill.stage == stage, PromptSkill.stage.is_(None)))
    query = query.order_by(PromptSkill.priority, PromptSkill.created_at)
    skills = list((await db.execute(query)).scalars().all())

    provider = provider_name or ""
    model = model_id or ""
    capabilities = {str(item) for item in (model_capabilities or [])}
    contract_evidence = _model_contract_evidence(provider, model, capability, task)

    best: tuple[int, tuple[float, float, float, int, int], PromptSkill, str, Optional[str]] | None = None
    for skill in skills:
        if not skill.is_builtin and skill.user_id != user_id:
            continue
        routing = _routing(skill)
        score_payload = _routing_score(
            routing,
            provider_name=provider,
            model_id=model,
            model_capabilities=capabilities,
            output_contract=output_contract,
        )
        if score_payload is None:
            continue
        score, reason, fallback = score_payload
        owner_bonus = 1000 if not skill.is_builtin and skill.user_id == user_id else 0
        sort_values = _quality_sort_values(skill, routing)
        candidate = (owner_bonus + score, sort_values, skill, reason, fallback)
        if best is None or candidate[:2] > best[:2]:
            best = candidate

    if best is None:
        return {
            "task": task,
            "provider_name": provider or None,
            "model_id": model or None,
            "model_capabilities": sorted(capabilities),
            "output_contract": output_contract,
            "used_prompt_skill": False,
            "prompt": internal_prompt.strip(),
            "skill_blocks": [],
            "prompt_skills": [],
            "prompt_skill_count": 0,
            "prompt_skill_id": None,
            "prompt_skill_name": None,
            "prompt_skill_version": None,
            "selected_scope": "internal",
            "routing_reason": "no_active_template",
            "fallback_reason": "internal_prompt_fallback",
            **contract_evidence,
        }

    _, _, skill, reason, fallback = best
    block = render_prompt_skill(skill, context or {})
    internal = (internal_prompt or "").strip()
    prompt = f"【{template_title}】\n{block}\n\n【{internal_title}】\n{internal}" if internal and block else block or internal
    return {
        "task": task,
        "provider_name": provider or None,
        "model_id": model or None,
        "model_capabilities": sorted(capabilities),
        "output_contract": output_contract or _routing(skill).get("output_contract"),
        "used_prompt_skill": bool(block),
        "prompt": prompt.strip(),
        "skill_blocks": [block] if block else [],
        "prompt_skills": [
            {
                "id": skill.id,
                "name": skill.name,
                "task": skill.task,
                "stage": skill.stage,
                "version": skill.version or 1,
                "routing": _routing(skill),
            }
        ],
        "prompt_skill_count": 1 if block else 0,
        "prompt_skill_id": skill.id,
        "prompt_skill_name": skill.name,
        "prompt_skill_version": skill.version or 1,
        "selected_scope": "builtin" if skill.is_builtin else "user",
        "routing_reason": reason,
        "fallback_reason": fallback,
        **contract_evidence,
    }
