"""Whole-novel series planning helpers."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.time_utils import utc_now
from app.models import (
    Chapter,
    MediaGenerationJob,
    Novel,
    Script,
    Shot,
    StoryEntity,
    Storyboard,
    VideoJob,
    Workflow,
)
from app.services.production_bible import build_production_bible_summary
from app.services.short_video_production import build_short_video_model_route


SERIES_PLAN_KEY = "series_plan"


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _uniq(values: Iterable[Any], limit: int = 8) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _compact_text(text: Optional[str], limit: int = 60) -> str:
    value = re.sub(r"\s+", " ", text or "").strip()
    if len(value) <= limit:
        return value
    return f"{value[:limit].rstrip()}..."


def _chapter_ids(chapters: Iterable[Chapter]) -> List[str]:
    return [chapter.id for chapter in chapters]


def _status_from_counts(
    *,
    chapter_count: int,
    script_count: int,
    storyboard_count: int,
    shot_count: int,
    video_count: int,
    media_count: int,
    completed_video_count: int,
    completed_media_count: int,
) -> str:
    if chapter_count <= 0:
        return "blocked"
    if completed_video_count > 0 or completed_media_count > 0:
        return "media_ready"
    if video_count > 0 or media_count > 0:
        return "media_generating"
    if shot_count > 0:
        return "shots_ready"
    if storyboard_count > 0:
        return "storyboard_ready"
    if script_count > 0:
        return "script_ready"
    return "planned"


def _next_action(status_value: str) -> Dict[str, str]:
    actions = {
        "blocked": ("补齐章节", "create_chapter", "该集没有可生产章节，先补齐正文。"),
        "planned": ("生成本集剧本", "generate_script", "把覆盖章节改编为短剧剧本。"),
        "script_ready": ("生成本集分镜", "generate_storyboard", "基于剧本生成分镜与镜头。"),
        "storyboard_ready": ("细化镜头", "review_shots", "补齐镜头对白、参考图、字幕和资产绑定。"),
        "shots_ready": ("生成音视频", "generate_media", "按镜头批量生成视频、配音或直生音视频。"),
        "media_generating": ("查看任务进度", "open_jobs", "等待或重试本集媒体生成任务。"),
        "media_ready": ("合成导出", "render_episode", "进入合成、字幕审阅和导出。"),
    }
    label, code, description = actions.get(status_value, actions["planned"])
    return {"label": label, "code": code, "description": description}


def _script_chapter_id(script: Optional[Script]) -> Optional[str]:
    if script is None:
        return None
    return script.chapter_id or _json_dict(script.extra_data).get("chapter_id")


def _storyboard_chapter_id(storyboard: Storyboard, scripts_by_id: Dict[str, Script]) -> Optional[str]:
    content = _json_dict(storyboard.content)
    return content.get("chapter_id") or _script_chapter_id(scripts_by_id.get(storyboard.script_id))


def _video_lineage_id(job: VideoJob, key: str) -> Optional[str]:
    return _json_dict(job.extra_data).get(key)


def _compact_production_bible_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "version": summary.get("version"),
        "novel_id": summary.get("novel_id"),
        "novel_title": summary.get("novel_title"),
        "story_bible_id": summary.get("story_bible_id"),
        "generated_at": summary.get("generated_at"),
        "style": summary.get("style"),
        "counts": summary.get("counts") or {},
        "anchors": summary.get("anchors") or {},
        "asset_readiness": summary.get("asset_readiness") or {},
        "voices": _json_list(summary.get("voices"))[:12],
        "state_machine": summary.get("state_machine") or {},
        "missing_requirements": _json_list(summary.get("missing_requirements"))[:12],
    }


def _episode_voice_count(summary: Dict[str, Any], episode: Dict[str, Any]) -> int:
    voices = _json_list(summary.get("voices"))
    character_names = set(_json_list(episode.get("key_characters")))
    if not character_names:
        return len(voices)
    return len([voice for voice in voices if voice.get("character_name") in character_names])


def _episode_missing_asset_count(summary: Dict[str, Any], episode: Dict[str, Any]) -> int:
    episode_names = set(
        _json_list(episode.get("key_characters"))
        + _json_list(episode.get("key_scenes"))
        + _json_list(episode.get("key_props"))
    )
    if not episode_names:
        return int(_json_dict(summary.get("asset_readiness")).get("missing_asset_count") or 0)

    missing = 0
    for group in ("characters", "scenes", "props"):
        for item in _json_list(summary.get(group)):
            if item.get("missing_asset") and item.get("name") in episode_names:
                missing += 1
    return missing


def _episode_continuity_summary(summary: Dict[str, Any], episode: Dict[str, Any]) -> Dict[str, Any]:
    anchors = _json_dict(summary.get("anchors"))
    state_machine = _json_dict(summary.get("state_machine"))
    return {
        "style": _json_dict(summary.get("style")).get("style") or episode.get("style"),
        "characters": _json_list(episode.get("key_characters")) or _json_list(anchors.get("character_names")),
        "scenes": _json_list(episode.get("key_scenes")) or _json_list(anchors.get("scene_names")),
        "props": _json_list(episode.get("key_props")) or _json_list(anchors.get("prop_names")),
        "events": _json_list(episode.get("key_events")),
        "voice_count": _episode_voice_count(summary, episode),
        "state_machine_available": bool(state_machine.get("available")),
        "state_counts": _json_dict(state_machine.get("current_state_counts")),
        "latest_events": _json_list(state_machine.get("latest_events"))[:4],
    }


def _episode_missing_requirements(
    summary: Dict[str, Any],
    episode: Dict[str, Any],
    readiness: Dict[str, Any],
) -> List[Dict[str, Any]]:
    requirements: List[Dict[str, Any]] = []
    if not readiness["has_workflow"]:
        requirements.append({"code": "workflow_missing", "message": "该集尚未创建生产工作流"})
    if not readiness["has_storyboard"]:
        requirements.append({"code": "storyboard_missing", "message": "该集尚未生成分镜"})
    if readiness["missing_asset_count"] > 0:
        requirements.append({
            "code": "episode_assets_missing",
            "message": "该集角色/场景/道具存在未定稿资产",
            "count": readiness["missing_asset_count"],
        })
    if episode.get("key_characters") and readiness["voice_count"] == 0:
        requirements.append({"code": "voice_cast_missing", "message": "该集角色尚未绑定声线"})
    requirements.extend(_json_list(summary.get("missing_requirements"))[:6])
    return requirements


def _normalize_episode_contract(episode: Dict[str, Any], position: int) -> Dict[str, Any]:
    normalized = dict(episode)
    episode_index = normalized.get("episode_index")
    if episode_index is None:
        episode_index = normalized.get("episode_number")
    normalized["episode_index"] = episode_index if episode_index is not None else position + 1
    if not isinstance(normalized.get("carry_over_state"), dict):
        normalized["carry_over_state"] = {"characters": [], "props": [], "events": []}
    return normalized


def _with_production_bible_summary(plan: Dict[str, Any], summary: Dict[str, Any]) -> Dict[str, Any]:
    if not plan:
        return plan

    enriched = dict(plan)
    compact_summary = _compact_production_bible_summary(summary)
    enriched["production_bible_summary"] = compact_summary
    episodes = []
    for position, episode in enumerate(_json_list(plan.get("episodes"))):
        if not isinstance(episode, dict):
            episodes.append(episode)
            continue
        episode_payload = _normalize_episode_contract(episode, position)
        missing_asset_count = _episode_missing_asset_count(summary, episode_payload)
        readiness = {
            "has_workflow": bool(episode_payload.get("workflow_id")),
            "has_storyboard": int(_json_dict(episode_payload.get("production_counts")).get("storyboards") or 0) > 0,
            "shot_count": int(_json_dict(episode_payload.get("production_counts")).get("shots") or 0),
            "asset_ready": missing_asset_count == 0,
            "missing_asset_count": missing_asset_count,
            "voice_count": _episode_voice_count(summary, episode_payload),
            "next_action": episode_payload.get("next_action") or _next_action(str(episode_payload.get("status") or "planned")),
        }
        episode_payload["production_readiness"] = readiness
        episode_payload["continuity_summary"] = _episode_continuity_summary(summary, episode_payload)
        episode_payload["missing_requirements"] = _episode_missing_requirements(summary, episode_payload, readiness)
        episodes.append(episode_payload)
    enriched["episodes"] = episodes
    return enriched


def _episode_narrative(
    novel: Novel,
    chapters: List[Chapter],
    entities_by_type: Dict[str, List[StoryEntity]],
    *,
    episode_number: int,
) -> Dict[str, str]:
    first_chapter = chapters[0] if chapters else None
    last_chapter = chapters[-1] if chapters else None
    protagonist = _uniq([entity.name for entity in entities_by_type.get("character", [])], 1)
    scene = _uniq([entity.name for entity in entities_by_type.get("scene", [])], 1)
    prop = _uniq([entity.name for entity in entities_by_type.get("prop", [])], 1)
    event = _uniq([entity.name for entity in entities_by_type.get("event", [])], 1)
    protagonist_name = protagonist[0] if protagonist else "主角"
    scene_name = scene[0] if scene else "核心场景"
    prop_name = prop[0] if prop else "关键道具"
    event_name = event[0] if event else (first_chapter.title if first_chapter else "关键事件")
    chapter_title = first_chapter.title if first_chapter else f"第{episode_number}集"
    ending_title = last_chapter.title if last_chapter else chapter_title

    content_hint = _compact_text(first_chapter.content if first_chapter else novel.description, 80)
    return {
        "hook": f"开场用《{chapter_title}》中的异常画面或强对白快速抓住注意力。",
        "conflict": f"{protagonist_name}围绕{event_name}在{scene_name}遭遇明确阻碍，目标不能含糊。",
        "turning_point": f"让{prop_name}、人物关系或事件证据发生可见变化，形成短剧式爽点/反转。",
        "cliffhanger": f"结尾停在《{ending_title}》的未解决动作或危险信号上，推动观众进入下一集。",
        "next_episode_bridge": "下一集从悬念结果或新危机开场，承接上一集人物状态、道具状态和事件因果。",
        "summary": content_hint or f"{novel.title}第{episode_number}集生产规划。",
    }


async def _load_novel(db: AsyncSession, user_id: str, novel_id: str) -> Novel:
    result = await db.execute(select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id)))
    novel = result.scalar_one_or_none()
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="小说不存在")
    return novel


async def get_series_plan(db: AsyncSession, user_id: str, novel_id: str) -> Dict[str, Any]:
    novel = await _load_novel(db, user_id, novel_id)
    plan = _json_dict(_json_dict(novel.extra_data).get(SERIES_PLAN_KEY))
    if not plan:
        return plan
    summary = await build_production_bible_summary(db, user_id, novel_id)
    return _with_production_bible_summary(plan, summary)


async def build_series_plan(
    db: AsyncSession,
    user_id: str,
    *,
    novel_id: str,
    target_episode_count: Optional[int] = None,
    chapters_per_episode: Optional[int] = None,
    target_duration_seconds: int = 60,
    aspect_ratio: str = "9:16",
    style: Optional[str] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    novel = await _load_novel(db, user_id, novel_id)

    chapters_result = await db.execute(
        select(Chapter)
        .where(and_(Chapter.novel_id == novel_id, Chapter.user_id == user_id))
        .order_by(Chapter.chapter_number, Chapter.created_at)
    )
    chapters = list(chapters_result.scalars().all())
    if not chapters:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先为小说创建或导入章节")

    chapter_ids = _chapter_ids(chapters)
    total_chapters = len(chapters)
    if chapters_per_episode and chapters_per_episode > 0:
        chunk_size = max(1, min(chapters_per_episode, total_chapters))
        episode_count = math.ceil(total_chapters / chunk_size)
    else:
        default_count = max(1, min(12, math.ceil(total_chapters / 2)))
        episode_count = max(1, min(target_episode_count or default_count, total_chapters))
        chunk_size = math.ceil(total_chapters / episode_count)

    script_result = await db.execute(
        select(Script).where(and_(Script.user_id == user_id, Script.novel_id == novel_id))
    )
    scripts = list(script_result.scalars().all())
    scripts_by_id = {script.id: script for script in scripts}
    scripts_by_chapter: Dict[str, List[Script]] = defaultdict(list)
    for script in scripts:
        chapter_id = _script_chapter_id(script)
        if chapter_id:
            scripts_by_chapter[chapter_id].append(script)

    script_ids = [script.id for script in scripts]
    storyboard_result = await db.execute(
        select(Storyboard).where(
            and_(
                Storyboard.user_id == user_id,
                or_(Storyboard.novel_id == novel_id, Storyboard.script_id.in_(script_ids)) if script_ids else Storyboard.novel_id == novel_id,
            )
        )
    )
    storyboards = list(storyboard_result.scalars().all())
    storyboards_by_id = {storyboard.id: storyboard for storyboard in storyboards}
    storyboards_by_chapter: Dict[str, List[Storyboard]] = defaultdict(list)
    for storyboard in storyboards:
        chapter_id = _storyboard_chapter_id(storyboard, scripts_by_id)
        if chapter_id:
            storyboards_by_chapter[chapter_id].append(storyboard)

    storyboard_ids = [storyboard.id for storyboard in storyboards]
    shot_result = await db.execute(
        select(Shot).where(
            and_(Shot.user_id == user_id, Shot.storyboard_id.in_(storyboard_ids))
            if storyboard_ids
            else Shot.user_id == "__no_storyboards__"
        )
    )
    shots = list(shot_result.scalars().all())
    shots_by_chapter: Dict[str, List[Shot]] = defaultdict(list)
    for shot in shots:
        storyboard = storyboards_by_id.get(shot.storyboard_id)
        if not storyboard:
            continue
        chapter_id = _storyboard_chapter_id(storyboard, scripts_by_id)
        if chapter_id:
            shots_by_chapter[chapter_id].append(shot)

    video_result = await db.execute(
        select(VideoJob)
        .where(VideoJob.user_id == user_id, VideoJob.is_active.is_(True))
        .order_by(desc(VideoJob.created_at))
        .limit(300)
    )
    video_jobs = [
        job
        for job in video_result.scalars().all()
        if _video_lineage_id(job, "novel_id") == novel_id
    ]
    videos_by_chapter: Dict[str, List[VideoJob]] = defaultdict(list)
    for job in video_jobs:
        chapter_id = _video_lineage_id(job, "chapter_id")
        if chapter_id:
            videos_by_chapter[chapter_id].append(job)

    media_result = await db.execute(
        select(MediaGenerationJob).where(
            and_(
                MediaGenerationJob.user_id == user_id,
                MediaGenerationJob.novel_id == novel_id,
                MediaGenerationJob.is_active.is_(True),
            )
        )
    )
    media_jobs = list(media_result.scalars().all())
    media_by_chapter: Dict[str, List[MediaGenerationJob]] = defaultdict(list)
    for job in media_jobs:
        if job.chapter_id:
            media_by_chapter[job.chapter_id].append(job)

    entity_result = await db.execute(
        select(StoryEntity).where(
            and_(
                StoryEntity.user_id == user_id,
                or_(StoryEntity.novel_id == novel_id, StoryEntity.novel_id.is_(None)),
            )
        )
    )
    entities = list(entity_result.scalars().all())
    entities_by_chapter: Dict[str, List[StoryEntity]] = defaultdict(list)
    global_entities: List[StoryEntity] = []
    for entity in entities:
        if entity.chapter_id in chapter_ids:
            entities_by_chapter[entity.chapter_id].append(entity)
        elif entity.novel_id == novel_id or entity.novel_id is None:
            global_entities.append(entity)

    workflow_result = await db.execute(
        select(Workflow).where(and_(Workflow.user_id == user_id, Workflow.novel_id == novel_id))
    )
    workflows = list(workflow_result.scalars().all())
    workflows_by_chapter: Dict[str, List[Workflow]] = defaultdict(list)
    for workflow in workflows:
        if workflow.chapter_id:
            workflows_by_chapter[workflow.chapter_id].append(workflow)

    production_bible_summary = await build_production_bible_summary(db, user_id, novel_id)

    episodes: List[Dict[str, Any]] = []
    for episode_index, start in enumerate(range(0, total_chapters, chunk_size), start=1):
        episode_chapters = chapters[start : start + chunk_size]
        episode_chapter_ids = _chapter_ids(episode_chapters)
        episode_entities = list(global_entities)
        for chapter_id in episode_chapter_ids:
            episode_entities.extend(entities_by_chapter.get(chapter_id, []))
        entities_by_type: Dict[str, List[StoryEntity]] = defaultdict(list)
        for entity in episode_entities:
            entities_by_type[entity.entity_type].append(entity)

        episode_scripts = [item for chapter_id in episode_chapter_ids for item in scripts_by_chapter.get(chapter_id, [])]
        episode_storyboards = [item for chapter_id in episode_chapter_ids for item in storyboards_by_chapter.get(chapter_id, [])]
        episode_shots = [item for chapter_id in episode_chapter_ids for item in shots_by_chapter.get(chapter_id, [])]
        episode_videos = [item for chapter_id in episode_chapter_ids for item in videos_by_chapter.get(chapter_id, [])]
        episode_media = [item for chapter_id in episode_chapter_ids for item in media_by_chapter.get(chapter_id, [])]
        completed_videos = [item for item in episode_videos if item.status == "succeeded" and item.video_url]
        completed_media = [
            item
            for item in episode_media
            if item.status == "succeeded" and (item.output_video_url or item.output_audio_url or item.output_manifest_url)
        ]
        status_value = _status_from_counts(
            chapter_count=len(episode_chapters),
            script_count=len(episode_scripts),
            storyboard_count=len(episode_storyboards),
            shot_count=len(episode_shots),
            video_count=len(episode_videos),
            media_count=len(episode_media),
            completed_video_count=len(completed_videos),
            completed_media_count=len(completed_media),
        )
        narrative = _episode_narrative(
            novel,
            episode_chapters,
            entities_by_type,
            episode_number=episode_index,
        )
        first_chapter = episode_chapters[0]
        last_chapter = episode_chapters[-1]
        workflow = next(
            (item for chapter_id in episode_chapter_ids for item in workflows_by_chapter.get(chapter_id, [])),
            None,
        )

        episodes.append(
            {
                "episode_index": episode_index,
                "episode_number": episode_index,
                "title": f"第{episode_index}集 {first_chapter.title}",
                "status": status_value,
                "next_action": _next_action(status_value),
                "target_duration_seconds": max(30, min(180, int(target_duration_seconds or 60))),
                "aspect_ratio": aspect_ratio or "9:16",
                "style": style or novel.genre or "anime",
                "chapter_ids": episode_chapter_ids,
                "chapters": [
                    {
                        "id": chapter.id,
                        "chapter_number": chapter.chapter_number,
                        "title": chapter.title,
                        "word_count": chapter.word_count or 0,
                    }
                    for chapter in episode_chapters
                ],
                "chapter_range": {
                    "start_number": first_chapter.chapter_number,
                    "end_number": last_chapter.chapter_number,
                    "label": f"第{first_chapter.chapter_number}-{last_chapter.chapter_number}章"
                    if first_chapter.id != last_chapter.id
                    else f"第{first_chapter.chapter_number}章",
                },
                "narrative": narrative,
                "key_characters": _uniq([entity.name for entity in entities_by_type.get("character", [])], 10),
                "key_scenes": _uniq([entity.name for entity in entities_by_type.get("scene", [])], 8),
                "key_props": _uniq([entity.name for entity in entities_by_type.get("prop", [])], 8),
                "key_events": _uniq([entity.name for entity in entities_by_type.get("event", [])], 8),
                "carry_over_state": {"characters": [], "props": [], "events": []},
                "production_counts": {
                    "chapters": len(episode_chapters),
                    "scripts": len(episode_scripts),
                    "storyboards": len(episode_storyboards),
                    "shots": len(episode_shots),
                    "video_jobs": len(episode_videos),
                    "media_jobs": len(episode_media),
                    "completed_media": len(completed_videos) + len(completed_media),
                },
                "primary_chapter_id": first_chapter.id,
                "workflow_id": workflow.id if workflow else None,
            }
        )

    now = utc_now().isoformat()
    plan = {
        "version": 1,
        "novel_id": novel.id,
        "novel_title": novel.title,
        "genre": novel.genre,
        "target_episode_count": len(episodes),
        "target_duration_seconds": max(30, min(180, int(target_duration_seconds or 60))),
        "aspect_ratio": aspect_ratio or "9:16",
        "style": style or novel.genre or "anime",
        "chapter_count": total_chapters,
        "status": "planned",
        "generated_at": now,
        "updated_at": now,
        "model_route": build_short_video_model_route(),
        "rules": [
            "每集必须继承上一集人物状态、道具状态、事件因果和环境变化。",
            "每集开场承接上一集悬念，结尾保留下一集钩子。",
            "角色形象、服装、声线、口吻和关键道具视觉 DNA 进入后续镜头生产约束。",
            "所有视频、配音、字幕和渲染包必须保留小说/章节/剧本/分镜/镜头血缘。",
        ],
        "episodes": episodes,
    }
    plan = _with_production_bible_summary(plan, production_bible_summary)

    if persist:
        extra_data = dict(_json_dict(novel.extra_data))
        extra_data[SERIES_PLAN_KEY] = plan
        novel.extra_data = extra_data
        novel.updated_at = utc_now()
        flag_modified(novel, "extra_data")
        await db.commit()
        await db.refresh(novel)

    return plan
