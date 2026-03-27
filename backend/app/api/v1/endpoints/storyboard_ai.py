"""
分镜AI辅助生成API
支持台词、视觉描述、镜头建议的AI生成
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.services.qianlian_service import QianlianService, create_qianlian_service

router = APIRouter(tags=["分镜AI生成"])


class GenerateDialogueRequest(BaseModel):
    """台词生成请求"""
    scene_description: str = Field(..., description="场景描述")
    chapter_content: Optional[str] = Field(None, description="章节内容（提供更多上下文）")
    characters: Optional[List[dict]] = Field(None, description="角色列表")
    style: str = Field("anime", description="风格：anime, realistic, etc.")
    shot_id: Optional[str] = Field(None, description="关联的镜头ID")


class GenerateDialogueResponse(BaseModel):
    """台词生成响应"""
    dialogue: str
    visual_description: str
    camera_suggestion: str
    duration: int


class BatchGenerateShotsRequest(BaseModel):
    """批量生成镜头请求"""
    storyboard_id: str = Field(..., description="分镜ID")
    scene_description: str = Field(..., description="场景描述")
    shot_count: int = Field(5, ge=1, le=20, description="生成镜头数量")
    style: str = Field("anime", description="风格")
    chapter_content: Optional[str] = Field(None, description="章节完整内容")
    characters: Optional[List[dict]] = Field(None, description="角色列表")


class ShotData(BaseModel):
    """镜头数据"""
    shot_number: int
    duration: int
    prompt: str
    dialogue: Optional[str] = None
    visual_description: str
    camera_angle: str


class BatchGenerateShotsResponse(BaseModel):
    """批量生成镜头响应"""
    shots: List[ShotData]
    total_duration: int


async def get_default_api_key(db: AsyncSession, user_id: str) -> str:
    """获取用户默认的千问/百炼 API Key"""
    from sqlalchemy import select, and_
    from app.models.llm_config import LLMConfig, LLMModel, LLMProvider

    # 查询用户的默认千问/百炼配置
    result = await db.execute(
        select(LLMConfig, LLMModel, LLMProvider)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
        .where(
            and_(
                LLMConfig.user_id == user_id,
                LLMConfig.is_active == True,
                LLMProvider.name.in_(["qianlian", "dashscope", "qwen"]),
                LLMConfig.is_default == True
            )
        )
    )
    row = result.first()

    if row:
        config, model, provider = row
        return config.api_key

    # 如果没有默认配置，尝试获取任意千问/百炼活跃配置
    result = await db.execute(
        select(LLMConfig, LLMModel, LLMProvider)
        .join(LLMModel, LLMConfig.model_id == LLMModel.id)
        .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
        .where(
            and_(
                LLMConfig.user_id == user_id,
                LLMConfig.is_active == True,
                LLMProvider.name.in_(["qianlian", "dashscope", "qwen"]),
            )
        )
        .order_by(LLMConfig.created_at.desc())
        .limit(1)
    )
    row = result.first()

    if row:
        config, model, provider = row
        return config.api_key

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="请先在【LLM配置】页面配置并保存千问/百炼的 API Key"
    )


@router.post("/generate-dialogue", response_model=GenerateDialogueResponse)
async def generate_dialogue(
    request: GenerateDialogueRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    AI生成台词和镜头建议

    根据场景描述，生成：
    - 台词/配音内容
    - 视觉描述建议
    - 镜头角度建议
    """
    try:
        api_key = await get_default_api_key(db, user_id)
        service = await create_qianlian_service(api_key)

        # 构建提示词
        system_prompt = """你是一个专业的动画分镜师，擅长创作台词和视觉描述。

请根据场景描述生成：
1. 对话台词（适合配音的简短对白，30字以内）
2. 视觉描述（画面构图、色彩、光影）
3. 镜头角度建议（全景、近景、特写等）
4. 建议时长（2-8秒）

请以JSON格式输出：
{
  "dialogue": "角色对白台词",
  "visual_description": "画面描述",
  "camera_suggestion": "镜头角度",
  "duration": 建议时长
}"""

        user_prompt = f"场景：{request.scene_description}"
        if request.chapter_content:
            user_prompt += f"\n\n章节内容：{request.chapter_content[:500]}..."
        if request.characters:
            chars = ", ".join([c.get("name", "未知角色") for c in request.characters])
            user_prompt += f"\n\n出场角色：{chars}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await service.chat_completion(
            model="qwen3.5-plus",
            messages=messages,
            temperature=0.8,
            max_tokens=500
        )

        content = response["choices"][0]["message"]["content"]

        # 尝试解析JSON响应
        import json
        try:
            # 提取JSON部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())

            return GenerateDialogueResponse(
                dialogue=data.get("dialogue", ""),
                visual_description=data.get("visual_description", ""),
                camera_suggestion=data.get("camera_suggestion", "中景"),
                duration=data.get("duration", 4)
            )
        except json.JSONDecodeError:
            # 如果JSON解析失败，返回默认结构
            return GenerateDialogueResponse(
                dialogue=content[:100] if len(content) > 100 else content,
                visual_description="生成失败，使用默认描述",
                camera_suggestion="中景",
                duration=4
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"台词生成失败: {str(e)}"
        )


@router.post("/generate-shots", response_model=BatchGenerateShotsResponse)
async def generate_shots(
    request: BatchGenerateShotsRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    AI批量生成分镜镜头

    根据场景描述，生成多个镜头组成完整的分镜序列
    """
    try:
        api_key = await get_default_api_key(db, user_id)
        service = await create_qianlian_service(api_key)

        # 构建提示词 - 明确要求中文输出
        system_prompt = """你是一个专业的视频分镜师，擅长将场景描述转化为详细的分镜脚本。

【重要】你必须使用中文生成所有内容，包括JSON中的所有字段值。

请根据场景描述，生成N个镜头组成的分镜序列。每个镜头需要包含：
- shot_number: 镜头编号（整数）
- duration: 时长（秒，整数，如4、6、8）
- prompt: 视频生成Prompt（用于AI视频生成的详细画面描述，必须是中文）
- dialogue: 台词（中文对白）
- visual_description: 视觉描述（画面构图、色彩，光影，中文描述）
- camera_angle: 镜头角度（使用中文，如：全景、中景、近景、特写、跟拍、摇镜头）

【重要】JSON数组中的所有字符串值必须使用中文！

请以JSON数组格式输出：
[
  {
    "shot_number": 1,
    "duration": 4,
    "prompt": "清晨的阳光洒在古老的石板路上，主角从街道尽头走来",
    "dialogue": "今天天气真好！",
    "visual_description": "暖色调的晨曦街道，画面左侧是古朴的砖墙，右侧是整齐的石板路",
    "camera_angle": "中景"
  }
]"""

        user_prompt = f"""请为以下场景生成分镜：

场景：{request.scene_description}
风格：{request.style}
镜头数量：{request.shot_count}个
"""

        if request.chapter_content:
            user_prompt += f"\n\n章节完整内容：\n{request.chapter_content[:2000]}..."

        if request.characters:
            chars_info = "\n".join([
                f"- {c.get('name', '未知')}: {c.get('description', '无描述')}"
                for c in request.characters
            ])
            user_prompt += f"\n\n角色列表：\n{chars_info}"

        user_prompt += "\n\n请生成" + str(request.shot_count) + "个镜头，从开场到结尾，形成完整的分镜序列。"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await service.chat_completion(
            model="qwen3.5-plus",
            messages=messages,
            temperature=0.3,
            max_tokens=2000
        )

        content = response["choices"][0]["message"]["content"]

        # 解析JSON响应
        import json
        try:
            # 提取JSON部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            shots_data = json.loads(content.strip())

            # 计算总时长
            total_duration = sum(s.get("duration", 4) for s in shots_data)

            # 确保shot_number正确
            for i, shot in enumerate(shots_data):
                shot["shot_number"] = i + 1
                if "prompt" not in shot:
                    shot["prompt"] = shot.get("visual_description", "")
                if "duration" not in shot:
                    shot["duration"] = 4

            return BatchGenerateShotsResponse(
                shots=[ShotData(**s) for s in shots_data],
                total_duration=total_duration
            )

        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"镜头生成失败: JSON解析错误 - {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"镜头生成失败: {str(e)}"
        )
