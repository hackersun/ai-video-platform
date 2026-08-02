"""Deterministic routing for published Prompt Profile versions."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any, Iterable

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.prompt_profiles.domain import PromptRouteQuery, PromptSelection, render_prompt
from app.features.prompt_profiles.repository import published_prompt_candidates
from app.features.prompt_profiles.versioning import ensure_legacy_prompt_profile
from app.models.prompt_skill import PromptSkill


ROUTING_PRECEDENCE = {
    "exact_model": 500,
    "model_family": 400,
    "provider": 300,
    "capability": 200,
    "task_generic": 100,
}


def safe_routing_metadata(
    routing: dict[str, Any], reason: str, output_contract: str | None,
) -> dict[str, Any]:
    return {
        "selector_kind": reason.removesuffix("_match"),
        "provider_scoped": bool(_patterns(routing.get("provider_filter"))),
        "model_scoped": bool(_patterns(routing.get("model_filter"))),
        "capability_scoped": bool(_patterns(routing.get("capability_filter"))),
        "output_contract_scoped": bool(output_contract),
    }


def _patterns(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if str(item or "").strip())
    return ()


def _matches(value: str, patterns: Iterable[str]) -> bool:
    normalized = str(value or "").lower()
    return any(fnmatchcase(normalized, pattern.lower()) for pattern in patterns)


def _model_match_kind(model_id: str, filters: tuple[str, ...]) -> str | None:
    matches = [pattern for pattern in filters if _matches(model_id, (pattern,))]
    if not matches:
        return None
    exact = any(not ({"*", "?", "["} & set(pattern)) for pattern in matches)
    return "exact_model" if exact else "model_family"


def routing_specificity(
    routing: dict[str, Any], *, provider_id: str, model_id: str,
    capabilities: set[str], output_contract: str | None,
) -> tuple[int, str, str | None] | None:
    providers = _patterns(routing.get("provider_filter"))
    models = _patterns(routing.get("model_filter"))
    required = set(_patterns(routing.get("capability_filter")))
    expected_output = str(routing.get("output_contract") or "").strip() or None
    if providers and not _matches(provider_id, providers):
        return None
    if required and not required.issubset(capabilities):
        return None
    if expected_output and expected_output != output_contract:
        return None
    if models:
        match_kind = _model_match_kind(model_id, models)
        if match_kind is None:
            return None
        return ROUTING_PRECEDENCE[match_kind], f"{match_kind}_match", None
    if providers:
        return ROUTING_PRECEDENCE["provider"], "provider_match", None
    if required:
        return ROUTING_PRECEDENCE["capability"], "capability_match", None
    return ROUTING_PRECEDENCE["task_generic"], "task_generic_match", "task_only_template"


def _legacy_compatibility_reason(
    profile_key: str,
    routing: dict[str, Any],
    reason: str,
    fallback: str | None,
) -> tuple[str, str | None]:
    if not profile_key.startswith("legacy"):
        return reason, fallback
    providers = _patterns(routing.get("provider_filter"))
    models = _patterns(routing.get("model_filter"))
    output_contract = str(routing.get("output_contract") or "").strip()
    if providers and models and output_contract:
        return "provider_model_contract_match", None
    if models and output_contract:
        return "model_contract_match", None
    if providers:
        return "provider_match", None
    if output_contract:
        return "output_contract_match", None
    return "task_only_template", "task_only_template"


async def _ranked_candidates(
    db: AsyncSession, query: PromptRouteQuery,
):
    ranked = []
    for profile, version in await published_prompt_candidates(
        db, user_id=query.user_id, task=query.task, stage=query.stage,
    ):
        routing = dict(version.routing or {})
        if version.output_contract:
            routing["output_contract"] = version.output_contract
        else:
            routing.pop("output_contract", None)
        match = routing_specificity(
            routing, provider_id=query.provider_id, model_id=query.model_id,
            capabilities=set(query.capabilities), output_contract=query.output_contract,
        )
        if match is None:
            continue
        score, reason, fallback = match
        published = version.published_at.timestamp() if version.published_at else 0.0
        ranked.append((
            -score, -(profile.user_id == query.user_id), -published, -version.version,
            profile.key, version.id, profile, version, reason, fallback,
        ))
    return sorted(ranked)


async def select_prompt_profile_version(
    db: AsyncSession, query: PromptRouteQuery | None = None, **kwargs,
):
    route = query or PromptRouteQuery(**kwargs)
    ranked = await _ranked_candidates(db, route)
    return ranked[0][7] if ranked else None


async def select_prompt_profile(
    db: AsyncSession, query: PromptRouteQuery | None = None, **kwargs,
) -> PromptSelection | None:
    route = query or PromptRouteQuery(**kwargs)
    ranked = await _ranked_candidates(db, route)
    if not ranked:
        return None
    *_, profile, version, reason, fallback = ranked[0]
    reason, fallback = _legacy_compatibility_reason(
        profile.key,
        dict(version.routing or {}),
        reason,
        fallback,
    )
    return PromptSelection(
        profile_id=profile.id, profile_version_id=version.id,
        profile_key=profile.key, profile_name=profile.name,
        version=version.version, stage=version.stage,
        prompt=render_prompt(version.content, version.variables or {}, route.context),
        routing_reason=reason, fallback_reason=fallback,
        output_contract=version.output_contract, checksum=version.checksum,
        routing=safe_routing_metadata(
            version.routing or {}, reason, version.output_contract,
        ),
    )


async def resolve_prompt_entries(
    db: AsyncSession,
    query: PromptRouteQuery,
) -> tuple[PromptSelection, ...]:
    """Resolve prompt content through the canonical routing owner."""
    legacy_skills = list((await db.scalars(
        select(PromptSkill).where(
            PromptSkill.task == query.task,
            PromptSkill.is_active == True,
            or_(PromptSkill.user_id == query.user_id, PromptSkill.is_builtin == True),
        )
    )).all())
    for skill in legacy_skills:
        await ensure_legacy_prompt_profile(db, skill)
    selection = await select_prompt_profile(db, query=query)
    if selection is None:
        statement = select(PromptSkill).where(
            PromptSkill.task == query.task,
            PromptSkill.is_active == True,
            or_(
                PromptSkill.user_id == query.user_id,
                PromptSkill.is_builtin == True,
            ),
        )
        if query.stage:
            statement = statement.where(
                or_(PromptSkill.stage == query.stage, PromptSkill.stage.is_(None))
            )
        skills = list((await db.scalars(
            statement.order_by(PromptSkill.priority, PromptSkill.created_at)
        )).all())
        for skill in skills:
            if skill.user_id == query.user_id or skill.is_builtin:
                await ensure_legacy_prompt_profile(db, skill)
        if skills:
            selection = await select_prompt_profile(db, query=query)
    return (selection,) if selection is not None else ()
