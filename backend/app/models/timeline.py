"""
时间线模型 - 多轨道视频编辑

一个 Timeline 包含多个 Track (轨道)
一个 Track 包含多个 Clip (片段)
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Timeline(Base):
    """
    时间线 - Project 下的一个编辑时间线

    可有多个: 主时间线、预告片、花絮等
    """

    __tablename__ = "timelines"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    project_id = Column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # === 基本信息 ===
    name = Column(String(200), nullable=False)  # "主线", "预告片", "花絮"
    description = Column(Text)

    # === 时间线设置 ===
    fps = Column(Integer, default=24)  # 24, 25, 30, 60
    aspect_ratio = Column(String(20), default="16:9")  # 16:9, 9:16, 1:1
    total_duration = Column(Float, default=0.0)  # 自动计算
    width = Column(Integer, default=1920)
    height = Column(Integer, default=1080)

    # === 轨道配置 ===
    video_track_count = Column(Integer, default=2)  # 视频轨道数
    audio_track_count = Column(Integer, default=3)  # 音频轨道数(背景音乐/对白/音效)
    subtitle_track_count = Column(Integer, default=1)  # 字幕轨道数

    # === 状态 ===
    status = Column(String(20), default="draft")  # draft, editing, locked, exported
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # 是否默认时间线

    # === 版本管理 ===
    version = Column(Integer, default=1)
    parent_timeline_id = Column(
        String(36), ForeignKey("timelines.id", ondelete="SET NULL"), nullable=True
    )

    # === 元数据 ===
    thumbnail_url = Column(Text)  # 缩略图
    preview_url = Column(Text)  # 预览URL
    extra_data = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Track(Base):
    """
    轨道 - 时间线上同类型的片段集合
    """

    __tablename__ = "tracks"

    id = Column(String(36), primary_key=True)
    timeline_id = Column(
        String(36), ForeignKey("timelines.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # === 轨道配置 ===
    track_type = Column(String(20), nullable=False)  # video, audio, subtitle, effect
    track_index = Column(Integer, nullable=False)  # 轨道顺序(从上到下)
    name = Column(String(100))  # "V1 - 主视频", "A1 - 背景音乐", "A2 - 音效", "S1 - 中文"

    # === 轨道属性 ===
    is_locked = Column(Boolean, default=False)  # 锁定
    is_muted = Column(Boolean, default=False)  # 静音
    is_hidden = Column(Boolean, default=False)  # 隐藏

    # === 视频轨道属性 ===
    opacity = Column(Float, default=1.0)  # 0-1

    # === 音频轨道属性 ===
    volume = Column(Float, default=1.0)  # 0-2
    pan = Column(Float, default=0.0)  # -1 (左) 到 1 (右)

    # === 效果 ===
    effects = Column(JSON)  # 轨道级效果

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Clip(Base):
    """
    片段 - 时间线中的一个剪辑单元

    source_type 支持:
    - shot: 分镜生成的视频
    - asset: 资产库中的视频/音频
    - video_job: 历史视频生成任务
    - tts_job: TTS 音频任务
    - synthesis_job: 合成任务
    - image: 静态图片
    """

    __tablename__ = "clips"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)

    # === 关联 ===
    timeline_id = Column(
        String(36), ForeignKey("timelines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    track_id = Column(String(36), ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False, index=True)

    # === 源资产 ===
    source_type = Column(String(50), nullable=False)  # shot, asset, video_job, tts_job, synthesis_job, image
    source_id = Column(String(36))  # 对应源ID

    # === 源内容URL (冗余存储，避免关联查询) ===
    source_url = Column(Text)  # 视频/音频 URL
    source_thumbnail = Column(Text)  # 缩略图
    source_duration = Column(Float, default=0)  # 原始时长

    # === 时间线位置 ===
    position = Column(Float, nullable=False, default=0)  # 在时间线中的起始位置(秒)
    duration = Column(Float, nullable=False, default=5)  # 片段时长(秒)
    in_point = Column(Float, default=0)  # 源资产的入点
    out_point = Column(Float)  # 源资产的出点

    # === 变换 ===
    speed = Column(Float, default=1.0)  # 播放速度 0.1 - 4.0
    scale = Column(Float, default=1.0)  # 缩放
    opacity = Column(Float, default=1.0)  # 透明度
    volume = Column(Float, default=1.0)  # 音量

    # === 位置变换 (画中画) ===
    position_x = Column(Float, default=0)  # X偏移(%)
    position_y = Column(Float, default=0)  # Y偏移(%)
    position_type = Column(String(20), default="fit")  # fit, fill, custom

    # === 裁剪 ===
    crop_left = Column(Float, default=0)  # 裁剪百分比
    crop_right = Column(Float, default=0)
    crop_top = Column(Float, default=0)
    crop_bottom = Column(Float, default=0)

    # === 旋转 ===
    rotation = Column(Float, default=0)  # 角度
    flip_h = Column(Boolean, default=False)  # 水平翻转
    flip_v = Column(Boolean, default=False)  # 垂直翻转

    # === 效果 ===
    transitions = Column(JSON)  # {"in": "fade", "out": "fade", "duration": 0.5}
    filters = Column(JSON)  # [{"type": "brightness", "value": 1.2}]
    blend_mode = Column(String(20), default="normal")  # 混合模式

    # === 关键帧动画 ===
    keyframes = Column(JSON)  # 位置/缩放/透明度关键帧

    # === 元数据 ===
    name = Column(String(200))  # 片段名称
    color = Column(String(20))  # 时间线中的颜色标签
    sort_order = Column(Integer, default=0)  # 同轨道内排序
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)

    # === 对字幕轨道的额外字段 ===
    text_content = Column(Text)  # 字幕文本
    font_family = Column(String(50), default="default")
    font_size = Column(Integer, default=24)
    font_color = Column(String(20), default="#FFFFFF")
    background_color = Column(String(20))  # 字幕背景

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
