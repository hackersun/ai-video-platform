"""统一创作工作台只读快照聚合。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Asset,
    Chapter,
    Clip,
    MediaGenerationJob,
    Novel,
    ProductionStateEvent,
    QualityEvaluation,
    Script,
    Shot,
    StoryBible,
    Storyboard,
    SynthesisJob,
    Timeline,
    TTSJob,
    VideoJob,
    Workflow,
)
from app.services.shot_quality_service import build_shot_quality_report
from app.services.studio_guidance import build_studio_guidance
from app.services.studio_mode import StudioModePolicy, apply_mode_policy
from app.services.story_state_machine import get_story_state_machine
from app.services.production_bible import build_production_bible_summary
from app.services.production_graph_service import project_story_state
from app.services.consistency_ledger_service import build_consistency_ledger
from app.services.series_production import resolve_production_graph_artifact_impact
from app.services.series_studio_flags import series_studio_contract
from app.services.studio_episode_shots import (
    load_studio_episode_shots,
    load_studio_episode_storyboards,
)


SHOT_LIMIT = 80
ASSET_LIMIT = 100
JOB_LIMIT = 100
REFERENCE_PACKAGE_EVIDENCE_LIMIT = 5


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _dt(value: Any) -> Optional[str]:
    return value.isoformat() if value else None


def _job_ids(values: Any) -> List[str]:
    return [str(value) for value in (values or []) if value]


def _production_strategy_metadata(strategy: Optional[str]) -> Dict[str, Any]:
    if not strategy:
        return {}
    strategy_map = {
        "draft_fast": {
            "production_strategy_label": "Draft Fast",
            "production_strategy_intent": "draft",
            "recommended_model_hint": "Seedance-2.0-fast",
        },
        "final_quality": {
            "production_strategy_label": "Final Quality",
            "production_strategy_intent": "final",
            "recommended_model_hint": "Seedance-2.0",
        },
        "low_cost": {
            "production_strategy_label": "Low Cost",
            "production_strategy_intent": "draft",
            "recommended_model_hint": "low-cost configuration",
        },
        "separate_video_tts": {
            "production_strategy_label": "Separate Video + TTS",
            "production_strategy_intent": "draft",
            "recommended_model_hint": None,
        },
        "direct_av_first": {
            "production_strategy_label": "Direct AV First",
            "production_strategy_intent": "draft",
            "recommended_model_hint": None,
        },
    }
    metadata = strategy_map.get(strategy, {})
    return {
        "production_strategy": strategy,
        "strategy_routing_enabled": True,
        **metadata,
    }


def _merge_latest_production_strategy(metadata: Dict[str, Any]) -> Dict[str, Any]:
    strategy = metadata.get("latest_production_strategy")
    strategy_metadata = _production_strategy_metadata(strategy)
    if not strategy_metadata:
        return metadata
    return {
        **metadata,
        "latest_production_strategy_label": strategy_metadata.get("production_strategy_label"),
        "latest_production_strategy_intent": strategy_metadata.get("production_strategy_intent"),
        "latest_recommended_model_hint": strategy_metadata.get("recommended_model_hint"),
        "production_strategy_metadata": strategy_metadata,
    }


def _job_strategy_summary(job: Any) -> Dict[str, Any]:
    extra = _json_dict(getattr(job, "extra_data", None))
    strategy = extra.get("production_strategy")
    if not strategy:
        return {}
    return {
        "production_strategy": strategy,
        "production_strategy_label": extra.get("production_strategy_label"),
        "production_strategy_intent": extra.get("production_strategy_intent"),
        "recommended_model_hint": extra.get("recommended_model_hint"),
    }


def _safe_reference_item(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    keys = "id asset_id type role name source reason role_tag entity_name view_key source_shot_id canonical_asset_id".split()
    return {key: item[key] for key in keys if item.get(key) is not None}


def _reference_count(package: Dict[str, Any], key: str, media_items: List[Any], package_items: List[Any], item_type: str) -> int:
    value = package.get(key)
    if isinstance(value, int):
        return value
    if media_items:
        return len(media_items)
    return len([item for item in package_items if _json_dict(item).get("type") == item_type])


def _reference_package_summary(job: Any) -> Dict[str, Any]:
    extra = _json_dict(getattr(job, "extra_data", None))
    package = _json_dict(extra.get("reference_package"))
    if not package:
        return {}

    items = _json_list(package.get("items"))
    images = _json_list(package.get("images"))
    videos = _json_list(package.get("videos"))
    dropped = _json_list(package.get("dropped"))
    evidence_source = items or [
        {"type": "image", **item} for item in images if isinstance(item, dict)
    ] + [
        {"type": "video", **item} for item in videos if isinstance(item, dict)
    ]
    safe_items = [
        safe_item
        for safe_item in (_safe_reference_item(item) for item in evidence_source[:REFERENCE_PACKAGE_EVIDENCE_LIMIT])
        if safe_item
    ]
    safe_dropped = [
        safe_item
        for safe_item in (_safe_reference_item(item) for item in dropped[:REFERENCE_PACKAGE_EVIDENCE_LIMIT])
        if safe_item
    ]
    image_count = _reference_count(package, "image_count", images, items, "image")
    video_count = _reference_count(package, "video_count", videos, items, "video")

    summary: Dict[str, Any] = {
        "image_count": image_count,
        "video_count": video_count,
        "dropped_count": len(dropped),
    }
    if safe_items:
        summary["items"] = safe_items
    if safe_dropped:
        summary["dropped"] = safe_dropped

    payload = {"reference_package": summary}
    if extra.get("reference_package_mode"):
        payload["reference_package_mode"] = extra.get("reference_package_mode")
    elif package.get("reference_package_mode"):
        payload["reference_package_mode"] = package.get("reference_package_mode")
    return payload


def _issue(
    code: str,
    message: str,
    *,
    severity: str = "blocking",
    repair_action: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "severity": severity,
        "repair_action": repair_action,
    }


def _action(code: str, label: str, *, href: Optional[str] = None, risk: str = "safe") -> Dict[str, Any]:
    return {"code": code, "label": label, "href": href, "risk": risk}


def _unique_actions(issues: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for issue in issues:
        action = issue.get("repair_action")
        if not isinstance(action, dict):
            continue
        code = str(action.get("code") or "")
        if not code or code in seen:
            continue
        seen.add(code)
        actions.append(action)
    return actions


def _chapter_ids_from_episode(episode: Dict[str, Any]) -> List[str]:
    return [str(value) for value in _json_list(episode.get("chapter_ids")) if value]


def _series_plan_with_current_episode(plan: Dict[str, Any], chapter_id: Optional[str]) -> Dict[str, Any]:
    if not plan:
        return {}

    payload = dict(plan)
    episodes = [episode for episode in _json_list(payload.get("episodes")) if isinstance(episode, dict)]
    current_episode = None
    if chapter_id:
        current_episode = next(
            (episode for episode in episodes if chapter_id in _chapter_ids_from_episode(episode)),
            None,
        )
    if current_episode is None and episodes:
        current_episode = episodes[0]
    payload["current_episode"] = current_episode
    return payload


def _saved_series_plan(novel: Optional[Novel], chapter_id: Optional[str]) -> Dict[str, Any]:
    if novel is None:
        return {}
    plan = _json_dict(_json_dict(novel.extra_data).get("series_plan"))
    return _series_plan_with_current_episode(plan, chapter_id)


async def _get_or_none(db: AsyncSession, model: Any, item_id: Optional[str], user_id: str) -> Any:
    if not item_id:
        return None
    result = await db.execute(select(model).where(model.id == item_id, model.user_id == user_id))
    return result.scalar_one_or_none()


async def _load_workflow(db: AsyncSession, user_id: str, workflow_id: str) -> Workflow:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id))
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")
    return workflow


async def _load_latest_story_bible(
    db: AsyncSession,
    user_id: str,
    *,
    novel_id: Optional[str],
    project_id: Optional[str],
) -> Optional[StoryBible]:
    query = select(StoryBible).where(StoryBible.user_id == user_id)
    if novel_id:
        query = query.where(StoryBible.novel_id == novel_id)
    elif project_id:
        query = query.where(StoryBible.project_id == project_id)
    else:
        return None
    result = await db.execute(query.order_by(desc(StoryBible.updated_at)).limit(1))
    return result.scalar_one_or_none()


def _story_bible_payload(story_bible: Optional[StoryBible]) -> Dict[str, Any]:
    if story_bible is None:
        return {}
    return {
        "id": story_bible.id,
        "title": story_bible.title,
        "novel_id": story_bible.novel_id,
        "project_id": story_bible.project_id,
        "style": story_bible.style,
        "worldview": story_bible.worldview,
        "character_rule_count": len(story_bible.character_rules or []),
        "scene_rule_count": len(story_bible.scene_rules or []),
        "prop_rule_count": len(story_bible.prop_rules or []),
        "event_count": len(story_bible.event_timeline or []),
        "updated_at": _dt(story_bible.updated_at),
    }


async def _production_graph_payload(
    db: AsyncSession,
    user_id: str,
    novel_id: Optional[str],
) -> Dict[str, Any]:
    if not novel_id:
        return {}
    novel = await _get_or_none(db, Novel, novel_id, user_id)
    if novel is None:
        return {}
    result = await db.execute(
        select(ProductionStateEvent)
        .where(
            ProductionStateEvent.user_id == user_id,
            ProductionStateEvent.novel_id == novel_id,
        )
        .order_by(ProductionStateEvent.production_version.desc())
        .limit(100)
    )
    events = sorted(result.scalars().all(), key=lambda event: event.production_version)
    projection = await project_story_state(db, user_id=user_id, novel_id=novel_id)
    if not events:
        return {
            "novel_id": novel_id,
            "version": 0,
            "hash": projection["graph_hash"],
            "current_state": {"entities": {}, "world": {}},
            "story_order": [],
            "production_revisions": [],
        }
    items: List[Dict[str, Any]] = []
    for event in events:
        impact = await resolve_production_graph_artifact_impact(
            db, user_id=user_id, novel=novel, event=event
        )
        items.append(
            {
                "id": event.id,
                "event_type": event.event_type,
                "entity_id": event.entity_id,
                "episode_index": event.episode_index,
                "story_time": _json_dict(event.story_time),
                "production_time": _json_dict(event.production_time),
                "before_state": _json_dict(event.before_state),
                "after_state": _json_dict(event.after_state),
                "approval_status": event.approval_status,
                "production_version": event.production_version,
                "event_hash": event.event_hash,
                "affected_episode_indices": impact["affected_episode_indices"],
                "affected_entity_ids": impact["affected_entity_ids"],
                "affected_shots": impact["affected_shots"],
                "created_at": _dt(event.created_at),
            }
        )
    story_order = sorted(
        items,
        key=lambda item: (
            int(_json_dict(item.get("story_time")).get("episode_index") or item.get("episode_index") or 0),
            int(_json_dict(item.get("story_time")).get("sequence") or 0),
            int(item.get("production_version") or 0),
        ),
    )
    return {
        "novel_id": novel_id,
        "version": projection["through_version"],
        "hash": projection["graph_hash"],
        "current_state": projection["state"],
        "story_order": story_order,
        "production_revisions": items,
    }


def _shot_payload(shot: Shot) -> Dict[str, Any]:
    extra = _json_dict(shot.extra_data)
    production_context = _json_dict(extra.get("production_context"))
    asset_locks = _json_list(production_context.get("asset_version_locks"))
    entity_refs = _json_dict(extra.get("entity_refs"))
    quality_report = build_shot_quality_report(shot)
    return {
        "id": shot.id,
        "storyboard_id": shot.storyboard_id,
        "shot_number": shot.shot_number,
        "episode_shot_number": extra.get("episode_shot_number"),
        "scene_index": extra.get("scene_index"),
        "scene_title": extra.get("scene_title"),
        "duration": shot.duration,
        "prompt": shot.prompt,
        "dialogue": shot.dialogue,
        "visual_description": shot.visual_description,
        "video_url": shot.video_url,
        "audio_url": shot.audio_url,
        "video_status": shot.video_status,
        "audio_status": shot.audio_status,
        "character_refs": _json_list(shot.character_refs),
        "entity_refs": entity_refs,
        "entity_ref_count": sum(len(_json_list(value)) for value in entity_refs.values()),
        "asset_version_locks": asset_locks,
        "asset_lock_count": len(asset_locks),
        "quality_report": quality_report,
        "updated_at": _dt(shot.updated_at),
    }


async def _load_assets(
    db: AsyncSession,
    user_id: str,
    *,
    project_id: Optional[str],
    novel_id: Optional[str],
) -> List[Asset]:
    filters = [or_(Asset.user_id == user_id, Asset.is_public == True), Asset.is_active == True]
    scope_filters = []
    if project_id:
        scope_filters.append(Asset.project_id == project_id)
    if novel_id:
        scope_filters.append(Asset.novel_id == novel_id)
    scope_filters.append(Asset.project_id.is_(None))
    filters.append(or_(*scope_filters))
    result = await db.execute(
        select(Asset)
        .where(*filters)
        .order_by(desc(Asset.updated_at), desc(Asset.created_at))
        .limit(ASSET_LIMIT)
    )
    return list(result.scalars().all())


def _asset_summary(assets: List[Asset]) -> Dict[str, Any]:
    by_category: Dict[str, int] = {}
    locked_count = 0
    final_count = 0
    for asset in assets:
        by_category[asset.category] = by_category.get(asset.category, 0) + 1
        if asset.is_locked:
            locked_count += 1
        if asset.is_final:
            final_count += 1
    return {
        "total_count": len(assets),
        "locked_count": locked_count,
        "final_count": final_count,
        "by_category": by_category,
        "items": [
            {
                "id": asset.id,
                "name": asset.name,
                "category": asset.category,
                "asset_type": asset.asset_type,
                "url": asset.url,
                "thumbnail_url": asset.thumbnail_url,
                "is_locked": bool(asset.is_locked),
                "is_final": bool(asset.is_final),
                "updated_at": _dt(asset.updated_at),
            }
            for asset in assets[:24]
        ],
    }


async def _load_jobs(db: AsyncSession, user_id: str, workflow: Workflow) -> Dict[str, Any]:
    video_ids = _job_ids(workflow.video_job_ids)
    video_query = select(VideoJob).where(VideoJob.user_id == user_id)
    video_query = video_query.where(VideoJob.id.in_(video_ids)) if video_ids else video_query.where(VideoJob.workflow_id == workflow.id)
    video_jobs = list((await db.execute(video_query.order_by(desc(VideoJob.created_at)).limit(JOB_LIMIT))).scalars().all())

    tts_ids = _job_ids(workflow.tts_job_ids)
    tts_query = select(TTSJob).where(TTSJob.user_id == user_id)
    tts_query = tts_query.where(TTSJob.id.in_(tts_ids)) if tts_ids else tts_query.where(TTSJob.workflow_id == workflow.id)
    tts_jobs = list((await db.execute(tts_query.order_by(desc(TTSJob.created_at)).limit(JOB_LIMIT))).scalars().all())

    synthesis_ids = _job_ids(workflow.synthesis_job_ids)
    synthesis_query = select(SynthesisJob).where(SynthesisJob.user_id == user_id)
    synthesis_query = (
        synthesis_query.where(SynthesisJob.id.in_(synthesis_ids))
        if synthesis_ids
        else synthesis_query.where(SynthesisJob.workflow_id == workflow.id)
    )
    synthesis_jobs = list((await db.execute(synthesis_query.order_by(desc(SynthesisJob.created_at)).limit(JOB_LIMIT))).scalars().all())

    media_jobs = list(
        (
            await db.execute(
                select(MediaGenerationJob)
                .where(MediaGenerationJob.user_id == user_id, MediaGenerationJob.workflow_id == workflow.id)
                .order_by(desc(MediaGenerationJob.created_at))
                .limit(JOB_LIMIT)
            )
        )
        .scalars()
        .all()
    )

    return {
        "summary": {
            "video_count": len(video_jobs),
            "tts_count": len(tts_jobs),
            "synthesis_count": len(synthesis_jobs),
            "media_count": len(media_jobs),
            "completed_media_count": len([job for job in media_jobs if job.status in {"completed", "succeeded"}]),
        },
        "video_jobs": [
            {
                "id": job.id,
                "status": job.status,
                "video_url": job.video_url,
                "created_at": _dt(job.created_at),
                **_job_strategy_summary(job),
                **_reference_package_summary(job),
            }
            for job in video_jobs
        ],
        "tts_jobs": [
            {
                "id": job.id,
                "status": job.status,
                "audio_url": job.audio_url,
                "created_at": _dt(job.created_at),
                **_job_strategy_summary(job),
            }
            for job in tts_jobs
        ],
        "synthesis_jobs": [
            {
                "id": job.id,
                "status": job.status,
                "output_url": job.output_url,
                "is_publishable": _json_dict(job.extra_data).get("is_publishable") is True,
                "created_at": _dt(job.created_at),
            }
            for job in synthesis_jobs
        ],
        "media_jobs": [
            {
                "id": job.id,
                "task_type": job.task_type,
                "media_type": job.media_type,
                "status": job.status,
                "output_video_url": job.output_video_url,
                "output_audio_url": job.output_audio_url,
                "output_manifest_url": job.output_manifest_url,
                "created_at": _dt(job.created_at),
                **_job_strategy_summary(job),
            }
            for job in media_jobs
        ],
    }


async def _load_quality_evaluation(db: AsyncSession, user_id: str, workflow_id: str) -> Dict[str, Any]:
    result = await db.execute(
        select(QualityEvaluation)
        .join(Workflow, QualityEvaluation.workflow_id == Workflow.id)
        .where(Workflow.user_id == user_id, QualityEvaluation.workflow_id == workflow_id)
        .order_by(desc(QualityEvaluation.evaluated_at), desc(QualityEvaluation.created_at))
    )
    latest_by_dimension: Dict[tuple[str, str], QualityEvaluation] = {}
    for row in result.scalars().all():
        latest_by_dimension.setdefault((str(row.artifact_id), str(row.dimension)), row)
    by_artifact: Dict[str, List[QualityEvaluation]] = {}
    for (artifact_id, _), row in latest_by_dimension.items():
        by_artifact.setdefault(artifact_id, []).append(row)
    if not by_artifact:
        return {}
    rows = max(
        by_artifact.values(),
        key=lambda items: max(item.evaluated_at for item in items),
    )
    return {
        "artifact_id": str(rows[0].artifact_id),
        "evaluation_ids": [str(row.id) for row in rows],
        "dimensions": [str(row.dimension) for row in rows],
        "score": round(min(float(row.score) for row in rows), 2),
        "blocking": any(bool(row.blocking) or row.severity == "blocking" for row in rows),
        "warning_count": sum(row.severity == "warning" for row in rows),
        "evaluated_at": max(row.evaluated_at for row in rows).isoformat(),
    }


async def _load_timeline(db: AsyncSession, user_id: str, project_id: Optional[str]) -> Dict[str, Any]:
    if not project_id:
        return {}
    result = await db.execute(
        select(Timeline)
        .where(Timeline.user_id == user_id, Timeline.project_id == project_id, Timeline.is_active == True)
        .order_by(desc(Timeline.updated_at), desc(Timeline.created_at))
        .limit(1)
    )
    timeline = result.scalar_one_or_none()
    if timeline is None:
        return {}
    clip_count = (
        await db.execute(select(Clip).where(Clip.timeline_id == timeline.id, Clip.is_active == True))
    ).scalars().all()
    return {
        "id": timeline.id,
        "name": timeline.name,
        "status": timeline.status,
        "aspect_ratio": timeline.aspect_ratio,
        "total_duration": timeline.total_duration,
        "clip_count": len(list(clip_count)),
        "preview_url": timeline.preview_url,
        "updated_at": _dt(timeline.updated_at),
    }


def _build_issues(
    *,
    workflow: Workflow,
    story_bible: Optional[StoryBible],
    shots: List[Dict[str, Any]],
    jobs: Dict[str, Any],
) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    if not workflow.novel_id:
        issues.append(_issue("select_novel", "工作流缺少小说，无法串联创作上下文。", repair_action=_action("open_workflow", "选择小说")))
    if not workflow.chapter_id:
        issues.append(_issue("select_chapter", "工作流缺少章节，无法定位本集内容。", repair_action=_action("open_workflow", "选择章节")))
    if not workflow.storyboard_id:
        issues.append(_issue("select_storyboard", "工作流缺少分镜，无法检查镜头生产条件。", repair_action=_action("open_workflow", "选择分镜")))
    if story_bible is None:
        issues.append(
            _issue(
                "missing_story_bible",
                "当前小说缺少 Story Bible，人物、场景、道具和事件一致性无法统一约束。",
                repair_action=_action("open_story_bible", "生成 Story Bible", href="/story-bibles", risk="navigation"),
            )
        )
    if not shots:
        issues.append(
            _issue(
                "missing_shots",
                "当前工作流还没有镜头，无法进入视频生成和合成。",
                repair_action=_action("open_storyboard", "生成或编辑分镜镜头", href="/storyboards", risk="navigation"),
            )
        )
    missing_entity_refs = [shot for shot in shots if not shot["entity_ref_count"]]
    if missing_entity_refs:
        issues.append(
            _issue(
                "missing_entity_refs",
                f"{len(missing_entity_refs)} 个镜头缺少人物/场景/道具/事件引用，跨镜头一致性风险较高。",
                severity="warning",
                repair_action=_action("fill_entity_refs", "补齐实体引用"),
            )
        )
    missing_locks = [shot for shot in shots if not shot["asset_lock_count"]]
    if missing_locks:
        issues.append(
            _issue(
                "missing_asset_locks",
                f"{len(missing_locks)} 个镜头缺少角色/场景/道具资产锁，生产出片前必须锁定。",
                repair_action=_action("apply_asset_locks", "应用资产锁"),
            )
        )
    if jobs["summary"]["video_count"] + jobs["summary"]["media_count"] == 0:
        issues.append(
            _issue(
                "missing_media_jobs",
                "还没有镜头视频或直生音视频任务，当前只能进行文本和分镜检查。",
                severity="warning",
                repair_action=_action("open_video_generation", "生成镜头视频", href="/video-generation", risk="navigation"),
            )
        )
    return issues


async def build_studio_snapshot(
    db: AsyncSession,
    user_id: str,
    workflow_id: str,
    *,
    mode_policy: Optional[StudioModePolicy] = None,
) -> Dict[str, Any]:
    workflow = await _load_workflow(db, user_id, workflow_id)
    novel = await _get_or_none(db, Novel, workflow.novel_id, user_id)
    chapter = await _get_or_none(db, Chapter, workflow.chapter_id, user_id)
    script = await _get_or_none(db, Script, workflow.script_id, user_id)
    storyboard = await _get_or_none(db, Storyboard, workflow.storyboard_id, user_id)
    storyboards = await load_studio_episode_storyboards(
        db, user_id=user_id, workflow=workflow, primary=storyboard,
    )
    story_bible = await _load_latest_story_bible(
        db,
        user_id,
        novel_id=workflow.novel_id,
        project_id=workflow.project_id,
    )
    state_machine = {}
    if story_bible is not None:
        state_machine = await get_story_state_machine(db, user_id, story_bible_id=story_bible.id)

    shots = [_shot_payload(shot) for shot in await load_studio_episode_shots(
        db, user_id=user_id, storyboards=storyboards, limit=SHOT_LIMIT,
    )]
    assets = await _load_assets(db, user_id, project_id=workflow.project_id, novel_id=workflow.novel_id)
    jobs = await _load_jobs(db, user_id, workflow)
    quality_evaluation = await _load_quality_evaluation(db, user_id, workflow.id)
    timeline = await _load_timeline(db, user_id, workflow.project_id)
    metadata = workflow.metadata_ if isinstance(workflow.metadata_, dict) else {}
    metadata = _merge_latest_production_strategy(metadata)
    production_snapshot = metadata.get("production_snapshot") if isinstance(metadata.get("production_snapshot"), dict) else {}
    production_bible_summary = (
        production_snapshot.get("summary")
        if isinstance(production_snapshot.get("summary"), dict)
        else None
    )
    if production_bible_summary is None and workflow.novel_id:
        production_bible_summary = await build_production_bible_summary(
            db, user_id, workflow.novel_id, as_of_chapter_id=workflow.chapter_id
        )
    series_plan = _saved_series_plan(novel, workflow.chapter_id)
    episode_contract = metadata.get("episode_contract") if isinstance(metadata.get("episode_contract"), dict) else None
    production_graph = await _production_graph_payload(db, user_id, workflow.novel_id)
    consistency_ledger = build_consistency_ledger(
        shots,
        episode_contract or {},
        [*_json_list(jobs.get("video_jobs")), *_json_list(jobs.get("media_jobs"))], quality_evaluation,
    )
    raw_issues = _build_issues(workflow=workflow, story_bible=story_bible, shots=shots, jobs=jobs)
    if quality_evaluation and quality_evaluation.get("blocking"):
        raw_issues.append(_issue("quality_blocker", "最新六维质量评估存在阻断项。"))
    elif quality_evaluation and quality_evaluation.get("warning_count"):
        raw_issues.append(_issue(
            "quality_warning",
            f"最新六维质量评估包含 {quality_evaluation['warning_count']} 个可确认警告。",
            severity="confirmable",
        ))
    policy_result = apply_mode_policy(raw_issues, mode_policy or StudioModePolicy())
    actions = _unique_actions(policy_result["issues"])

    payload = {
        "series_studio": series_studio_contract(),
        "workflow": {
            "id": workflow.id,
            "title": workflow.title,
            "status": workflow.status,
            "current_step": workflow.current_step,
            "completed_steps": workflow.completed_steps or [],
            "project_id": workflow.project_id,
            "novel_id": workflow.novel_id,
            "chapter_id": workflow.chapter_id,
            "script_id": workflow.script_id,
            "storyboard_id": workflow.storyboard_id,
            "latest_production_strategy": metadata.get("latest_production_strategy"),
            "latest_production_strategy_label": metadata.get("latest_production_strategy_label"),
            "latest_production_strategy_intent": metadata.get("latest_production_strategy_intent"),
            "latest_recommended_model_hint": metadata.get("latest_recommended_model_hint"),
            "metadata": metadata,
            "updated_at": _dt(workflow.updated_at),
        },
        "story_context": {
            "novel": {"id": novel.id, "title": novel.title, "genre": novel.genre} if novel else None,
            "chapter": {"id": chapter.id, "title": chapter.title, "chapter_number": chapter.chapter_number} if chapter else None,
            "script": {"id": script.id, "title": script.title, "status": script.status} if script else None,
            "storyboard": {
                "id": storyboard.id,
                "title": storyboard.title,
                "shot_count": len(shots),
                "scene_count": len(storyboards),
                "storyboard_ids": [board.id for board in storyboards],
            } if storyboard else None,
        },
        "story_bible": _story_bible_payload(story_bible),
        "production_bible_summary": production_bible_summary,
        "series_plan": series_plan,
        "episode_contract": episode_contract,
        "production_graph": production_graph,
        "consistency_ledger": consistency_ledger,
        "quality_evaluation": quality_evaluation,
        "state_machine": state_machine,
        "production": {
            "shot_count": len(shots),
            "asset_lock_coverage": round(
                len([shot for shot in shots if shot["asset_lock_count"]]) / len(shots),
                2,
            )
            if shots
            else 0,
            "entity_ref_coverage": round(
                len([shot for shot in shots if shot["entity_ref_count"]]) / len(shots),
                2,
            )
            if shots
            else 0,
            "ready": policy_result["ready"],
        },
        "shots": shots,
        "assets": _asset_summary(assets),
        "jobs": jobs,
        "timeline": timeline,
        "issues": policy_result["issues"],
        "actions": actions,
        "mode_policy": {
            key: value
            for key, value in policy_result.items()
            if key
            not in {
                "issues",
            }
        },
    }
    payload["guidance"] = build_studio_guidance(
        workflow=payload["workflow"],
        story_context=payload["story_context"],
        story_bible=payload["story_bible"],
        production_bible_summary=payload["production_bible_summary"] or {},
        production=payload["production"],
        timeline=payload["timeline"] or {},
        issues=payload["issues"],
        actions=payload["actions"],
        mode_policy=payload["mode_policy"],
        episode_contract=payload["episode_contract"] or {},
        production_graph=payload["production_graph"] or {},
        assets=payload["assets"] or {},
        jobs=payload["jobs"] or {},
        consistency_ledger=payload["consistency_ledger"] or {},
        orchestration=_json_dict(
            metadata.get("studio_orchestration") or metadata.get("episode_preview_orchestration")
        ),
        quality_evaluation=payload["quality_evaluation"] or {},
    )
    payload["stage_gate"] = {
        key: payload["guidance"].get(key)
        for key in (
            "current_stage",
            "stages",
            "blockers",
            "confirmable_warnings",
            "completed_evidence",
            "recommended_action",
            "orchestration_resume",
        )
    }
    recommended_code = _json_dict(payload["guidance"].get("recommended_action")).get("code")
    if recommended_code:
        payload["actions"] = [item for item in payload["actions"] if item.get("code") != recommended_code]
        payload["issues"] = [
            {
                **item,
                "repair_action": None
                if _json_dict(item.get("repair_action")).get("code") == recommended_code
                else item.get("repair_action"),
            }
            for item in payload["issues"]
        ]
    return payload
