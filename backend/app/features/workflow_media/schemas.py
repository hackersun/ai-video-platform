"""Public request and response contracts for workflow media generation."""

from typing import List, Optional

from pydantic import BaseModel, Field


class WorkflowMediaBatchRequest(BaseModel):
    production_strategy: Optional[str] = Field(
        None,
        description="业务生产策略：draft_fast/final_quality/low_cost/separate_video_tts/direct_av_first",
    )
    strategy: str = Field("direct_av_first", description="direct_av_first/separate_video_tts")
    shot_ids: Optional[List[str]] = Field(None, description="指定镜头ID，不传则使用工作流分镜下全部镜头")
    duration_seconds: Optional[int] = Field(None, ge=1, le=60)
    resolution: str = "720p"
    subtitle_mode: str = "shot_dialogue"
    audio_mode: str = "model_audio"
    native_audio: bool = Field(False, description="仅本次请求启用 Seedance 1.5 Pro 原生有声视频；开启后不提交独立 TTS")
    model_config_id: Optional[str] = Field(None, description="已保存的视频/直生音视频模型配置ID")
    audio_model_config_id: Optional[str] = Field(None, description="已保存的声音/TTS 模型配置ID")
    voice_model: str = Field("female-shaonj", description="默认 TTS 音色ID")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="TTS 语速")
    story_bible_id: Optional[str] = Field(None, description="用于解析角色音色的一致性 Story Bible ID")
    use_story_bible_voice: bool = Field(True, description="是否优先使用 Story Bible 中的角色音色")
    require_real_video: bool = Field(False, description="为 true 时禁止 DEV_MODE 视频占位回退")
    require_provider_reference_image: bool = Field(
        False,
        description="为 true 时必须有可提交给云端视频模型的公网参考图",
    )


class WorkflowMediaBatchResponse(BaseModel):
    workflow_id: str
    strategy: str
    production_strategy: Optional[str] = None
    created_count: int
    video_job_ids: List[str] = Field(default_factory=list)
    tts_job_ids: List[str] = Field(default_factory=list)
    tts_voice_lock_count: int = 0
    media_job_ids: List[str]
    subtitle_track_ids: List[str]
    pending_video_job_ids: List[str] = Field(default_factory=list)
    pending_tts_job_ids: List[str] = Field(default_factory=list)
    ready_for_concatenate: bool = True
    message: str
