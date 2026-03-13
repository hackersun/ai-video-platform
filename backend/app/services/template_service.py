"""
模板服务
"""

from typing import List, Optional, Dict
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.template import (
    Template, TemplateTag, UserTemplate, TemplateReview,
    TemplateStatus, TemplateVisibility
)
from app.schemas.template import (
    TemplateCreate, TemplateUpdate, TemplateFilter,
    TemplateListResponse
)


class TemplateService:
    """模板服务"""

    def __init__(self, db: Session):
        self.db = db

    def create_template(self, user_id: UUID, template_data: TemplateCreate) -> Template:
        """创建模板"""
        template = Template(
            title=template_data.title,
            description=template_data.description,
            content_type=template_data.content_type,
            style_type=template_data.style_type,
            industry=template_data.industry,
            duration=template_data.duration,
            platform=template_data.platform,
            template_data=template_data.template_data,
            preview_url=template_data.preview_url,
            thumbnail_url=template_data.thumbnail_url,
            price=template_data.price or 0.0,
            author_id=user_id,
            status=TemplateStatus.DRAFT,
            visibility=TemplateVisibility.PRIVATE,
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        # 添加标签
        if template_data.tags:
            self._add_tags_to_template(template.id, template_data.tags)
        
        return template

    def get_template(self, template_id: UUID) -> Optional[Template]:
        """获取模板详情"""
        return self.db.query(Template).filter(Template.id == template_id).first()

    def list_templates(
        self,
        filters: TemplateFilter,
        user_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 20
    ) -> Dict:
        """获取模板列表"""
        query = self.db.query(Template)
        
        # 基础过滤
        query = query.filter(Template.status == TemplateStatus.APPROVED)
        query = query.filter(Template.visibility.in_([TemplateVisibility.PUBLIC, TemplateVisibility.MARKET]))
        
        # 应用过滤器
        if filters.content_type:
            query = query.filter(Template.content_type == filters.content_type)
        if filters.style_type:
            query = query.filter(Template.style_type == filters.style_type)
        if filters.industry:
            query = query.filter(Template.industry == filters.industry)
        if filters.duration:
            query = query.filter(Template.duration == filters.duration)
        if filters.platform:
            query = query.filter(Template.platform == filters.platform)
        if filters.min_price is not None:
            query = query.filter(Template.price >= filters.min_price)
        if filters.max_price is not None:
            query = query.filter(Template.price <= filters.max_price)
        if filters.is_free:
            query = query.filter(Template.price == 0)
        
        # 搜索
        if filters.search:
            search = f"%{filters.search}%"
            query = query.filter(
                (Template.title.ilike(search)) |
                (Template.description.ilike(search))
            )
        
        # 排序
        if filters.sort_by == "newest":
            query = query.order_by(Template.created_at.desc()))
        elif filters.sort_by == "popular":
            query = query.order_by(Template.download_count.desc())
        elif filters.sort_by == "rating":
            query = query.order_by(Template.rating.desc())
        elif filters.sort_by == "price_asc":
            query = query.order_by(Template.price.asc())
        elif filters.sort_by == "price_desc":
            query = query.order_by(Template.price.desc())
        else:
            query = query.order_by(Template.created_at.desc())
        
        # 分页
        total = query.count()
        templates = query.offset(skip).limit(limit).all()
        
        return {
            "items": templates,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    def update_template(
        self,
        template_id: UUID,
        user_id: UUID,
        template_data: TemplateUpdate
    ) -> Template:
        """更新模板"""
        template = self.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        if template.author_id != user_id:
            raise HTTPException(status_code=403, detail="无权修改此模板")
        
        # 更新字段
        for field, value in template_data.dict(exclude_unset=True).items():
            if field != "tags":
                setattr(template, field, value)
        
        template.updated_at = datetime.utcnow()
        
        # 更新标签
        if template_data.tags:
            self._update_template_tags(template_id, template_data.tags)
        
        self.db.commit()
        self.db.refresh(template)
        
        return template

    def delete_template(self, template_id: UUID, user_id: UUID) -> bool:
        """删除模板"""
        template = self.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        if template.author_id != user_id:
            raise HTTPException(status_code=403, detail="无权删除此模板")
        
        self.db.delete(template)
        self.db.commit()
        
        return True

    def publish_template(self, template_id: UUID, user_id: UUID) -> Template:
        """发布模板到市场"""
        template = self.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        if template.author_id != user_id:
            raise HTTPException(status_code=403, detail="无权发布此模板")
        
        template.status = TemplateStatus.PENDING
        template.visibility = TemplateVisibility.MARKET
        template.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(template)
        
        return template

    def _add_tags_to_template(self, template_id: UUID, tag_names: List[str]):
        """添加标签到模板"""
        for tag_name in tag_names:
            # 查找或创建标签
            tag = self.db.query(TemplateTag).filter(TemplateTag.name == tag_name).first()
            if not tag:
                tag = TemplateTag(name=tag_name)
                self.db.add(tag)
                self.db.flush()
            
            # TODO: 添加关联

    def _update_template_tags(self, template_id: UUID, tag_names: List[str]):
        """更新模板标签"""
        # TODO: 实现标签更新逻辑
        pass

    # 用户模板操作
    def add_to_favorites(self, user_id: UUID, template_id: UUID) -> UserTemplate:
        """收藏模板"""
        # 检查是否已收藏
        existing = self.db.query(UserTemplate).filter(
            UserTemplate.user_id == user_id,
            UserTemplate.template_id == template_id,
            UserTemplate.type == "favorite"
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="已收藏此模板")
        
        user_template = UserTemplate(
            user_id=user_id,
            template_id=template_id,
            type="favorite"
        )
        
        self.db.add(user_template)
        self.db.commit()
        self.db.refresh(user_template)
        
        return user_template

    def remove_from_favorites(self, user_id: UUID, template_id: UUID) -> bool:
        """取消收藏"""
        user_template = self.db.query(UserTemplate).filter(
            UserTemplate.user_id == user_id,
            UserTemplate.template_id == template_id,
            UserTemplate.type == "favorite"
        ).first()
        
        if not user_template:
            raise HTTPException(status_code=404, detail="未收藏此模板")
        
        self.db.delete(user_template)
        self.db.commit()
        
        return True

    def get_user_favorites(self, user_id: UUID, skip: int = 0, limit: int = 20) -> Dict:
        """获取用户收藏"""
        query = self.db.query(Template).join(
            UserTemplate,
            Template.id == UserTemplate.template_id
        ).filter(
            UserTemplate.user_id == user_id,
            UserTemplate.type == "favorite"
        )
        
        total = query.count()
        templates = query.order_by(UserTemplate.created_at.desc()).offset(skip).limit(limit).all()
        
        return {
            "items": templates,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    def get_user_templates(self, user_id: UUID, skip: int = 0, limit: int = 20) -> Dict:
        """获取用户创建的模板"""
        query = self.db.query(Template).filter(Template.author_id == user_id)
        
        total = query.count()
        templates = query.order_by(Template.created_at.desc()).offset(skip).limit(limit).all()
        
        return {
            "items": templates,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    def record_template_usage(self, user_id: UUID, template_id: UUID):
        """记录模板使用"""
        # 更新下载次数
        template = self.get_template(template_id)
        if template:
            template.download_count += 1
            self.db.commit()
        
        # 添加到使用历史
        user_template = UserTemplate(
            user_id=user_id,
            template_id=template_id,
            type="history"
        )
        self.db.add(user_template)
        self.db.commit()

    def get_categories(self) -> Dict:
        """获取模板分类"""
        return {
            "content_types": [
                {"id": "short_video", "name": "短视频", "icon": "video"},
                {"id": "promo", "name": "宣传片", "icon": "megaphone"},
                {"id": "product", "name": "产品介绍", "icon": "package"},
                {"id": "education", "name": "教育培训", "icon": "book"},
                {"id": "social", "name": "社交媒体", "icon": "share"},
                {"id": "ad", "name": "广告", "icon": "target"},
                {"id": "vlog", "name": "Vlog", "icon": "camera"},
                {"id": "animation", "name": "动画", "icon": "film"},
            ],
            "style_types": [
                {"id": "business", "name": "商务专业"},
                {"id": "lively", "name": "活泼可爱"},
                {"id": "tech", "name": "科技感"},
                {"id": "retro", "name": "复古风"},
                {"id": "minimal", "name": "极简主义"},
                {"id": "cinematic", "name": "电影感"},
                {"id": "cartoon", "name": "卡通"},
                {"id": "realistic", "name": "写实"},
            ],
            "industries": [
                {"id": "ecommerce", "name": "电商"},
                {"id": "education", "name": "教育"},
                {"id": "finance", "name": "金融"},
                {"id": "medical", "name": "医疗"},
                {"id": "food", "name": "餐饮"},
                {"id": "travel", "name": "旅游"},
                {"id": "tech", "name": "科技"},
                {"id": "entertainment", "name": "娱乐"},
            ],
            "durations": [
                {"id": "15s", "name": "15秒"},
                {"id": "30s", "name": "30秒"},
                {"id": "60s", "name": "60秒"},
                {"id": "3min", "name": "3分钟"},
                {"id": "5min", "name": "5分钟"},
            ],
            "platforms": [
                {"id": "douyin", "name": "抖音"},
                {"id": "kuaishou", "name": "快手"},
                {"id": "xiaohongshu", "name": "小红书"},
                {"id": "bilibili", "name": "B站"},
                {"id": "youtube", "name": "YouTube"},
                {"id": "instagram", "name": "Instagram"},
                {"id": "tiktok", "name": "TikTok"},
            ],
        }