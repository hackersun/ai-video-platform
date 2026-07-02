"""Production control helpers for novel-to-anime workflows.

This module keeps P0/P1 production controls lightweight by reusing existing
Novel/Workflow/Shot/Asset/MediaJob metadata instead of adding migration-heavy
tables. It provides three user-facing capabilities:

- final production pack and asset version locks
- persistent media audit for generated history
- AI producer assistant recommendations and executable next steps
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.dev_generation import dev_image_url
from app.core.time_utils import utc_now
from app.models import (
    Asset,
    Chapter,
    MediaGenerationJob,
    Novel,
    Shot,
    StoryEntity,
    Storyboard,
    SynthesisJob,
    TTSJob,
    VideoJob,
    Workflow,
)
from app.services.media_persistence import audit_media_url, persist_remote_media_url
from app.services.production_bible import build_production_bible_summary, build_production_snapshot
from app.services.shot_quality_service import build_shot_quality_report, estimate_shot_generation_budget
from app.services.short_video_production import build_shot_production_contract, persist_contract_to_shot


PRODUCTION_PACK_KEY = "production_pack"


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _uniq(values: Iterable[Any], limit: int = 20) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _scope_label(asset: Asset) -> str:
    if asset.entity_id:
        return "entity"
    if asset.script_id:
        return "script"
    if asset.chapter_id:
        return "chapter"
    if asset.novel_id:
        return "novel"
    if asset.project_id:
        return "project"
    return "global"


async def _load_novel(db: AsyncSession, user_id: str, novel_id: str) -> Novel:
    result = await db.execute(select(Novel).where(Novel.id == novel_id, Novel.user_id == user_id))
    novel = result.scalar_one_or_none()
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="小说不存在")
    return novel


async def _load_workflow(db: AsyncSession, user_id: str, workflow_id: str) -> Workflow:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id))
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")
    return workflow


async def _assets_for_novel(db: AsyncSession, user_id: str, novel_id: str) -> List[Asset]:
    result = await db.execute(
        select(Asset)
        .where(
            Asset.is_active == True,
            or_(Asset.user_id == user_id, Asset.is_public == True),
            or_(Asset.novel_id == novel_id, Asset.novel_id.is_(None)),
        )
        .order_by(desc(Asset.usage_count), desc(Asset.updated_at), desc(Asset.created_at))
        .limit(300)
    )
    return list(result.scalars().all())


async def _entities_for_novel(db: AsyncSession, user_id: str, novel_id: str) -> List[StoryEntity]:
    result = await db.execute(
        select(StoryEntity)
        .where(
            StoryEntity.user_id == user_id,
            or_(StoryEntity.novel_id == novel_id, StoryEntity.novel_id.is_(None)),
        )
        .order_by(StoryEntity.created_at)
    )
    return list(result.scalars().all())


async def _shots_for_workflow(db: AsyncSession, user_id: str, workflow: Workflow) -> List[Shot]:
    if not workflow.storyboard_id:
        return []
    result = await db.execute(
        select(Shot)
        .where(Shot.user_id == user_id, Shot.storyboard_id == workflow.storyboard_id)
        .order_by(Shot.shot_number)
    )
    return list(result.scalars().all())


async def _shots_for_novel(db: AsyncSession, user_id: str, novel_id: str) -> List[Shot]:
    result = await db.execute(
        select(Shot)
        .join(Storyboard, Shot.storyboard_id == Storyboard.id)
        .where(Shot.user_id == user_id, Storyboard.novel_id == novel_id)
        .order_by(Shot.shot_number)
    )
    return list(result.scalars().all())


def _asset_lock(asset: Asset, role: str, entity: Optional[StoryEntity] = None) -> Dict[str, Any]:
    return {
        "asset_id": asset.id,
        "role": role,
        "version": asset.usage_count or 1,
        "name": asset.name,
        "url": asset.url,
        "thumbnail_url": asset.thumbnail_url,
        "locked_at": utc_now().isoformat(),
        "asset_updated_at": str(asset.updated_at),
        "asset_type": asset.asset_type,
        "category": asset.category,
        "scope": _scope_label(asset),
        "entity_id": entity.id if entity else asset.entity_id,
        "entity_name": entity.name if entity else None,
    }


def _match_assets_for_entity(entity: StoryEntity, assets: List[Asset]) -> List[Asset]:
    names = [entity.name] + [str(alias) for alias in _json_list(entity.aliases)]
    entity_attrs = _json_dict(entity.attributes)
    asset_pack = _json_dict(entity_attrs.get("asset_pack") or entity_attrs.get("reference_assets"))
    explicit_urls = {
        str(value)
        for value in asset_pack.values()
        if isinstance(value, str) and value.strip()
    }
    matched: List[Asset] = []
    for asset in assets:
        if asset.entity_id and asset.entity_id == entity.id:
            matched.append(asset)
            continue
        if asset.category != entity.entity_type and not (
            entity.entity_type == "character" and asset.category == "costume"
        ):
            continue
        text = f"{asset.name} {asset.description or ''} {' '.join(asset.tags or [])}"
        if any(name and name in text for name in names):
            matched.append(asset)
            continue
        if asset.url and asset.url in explicit_urls:
            matched.append(asset)
    return matched


def _fallback_asset_for_entity(user_id: str, novel_id: str, entity: StoryEntity) -> Asset:
    attrs = _json_dict(entity.attributes)
    visual = _json_dict(attrs.get("visual_dna") or attrs.get("scene_dna") or attrs.get("prop_dna"))
    prompt = entity.description or "，".join(f"{key}:{value}" for key, value in visual.items()) or entity.name
    return Asset(
        id=str(uuid4()),
        user_id=user_id,
        category=entity.entity_type,
        name=f"{entity.name} 定稿参考",
        description=f"由实体库自动创建的定稿占位资产，用于锁定 {entity.name} 的视觉/声音设定。",
        asset_type="image" if entity.entity_type in {"character", "scene", "prop"} else "text",
        url=dev_image_url(f"asset-lock-{entity.id}", entity.name) if entity.entity_type in {"character", "scene", "prop"} else None,
        thumbnail_url=dev_image_url(f"asset-lock-thumb-{entity.id}", entity.name) if entity.entity_type in {"character", "scene", "prop"} else None,
        novel_id=novel_id,
        chapter_id=entity.chapter_id,
        script_id=getattr(entity, "script_id", None),
        entity_id=entity.id,
        tags=["自动定稿", entity.entity_type],
        style_tags=["anime", "production-lock"],
        prompt_template=prompt,
        generation_params={
            "source": "production_pack",
            "entity_id": entity.id,
            "entity_type": entity.entity_type,
            "created_at": utc_now().isoformat(),
        },
        is_public=False,
        is_active=True,
    )


async def build_novel_production_pack(
    db: AsyncSession,
    user_id: str,
    novel_id: str,
    *,
    create_missing_assets: bool = True,
    persist: bool = True,
) -> Dict[str, Any]:
    novel = await _load_novel(db, user_id, novel_id)
    entities = await _entities_for_novel(db, user_id, novel_id)
    assets = await _assets_for_novel(db, user_id, novel_id)
    locks_by_entity: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    created_assets: List[Asset] = []
    missing_entities: List[Dict[str, Any]] = []

    for entity in entities:
        if entity.novel_id not in {None, novel_id}:
            continue
        matched = _match_assets_for_entity(entity, assets)
        if not matched and create_missing_assets and entity.entity_type in {"character", "scene", "prop"}:
            asset = _fallback_asset_for_entity(user_id, novel_id, entity)
            db.add(asset)
            assets.append(asset)
            created_assets.append(asset)
            matched = [asset]
        if not matched and entity.entity_type in {"character", "scene", "prop"}:
            missing_entities.append({"entity_id": entity.id, "entity_type": entity.entity_type, "name": entity.name})
        for asset in matched[:6]:
            role = {
                "character": "character_reference",
                "scene": "scene_reference",
                "prop": "prop_reference",
                "event": "event_reference",
            }.get(entity.entity_type, "reference")
            locks_by_entity[entity.id].append(_asset_lock(asset, role, entity))

    locks = [lock for items in locks_by_entity.values() for lock in items]
    pack = {
        "version": "production-pack-v1",
        "novel_id": novel.id,
        "novel_title": novel.title,
        "generated_at": utc_now().isoformat(),
        "summary": {
            "entity_count": len(entities),
            "asset_count": len(assets),
            "lock_count": len(locks),
            "created_asset_count": len(created_assets),
            "missing_entity_count": len(missing_entities),
        },
        "locks": locks,
        "locks_by_entity": dict(locks_by_entity),
        "created_asset_ids": [asset.id for asset in created_assets],
        "missing_entities": missing_entities,
        "recommendations": (
            ["仍有实体缺少可锁定资产，建议补齐角色定稿图、场景参考图或道具 DNA。"]
            if missing_entities
            else ["小说级资产定稿包已可用于镜头和媒体任务锁定。"]
        ),
    }

    if persist:
        extra = dict(_json_dict(novel.extra_data))
        extra[PRODUCTION_PACK_KEY] = pack
        novel.extra_data = extra
        novel.updated_at = utc_now()
        flag_modified(novel, "extra_data")
        await db.commit()
        await db.refresh(novel)
    elif created_assets:
        await db.rollback()
    return pack


def _lock_matches_shot(lock: Dict[str, Any], shot: Shot) -> bool:
    extra = _json_dict(shot.extra_data)
    entity_refs = _json_dict(extra.get("entity_refs"))
    names = []
    for key in ("characters", "scenes", "props", "events"):
        for item in _json_list(entity_refs.get(key)):
            if isinstance(item, dict):
                names.append(item.get("name"))
            else:
                names.append(item)
    shot_text = " ".join(str(value or "") for value in [shot.prompt, shot.visual_description, shot.dialogue, extra.get("subtitle_text"), *names])
    entity_name = str(lock.get("entity_name") or "")
    lock_name = str(lock.get("name") or "")
    return bool((entity_name and entity_name in shot_text) or (lock_name and lock_name in shot_text))


async def apply_asset_locks_to_workflow(
    db: AsyncSession,
    user_id: str,
    workflow_id: str,
    *,
    persist: bool = True,
    create_missing_assets: bool = True,
) -> Dict[str, Any]:
    workflow = await _load_workflow(db, user_id, workflow_id)
    if not workflow.novel_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="工作流缺少小说，无法生成资产定稿包")
    pack = await build_novel_production_pack(
        db,
        user_id,
        workflow.novel_id,
        create_missing_assets=create_missing_assets,
        persist=True,
    )
    shots = await _shots_for_workflow(db, user_id, workflow)
    updated: List[Dict[str, Any]] = []
    for shot in shots:
        extra = dict(_json_dict(shot.extra_data))
        production_context = dict(_json_dict(extra.get("production_context")))
        existing = _json_list(production_context.get("asset_version_locks"))
        existing_ids = {item.get("asset_id") for item in existing if isinstance(item, dict)}
        matched = [lock for lock in pack["locks"] if _lock_matches_shot(lock, shot)]
        if not matched:
            matched = pack["locks"][:3]
        merged = existing + [lock for lock in matched if lock.get("asset_id") not in existing_ids]
        production_context["asset_version_locks"] = merged
        production_context["production_pack_version"] = pack["version"]
        production_context["production_pack_generated_at"] = pack["generated_at"]
        production_context["updated_at"] = utc_now().isoformat()
        extra["production_context"] = production_context
        shot.extra_data = extra
        shot.updated_at = utc_now()
        quality_report = build_shot_quality_report(shot)
        extra["quality_report"] = quality_report
        shot.extra_data = extra
        updated.append({
            "shot_id": shot.id,
            "shot_number": shot.shot_number,
            "lock_count": len(merged),
            "status": quality_report.get("status"),
        })

    metadata = dict(_json_dict(workflow.metadata_))
    metadata["production_pack"] = {
        "novel_id": workflow.novel_id,
        "generated_at": pack["generated_at"],
        "lock_count": pack["summary"]["lock_count"],
        "applied_shot_count": len(updated),
    }
    production_bible_summary = await build_production_bible_summary(db, user_id, workflow.novel_id)
    metadata["production_snapshot"] = build_production_snapshot(
        production_bible_summary,
        reason="asset_locks_applied",
    )
    workflow.metadata_ = metadata
    workflow.updated_at = utc_now()
    flag_modified(workflow, "metadata_")
    if persist:
        await db.commit()
    return {
        "workflow_id": workflow.id,
        "novel_id": workflow.novel_id,
        "production_pack": pack,
        "production_bible_summary": production_bible_summary,
        "production_snapshot": metadata["production_snapshot"],
        "applied_shots": updated,
    }


async def _persist_job_url(
    url: Optional[str],
    media_type: str,
    subdir: str,
    prefix: str,
    dry_run: bool,
) -> tuple[Optional[str], Optional[str]]:
    audit = audit_media_url(url)
    if not url or dry_run or audit.get("persistent"):
        return url, None
    try:
        persisted = await persist_remote_media_url(url, media_type=media_type, subdir=subdir, prefix=prefix)
        return persisted, None
    except Exception as exc:  # pragma: no cover - defensive branch depends on network/provider
        return url, str(exc)


def _media_item(kind: str, item_id: str, field: str, url: Optional[str], extra: Optional[dict] = None) -> Dict[str, Any]:
    return {
        "kind": kind,
        "id": item_id,
        "field": field,
        "url": url,
        "audit": audit_media_url(url),
        **(extra or {}),
    }


async def audit_and_persist_workflow_media(
    db: AsyncSession,
    user_id: str,
    workflow_id: str,
    *,
    persist_remote: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    workflow = await _load_workflow(db, user_id, workflow_id)
    items: List[Dict[str, Any]] = []

    video_result = await db.execute(select(VideoJob).where(VideoJob.user_id == user_id, VideoJob.workflow_id == workflow.id, VideoJob.is_active == True))
    video_jobs = list(video_result.scalars().all())
    media_result = await db.execute(select(MediaGenerationJob).where(MediaGenerationJob.user_id == user_id, MediaGenerationJob.workflow_id == workflow.id, MediaGenerationJob.is_active == True))
    media_jobs = list(media_result.scalars().all())
    tts_result = await db.execute(select(TTSJob).where(TTSJob.user_id == user_id, TTSJob.workflow_id == workflow.id, TTSJob.is_active == True))
    tts_jobs = list(tts_result.scalars().all())
    synthesis_result = await db.execute(select(SynthesisJob).where(SynthesisJob.user_id == user_id, SynthesisJob.workflow_id == workflow.id, SynthesisJob.is_active == True))
    synthesis_jobs = list(synthesis_result.scalars().all())

    for job in video_jobs:
        new_url, error = await _persist_job_url(job.video_url, "video", "videos", f"video-{job.id}", dry_run or not persist_remote)
        if new_url != job.video_url:
            extra = dict(_json_dict(job.extra_data))
            extra.setdefault("persistence", {})["original_video_url"] = job.video_url
            job.video_url = new_url
            job.extra_data = extra
        items.append(_media_item("video_job", job.id, "video_url", job.video_url, {"error": error}))
        new_cover, error = await _persist_job_url(job.cover_url, "image", "covers", f"video-cover-{job.id}", dry_run or not persist_remote)
        if new_cover != job.cover_url:
            job.cover_url = new_cover
        if job.cover_url:
            items.append(_media_item("video_job", job.id, "cover_url", job.cover_url, {"error": error}))

    for job in media_jobs:
        new_url, error = await _persist_job_url(job.output_video_url, "video", "media-videos", f"media-video-{job.id}", dry_run or not persist_remote)
        if new_url != job.output_video_url:
            job.output_video_url = new_url
        items.append(_media_item("media_job", job.id, "output_video_url", job.output_video_url, {"error": error}))
        new_audio, error = await _persist_job_url(job.output_audio_url, "audio", "media-audio", f"media-audio-{job.id}", dry_run or not persist_remote)
        if new_audio != job.output_audio_url:
            job.output_audio_url = new_audio
        if job.output_audio_url:
            items.append(_media_item("media_job", job.id, "output_audio_url", job.output_audio_url, {"error": error}))
        if job.output_manifest_url:
            items.append(_media_item("media_job", job.id, "output_manifest_url", job.output_manifest_url))
        if job.cover_url:
            items.append(_media_item("media_job", job.id, "cover_url", job.cover_url))

    for job in tts_jobs:
        new_audio, error = await _persist_job_url(job.audio_url, "audio", "tts", f"tts-{job.id}", dry_run or not persist_remote)
        if new_audio != job.audio_url:
            job.audio_url = new_audio
        items.append(_media_item("tts_job", job.id, "audio_url", job.audio_url, {"error": error}))

    for job in synthesis_jobs:
        if job.video_url:
            items.append(_media_item("synthesis_job", job.id, "video_url", job.video_url))
        if job.audio_url:
            items.append(_media_item("synthesis_job", job.id, "audio_url", job.audio_url))
        if job.output_url:
            items.append(_media_item("synthesis_job", job.id, "output_url", job.output_url))
        artifacts = _json_dict(_json_dict(job.extra_data).get("render_artifacts"))
        for field, url in artifacts.items():
            items.append(_media_item("render_artifact", job.id, field, url))

    status_counts = Counter(item["audit"]["status"] for item in items)
    missing = [item for item in items if item["audit"]["status"] in {"missing", "local_missing"}]
    remote = [item for item in items if item["audit"]["status"] == "remote"]
    audit_summary = {
        "checked_at": utc_now().isoformat(),
        "item_count": len(items),
        "missing_count": len(missing),
        "remote_count": len(remote),
        "status_counts": dict(status_counts),
        "dry_run": dry_run,
    }
    if not dry_run:
        metadata = dict(_json_dict(workflow.metadata_))
        metadata["media_persistence_audit"] = audit_summary
        workflow.metadata_ = metadata
        workflow.updated_at = utc_now()
        await db.commit()
    return {
        "workflow_id": workflow.id,
        "summary": audit_summary,
        "items": items,
        "blocking_issues": [
            {"code": "missing_media_file", "message": f"{item['kind']} {item['field']} 文件不存在", "item": item}
            for item in missing[:30]
        ],
        "recommendations": (
            ["存在本地媒体文件缺失，请重新生成对应镜头或恢复静态文件。"]
            if missing
            else ["媒体历史巡检通过，当前可用产物可以长期播放或下载。"]
        ),
    }


async def build_workflow_quality_report(
    db: AsyncSession,
    user_id: str,
    workflow_id: str,
    *,
    persist: bool = True,
) -> Dict[str, Any]:
    workflow = await _load_workflow(db, user_id, workflow_id)
    shots = await _shots_for_workflow(db, user_id, workflow)
    items: List[Dict[str, Any]] = []
    for shot in shots:
        quality_report = build_shot_quality_report(shot)
        budget_estimate = estimate_shot_generation_budget(shot)
        items.append({
            "shot_id": shot.id,
            "shot_number": shot.shot_number,
            "quality_report": quality_report,
            "budget_estimate": budget_estimate,
        })
        if persist:
            extra = dict(_json_dict(shot.extra_data))
            extra["quality_report"] = quality_report
            extra["budget_estimate"] = budget_estimate
            shot.extra_data = extra
            shot.updated_at = utc_now()
    blockers = [blocker for item in items for blocker in _json_list(item["quality_report"].get("blockers"))]
    warnings = [warning for item in items for warning in _json_list(item["quality_report"].get("warnings"))]
    scores = [int(item["quality_report"].get("score") or 0) for item in items]
    summary = {
        "shot_count": len(items),
        "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "blocked_count": sum(1 for item in items if item["quality_report"].get("status") == "blocked"),
        "warning_count": sum(1 for item in items if item["quality_report"].get("status") == "warning"),
        "ready_count": sum(1 for item in items if item["quality_report"].get("status") == "ready"),
        "blocker_count": len(blockers),
        "risk_count": len(warnings),
    }
    metadata = dict(_json_dict(workflow.metadata_))
    metadata["production_quality_report"] = {
        **summary,
        "checked_at": utc_now().isoformat(),
    }
    workflow.metadata_ = metadata
    workflow.updated_at = utc_now()
    if persist:
        await db.commit()
    return {
        "workflow_id": workflow.id,
        "summary": summary,
        "items": items,
        "blocking_issues": [{"code": "shot_quality_blocker", "message": text} for text in blockers[:30]],
        "warnings": [{"code": "shot_quality_warning", "message": text} for text in warnings[:50]],
        "recommendations": _quality_recommendations(summary),
    }


async def refresh_workflow_production_contracts(
    db: AsyncSession,
    user_id: str,
    workflow_id: str,
    *,
    shot_ids: Optional[List[str]] = None,
    force: bool = False,
    persist: bool = True,
) -> Dict[str, Any]:
    workflow = await _load_workflow(db, user_id, workflow_id)
    shots = await _shots_for_workflow(db, user_id, workflow)
    requested_ids = {str(shot_id) for shot_id in (shot_ids or []) if str(shot_id).strip()}
    refreshed: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for shot in shots:
        if requested_ids and shot.id not in requested_ids:
            continue
        production_context = _json_dict(_json_dict(shot.extra_data).get("production_context"))
        if production_context.get("production_contract") and not force and not requested_ids:
            skipped.append({"shot_id": shot.id, "shot_number": shot.shot_number, "reason": "contract_exists"})
            continue
        contract = await build_shot_production_contract(db, user_id, shot.id)
        contract["lineage"] = {**_json_dict(contract.get("lineage")), "workflow_id": workflow.id}
        persist_contract_to_shot(shot, contract)
        refreshed.append({
            "shot_id": shot.id,
            "shot_number": shot.shot_number,
            "contract_version": contract.get("contract_version"),
            "seed": contract.get("seed"),
        })

    if persist:
        metadata = dict(_json_dict(workflow.metadata_))
        production_bible_summary = None
        if workflow.novel_id:
            production_bible_summary = await build_production_bible_summary(db, user_id, workflow.novel_id)
        metadata["production_contracts"] = {
            "refreshed_at": utc_now().isoformat(),
            "refreshed_count": len(refreshed),
            "skipped_count": len(skipped),
        }
        if production_bible_summary:
            metadata["production_snapshot"] = build_production_snapshot(
                production_bible_summary,
                reason="production_contracts_refreshed",
            )
        workflow.metadata_ = metadata
        workflow.updated_at = utc_now()
        flag_modified(workflow, "metadata_")
        await db.commit()

    response = {
        "workflow_id": workflow.id,
        "storyboard_id": workflow.storyboard_id,
        "refreshed_count": len(refreshed),
        "skipped_count": len(skipped),
        "refreshed_shots": refreshed,
        "skipped_shots": skipped,
    }
    snapshot = _json_dict(_json_dict(workflow.metadata_).get("production_snapshot"))
    if snapshot:
        response["production_snapshot"] = snapshot
        response["production_bible_summary"] = _json_dict(snapshot.get("summary"))
    return response


def _quality_recommendations(summary: Dict[str, Any]) -> List[str]:
    if not summary["shot_count"]:
        return ["当前工作流还没有镜头，请先生成分镜和镜头。"]
    recommendations = []
    if summary["blocked_count"]:
        recommendations.append("先修复缺少提示词、视觉描述或字幕的阻断镜头，再批量生成。")
    if summary["warning_count"]:
        recommendations.append("补齐角色/场景/道具引用、关键帧和资产锁，降低多镜头漂移。")
    if summary["average_score"] >= 85 and not summary["blocked_count"]:
        recommendations.append("当前镜头质量已达到出片前检查要求，可进入批量生成或渲染。")
    return recommendations


async def build_ai_producer_assistant(
    db: AsyncSession,
    user_id: str,
    workflow_id: str,
    *,
    auto_fix: bool = False,
    action_code: Optional[str] = None,
) -> Dict[str, Any]:
    workflow = await _load_workflow(db, user_id, workflow_id)
    actions: List[Dict[str, Any]] = []
    executed: List[Dict[str, Any]] = []

    def should_execute(code: str) -> bool:
        return auto_fix and (not action_code or action_code == code)

    if not workflow.novel_id:
        actions.append({"code": "select_novel", "label": "选择小说", "priority": "P0", "status": "blocked", "detail": "工作流缺少小说，无法串联整部动漫生产。"})
        return {"workflow_id": workflow.id, "summary": {"next_action": actions[0], "ready": False}, "actions": actions, "executed": executed}

    novel = await _load_novel(db, user_id, workflow.novel_id)
    chapters_result = await db.execute(select(Chapter).where(Chapter.user_id == user_id, Chapter.novel_id == novel.id).order_by(Chapter.chapter_number))
    chapters = list(chapters_result.scalars().all())
    shots = await _shots_for_workflow(db, user_id, workflow)
    pack = _json_dict(_json_dict(novel.extra_data).get(PRODUCTION_PACK_KEY))

    if not chapters:
        actions.append({"code": "create_chapter", "label": "补章节", "priority": "P0", "status": "blocked", "detail": "小说还没有章节，无法生成剧本、分镜和镜头。"})
    if not pack:
        actions.append({"code": "build_production_pack", "label": "生成资产定稿包", "priority": "P0", "status": "ready", "detail": "锁定角色、场景、道具参考资产，避免多集生成漂移。"})
        if should_execute("build_production_pack"):
            result = await apply_asset_locks_to_workflow(db, user_id, workflow.id, persist=True)
            executed.append({"code": "build_production_pack", "result": result.get("production_pack", {}).get("summary")})
    elif workflow.storyboard_id and any(not _json_list(_json_dict(_json_dict(shot.extra_data).get("production_context")).get("asset_version_locks")) for shot in shots):
        actions.append({"code": "apply_asset_locks", "label": "应用资产锁到镜头", "priority": "P0", "status": "ready", "detail": "部分镜头缺少资产锁，需要从小说定稿包同步。"})
        if should_execute("apply_asset_locks"):
            result = await apply_asset_locks_to_workflow(db, user_id, workflow.id, persist=True)
            executed.append({"code": "apply_asset_locks", "result": {"applied_shot_count": len(result.get("applied_shots") or [])}})

    missing_contracts = [
        shot for shot in shots
        if not _json_dict(_json_dict(shot.extra_data).get("production_context")).get("production_contract")
    ]
    if workflow.storyboard_id and missing_contracts:
        actions.append({"code": "refresh_contracts", "label": "刷新镜头生产合约", "priority": "P0", "status": "ready", "detail": f"{len(missing_contracts)} 个镜头缺少 Production Contract。"})
        if should_execute("refresh_contracts"):
            result = await refresh_workflow_production_contracts(
                db,
                user_id,
                workflow.id,
                shot_ids=[shot.id for shot in missing_contracts],
                persist=True,
            )
            executed.append({"code": "refresh_contracts", "result": {"refreshed_count": result["refreshed_count"]}})

    media_audit = await audit_and_persist_workflow_media(db, user_id, workflow.id, persist_remote=False, dry_run=True)
    if media_audit["summary"]["missing_count"]:
        actions.append({"code": "regenerate_missing_media", "label": "重生成缺失媒体", "priority": "P0", "status": "manual", "detail": f"{media_audit['summary']['missing_count']} 个媒体链接缺失，需要重新生成或恢复文件。"})
    elif media_audit["summary"]["remote_count"]:
        actions.append({"code": "persist_remote_media", "label": "转存远端临时媒体", "priority": "P0", "status": "ready", "detail": f"{media_audit['summary']['remote_count']} 个远端媒体建议转存。"})
        if should_execute("persist_remote_media"):
            result = await audit_and_persist_workflow_media(db, user_id, workflow.id, persist_remote=True, dry_run=False)
            executed.append({"code": "persist_remote_media", "result": result.get("summary")})

    quality = await build_workflow_quality_report(db, user_id, workflow.id, persist=auto_fix and not action_code)
    if quality["summary"]["blocked_count"]:
        actions.append({"code": "fix_shot_blockers", "label": "修复镜头阻断项", "priority": "P0", "status": "manual", "detail": "存在缺少提示词、视觉描述或字幕的镜头。"})
    elif quality["summary"]["warning_count"]:
        actions.append({"code": "review_quality_warnings", "label": "处理质量提醒", "priority": "P1", "status": "manual", "detail": "建议补充关键帧、角色/场景/道具引用和审核状态。"})

    next_action = actions[0] if actions else {"code": "ready_for_generation", "label": "可以进入生成/渲染", "priority": "P0", "status": "ready", "detail": "当前工作流关键生产输入已就绪。"}
    return {
        "workflow_id": workflow.id,
        "novel_id": novel.id,
        "summary": {
            "ready": not actions,
            "next_action": next_action,
            "requested_action_code": action_code,
            "action_count": len(actions),
            "executed_count": len(executed),
            "media_missing_count": media_audit["summary"]["missing_count"],
            "quality_average_score": quality["summary"]["average_score"],
        },
        "actions": actions,
        "executed": executed,
        "media_audit": media_audit["summary"],
        "quality": quality["summary"],
    }
