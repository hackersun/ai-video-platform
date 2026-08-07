"""Application service for reporting effective Prompt usage by production stage."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.bindings import ModelBindingError, resolve_model_binding
from app.features.model_config.prompt_usage_contract import (
    PROMPT_USAGE_GROUPS,
    PromptUsageStage,
    prompt_usage_stage,
    prompt_usage_stages,
)
from app.features.model_config.prompt_usage_repository import (
    PromptUsageModelIdentity,
    load_prompt_usage_model_identity,
)
from app.services.prompt_template_router import select_prompt_skill_for_model


class PromptUsageError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(code)
        self.code = code
        self.message = message


_ROUTING_PRESENTATION = {
    "exact_model_match": ("overridden", "模型专用覆盖", "当前模型命中了模型专用模板。"),
    "provider_model_contract_match": ("overridden", "模型专用覆盖", "当前模型命中了模型专用模板。"),
    "model_contract_match": ("overridden", "模型专用覆盖", "当前模型命中了模型专用模板。"),
    "model_family_match": ("effective", "模型系列模板", "当前模型使用同系列模型模板。"),
    "provider_match": ("effective", "供应商模板", "当前模型使用供应商通用模板。"),
    "capability_match": ("effective", "能力模板", "当前模型使用同能力模型模板。"),
    "output_contract_match": ("effective", "输出格式模板", "当前环节使用匹配输出格式的模板。"),
    "task_generic_match": ("effective", "环节通用模板", "当前模型使用此环节的通用模板。"),
    "task_only_template": ("effective", "环节通用模板", "当前模型使用此环节的通用模板。"),
}


def _not_applicable(stage: PromptUsageStage) -> dict[str, Any]:
    return {
        "id": stage.id, "name": stage.name, "uses_prompt": False,
        "status": "not_applicable", "message": "此环节不使用提示词模板。",
        "model": None, "template": None,
        "routing": {"source_label": "无需提示词"},
    }


def _invalid_binding(stage: PromptUsageStage) -> dict[str, Any]:
    return {
        "id": stage.id, "name": stage.name, "uses_prompt": True,
        "status": "invalid_binding",
        "message": "当前环节没有可用的默认模型，请先完成模型配置。",
        "model": None, "template": None,
        "routing": {"source_label": "模型配置异常"},
    }


def _model_payload(identity: PromptUsageModelIdentity) -> dict[str, Any]:
    return {
        "profile_version_id": identity.profile_version_id,
        "provider_code": identity.provider_code,
        "provider_name": identity.provider_name,
        "api_model_id": identity.api_model_id,
        "name": identity.model_name,
        "capabilities": list(identity.capabilities),
    }


async def _resolve_routed_stage(
    db: AsyncSession,
    *,
    user_id: str,
    stage: PromptUsageStage,
    binding,
) -> dict[str, Any]:
    identity = await load_prompt_usage_model_identity(db, binding)
    route = await select_prompt_skill_for_model(
        db, user_id=user_id, task=stage.prompt_task or "",
        provider_name=identity.provider_code, model_id=identity.api_model_id,
        model_capabilities=list(identity.capabilities), capability=stage.capability,
        output_contract=stage.output_contract, stage=stage.prompt_stage,
    )
    if not route.get("used_prompt_skill"):
        status, source_label, message = (
            "internal_fallback", "内置兜底", "尚未配置模板，将使用代码内置提示词。"
        )
        template = None
    else:
        status, source_label, message = _ROUTING_PRESENTATION.get(
            str(route.get("routing_reason")),
            ("effective", "当前生效", "当前模型已匹配可用模板。"),
        )
        template = {
            "id": route.get("prompt_skill_id"),
            "profile_version_id": route.get("prompt_profile_version_id"),
            "name": route.get("prompt_skill_name"),
            "version": route.get("prompt_skill_version"),
        }
    return {
        "id": stage.id, "name": stage.name, "uses_prompt": True,
        "status": status, "message": message,
        "model": _model_payload(identity), "template": template,
        "routing": {"source_label": source_label},
    }


async def resolve_prompt_usage_stage(
    db: AsyncSession,
    *,
    user_id: str,
    stage_id: str,
    profile_version_id: str | None = None,
) -> dict[str, Any]:
    try:
        stage = prompt_usage_stage(stage_id)
    except KeyError as error:
        raise PromptUsageError("stage_not_found", "未找到这个生产环节。") from error
    if not stage.uses_prompt:
        return _not_applicable(stage)
    try:
        binding = await resolve_model_binding(
            db, user_id=user_id, task=stage.model_task or "",
            capability=stage.capability,
            explicit_profile_version_id=profile_version_id,
        )
    except ModelBindingError as error:
        if profile_version_id:
            raise PromptUsageError("model_not_available", "所选模型不可用于这个生产环节。") from error
        return _invalid_binding(stage)
    return await _resolve_routed_stage(
        db, user_id=user_id, stage=stage, binding=binding,
    )


async def get_prompt_usage_map(db: AsyncSession, *, user_id: str) -> dict[str, Any]:
    model_cache: dict[tuple[str, str], Any] = {}
    resolved: dict[str, dict[str, Any]] = {}
    for stage in prompt_usage_stages():
        if not stage.uses_prompt:
            resolved[stage.id] = _not_applicable(stage)
            continue
        key = (stage.model_task or "", stage.capability or "")
        if key not in model_cache:
            try:
                model_cache[key] = await resolve_model_binding(
                    db, user_id=user_id, task=key[0], capability=stage.capability,
                )
            except ModelBindingError:
                model_cache[key] = None
        binding = model_cache[key]
        resolved[stage.id] = (
            await _resolve_routed_stage(db, user_id=user_id, stage=stage, binding=binding)
            if binding is not None else _invalid_binding(stage)
        )
    counts = Counter(item["status"] for item in resolved.values())
    return {
        "summary": {"total": len(resolved), "counts": dict(counts)},
        "groups": [
            {"id": group.id, "name": group.name,
             "stages": [resolved[stage_id] for stage_id in group.stage_ids]}
            for group in PROMPT_USAGE_GROUPS
        ],
    }


__all__ = [
    "PromptUsageError", "get_prompt_usage_map", "resolve_prompt_usage_stage",
]
