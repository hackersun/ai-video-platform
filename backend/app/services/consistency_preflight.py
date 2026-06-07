"""Production preflight package for generation tasks."""

from __future__ import annotations

import ipaddress
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chapter, LLMConfig, LLMModel, LLMProvider, Novel, Script, Shot, Storyboard
from app.models.external_api import ExternalAPIConfig, ExternalAPIProvider
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
    try:
        api_key = config.get_api_key_decrypted()
    except Exception:
        api_key = ""
    if not api_key:
        issues.append(
            _issue(
                "model_api_key_missing",
                f"模型配置“{config.name}”API Key 为空或无法解密，请重新保存并验证",
                field="model_config_id",
            )
        )
    return route, issues


async def _resolve_external_config_route(
    db: AsyncSession,
    user_id: str,
    external_config_id: Optional[str],
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    if not external_config_id:
        return {}, []

    result = await db.execute(
        select(ExternalAPIConfig, ExternalAPIProvider)
        .join(ExternalAPIProvider, ExternalAPIConfig.provider_id == ExternalAPIProvider.id)
        .where(
            and_(
                ExternalAPIConfig.id == external_config_id,
                ExternalAPIConfig.user_id == user_id,
                ExternalAPIConfig.is_active == True,
            )
        )
        .limit(1)
    )
    row = result.first()
    if not row:
        return {"external_config_id": external_config_id}, [
            _issue("external_config_missing", "外部生产适配配置不存在或已停用", field="external_config_id")
        ]

    config, provider = row
    route = {
        "external_config_id": config.id,
        "external_provider_id": provider.id,
        "external_provider_name": provider.name,
        "external_provider_name_cn": provider.name_cn or provider.name,
        "api_type": provider.api_type,
        "test_status": config.test_status,
        "is_default": config.is_default,
    }
    issues: List[Dict[str, Any]] = []
    if config.test_status != "success":
        issues.append(
            _issue(
                "external_config_unverified",
                f"外部生产适配“{config.name}”尚未验证通过，生产任务提交前需要先测试通过",
                field="external_config_id",
            )
        )
    try:
        api_key = config.get_api_key_decrypted()
    except Exception:
        api_key = ""
    if not api_key and provider.auth_type != "none":
        issues.append(
            _issue(
                "external_config_api_key_missing",
                f"外部生产适配“{config.name}”API Key 为空或无法解密",
                field="external_config_id",
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


async def _validate_supplied_lineage(
    db: AsyncSession,
    user_id: str,
    lineage: Dict[str, Any],
    *,
    novel_id: Optional[str],
    chapter_id: Optional[str],
    script_id: Optional[str],
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []

    if novel_id:
        result = await db.execute(select(Novel).where(Novel.id == novel_id, Novel.user_id == user_id))
        novel = result.scalar_one_or_none()
        if not novel:
            issues.append(_issue("novel_missing", "小说不存在或无权限访问", field="novel_id"))
        elif lineage.get("novel_id") and lineage["novel_id"] != novel_id:
            issues.append(_issue("lineage_mismatch", "novel_id 与已解析链路不匹配", field="novel_id"))
        else:
            lineage["novel_id"] = novel_id

    chapter = None
    if chapter_id:
        result = await db.execute(select(Chapter).where(Chapter.id == chapter_id, Chapter.user_id == user_id))
        chapter = result.scalar_one_or_none()
        if not chapter:
            issues.append(_issue("chapter_missing", "章节不存在或无权限访问", field="chapter_id"))
        else:
            if lineage.get("chapter_id") and lineage["chapter_id"] != chapter_id:
                issues.append(_issue("lineage_mismatch", "chapter_id 与已解析链路不匹配", field="chapter_id"))
            else:
                lineage["chapter_id"] = chapter_id
            if novel_id and chapter.novel_id != novel_id:
                issues.append(_issue("lineage_mismatch", "chapter_id 不属于所选 novel_id", field="chapter_id"))
            elif lineage.get("novel_id") and chapter.novel_id != lineage["novel_id"]:
                issues.append(_issue("lineage_mismatch", "chapter_id 与已解析小说链路不匹配", field="chapter_id"))
            elif not lineage.get("novel_id"):
                lineage["novel_id"] = chapter.novel_id

    if script_id:
        result = await db.execute(select(Script).where(Script.id == script_id, Script.user_id == user_id))
        script = result.scalar_one_or_none()
        if not script:
            issues.append(_issue("script_missing", "剧本不存在或无权限访问", field="script_id"))
        else:
            if lineage.get("script_id") and lineage["script_id"] != script_id:
                issues.append(_issue("lineage_mismatch", "script_id 与已解析链路不匹配", field="script_id"))
            else:
                lineage["script_id"] = script_id
            if script.novel_id:
                if novel_id and script.novel_id != novel_id:
                    issues.append(_issue("lineage_mismatch", "script_id 不属于所选 novel_id", field="script_id"))
                elif lineage.get("novel_id") and script.novel_id != lineage["novel_id"]:
                    issues.append(_issue("lineage_mismatch", "script_id 与已解析小说链路不匹配", field="script_id"))
                elif not lineage.get("novel_id"):
                    lineage["novel_id"] = script.novel_id
            if script.chapter_id:
                if chapter_id and script.chapter_id != chapter_id:
                    issues.append(_issue("lineage_mismatch", "script_id 不属于所选 chapter_id", field="script_id"))
                elif lineage.get("chapter_id") and script.chapter_id != lineage["chapter_id"]:
                    issues.append(_issue("lineage_mismatch", "script_id 与已解析章节链路不匹配", field="script_id"))
                elif not lineage.get("chapter_id"):
                    lineage["chapter_id"] = script.chapter_id

    return issues


async def build_generation_context_package(
    db: AsyncSession,
    user_id: str,
    *,
    task_type: str,
    model_config_id: Optional[str] = None,
    external_config_id: Optional[str] = None,
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
    issues.extend(
        await _validate_supplied_lineage(
            db,
            user_id,
            lineage,
            novel_id=novel_id,
            chapter_id=chapter_id,
            script_id=script_id,
        )
    )

    model_route, model_issues = await _resolve_model_route(db, user_id, model_config_id)
    issues.extend(model_issues)
    external_route, external_issues = await _resolve_external_config_route(db, user_id, external_config_id)
    issues.extend(external_issues)
    if external_route:
        model_route = {**model_route, "external_config": external_route}

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


def preflight_failure_detail(package: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "code": "generation_preflight_failed",
        "message": "生成预检未通过，请先处理阻断项或明确选择降级策略。",
        "issues": package.get("issues") or [],
        "blocking_issue_count": package.get("blocking_issue_count") or 0,
        "autofix_actions": package.get("autofix_actions") or [],
    }
