"""
角色数据库模型
"""

from app.core.time_utils import utc_now
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Character(Base):
    """角色模型"""
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    novel_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("novels.id", ondelete="CASCADE"), nullable=True, index=True)
    chapter_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    appearance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    personality: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voice: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    avatar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON字符串存储
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<Character {self.name}>"
