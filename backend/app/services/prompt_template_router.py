"""Compatibility projection for canonical, model-aware Prompt routing."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.prompt_profiles.public import (
    PromptRouteQuery,
    PromptSelection,
    resolve_prompt_entries,
)
from app.features.model_execution_contract import resolve_model_execution_contract
from app.services.default_prompt_skills import ensure_standard_prompt_skills


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


def _compose_prompt(block: str, internal: str, titles: tuple[str, str]) -> str:
    if internal and block:
        return f"【{titles[0]}】\n{block}\n\n【{titles[1]}】\n{internal}"
    return block or internal


def _route_base(
    task: str, provider: str, model: str, capabilities: set[str],
    output_contract: str | None, contract_evidence: dict,
) -> dict[str, Any]:
    return {
        "task": task, "provider_name": provider or None, "model_id": model or None,
        "model_capabilities": sorted(capabilities), "output_contract": output_contract,
        **contract_evidence,
    }


def _empty_route_payload(base: dict[str, Any], internal_prompt: str) -> dict[str, Any]:
    return {
        **base, "used_prompt_skill": False, "prompt": internal_prompt.strip(),
        "skill_blocks": [], "prompt_skills": [], "prompt_skill_count": 0,
        "prompt_skill_id": None, "prompt_skill_name": None,
        "prompt_skill_version": None, "prompt_profile_version_id": None,
        "selected_scope": "internal", "routing_reason": "no_active_template",
        "fallback_reason": "internal_prompt_fallback",
    }


def _canonical_route_payload(
    base: dict[str, Any], selection: PromptSelection, internal_prompt: str,
    titles: tuple[str, str],
) -> dict[str, Any]:
    block = selection.prompt
    return {
        **base, "output_contract": selection.output_contract or base["output_contract"],
        "used_prompt_skill": bool(block),
        "prompt": _compose_prompt(block, internal_prompt.strip(), titles).strip(),
        "skill_blocks": [block] if block else [],
        "prompt_skills": [{
            "id": selection.profile_id, "name": selection.profile_name,
            "task": base["task"], "stage": selection.stage,
            "version": selection.version, "routing": dict(selection.routing),
        }],
        "prompt_skill_count": 1 if block else 0,
        "prompt_skill_id": selection.profile_id,
        "prompt_skill_name": selection.profile_name,
        "prompt_skill_version": selection.version,
        "prompt_profile_version_id": selection.profile_version_id,
        "selected_scope": "user", "routing_reason": selection.routing_reason,
        "fallback_reason": selection.fallback_reason,
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
    provider = provider_name or ""
    model = model_id or ""
    capabilities = {str(item) for item in (model_capabilities or [])}
    contract_evidence = _model_contract_evidence(provider, model, capability, task)
    base = _route_base(task, provider, model, capabilities, output_contract, contract_evidence)
    titles = (template_title, internal_title)
    await ensure_standard_prompt_skills(db, commit=False)
    selections = await resolve_prompt_entries(
        db,
        PromptRouteQuery(
            user_id=user_id,
            task=task,
            provider_id=provider,
            model_id=model,
            capabilities=frozenset(capabilities),
            output_contract=output_contract,
            stage=stage,
            context=context or {},
        ),
    )
    if selections:
        return _canonical_route_payload(base, selections[0], internal_prompt, titles)
    return _empty_route_payload(base, internal_prompt)
