"""
小说和剧本模型
"""

from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class Novel(Base):
    """小说表"""
    __tablename__ = "novels"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    description = Column(Text)
    genre = Column(String(50))
    status = Column(String(20), default="draft")  # draft, published, archived
    cover_image = Column(String(500))
    word_count = Column(Integer, default=0)
    
    # AI生成元数据
    ai_generated = Column(Boolean, default=False)
    ai_metadata = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    author = relationship("User", back_populates="novels")
    chapters = relationship("Chapter", back_populates="novel", cascade="all, delete-orphan")
    scripts = relationship("Script", back_populates="novel", cascade="all, delete-orphan")


class Chapter(Base):
    """章节表"""
    __tablename__ = "chapters"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), ForeignKey("novels.id"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text)
    chapter_number = Column(Integer, nullable=False)
    status = Column(String(20), default="draft")
    word_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    novel = relationship("Novel", back_populates="chapters")


class Script(Base):
    """剧本表"""
    __tablename__ = "scripts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), ForeignKey("novels.id"))
    chapter_id = Column(UUID(as_uuid=True), ForeignKey("chapters.id"))
    title = Column(String(255), nullable=False)
    content = Column(JSON)  # 剧本结构化数据
    format = Column(String(20), default="standard")  # standard, screenplay
    status = Column(String(20), default="draft")
    ai_generated = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    novel = relationship("Novel", back_populates="scripts")
    scenes = relationship("Scene", back_populates="script", cascade="all, delete-orphan")


class Scene(Base):
    """场景表"""
    __tablename__ = "scenes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    script_id = Column(UUID(as_uuid=True), ForeignKey("scripts.id"), nullable=False)
    scene_number = Column(Integer, nullable=False)
    title = Column(String(255))
    description = Column(Text)
    characters = Column(ARRAY(UUID(as_uuid=True)))
    location = Column(String(255))
    time_of_day = Column(String(50))
    props = Column(ARRAY(String))
    dialogue = Column(JSON)
    action_description = Column(Text)
    camera_direction = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    script = relationship("Script", back_populates="scenes")
