"""
版本管理 API 端点
"""
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Novel, Chapter, Script, Storyboard, Shot
from app.services import version_service


router = APIRouter(prefix="/versions", tags=["版本管理"])


# ============== Pydantic 模型 ==============

class VersionSnapshot(BaseModel):
    """版本快照信息（不包含完整快照内容）"""
    id: str
    user_id: str
    resource_type: str
    resource_id: str
    version_number: int
    version_label: Optional[str] = None
    change_summary: Optional[str] = None
    created_at: str
    created_by: Optional[str] = None


class VersionDetail(VersionSnapshot):
    """版本详情（包含快照内容）"""
    snapshot: dict


class VersionCreate(BaseModel):
    """创建版本请求"""
    version_label: Optional[str] = Field(None, max_length=100, description="版本标签")
    change_summary: Optional[str] = Field(None, description="变更摘要")


class VersionRollbackRequest(BaseModel):
    """回滚请求"""
    confirm: bool = Field(True, description="确认回滚")


class VersionDiffResponse(BaseModel):
    """版本差异响应"""
    version_id: str
    version_number: int
    prev_version_id: Optional[str] = None
    prev_version_number: Optional[int] = None
    diff: dict
    is_first: Optional[bool] = None


class VersionRuleResponse(BaseModel):
    """版本规则响应"""
    resource_type: str
    max_versions: int
    auto_snapshot: bool
    auto_cleanup: bool


# ============== 辅助函数 ==============

RESOURCE_MODELS = {
    "novel": Novel,
    "chapter": Chapter,
    "script": Script,
    "storyboard": Storyboard,
    "shot": Shot,
}


async def get_resource(db: AsyncSession, resource_type: str, resource_id: str, user_id: str):
    """获取资源并验证权限"""
    if resource_type not in RESOURCE_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的资源类型: {resource_type}"
        )

    model = RESOURCE_MODELS[resource_type]
    result = await db.execute(
        select(model).where(
            and_(
                model.id == resource_id,
                model.user_id == user_id,
            )
        )
    )
    resource = result.scalar_one_or_none()

    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"资源不存在"
        )

    return resource


def build_version_response(version: "version_service.Version") -> VersionSnapshot:
    """构建版本快照响应"""
    return VersionSnapshot(
        id=version.id,
        user_id=version.user_id,
        resource_type=version.resource_type,
        resource_id=version.resource_id,
        version_number=version.version_number,
        version_label=version.version_label,
        change_summary=version.change_summary,
        created_at=version.created_at.isoformat() if version.created_at else None,
        created_by=version.created_by,
    )


def build_version_detail_response(version: "version_service.Version") -> VersionDetail:
    """构建版本详情响应"""
    return VersionDetail(
        id=version.id,
        user_id=version.user_id,
        resource_type=version.resource_type,
        resource_id=version.resource_id,
        version_number=version.version_number,
        version_label=version.version_label,
        change_summary=version.change_summary,
        created_at=version.created_at.isoformat() if version.created_at else None,
        created_by=version.created_by,
        snapshot=version.snapshot or {},
    )


# ============== API 端点 ==============

@router.get("/{resource_type}/{resource_id}", response_model=list[VersionSnapshot])
async def list_versions(
    resource_type: str,
    resource_id: str,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取资源的所有版本历史"""
    # 验证资源存在
    await get_resource(db, resource_type, resource_id, user_id)

    versions = await version_service.list_versions(
        db=db,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        limit=limit,
    )

    return [build_version_response(v) for v in versions]


@router.get("/count/{resource_type}/{resource_id}")
async def get_version_count(
    resource_type: str,
    resource_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取资源的版本数量"""
    # 验证资源存在
    await get_resource(db, resource_type, resource_id, user_id)

    count = await version_service.get_version_count(
        db=db,
        resource_type=resource_type,
        resource_id=resource_id,
    )

    return {"count": count}


@router.get("/detail/{version_id}", response_model=VersionDetail)
async def get_version_detail(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取版本详情（包含快照内容）"""
    version = await version_service.get_version(db, version_id, user_id)

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="版本不存在"
        )

    return build_version_detail_response(version)


@router.post("/{resource_type}/{resource_id}", response_model=VersionSnapshot, status_code=status.HTTP_201_CREATED)
async def create_version(
    resource_type: str,
    resource_id: str,
    request: VersionCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """为资源创建新版本快照"""
    # 验证资源存在并获取当前数据
    resource = await get_resource(db, resource_type, resource_id, user_id)

    # 创建快照
    snapshot = version_service.resource_to_snapshot(resource)

    version = await version_service.create_version(
        db=db,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        snapshot=snapshot,
        version_label=request.version_label,
        change_summary=request.change_summary,
    )

    return build_version_response(version)


@router.post("/{version_id}/rollback", response_model=dict)
async def rollback_version(
    version_id: str,
    request: VersionRollbackRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """回滚到指定版本"""
    if not request.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="需要确认回滚操作"
        )

    # 获取版本
    version = await version_service.get_version(db, version_id, user_id)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="版本不存在"
        )

    # 获取当前资源
    resource = await get_resource(db, version.resource_type, version.resource_id, user_id)

    # 在回滚前创建当前版本的快照
    current_snapshot = version_service.resource_to_snapshot(resource)
    await version_service.create_version(
        db=db,
        user_id=user_id,
        resource_type=version.resource_type,
        resource_id=version.resource_id,
        snapshot=current_snapshot,
        version_label="回滚前备份",
        change_summary=f"回滚到 v{version.version_number} 前的自动备份",
    )

    # 恢复快照数据到资源
    snapshot = version.snapshot or {}
    for key, value in snapshot.items():
        if hasattr(resource, key):
            setattr(resource, key, value)

    await db.commit()

    return {
        "message": "回滚成功",
        "version_id": version.id,
        "version_number": version.version_number,
        "resource_type": version.resource_type,
        "resource_id": version.resource_id,
    }


@router.get("/{version_id}/diff", response_model=VersionDiffResponse)
async def get_version_diff(
    version_id: str,
    compare_with_current: bool = Query(False, description="与当前资源状态比较"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """比较版本差异

    - compare_with_current=False: 与上一个版本比较
    - compare_with_current=True: 与当前资源状态比较
    """
    diff_result = await version_service.compute_diff(
        db=db,
        version_id=version_id,
        user_id=user_id,
        compare_with_current=compare_with_current,
    )

    if not diff_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="版本不存在"
        )

    return VersionDiffResponse(
        version_id=diff_result["version_id"],
        version_number=diff_result["version_number"],
        prev_version_id=diff_result.get("prev_version_id"),
        prev_version_number=diff_result.get("prev_version_number"),
        diff=diff_result["diff"],
        is_first=diff_result.get("is_first"),
    )


@router.delete("/{version_id}")
async def delete_version(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """删除指定版本"""
    version = await version_service.get_version(db, version_id, user_id)

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="版本不存在"
        )

    await version_service.delete_version(db, version_id, user_id)

    return {"message": "版本已删除", "version_id": version_id}


# ============== 版本规则管理 ==============

@router.get("/rules/{resource_type}", response_model=VersionRuleResponse)
async def get_version_rule(
    resource_type: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取资源类型的版本规则"""
    if resource_type not in version_service.RESOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的资源类型: {resource_type}"
        )

    rule = await version_service.get_version_rules(db, resource_type)
    return VersionRuleResponse(
        resource_type=rule.resource_type,
        max_versions=rule.max_versions,
        auto_snapshot=rule.auto_snapshot,
        auto_cleanup=rule.auto_cleanup,
    )