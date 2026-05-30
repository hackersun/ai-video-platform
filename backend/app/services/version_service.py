"""
版本控制服务
"""
from typing import Optional, Any
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func

from app.models.version import Version, VersionRule
from app.core.time_utils import utc_now


# 支持的资源类型
RESOURCE_TYPES = ["novel", "chapter", "script", "storyboard", "shot"]

# 默认版本规则
DEFAULT_VERSION_RULES = {
    "novel": {"max_versions": 10, "auto_snapshot": True, "auto_cleanup": True},
    "chapter": {"max_versions": 10, "auto_snapshot": True, "auto_cleanup": True},
    "script": {"max_versions": 10, "auto_snapshot": True, "auto_cleanup": True},
    "storyboard": {"max_versions": 10, "auto_snapshot": True, "auto_cleanup": True},
    "shot": {"max_versions": 10, "auto_snapshot": True, "auto_cleanup": True},
}


async def get_version_rules(db: AsyncSession, resource_type: str) -> VersionRule:
    """获取指定资源类型的版本规则"""
    result = await db.execute(
        select(VersionRule).where(VersionRule.resource_type == resource_type)
    )
    rule = result.scalar_one_or_none()

    if rule is None:
        # 创建默认规则
        default = DEFAULT_VERSION_RULES.get(resource_type, DEFAULT_VERSION_RULES["novel"])
        rule = VersionRule(
            resource_type=resource_type,
            max_versions=default["max_versions"],
            auto_snapshot=default["auto_snapshot"],
            auto_cleanup=default["auto_cleanup"],
        )
        db.add(rule)
        await db.commit()
        await db.refresh(rule)

    return rule


async def get_next_version_number(db: AsyncSession, resource_type: str, resource_id: str) -> int:
    """获取下一个版本号"""
    result = await db.execute(
        select(func.max(Version.version_number))
        .where(
            and_(
                Version.resource_type == resource_type,
                Version.resource_id == resource_id,
            )
        )
    )
    max_version = result.scalar_one_or_none()
    return (max_version or 0) + 1


async def create_version(
    db: AsyncSession,
    user_id: str,
    resource_type: str,
    resource_id: str,
    snapshot: dict,
    version_label: Optional[str] = None,
    change_summary: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Version:
    """创建新版本"""
    version_number = await get_next_version_number(db, resource_type, resource_id)

    version = Version(
        id=str(uuid4()),
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        version_number=version_number,
        version_label=version_label,
        snapshot=snapshot,
        change_summary=change_summary,
        created_by=created_by or user_id,
    )

    db.add(version)
    await db.flush()

    # 检查是否需要清理旧版本
    rule = await get_version_rules(db, resource_type)
    if rule.auto_cleanup:
        await cleanup_old_versions(db, resource_type, resource_id, rule.max_versions)

    await db.commit()
    await db.refresh(version)
    return version


async def list_versions(
    db: AsyncSession,
    user_id: str,
    resource_type: str,
    resource_id: str,
    limit: int = 50,
) -> list[Version]:
    """获取资源的所有版本列表"""
    result = await db.execute(
        select(Version)
        .where(
            and_(
                Version.user_id == user_id,
                Version.resource_type == resource_type,
                Version.resource_id == resource_id,
            )
        )
        .order_by(desc(Version.version_number))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_version(db: AsyncSession, version_id: str, user_id: str) -> Optional[Version]:
    """获取指定版本详情"""
    result = await db.execute(
        select(Version).where(
            and_(Version.id == version_id, Version.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def get_version_by_number(
    db: AsyncSession,
    user_id: str,
    resource_type: str,
    resource_id: str,
    version_number: int,
) -> Optional[Version]:
    """根据版本号获取版本"""
    result = await db.execute(
        select(Version).where(
            and_(
                Version.user_id == user_id,
                Version.resource_type == resource_type,
                Version.resource_id == resource_id,
                Version.version_number == version_number,
            )
        )
    )
    return result.scalar_one_or_none()


async def cleanup_old_versions(
    db: AsyncSession,
    resource_type: str,
    resource_id: str,
    max_versions: int,
) -> int:
    """清理旧版本，保留最新的max_versions个"""
    # 获取所有版本按版本号降序
    result = await db.execute(
        select(Version)
        .where(
            and_(
                Version.resource_type == resource_type,
                Version.resource_id == resource_id,
            )
        )
        .order_by(desc(Version.version_number))
    )
    all_versions = list(result.scalars().all())

    if len(all_versions) <= max_versions:
        return 0

    # 删除超出限制的旧版本
    versions_to_delete = all_versions[max_versions:]
    deleted_count = 0

    for version in versions_to_delete:
        await db.delete(version)
        deleted_count += 1

    return deleted_count


async def get_version_count(
    db: AsyncSession,
    resource_type: str,
    resource_id: str,
) -> int:
    """获取资源的版本数量"""
    result = await db.execute(
        select(func.count(Version.id))
        .where(
            and_(
                Version.resource_type == resource_type,
                Version.resource_id == resource_id,
            )
        )
    )
    return result.scalar() or 0


async def delete_version(db: AsyncSession, version_id: str, user_id: str) -> bool:
    """删除指定版本"""
    version = await get_version(db, version_id, user_id)
    if version:
        await db.delete(version)
        await db.commit()
        return True
    return False


def compare_snapshots(old_snapshot: dict, new_snapshot: dict) -> dict:
    """比较两个快照的差异"""
    diff = {
        "added": {},
        "removed": {},
        "changed": {},
    }

    all_keys = set(old_snapshot.keys()) | set(new_snapshot.keys())

    for key in all_keys:
        old_value = old_snapshot.get(key)
        new_value = new_snapshot.get(key)

        if key not in old_snapshot:
            diff["added"][key] = new_value
        elif key not in new_snapshot:
            diff["removed"][key] = old_value
        elif old_value != new_value:
            diff["changed"][key] = {
                "old": old_value,
                "new": new_value,
            }

    return diff


async def compute_diff(
    db: AsyncSession,
    version_id: str,
    user_id: str,
    compare_with_current: bool = False,
) -> Optional[dict]:
    """计算版本差异

    Args:
        db: 数据库会话
        version_id: 版本ID
        user_id: 用户ID
        compare_with_current: 如果为True，与当前资源状态比较；否则与上一个版本比较
    """
    version = await get_version(db, version_id, user_id)
    if not version:
        return None

    if compare_with_current:
        # 获取当前资源状态
        current_data = await get_current_resource_data(db, version.resource_type, version.resource_id)
        if current_data:
            return {
                "version_id": version.id,
                "version_number": version.version_number,
                "diff": compare_snapshots(version.snapshot or {}, current_data),
            }
        return None

    # 与上一个版本比较
    if version.version_number <= 1:
        return {
            "version_id": version.id,
            "version_number": version.version_number,
            "diff": {"message": "这是第一个版本，无更早版本可比较"},
            "is_first": True,
        }

    prev_version = await get_version_by_number(
        db,
        user_id,
        version.resource_type,
        version.resource_id,
        version.version_number - 1,
    )

    if not prev_version:
        return {
            "version_id": version.id,
            "version_number": version.version_number,
            "diff": {"message": "未找到上一个版本"},
        }

    return {
        "version_id": version.id,
        "version_number": version.version_number,
        "prev_version_id": prev_version.id,
        "prev_version_number": prev_version.version_number,
        "diff": compare_snapshots(prev_version.snapshot or {}, version.snapshot or {}),
    }


async def get_current_resource_data(
    db: AsyncSession,
    resource_type: str,
    resource_id: str,
) -> Optional[dict]:
    """获取资源的当前数据"""
    from app.models import Novel, Chapter, Script, Storyboard, Shot

    model_map = {
        "novel": Novel,
        "chapter": Chapter,
        "script": Script,
        "storyboard": Storyboard,
        "shot": Shot,
    }

    model = model_map.get(resource_type)
    if not model:
        return None

    result = await db.execute(select(model).where(model.id == resource_id))
    resource = result.scalar_one_or_none()

    if not resource:
        return None

    # 获取所有非私有列的值
    data = {}
    for col in resource.__table__.columns:
        value = getattr(resource, col.name, None)
        # 跳过敏感字段
        if col.name not in ("password_hash", "api_key", "secret"):
            data[col.name] = value

    return data


def resource_to_snapshot(resource: Any) -> dict:
    """将资源对象转换为快照字典"""
    data = {}
    for col in resource.__table__.columns:
        value = getattr(resource, col.name, None)
        data[col.name] = value
    return data