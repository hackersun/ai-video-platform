"""Final-quality reference package rules for workflow media generation."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.workflow_media.errors import WorkflowMediaError
from app.models import Shot, Workflow
from app.services.reference_package_builder import bind_reference_package, build_reference_package
from app.services.video_reference_adapter import requires_provider_bindings


def supports_reference_package(model_limits: Dict[str, Any]) -> bool:
    """Return whether the selected model requires a bound reference package."""
    return requires_provider_bindings(model_limits)


def _extra(value: Any) -> Dict[str, Any]:
    return value.extra_data if isinstance(value.extra_data, dict) else {}


def shot_character_names(shot: Shot) -> List[str]:
    """Return unique character names using the workflow endpoint's legacy precedence."""
    names: List[str] = []
    refs = shot.character_refs if isinstance(shot.character_refs, list) else []
    if not refs:
        entity_refs = _extra(shot).get("entity_refs")
        entity_refs = entity_refs if isinstance(entity_refs, dict) else {}
        refs = entity_refs.get("characters") if isinstance(entity_refs.get("characters"), list) else []
    for ref in refs:
        if isinstance(ref, str):
            candidate = ref.strip()
        elif isinstance(ref, dict):
            candidate = str(
                ref.get("name")
                or ref.get("character_name")
                or ref.get("entity_name")
                or ref.get("label")
                or ""
            ).strip()
        else:
            candidate = ""
        if candidate and candidate not in names:
            names.append(candidate)
    return names


def workflow_shot_lineage(workflow: Workflow, shot: Shot) -> Dict[str, Any]:
    """Build the canonical lineage passed to the reference package builder."""
    return {
        "workflow_id": workflow.id,
        "novel_id": workflow.novel_id,
        "chapter_id": workflow.chapter_id,
        "script_id": workflow.script_id,
        "storyboard_id": workflow.storyboard_id or shot.storyboard_id,
        "shot_id": shot.id,
        "shot_number": shot.shot_number,
    }


def _protagonist_count(package: Dict[str, Any]) -> int:
    return sum(
        1
        for item in package.get("images") or []
        if isinstance(item, dict) and item.get("role_tag") == "protagonist"
    )


def _issue(code: str, shot: Shot, package: Dict[str, Any]) -> Dict[str, Any]:
    character_names = shot_character_names(shot)
    return {
        "code": code,
        "shot_id": shot.id,
        "shot_number": shot.shot_number,
        "entity_name": character_names[0] if character_names else None,
        "available_reference_images": _protagonist_count(package),
        "required_reference_images": 2,
        "dropped": package.get("dropped") or [],
    }


def _raise_reference_issues(issues: List[Dict[str, Any]]) -> None:
    first_issue = issues[0]
    error_code = str(first_issue.get("code") or "reference_package_insufficient")
    message = (
        "所选模型的 final_quality 生成缺少已验证供应商引用，请先在定稿卡生成模型引用"
        if error_code == "provider_binding_required"
        else "Seedance 2.0 final_quality 生成前，主角至少需要 2 个可公网提交的锁定参考视图"
    )
    raise WorkflowMediaError(422, {
        "code": error_code,
        "message": message,
        "entity_name": first_issue.get("entity_name"),
        "issues": issues,
    })


def _required_options(options: Dict[str, Any]) -> tuple[Any, str, str]:
    expected = {"model_limits", "resolve_public_url", "provider_id", "model_id"}
    unexpected = set(options) - expected
    missing = expected - set(options)
    if unexpected or missing:
        names = sorted(unexpected or missing)
        problem = "unexpected" if unexpected else "missing"
        raise TypeError(f"{problem} keyword argument(s): {', '.join(names)}")
    return options["resolve_public_url"], options["provider_id"], options["model_id"]


async def build_final_quality_reference_packages(
    db: AsyncSession,
    user_id: str,
    workflow: Workflow,
    shots: List[Shot],
    **options: Any,
) -> Dict[str, Dict[str, Any]]:
    """Build and bind final-quality references, preserving legacy fail-closed behavior."""
    model_limits = options.get("model_limits")
    if not supports_reference_package(model_limits):
        return {}
    resolve_public_url, provider_id, model_id = _required_options(options)
    packages: Dict[str, Dict[str, Any]] = {}
    issues: List[Dict[str, Any]] = []
    for shot in shots:
        canonical = await build_reference_package(
            db,
            user_id,
            shot=shot,
            lineage=workflow_shot_lineage(workflow, shot),
            model_limits=model_limits,
            resolve_public_url=resolve_public_url,
        )
        if _protagonist_count(canonical) < 2:
            issues.append(_issue("reference_package_insufficient", shot, canonical))
            continue
        package = await bind_reference_package(
            db, canonical, provider_id=provider_id, model_id=model_id
        )
        packages[shot.id] = package
        if _protagonist_count(package) < 2:
            issues.append(_issue("provider_binding_required", shot, package))
    if issues:
        _raise_reference_issues(issues)
    return packages


__all__ = [
    "build_final_quality_reference_packages",
    "shot_character_names",
    "supports_reference_package",
    "workflow_shot_lineage",
]
