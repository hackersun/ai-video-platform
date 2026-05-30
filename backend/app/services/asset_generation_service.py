"""
资产生成服务
支持角色、场景、道具等资产的AI生成和版本管理
"""
from typing import Dict, List, Optional, Any
from uuid import uuid4
from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models.asset import Asset
from app.services.volcano_service import VolcanoService


class AssetGenerationService:
    """资产生成服务"""

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id
        self.volcano_service: Optional[VolcanoService] = None

    def set_volcano_service(self, volcano_service: VolcanoService):
        """设置火山引擎服务"""
        self.volcano_service = volcano_service

    async def generate_character_assets(
        self,
        character_id: str,
        character_name: str,
        character_description: str,
        style: str = "anime",
        project_id: Optional[str] = None,
        novel_id: Optional[str] = None,
    ) -> Dict[str, Asset]:
        """
        生成角色资产：头像、全身、表情、姿态

        Returns:
            Dict包含 avatar(头像), full_body(全身), expressions(表情集), poses(姿态集)
        """
        if not self.volcano_service:
            raise ValueError("Volcano service not configured")

        results = {}

        # 1. 生成头像
        avatar_prompt = self._build_avatar_prompt(character_name, character_description, style)
        avatar_result = await self.volcano_service.generate_image(
            prompt=avatar_prompt,
            size="1k",
        )
        avatar_url = avatar_result.get("data", [{}])[0].get("url") if avatar_result.get("data") else None

        if avatar_url:
            avatar_asset = await self._create_asset(
                name=f"{character_name} 头像",
                category="character",
                asset_type="image",
                url=avatar_url,
                character_id=character_id,
                entity_id=character_id,
                entity_type="character",
                project_id=project_id,
                novel_id=novel_id,
                source_prompt=avatar_prompt,
                generation_params={"asset_subtype": "avatar", "style": style},
            )
            results["avatar"] = avatar_asset

        # 2. 生成全身图
        full_body_prompt = self._build_fullbody_prompt(character_name, character_description, style)
        full_body_result = await self.volcano_service.generate_image(
            prompt=full_body_prompt,
            size="2k_w",
        )
        full_body_url = full_body_result.get("data", [{}])[0].get("url") if full_body_result.get("data") else None

        if full_body_url:
            full_body_asset = await self._create_asset(
                name=f"{character_name} 全身图",
                category="character",
                asset_type="image",
                url=full_body_url,
                character_id=character_id,
                entity_id=character_id,
                entity_type="character",
                project_id=project_id,
                novel_id=novel_id,
                source_prompt=full_body_prompt,
                generation_params={"asset_subtype": "full_body", "style": style},
            )
            results["full_body"] = full_body_asset

        # 3. 生成表情集（开心、愤怒、悲伤、惊讶等）
        expressions_prompt = self._build_expressions_prompt(character_name, character_description, style)
        expressions_result = await self.volcano_service.generate_image(
            prompt=expressions_prompt,
            size="1k",
            num=1,
        )
        expressions_url = expressions_result.get("data", [{}])[0].get("url") if expressions_result.get("data") else None

        if expressions_url:
            expressions_asset = await self._create_asset(
                name=f"{character_name} 表情集",
                category="character",
                asset_type="image",
                url=expressions_url,
                character_id=character_id,
                entity_id=character_id,
                entity_type="character",
                project_id=project_id,
                novel_id=novel_id,
                source_prompt=expressions_prompt,
                expressions=[
                    {"name": "happy", "description": "开心", "url": expressions_url},
                ],
                generation_params={"asset_subtype": "expressions", "style": style},
            )
            results["expressions"] = expressions_asset

        # 4. 生成姿态集
        poses_prompt = self._build_poses_prompt(character_name, character_description, style)
        poses_result = await self.volcano_service.generate_image(
            prompt=poses_prompt,
            size="2k_w",
        )
        poses_url = poses_result.get("data", [{}])[0].get("url") if poses_result.get("data") else None

        if poses_url:
            poses_asset = await self._create_asset(
                name=f"{character_name} 姿态集",
                category="character",
                asset_type="image",
                url=poses_url,
                character_id=character_id,
                entity_id=character_id,
                entity_type="character",
                project_id=project_id,
                novel_id=novel_id,
                source_prompt=poses_prompt,
                poses=[
                    {"name": "standing", "description": "站立", "url": poses_url},
                ],
                generation_params={"asset_subtype": "poses", "style": style},
            )
            results["poses"] = poses_asset

        return results

    async def generate_scene_assets(
        self,
        scene_id: str,
        scene_name: str,
        scene_description: str,
        style: str = "anime",
        project_id: Optional[str] = None,
        novel_id: Optional[str] = None,
    ) -> Dict[str, Asset]:
        """
        生成场景资产：主场景、细节图、特效层

        Returns:
            Dict包含 main_scene(主场景), detail(细节图), effect(特效层)
        """
        if not self.volcano_service:
            raise ValueError("Volcano service not configured")

        results = {}

        # 1. 生成主场景
        main_prompt = self._build_scene_prompt(scene_name, scene_description, style)
        main_result = await self.volcano_service.generate_image(
            prompt=main_prompt,
            size="3k",
        )
        main_url = main_result.get("data", [{}])[0].get("url") if main_result.get("data") else None

        if main_url:
            main_asset = await self._create_asset(
                name=f"{scene_name} 主场景",
                category="scene",
                asset_type="image",
                url=main_url,
                entity_id=scene_id,
                entity_type="scene",
                project_id=project_id,
                novel_id=novel_id,
                source_prompt=main_prompt,
                generation_params={"asset_subtype": "main_scene", "style": style},
            )
            results["main_scene"] = main_asset

        # 2. 生成细节图
        detail_prompt = self._build_scene_detail_prompt(scene_name, scene_description, style)
        detail_result = await self.volcano_service.generate_image(
            prompt=detail_prompt,
            size="2k",
        )
        detail_url = detail_result.get("data", [{}])[0].get("url") if detail_result.get("data") else None

        if detail_url:
            detail_asset = await self._create_asset(
                name=f"{scene_name} 细节图",
                category="scene",
                asset_type="image",
                url=detail_url,
                entity_id=scene_id,
                entity_type="scene",
                project_id=project_id,
                novel_id=novel_id,
                source_prompt=detail_prompt,
                generation_params={"asset_subtype": "detail", "style": style},
            )
            results["detail"] = detail_asset

        return results

    async def generate_prop_assets(
        self,
        prop_id: str,
        prop_name: str,
        prop_description: str,
        style: str = "anime",
        project_id: Optional[str] = None,
        novel_id: Optional[str] = None,
    ) -> Dict[str, Asset]:
        """
        生成道具资产：道具主图、细节图

        Returns:
            Dict包含 main(道具主图), detail(细节图)
        """
        if not self.volcano_service:
            raise ValueError("Volcano service not configured")

        results = {}

        # 1. 生成道具主图
        main_prompt = self._build_prop_prompt(prop_name, prop_description, style)
        main_result = await self.volcano_service.generate_image(
            prompt=main_prompt,
            size="1k",
        )
        main_url = main_result.get("data", [{}])[0].get("url") if main_result.get("data") else None

        if main_url:
            main_asset = await self._create_asset(
                name=f"{prop_name} 主图",
                category="prop",
                asset_type="image",
                url=main_url,
                entity_id=prop_id,
                entity_type="prop",
                project_id=project_id,
                novel_id=novel_id,
                source_prompt=main_prompt,
                generation_params={"asset_subtype": "main", "style": style},
            )
            results["main"] = main_asset

        return results

    async def lock_asset_version(self, asset_id: str) -> Asset:
        """
        锁定资产版本

        1. 如果该实体已有其他锁定版本，自动解锁
        2. 将当前资产设为锁定状态
        3. 如果有之前的定稿，将之前的定稿替换为当前版本
        """
        result = await self.db.execute(select(Asset).where(Asset.id == asset_id))
        asset = result.scalar_one_or_none()
        if not asset:
            raise ValueError(f"Asset not found: {asset_id}")

        entity_type = getattr(asset, "entity_type", None) if hasattr(asset, "entity_type") else None
        entity_id = asset.entity_id

        # 如果有实体关联，解锁同实体的其他锁定资产
        if entity_type and entity_id:
            existing_locked = await self.db.execute(
                select(Asset).where(
                    and_(
                        Asset.entity_id == entity_id,
                        Asset.entity_type == entity_type,
                        Asset.is_locked == True,
                        Asset.id != asset_id,
                    )
                )
            )
            for locked_asset in existing_locked.scalars().all():
                locked_asset.is_locked = False
                locked_asset.is_final = False
                locked_asset.replaced_by_id = asset_id

        # 设置当前资产为锁定
        asset.is_locked = True
        asset.locked_at = utc_now()
        asset.locked_by = self.user_id
        asset.is_final = True

        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    async def unlock_asset(self, asset_id: str) -> Asset:
        """解锁资产版本"""
        result = await self.db.execute(select(Asset).where(Asset.id == asset_id))
        asset = result.scalar_one_or_none()
        if not asset:
            raise ValueError(f"Asset not found: {asset_id}")

        asset.is_locked = False
        asset.is_final = False

        # 如果有被这个资产替代的版本，恢复其定稿状态
        if asset.replaced_by_id:
            replaced_result = await self.db.execute(select(Asset).where(Asset.id == asset.replaced_by_id))
            replaced_asset = replaced_result.scalar_one_or_none()
            if replaced_asset:
                replaced_asset.is_locked = True
                replaced_asset.is_final = True
                asset.replaced_by_id = None

        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    async def get_entity_locked_assets(self, entity_type: str, entity_id: str) -> List[Asset]:
        """获取实体的锁定资产"""
        result = await self.db.execute(
            select(Asset).where(
                and_(
                    Asset.entity_id == entity_id,
                    Asset.entity_type == entity_type,
                    Asset.is_locked == True,
                )
            )
        )
        return list(result.scalars().all())

    async def get_entity_asset_versions(self, entity_type: str, entity_id: str) -> List[Asset]:
        """获取实体的所有资产版本（按version排序）"""
        result = await self.db.execute(
            select(Asset)
            .where(
                and_(
                    Asset.entity_id == entity_id,
                    Asset.entity_type == entity_type,
                )
            )
            .order_by(Asset.version.desc())
        )
        return list(result.scalars().all())

    async def _create_asset(
        self,
        name: str,
        category: str,
        asset_type: str,
        url: str,
        character_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        project_id: Optional[str] = None,
        novel_id: Optional[str] = None,
        source_prompt: Optional[str] = None,
        expressions: Optional[List[Dict]] = None,
        poses: Optional[List[Dict]] = None,
        generation_params: Optional[Dict] = None,
    ) -> Asset:
        """创建资产记录"""
        asset = Asset(
            id=str(uuid4()),
            user_id=self.user_id,
            name=name,
            category=category,
            asset_type=asset_type,
            url=url,
            thumbnail_url=url,
            character_id=character_id,
            entity_id=entity_id,
            entity_type=entity_type,
            project_id=project_id,
            novel_id=novel_id,
            source_prompt=source_prompt,
            expressions=expressions,
            poses=poses,
            generation_params=generation_params,
        )
        self.db.add(asset)
        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    def _build_avatar_prompt(self, name: str, description: str, style: str) -> str:
        """构建头像生成提示词"""
        style_keywords = {
            "anime": "anime style, high quality, detailed, clean lineart, vibrant colors",
            "realistic": "photorealistic, ultra detailed, professional photography",
            "cartoon": "cartoon style, animated, colorful, fun",
        }
        keywords = style_keywords.get(style, style_keywords["anime"])
        return f"{keywords}, portrait of {name}, {description}, face close-up, head and shoulders"

    def _build_fullbody_prompt(self, name: str, description: str, style: str) -> str:
        """构建全身图生成提示词"""
        style_keywords = {
            "anime": "anime style, high quality illustration, detailed, vibrant colors",
            "realistic": "photorealistic, ultra detailed, full body photography",
            "cartoon": "cartoon style, animated, colorful, fun",
        }
        keywords = style_keywords.get(style, style_keywords["anime"])
        return f"{keywords}, full body portrait of {name}, {description}, standing pose, visible from head to toe"

    def _build_expressions_prompt(self, name: str, description: str, style: str) -> str:
        """构建表情集生成提示词"""
        style_keywords = {
            "anime": "anime style, chibi expression sheet, multiple expressions in one image",
            "realistic": "photorealistic, multiple facial expressions, portrait series",
            "cartoon": "cartoon style, expression sheet, 4 expressions",
        }
        keywords = style_keywords.get(style, style_keywords["anime"])
        return f"{keywords}, {name} {description}, expression sheet, happy, angry, sad, surprised expressions"

    def _build_poses_prompt(self, name: str, description: str, style: str) -> str:
        """构建姿态集生成提示词"""
        style_keywords = {
            "anime": "anime style, pose reference sheet, multiple poses in one image",
            "realistic": "photorealistic, pose reference, standing walking sitting running",
            "cartoon": "cartoon style, pose sheet, dynamic poses",
        }
        keywords = style_keywords.get(style, style_keywords["anime"])
        return f"{keywords}, {name} {description}, pose reference sheet, standing walking gesturing"

    def _build_scene_prompt(self, name: str, description: str, style: str) -> str:
        """构建场景生成提示词"""
        style_keywords = {
            "anime": "anime style background, detailed, atmospheric, vibrant colors",
            "realistic": "photorealistic scene, professional photography, cinematic",
            "cartoon": "cartoon style background, colorful, illustrative",
        }
        keywords = style_keywords.get(style, style_keywords["anime"])
        return f"{keywords}, {name}, {description}, wide shot, establishing scene, detailed environment"

    def _build_scene_detail_prompt(self, name: str, description: str, style: str) -> str:
        """构建场景细节图提示词"""
        style_keywords = {
            "anime": "anime style, close-up detail, intricate, high quality",
            "realistic": "photorealistic, macro detail, sharp focus",
            "cartoon": "cartoon style, detail view, clear",
        }
        keywords = style_keywords.get(style, style_keywords["anime"])
        return f"{keywords}, {name} detail, {description}, close-up detail shot"

    def _build_prop_prompt(self, name: str, description: str, style: str) -> str:
        """构建道具生成提示词"""
        style_keywords = {
            "anime": "anime style, item illustration, clean design, high quality",
            "realistic": "photorealistic, product photography, detailed",
            "cartoon": "cartoon style, prop design, colorful",
        }
        keywords = style_keywords.get(style, style_keywords["anime"])
        return f"{keywords}, {name}, {description}, isolated on white background, clear view, detailed"