"""Public video generation command schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field

from app.features.video_generation.constants import VIDEO_MODEL_ID


class VideoGenerateRequest(BaseModel):
    """视频生成请求"""

    prompt: str = Field(..., description="视频描述")
    model: str = Field(VIDEO_MODEL_ID, description="视频模型ID，优先使用统一模型 registry ID")
    duration: int = Field(5, ge=3, le=15, description="视频时长（秒），按所选模型目录能力约束")
    resolution: str = Field("720p", description="分辨率: 480p, 720p, 1080p")
    api_key: Optional[str] = Field(None, description="火山引擎API Key（可选，默认使用用户在LLM配置中的密钥）")
    model_config_id: Optional[str] = Field(None, description="已保存的视频模型配置ID")
    image_url: Optional[str] = Field(None, description="参考图片URL，用于图生视频")
    seed: Optional[int] = Field(None, description="随机种子")
    project_id: Optional[str] = Field(None, description="来源项目ID")
    workflow_id: Optional[str] = Field(None, description="来源工作流ID")
    shot_id: Optional[str] = Field(None, description="来源镜头ID")
    storyboard_id: Optional[str] = Field(None, description="来源分镜ID")
    script_id: Optional[str] = Field(None, description="来源剧本ID")
    chapter_id: Optional[str] = Field(None, description="来源章节ID")
    novel_id: Optional[str] = Field(None, description="来源小说ID")
    story_bible_id: Optional[str] = Field(None, description="用于一致性约束的 Story Bible ID")
    character_ids: List[str] = Field(default_factory=list, description="需要注入一致性设定的角色ID列表")
    use_consistency_context: bool = Field(True, description="是否自动注入 Story Bible/项目/镜头/角色一致性上下文")
    native_audio: bool = Field(False, description="是否由视频模型直接生成对白音频，用于选择有声视频 Prompt Skill")
    unsafe_skip_consistency_preflight: bool = Field(
        False,
        description="仅用于明确的生产降级调试：跳过一致性上下文注入；生产硬预检仍会执行",
    )
