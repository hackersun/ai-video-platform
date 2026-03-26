"""
镜头模型
"""
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON, Float, Boolean
from datetime import datetime
from app.core.database import Base


class Shot(Base):
    """镜头模型"""
    __tablename__ = "shots"

    id = Column(String(36), primary_key=True)
    storyboard_id = Column(String(36), ForeignKey("storyboards.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    shot_number = Column(Integer, nullable=False, default=1)
    duration = Column(Integer, default=4)
    prompt = Column(Text)
    dialogue = Column(Text)
    visual_description = Column(Text)
    camera_angle = Column(String(50))
    video_url = Column(String(500))
    audio_url = Column(String(500))
    video_status = Column(String(20), default="pending")
    audio_status = Column(String(20), default="pending")

    # === 精细化控制字段 ===
    # 运镜
    camera_movement = Column(String(50))  # static, pan_left, pan_right, tilt_up, tilt_down, zoom_in, zoom_out, dolly, crane, handheld
    movement_speed = Column(Float, default=1.0)  # 运镜速度
    movement_start_pos = Column(String(50))  # 起始位置描述
    movement_end_pos = Column(String(50))  # 终止位置描述

    # 情绪
    emotion = Column(String(50))  # happy, sad, angry, surprised, neutral, tense, relaxed, excited
    emotion_intensity = Column(Float, default=0.5)  # 情绪强度 0-1

    # 光影
    lighting = Column(String(50))  # natural, dramatic, soft, rim, back, neon, moonlight, golden_hour
    color_grading = Column(String(50))  # warm, cool, desaturated, vibrant, vintage, cinematic, noir

    # 配乐和音效提示
    music_cue = Column(String(500))  # 配乐提示
    sfx_cue = Column(String(500))  # 音效提示
    ambient_sound = Column(String(500))  # 环境音

    # 关键帧
    keyframes = Column(JSON)  # [{"time": 0.0, "prompt": "开场全景"}, {"time": 0.5, "prompt": "特写角色"}]

    # 多版本管理
    version = Column(Integer, default=1)
    parent_shot_id = Column(String(36), ForeignKey("shots.id", ondelete="SET NULL"), nullable=True)
    version_note = Column(String(200))

    # 时间线位置（用于 Timeline 编辑）
    timeline_track = Column(Integer, default=0)
    timeline_position = Column(Float, default=0.0)

    # 角色引用（用于一致性注入）
    character_refs = Column(JSON)  # [{"character_id": "...", "appearance": "casual", "expression": "happy"}]

    # 额外数据
    extra_data = Column(JSON)

    # 参考图
    image_url = Column(Text, nullable=True)       # 参考图 URL
    image_status = Column(String(20), default="pending")  # pending/generating/succeeded/failed
    image_asset_id = Column(String(36), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
