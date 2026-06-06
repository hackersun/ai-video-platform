"""
资产锁定服务 - 锁定镜头引用的所有资产版本
"""
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, Shot
from app.services.entity_ref_normalizer import ENTITY_REF_KEYS, entity_ref_ids


class AssetLockService:
    """资产锁定服务 - 锁定镜头引用的所有资产版本"""

    async def lock_shot_assets(
        self,
        db: AsyncSession,
        shot: Shot,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        锁定镜头引用的所有资产版本

        Args:
            db: 数据库会话
            shot: 镜头对象
            force: 是否强制锁定（暂未使用）

        Returns:
            包含锁定资产信息的字典
        """
        locked_assets: Dict[str, Any] = {}

        # 获取镜头引用的实体，兼容旧 ID 列表和新 dict refs
        extra_data = dict(shot.extra_data or {})
        entity_refs = extra_data.get("entity_refs", {})
        if not entity_refs:
            return {"locked_assets": {}, "count": 0}

        novel_id = extra_data.get("novel_id")
        for entity_key in ["characters", "scenes", "props"]:
            entity_type = ENTITY_REF_KEYS[entity_key]
            for entity_id in entity_ref_ids(entity_refs, entity_key):
                # 获取该实体最新锁定的资产
                asset = await self._get_entity_locked_asset(
                    db,
                    entity_type,
                    entity_id,
                    user_id=getattr(shot, "user_id", None),
                    novel_id=novel_id,
                )
                if asset:
                    key = f"{entity_type}_{entity_id}"
                    locked_assets[key] = {
                        "asset_id": asset.id,
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "category": asset.category,
                        "name": asset.name,
                        "asset_name": asset.name,
                        "asset_url": asset.url,
                        "url": asset.url,
                        "thumbnail_url": asset.thumbnail_url,
                        "description": asset.description,
                        "version": asset.version,
                        "is_final": asset.is_final,
                        "is_locked": asset.is_locked,
                    }

        # 保存到shot.extra_data.locked_assets
        extra_data["locked_assets"] = locked_assets
        shot.extra_data = extra_data

        return {"locked_assets": locked_assets, "count": len(locked_assets)}

    async def _get_entity_locked_asset(
        self,
        db: AsyncSession,
        entity_type: str,
        entity_id: str,
        *,
        user_id: Optional[str] = None,
        novel_id: Optional[str] = None,
    ) -> Optional[Asset]:
        """
        获取实体的锁定资产

        Args:
            db: 数据库会话
            entity_type: 实体类型 (character, scene, prop)
            entity_id: 实体ID

        Returns:
            锁定的资产对象，若无则返回None
        """
        filters = [
            Asset.entity_id == entity_id,
            Asset.is_locked == True,
            Asset.is_final == True,
            Asset.is_active == True,
            or_(Asset.entity_type == entity_type, Asset.category == entity_type),
        ]
        if user_id:
            filters.append(or_(Asset.user_id == user_id, Asset.is_public == True))
        if novel_id:
            filters.append(or_(Asset.novel_id == novel_id, Asset.novel_id.is_(None)))

        # 查找该实体最新锁定的资产
        result = await db.execute(
            select(Asset)
            .where(and_(*filters))
            .order_by(desc(Asset.locked_at), desc(Asset.updated_at), desc(Asset.version))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_locked_asset_prompts(
        self,
        db: AsyncSession,
        shot: Shot
    ) -> List[str]:
        """
        获取锁定资产的prompt片段

        Args:
            db: 数据库会话
            shot: 镜头对象

        Returns:
            资产描述prompt列表
        """
        locked = shot.extra_data.get("locked_assets", {}) if shot.extra_data else {}
        prompts: List[str] = []

        for key, info in locked.items():
            result = await db.execute(
                select(Asset).where(Asset.id == info["asset_id"])
            )
            asset = result.scalar_one_or_none()

            if asset:
                entity_type = info.get("entity_type", "entity")
                prompts.append(
                    f"{entity_type}: {asset.name}, "
                    f"外观: {asset.description or '与资产一致'}"
                )

        return prompts

    async def unlock_shot_assets(
        self,
        db: AsyncSession,
        shot: Shot
    ) -> Dict[str, Any]:
        """
        解锁镜头引用的所有资产

        Args:
            db: 数据库会话
            shot: 镜头对象

        Returns:
            操作结果
        """
        extra_data = shot.extra_data or {}
        locked_assets = extra_data.get("locked_assets", {})

        unlocked_count = len(locked_assets) if isinstance(locked_assets, dict) else 0

        # 清除shot中的锁定资产记录
        if "locked_assets" in extra_data:
            del extra_data["locked_assets"]
        shot.extra_data = extra_data

        return {"unlocked_count": unlocked_count}
