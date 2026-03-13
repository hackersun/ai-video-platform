"""
素材库模型
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


class AssetType(str, enum.Enum):
    """素材类型"""
    VIDEO = "video"           # 视频素材
    IMAGE = "image"           # 图片素材
    AUDIO = "audio"           # 音频素材
    FONT = "font"             # 字体素材
    MODEL3D = "model3d"       # 3D素材
    EFFECT = "effect"         # 特效素材


class AssetStatus(str, enum.Enum):
    """素材状态"""
    UPLOADING = "uploading"   # 上传中
    PROCESSING = "processing" # 处理中
    READY = "ready"           # 就绪
    FAILED = "failed"         # 失败


class Asset(Base):
    """素材表"""

    __tablename__ = "assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # 类型和格式
    asset_type = Column(String(20), nullable=False)  # video, image, audio, font, model3d, effect
    mime_type = Column(String(100))
    file_format = Column(String(20))  # mp4, jpg, png, mp3, ttf 等
    
    # 文件信息
    file_size = Column(Integer, default=0)  # 字节
    duration = Column(Float, default=0)     # 视频/音频时长(秒)
    width = Column(Integer)                  # 宽度
    height = Column(Integer)                # 高度
    fps = Column(Integer)                   # 帧率
    
    # 存储
    storage_path = Column(String(500))      # 存储路径
    original_url = Column(String(500))      # 原始文件URL
    preview_url = Column(String(500))      # 预览图URL
    thumbnail_url = Column(String(500))     # 缩略图URL
    
    # 元数据
    metadata = Column(JSON)                # 额外元数据
    ai_tags = Column(JSON)                 # AI自动生成的标签
    custom_tags = Column(JSON)             # 用户自定义标签
    
    # 权限
    is_public = Column(Boolean, default=False)
    license_type = Column(String(50), default="royalty_free")  # 许可类型
    
    # 统计
    download_count = Column(Integer, default=0)
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    
    # 状态
    status = Column(String(20), default=AssetStatus.UPLOADING)
    
    # 所有者
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    
    # 分类
    category_id = Column(UUID(as_uuid=True), ForeignKey("asset_categories.id"))
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    owner = relationship("User", back_populates="assets")
    category = relationship("AssetCategory", back_populates="assets")

    def __repr__(self):
        return f"<Asset {self.id} {self.name}>"


class AssetCategory(Base):
    """素材分类"""

    __tablename__ = "asset_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    icon = Column(String(100))
    color = Column(String(7), default="#6366f1")
    
    # 层级
    parent_id = Column(UUID(as_uuid=True), ForeignKey("asset_categories.id"))
    sort_order = Column(Integer, default=0)
    
    # 关联的素材类型
    asset_types = Column(JSON)  # ["video", "image", "audio"]
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    parent = relationship("AssetCategory", remote_side=[id], back_populates="children")
    children = relationship("AssetCategory", back_populates="parent")
    assets = relationship("Asset", back_populates="category")


class AssetFolder(Base):
    """素材文件夹"""

    __tablename__ = "asset_folders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # 层级结构
    parent_id = Column(UUID(as_uuid=True), ForeignKey("asset_folders.id"))
    path = Column(String(500))  # 完整路径，如 "/我的素材/视频/片头"
    
    # 所有者
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True)
    
    # 统计
    asset_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    owner = relationship("User")
    parent_folder = relationship("AssetFolder", remote_side=[id], back_populates="subfolders")
    subfolders = relationship("AssetFolder", back_populates="parent_folder")


class AssetUsage(Base):
    """素材使用记录"""

    __tablename__ = "asset_usages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 使用场景
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    scene_id = Column(String(36))
    
    # 时间戳
    used_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    asset = relationship("Asset")
    user = relationship("User")


class AssetFavorite(Base):
    """素材收藏"""

    __tablename__ = "asset_favorites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 唯一约束
    __table_args__ = (
        {"unique_constraint": ("user_id", "asset_id")},
    )