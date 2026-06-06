"""
一致性检查 API 端点
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Shot, StoryBible, Storyboard
from app.services.consistency_checker import ConsistencyChecker, ConsistencyReport
from app.services.consistency_preflight import build_generation_context_package

router = APIRouter(tags=["一致性检查"])


class ConsistencyIssueResponse(BaseModel):
    """一致性问题的响应模型"""
    type: str
    severity: str
    entity: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None
    message: Optional[str] = None


class ShotConsistencyResponse(BaseModel):
    """单个镜头一致性检查响应"""
    shot_id: str
    is_consistent: bool
    error_count: int
    warning_count: int
    info_count: int
    issues: List[ConsistencyIssueResponse]


class StoryboardConsistencyResponse(BaseModel):
    """分镜一致性批量检查响应"""
    storyboard_id: str
    total_shots: int
    consistent_count: int
    inconsistent_count: int
    consistency_rate: float
    total_errors: int
    total_warnings: int
    shots: List[ShotConsistencyResponse]


class ConsistencySummaryResponse(BaseModel):
    """一致性检查汇总响应"""
    storyboard_id: str
    total_shots: int
    consistent_shots: int
    inconsistent_shots: int
    consistency_rate: float
    total_errors: int
    total_warnings: int
    total_infos: int
    issues_by_type: dict


class GenerationPreflightRequest(BaseModel):
    task_type: str
    model_config_id: Optional[str] = None
    image_url: Optional[str] = None
    production_mode: bool = True
    require_public_reference_image: bool = False
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    storyboard_id: Optional[str] = None
    shot_id: Optional[str] = None


class GenerationPreflightResponse(BaseModel):
    task_type: str
    ready: bool
    blocking_issue_count: int
    warning_issue_count: int
    lineage: Dict[str, Any]
    entity_refs: Dict[str, List[Dict[str, Any]]]
    asset_version_locks: List[Dict[str, Any]]
    reference_images: List[Dict[str, Any]]
    model_route: Dict[str, Any]
    issues: List[Dict[str, Any]]
    autofix_actions: List[Dict[str, Any]]


def _build_shot_consistency_response(report: ConsistencyReport) -> ShotConsistencyResponse:
    """从ConsistencyReport构建响应"""
    return ShotConsistencyResponse(
        shot_id=report.shot_id,
        is_consistent=report.is_consistent,
        error_count=report.error_count,
        warning_count=report.warning_count,
        info_count=report.info_count,
        issues=[
            ConsistencyIssueResponse(
                type=i.type,
                severity=i.severity,
                entity=i.entity,
                expected=i.expected,
                actual=i.actual,
                message=i.message
            )
            for i in report.issues
        ]
    )


@router.post("/preflight", response_model=GenerationPreflightResponse)
async def preflight_generation_context(
    request: GenerationPreflightRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> GenerationPreflightResponse:
    """Build the production generation package and blocking issues."""
    package = await build_generation_context_package(
        db,
        user_id,
        task_type=request.task_type,
        model_config_id=request.model_config_id,
        image_url=request.image_url,
        production_mode=request.production_mode,
        require_public_reference_image=request.require_public_reference_image,
        novel_id=request.novel_id,
        chapter_id=request.chapter_id,
        script_id=request.script_id,
        storyboard_id=request.storyboard_id,
        shot_id=request.shot_id,
    )
    return GenerationPreflightResponse(**package)


async def _get_story_bible_for_shot(
    db: AsyncSession,
    shot: Shot
) -> Optional[StoryBible]:
    """从镜头的extra_data中获取关联的Story Bible"""
    if not shot.extra_data:
        return None

    story_bible_id = shot.extra_data.get("story_bible_id")
    if not story_bible_id:
        return None

    result = await db.execute(
        select(StoryBible).where(StoryBible.id == story_bible_id)
    )
    return result.scalar_one_or_none()


async def _get_storyboard_or_404(
    db: AsyncSession,
    storyboard_id: str,
    user_id: str
) -> Storyboard:
    """获取分镜或抛出404"""
    result = await db.execute(
        select(Storyboard).where(
            and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id)
        )
    )
    storyboard = result.scalar_one_or_none()
    if not storyboard:
        raise HTTPException(status_code=404, detail="分镜不存在")
    return storyboard


async def _get_shot_or_404(
    db: AsyncSession,
    shot_id: str,
    user_id: str
) -> Shot:
    """获取镜头或抛出404"""
    result = await db.execute(
        select(Shot).where(
            and_(Shot.id == shot_id, Shot.user_id == user_id)
        )
    )
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="镜头不存在")
    return shot


@router.get("/shot/{shot_id}", response_model=ShotConsistencyResponse)
async def check_shot_consistency(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
) -> ShotConsistencyResponse:
    """
    检查单个镜头的一致性

    检查项：
    1. entity_refs是否填充
    2. 角色外观是否与Story Bible一致
    3. 是否使用锁定资产
    4. TTS音色一致性
    """
    # 验证镜头所有权
    shot = await _get_shot_or_404(db, shot_id, user_id)

    # 获取关联的Story Bible
    story_bible = await _get_story_bible_for_shot(db, shot)

    # 执行一致性检查
    checker = ConsistencyChecker()
    report = await checker.check_shot_consistency(db, shot, story_bible)

    return _build_shot_consistency_response(report)


@router.get("/storyboard/{storyboard_id}", response_model=StoryboardConsistencyResponse)
async def check_storyboard_consistency(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
) -> StoryboardConsistencyResponse:
    """
    批量检查分镜中所有镜头的一致性

    返回每个镜头的检查结果和统计信息
    """
    # 验证分镜所有权
    storyboard = await _get_storyboard_or_404(db, storyboard_id, user_id)

    # 获取所有镜头
    shots_result = await db.execute(
        select(Shot).where(
            and_(Shot.storyboard_id == storyboard_id, Shot.user_id == user_id)
        ).order_by(Shot.shot_number)
    )
    shots = list(shots_result.scalars().all())

    if not shots:
        return StoryboardConsistencyResponse(
            storyboard_id=storyboard_id,
            total_shots=0,
            consistent_count=0,
            inconsistent_count=0,
            consistency_rate=1.0,
            total_errors=0,
            total_warnings=0,
            shots=[]
        )

    # 获取Story Bible
    story_bible = None
    if storyboard.story_bible_id:
        sb_result = await db.execute(
            select(StoryBible).where(StoryBible.id == storyboard.story_bible_id)
        )
        story_bible = sb_result.scalar_one_or_none()

    # 检查所有镜头
    checker = ConsistencyChecker()
    shot_reports = []
    consistent_count = 0
    total_errors = 0
    total_warnings = 0

    for shot in shots:
        report = await checker.check_shot_consistency(db, shot, story_bible)
        shot_reports.append(_build_shot_consistency_response(report))
        if report.is_consistent:
            consistent_count += 1
        total_errors += report.error_count
        total_warnings += report.warning_count

    total_shots = len(shots)
    return StoryboardConsistencyResponse(
        storyboard_id=storyboard_id,
        total_shots=total_shots,
        consistent_count=consistent_count,
        inconsistent_count=total_shots - consistent_count,
        consistency_rate=consistent_count / total_shots if total_shots > 0 else 1.0,
        total_errors=total_errors,
        total_warnings=total_warnings,
        shots=shot_reports
    )


@router.get("/storyboard/{storyboard_id}/summary", response_model=ConsistencySummaryResponse)
async def get_storyboard_consistency_summary(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
) -> ConsistencySummaryResponse:
    """
    获取分镜一致性检查汇总信息

    返回统计信息和按问题类型分类的汇总
    """
    # 验证分镜所有权
    storyboard = await _get_storyboard_or_404(db, storyboard_id, user_id)

    # 获取所有镜头
    shots_result = await db.execute(
        select(Shot).where(
            and_(Shot.storyboard_id == storyboard_id, Shot.user_id == user_id)
        )
    )
    shots = list(shots_result.scalars().all())

    # 获取Story Bible
    story_bible = None
    if storyboard.story_bible_id:
        sb_result = await db.execute(
            select(StoryBible).where(StoryBible.id == storyboard.story_bible_id)
        )
        story_bible = sb_result.scalar_one_or_none()

    # 获取汇总信息
    checker = ConsistencyChecker()
    summary = await checker.get_consistency_summary(db, shots, story_bible)

    return ConsistencySummaryResponse(
        storyboard_id=storyboard_id,
        total_shots=summary["total_shots"],
        consistent_shots=summary["consistent_shots"],
        inconsistent_shots=summary["inconsistent_shots"],
        consistency_rate=summary["consistency_rate"],
        total_errors=summary["total_errors"],
        total_warnings=summary["total_warnings"],
        total_infos=summary["total_infos"],
        issues_by_type=summary["issues_by_type"]
    )


@router.get("/shot/{shot_id}/entity-refs")
async def check_shot_entity_refs(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    检查镜头实体引用状态

    返回entity_refs的详细状态，包括哪些已填充、哪些缺失
    """
    shot = await _get_shot_or_404(db, shot_id, user_id)

    entity_refs = shot.extra_data.get("entity_refs", {}) if shot.extra_data else {}
    character_refs = shot.character_refs or []

    return {
        "shot_id": shot_id,
        "has_entity_refs": bool(entity_refs and any(entity_refs.values())),
        "entity_refs": {
            "characters": entity_refs.get("characters", []),
            "scenes": entity_refs.get("scenes", []),
            "props": entity_refs.get("props", []),
            "events": entity_refs.get("events", []),
        },
        "has_character_refs": bool(character_refs),
        "character_refs_count": len(character_refs),
        "character_refs": character_refs[:5] if character_refs else [],  # 只返回前5个
    }


@router.post("/shots/batch-check")
async def batch_check_shots_consistency(
    shot_ids: List[str] = Query(..., min_length=1, max_length=100, description="镜头ID列表"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    批量检查多个镜头的一致性

    适用于需要检查指定镜头列表的场景
    """
    if len(shot_ids) > 100:
        raise HTTPException(
            status_code=422,
            detail="单次最多检查100个镜头"
        )

    # 获取所有镜头
    result = await db.execute(
        select(Shot).where(
            and_(Shot.id.in_(shot_ids), Shot.user_id == user_id)
        )
    )
    shots = list(result.scalars().all())
    shot_map = {shot.id: shot for shot in shots}

    # 检查每个镜头
    checker = ConsistencyChecker()
    results = {}
    consistent_count = 0
    total_errors = 0
    total_warnings = 0

    for shot_id in shot_ids:
        shot = shot_map.get(shot_id)
        if not shot:
            continue

        story_bible = await _get_story_bible_for_shot(db, shot)
        report = await checker.check_shot_consistency(db, shot, story_bible)
        results[shot_id] = _build_shot_consistency_response(report)

        if report.is_consistent:
            consistent_count += 1
        total_errors += report.error_count
        total_warnings += report.warning_count

    total_shots = len(results)
    missing_ids = [sid for sid in shot_ids if sid not in shot_map]

    return {
        "total": len(shot_ids),
        "checked": total_shots,
        "missing_ids": missing_ids,
        "consistent_count": consistent_count,
        "inconsistent_count": total_shots - consistent_count,
        "consistency_rate": consistent_count / total_shots if total_shots > 0 else 1.0,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "shots": list(results.values())
    }
