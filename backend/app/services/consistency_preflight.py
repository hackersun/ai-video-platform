"""Production preflight package for generation tasks."""

from __future__ import annotations

import ipaddress
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LLMConfig, LLMModel, LLMProvider, Shot, Storyboard
from app.services.consistency_context import _locked_asset_refs_from_extra
from app.services.entity_ref_normalizer import normalize_entity_refs


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _issue(code: str, message: str, *, severity: str = "blocking", field: Optional[str] = None) -> Dict[str, Any]:
    return {"code": code, "message": message, "severity": severity, "field": field}


def _is_public_http_url(url: Optional[str]) -> tuple[bool, Optional[str]]:
    if not url:
        return False, "未提供参考图"
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return False, "参考图不是公网 http(s) URL"
    hostname = parsed.hostname
    if not hostname:
        return False, "参考图缺少有效域名"
    host = hostname.lower()
    if host in {"localhost", "local"} or host.endswith(".local"):
        return False, "参考图指向本机或局域网域名"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True, None
    if not ip.is_global:
        return False, "参考图指向内网、本机或保留 IP"
    return True, None


async def _resolve_model_route(
    db: AsyncSession,
    user_id: str,
    model_config_id: Optional[str],
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    if not model_config_id:
        return {}, []

    result = await db.execute(
        select(LLMConfig, LLMModel, LLMProvider)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
        .where(
            and_(
                LLMConfig.id == model_config_id,
                LLMConfig.user_id == user_id,
                LLMConfig.is_active == True,
            )
        )
        .limit(1)
    )
    row = result.first()
    if not row:
        return {"model_config_id": model_config_id}, [
            _issue("model_config_missing", "所选模型配置不存在或已停用", field="model_config_id")
        ]

    config, model, provider = row
    route = {
        "provider_id": provider.name or provider.id,
        "provider_name": provider.name_cn or provider.name,
        "model_config_id": config.id,
        "config_model_id": model.id,
        "api_model_id": model.model_id,
        "model_name": model.model_name_cn or model.model_name,
        "model_type": model.model_type,
        "capabilities": model.capabilities or [],
        "test_status": config.test_status,
        "is_default": config.is_default,
    }
    issues: List[Dict[str, Any]] = []
    if config.test_status != "success":
        issues.append(
            _issue(
                "model_unverified",
                f"模型配置“{config.name}”尚未验证通过，生产生成前需要先测试通过",
                field="model_config_id",
            )
        )
    return route, issues


async def _resolve_lineage(
    db: AsyncSession,
    user_id: str,
    *,
    shot_id: Optional[str],
    storyboard_id: Optional[str],
) -> tuple[Dict[str, Any], List[Dict[str, Any]], Optional[Shot]]:
    lineage: Dict[str, Any] = {"shot_id": shot_id, "storyboard_id": storyboard_id}
    issues: List[Dict[str, Any]] = []
    shot = None
    storyboard = None

    if shot_id:
        result = await db.execute(select(Shot).where(Shot.id == shot_id, Shot.user_id == user_id))
        shot = result.scalar_one_or_none()
        if not shot:
            issues.append(_issue("shot_missing", "镜头不存在或无权限访问", field="shot_id"))
            return lineage, issues, None
        lineage["storyboard_id"] = shot.storyboard_id
        if storyboard_id and storyboard_id != shot.storyboard_id:
            issues.append(_issue("lineage_mismatch", "shot_id 与 storyboard_id 不匹配", field="storyboard_id"))

    if lineage.get("storyboard_id"):
        result = await db.execute(
            select(Storyboard).where(Storyboard.id == lineage["storyboard_id"], Storyboard.user_id == user_id)
        )
        storyboard = result.scalar_one_or_none()
        if not storyboard:
            issues.append(_issue("storyboard_missing", "分镜不存在或无权限访问", field="storyboard_id"))
        else:
            lineage["script_id"] = storyboard.script_id
            lineage["novel_id"] = storyboard.novel_id
            content = _json_dict(storyboard.content)
            if content.get("chapter_id"):
                lineage["chapter_id"] = content["chapter_id"]

    return lineage, issues, shot


async def build_generation_context_package(
    db: AsyncSession,
    user_id: str,
    *,
    task_type: str,
    model_config_id: Optional[str] = None,
    image_url: Optional[str] = None,
    production_mode: bool = True,
    require_public_reference_image: bool = False,
    shot_id: Optional[str] = None,
    storyboard_id: Optional[str] = None,
    novel_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    script_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a lightweight package and production blocking issues."""
    issues: List[Dict[str, Any]] = []
    lineage, lineage_issues, shot = await _resolve_lineage(
        db,
        user_id,
        shot_id=shot_id,
        storyboard_id=storyboard_id,
    )
    issues.extend(lineage_issues)
    for key, value in (("novel_id", novel_id), ("chapter_id", chapter_id), ("script_id", script_id)):
        if value and lineage.get(key) and lineage[key] != value:
            issues.append(_issue("lineage_mismatch", f"{key} 与已解析链路不匹配", field=key))
        elif value:
            lineage[key] = value

    model_route, model_issues = await _resolve_model_route(db, user_id, model_config_id)
    issues.extend(model_issues)

    if require_public_reference_image or image_url:
        is_public, reason = _is_public_http_url(image_url)
        if not is_public:
            issues.append(
                _issue(
                    "reference_image_not_public",
                    f"{reason}，云端图生视频需要公网可访问对象存储/CDN地址",
                    field="image_url",
                )
            )

    shot_extra = _json_dict(getattr(shot, "extra_data", None)) if shot else {}
    entity_refs = normalize_entity_refs(shot_extra.get("entity_refs"))
    locked_assets = _locked_asset_refs_from_extra(shot_extra)
    if production_mode and task_type in {"shot_video", "direct_audio_video", "image_generation"} and shot:
        if not any(entity_refs.values()):
            issues.append(_issue("missing_entity_refs", "镜头缺少人物/场景/道具/事件引用，建议先 AI 补齐实体引用"))
        if task_type in {"shot_video", "direct_audio_video"} and not locked_assets:
            issues.append(_issue("missing_asset_locks", "镜头缺少角色/场景/道具定稿资产锁，可能导致跨镜头画风或人物漂移"))

    blocking = [item for item in issues if item.get("severity") == "blocking"]
    package = {
        "task_type": task_type,
        "lineage": lineage,
        "entity_refs": entity_refs,
        "asset_version_locks": locked_assets,
        "reference_images": [{"url": image_url, "public": _is_public_http_url(image_url)[0]}] if image_url else [],
        "model_route": model_route,
        "issues": issues,
        "blocking_issue_count": len(blocking),
        "warning_issue_count": len([item for item in issues if item.get("severity") == "warning"]),
        "ready": len(blocking) == 0,
        "autofix_actions": [
            {"code": "fill_entity_refs", "label": "AI 补齐实体引用"}
            for item in issues
            if item.get("code") == "missing_entity_refs"
        ],
    }
    return package
