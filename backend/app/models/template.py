"""
模板库模型
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, ForeignKey, DateTime, 
    Boolean, JSON, Float, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum

from app.core.database import Base


class TemplateStatus(str, enum.Enum):
    """模板状态"""
    DRAFT = "draft"           # 草稿
    PENDING = "pending"       # 待审核
    APPROVED = "approved"     # 已通过
    REJECTED = "rejected"     # 已拒绝
    ARCHIVED = "archived"     # 已归档


class TemplateVisibility(str, enum.Enum):
    """模板可见性"""
    PRIVATE = "private"       # 私有
    PUBLIC = "public"         # 公开
    MARKET = "market"         # 市场


class Template(Base):
    """模板表"""

    __tablename__ = "templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    
    # 分类
    content_type = Column(String(50))      # 短视频、宣传片、产品介绍等
    style_type = Column(String(50))        # 商务、活泼、科技感等
    industry = Column(String(50))          # 电商、教育、金融等
    duration = Column(String(20))          # 15秒、30秒、60秒等
    platform = Column(String(50))          # 抖音、快手、B站等
    
    # 模板数据
    template_data = Column(JSON)           # 模板结构数据
    preview_url = Column(String(500))      # 预览视频URL
    thumbnail_url = Column(String(500))    # 缩略图URL
    
    # 价格和统计
    price = Column(Float, default=0.0)     # 价格（0表示免费）
    download_count = Column(Integer, default=0)
    rating = Column(Float, default=5.0)    # 评分
    rating_count = Column(Integer, default=0)
    
    # 状态
    status = Column(String(20), default=TemplateStatus.DRAFT)
    visibility = Column(String(20), default=TemplateVisibility.PRIVATE)
    is_featured = Column(Boolean, default=False)  # 是否推荐
    
    # 作者
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime)
    
    # 关系
    author = relationship("User", back_populates="templates")
    tags = relationship("TemplateTag", secondary="template_tag_association", back_populates="templates")


class TemplateTag(Base):
    """模板标签"""

    __tablename__ = "template_tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))
    color = Column(String(7), default="#6366f1")  # 标签颜色
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    templates = relationship("Template", secondary="template_tag_association", back_populates="tags")


class TemplateTagAssociation(Base):
    """模板标签关联"""

    __tablename__ = "template_tag_association"

    template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id"), primary_key=True)
    tag_id = Column(UUID(as_uuid=True), ForeignKey("template_tags.id"), primary_key=True)


class UserTemplate(Base):
    """用户模板（收藏、使用记录）"""

    __tablename__ = "user_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=False)
    
    # 类型
    type = Column(String(20), default="favorite")  # favorite, history, draft
    
    # 自定义数据
    custom_data = Column(JSON)  # 用户自定义的模板数据
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 唯一约束
    __table_args__ = (
        # 用户不能重复收藏同一个模板
        {"unique_constraint": ("user_id", "template_id", "type")},
    )


class TemplateReview(Base):
    """模板评价"""

    __tablename__ = "template_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    rating = Column(Integer, nullable=False)  # 1-5星
    comment = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TemplateMarketCategory(Base):
    """模板市场分类"""

    __tablename__ = "template_market_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    icon = Column(String(100))
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    parent_id = Column(UUID(as_uuid=True), ForeignKey("template_market_categories.id"))
    
    created_at = Column(DateTime, default=datetime.utcnow)