"""Truthful, read-only production readiness checks for Model Center."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.model_config.domain import VERIFIED_CONNECTION_STATUSES
from app.models.model_center import (
    ModelBinding,
    ModelCertificationRun,
    ModelConnection,
    ModelProfileVersion,
    ProductionRecipeVersion,
)
from app.models.prompt_profile import PromptProfile, PromptProfileVersion


PROMPT_CAPABILITIES = {
    "text_generation", "vision_analysis", "image_generation", "video_generation",
    "speech_generation", "subtitle_generation",
}


def _issue(
    code: str, message: str, *, section: str, resource_id: str = "",
    capability: str | None = None, action_label: str,
) -> dict:
    return {
        "code": code, "message": message, "severity": "blocker", "section": section,
        "capability": capability, "resource_id": resource_id, "action_label": action_label,
    }


async def production_readiness(db: AsyncSession, *, user_id: str) -> list[dict]:
    connections = list((await db.scalars(select(ModelConnection).where(
        ModelConnection.user_id == user_id,
    ))).all())
    bindings = list((await db.scalars(select(ModelBinding).where(
        ModelBinding.user_id == user_id, ModelBinding.is_active == True,
    ))).all())
    profiles = {
        row.id: row for row in (await db.scalars(select(ModelProfileVersion).where(
            ModelProfileVersion.id.in_({item.profile_version_id for item in bindings}),
        ))).all()
    } if bindings else {}
    issues = _connection_issues(connections)
    issues.extend(_binding_issues(bindings, profiles))
    issues.extend(await _prompt_issues(db, user_id=user_id, bindings=bindings, profiles=profiles))
    issues.extend(await _recipe_issues(db, user_id=user_id))
    issues.extend(await _certification_issues(db, user_id=user_id, bindings=bindings))
    unique = {(item["code"], item.get("capability"), item["resource_id"]): item for item in issues}
    return sorted(unique.values(), key=lambda item: (item["section"], item["code"], item["resource_id"]))


def _connection_issues(connections: list[ModelConnection]) -> list[dict]:
    if not connections:
        return [_issue(
            "connection_missing", "尚未保存模型连接。", section="connections",
            action_label="新增模型连接",
        )]
    if not any(item.status in VERIFIED_CONNECTION_STATUSES for item in connections):
        return [_issue(
            "connection_unverified", "没有已认证的模型连接。", section="connections",
            action_label="测试模型连接",
        )]
    return []


def _binding_issues(bindings: list[ModelBinding], profiles: dict[str, ModelProfileVersion]) -> list[dict]:
    if not bindings:
        return [_issue(
            "active_binding_missing", "尚未建立已启用的能力绑定。", section="bindings",
            action_label="建立能力绑定",
        )]
    return [
        _issue(
            "published_model_missing", "能力绑定引用的模型版本尚未发布或已不存在。",
            section="catalog", capability=binding.capability,
            resource_id=binding.profile_version_id, action_label="修复模型版本",
        )
        for binding in bindings
        if profiles.get(binding.profile_version_id) is None
        or profiles[binding.profile_version_id].status != "published"
    ]


async def _prompt_issues(
    db: AsyncSession, *, user_id: str, bindings: list[ModelBinding],
    profiles: dict[str, ModelProfileVersion],
) -> list[dict]:
    required = [
        (binding, profiles.get(binding.profile_version_id)) for binding in bindings
        if binding.capability in PROMPT_CAPABILITIES
    ]
    keys = {profile.prompt_profile_key for _, profile in required if profile and profile.prompt_profile_key}
    published_keys = set((await db.scalars(select(PromptProfile.key).join(
        PromptProfileVersion, PromptProfileVersion.profile_id == PromptProfile.id,
    ).where(
        PromptProfile.user_id.in_((user_id, "system")), PromptProfile.key.in_(keys),
        PromptProfileVersion.status == "published",
    ))).all()) if keys else set()
    return [
        _issue(
            "prompt_profile_missing", "模型绑定缺少已发布的提示词模板。",
            section="prompts", capability=binding.capability,
            resource_id=binding.id, action_label="配置提示词模板",
        )
        for binding, profile in required
        if profile is None or not profile.prompt_profile_key
        or profile.prompt_profile_key not in published_keys
    ]


async def _recipe_issues(db: AsyncSession, *, user_id: str) -> list[dict]:
    published = await db.scalar(select(ProductionRecipeVersion.id).where(
        ProductionRecipeVersion.user_id == user_id,
        ProductionRecipeVersion.status == "published",
    ).limit(1))
    return [] if published else [_issue(
        "published_recipe_missing", "尚未发布可供工作台使用的组合预设。",
        section="recipes", action_label="发布组合预设",
    )]


async def _certification_issues(
    db: AsyncSession, *, user_id: str, bindings: list[ModelBinding],
) -> list[dict]:
    profile_ids = {item.profile_version_id for item in bindings}
    certified = set((await db.scalars(select(ModelCertificationRun.profile_version_id).where(
        ModelCertificationRun.user_id == user_id,
        ModelCertificationRun.profile_version_id.in_(profile_ids),
        ModelCertificationRun.status == "success",
        ModelCertificationRun.level.in_(("contract", "live")),
    ))).all()) if profile_ids else set()
    return [
        _issue(
            "model_certification_missing", "已绑定模型缺少成功的契约或真实认证。",
            section="test-lab", capability=binding.capability,
            resource_id=binding.profile_version_id, action_label="运行模型认证",
        )
        for binding in bindings if binding.profile_version_id not in certified
    ]
