"""
分镜管理 API 端点
"""
import asyncio
import uuid
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, text
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.llm_config import LLMProvider, LLMModel, LLMConfig
from app.models import Storyboard, Shot

router = APIRouter(tags=["分镜管理"])


# ============== Pydantic 模型 ==============

class StoryboardCreate(BaseModel):
    """创建分镜请求"""
    script_id: str = Field(..., description="所属剧本ID")
    title: str = Field(..., min_length=1, max_length=200, description="分镜标题")
    description: Optional[str] = Field(None, description="分镜描述")
    content: Optional[dict] = Field(None, description="分镜内容")


class StoryboardUpdate(BaseModel):
    """更新分镜请求"""
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[dict] = None
    shot_count: Optional[int] = None
    total_duration: Optional[int] = None
    status: Optional[str] = None


class StoryboardResponse(BaseModel):
    """分镜响应"""
    id: str
    script_id: str
    user_id: str
    title: str
    script_title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[dict] = None
    shot_count: int
    total_duration: int
    status: str
    created_at: str
    updated_at: str


class StoryboardGenerateRequest(BaseModel):
    """AI生成分镜请求"""
    script_id: str = Field(..., description="剧本ID")
    shot_count: Optional[int] = Field(None, ge=1, le=50, description="镜头数量（默认自动）")
    style: str = Field(default="anime", description="分镜风格（anime/realistic/cartoon等）")


class ShotBriefResponse(BaseModel):
    """镜头简要响应（嵌套在分镜生成响应中）"""
    id: str
    shot_number: int
    duration: int
    prompt: Optional[str]
    dialogue: Optional[str]
    visual_description: Optional[str]
    camera_angle: Optional[str]


class StoryboardGenerateResponse(BaseModel):
    """AI生成分镜响应"""
    id: str
    script_id: str
    user_id: str
    title: str
    script_title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[dict] = None
    shot_count: int
    total_duration: int
    status: str
    shots: List[ShotBriefResponse]
    created_at: str
    updated_at: str


# ============== LLM API Key 辅助函数 ==============

async def get_user_qwen_api_key(db: AsyncSession, user_id: str) -> tuple[str, str, str, Optional[str]]:
    """
    获取用户的千问/DashScope API密钥

    Returns:
        tuple: (api_key, provider_name, model_id, base_url)

    Raises:
        HTTPException: 如果未找到有效配置
    """
    result = await db.execute(
        select(LLMConfig).where(
            and_(LLMConfig.user_id == user_id, LLMConfig.is_active == True)
        ).order_by(desc(LLMConfig.is_default), desc(LLMConfig.last_used_at))
    )
    config = result.scalars().first()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先配置大模型API密钥"
        )

    if not config.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="大模型API密钥未设置"
        )

    model_result = await db.execute(
        select(LLMModel).where(LLMModel.id == config.model_id)
    )
    model = model_result.scalar_one_or_none()

    provider_result = await db.execute(
        select(LLMProvider).where(LLMProvider.id == model.provider_id) if model else select(LLMProvider).where(LLMProvider.name == "dashscope")
    )
    provider = provider_result.scalars().first()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未找到大模型提供商配置"
        )

    return config.api_key, provider.name, model.model_id if model else "qwen-long", model.base_url if model else None


async def get_script_for_user(db: AsyncSession, script_id: str, user_id: str):
    from app.models import Script

    result = await db.execute(
        select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
    )
    script = result.scalar_one_or_none()
    if script is None:
        raise HTTPException(status_code=404, detail="剧本不存在")
    return script


def build_storyboard_response(
    storyboard: Storyboard,
    script_title: Optional[str] = None,
) -> StoryboardResponse:
    return StoryboardResponse(
        id=str(storyboard.id),
        script_id=str(storyboard.script_id),
        user_id=str(storyboard.user_id),
        title=storyboard.title,
        script_title=script_title,
        description=storyboard.description,
        content=storyboard.content,
        shot_count=storyboard.shot_count or 0,
        total_duration=storyboard.total_duration or 0,
        status=storyboard.status or "draft",
        created_at=str(storyboard.created_at),
        updated_at=str(storyboard.updated_at),
    )


# ============== API 端点 ==============

@router.get("/script/{script_id}", response_model=List[StoryboardResponse])
async def list_storyboards_by_script(
    script_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取指定剧本的所有分镜"""
    script = await get_script_for_user(db, script_id, user_id)

    result = await db.execute(
        select(Storyboard)
        .where(and_(Storyboard.script_id == script_id, Storyboard.user_id == user_id))
        .order_by(desc(Storyboard.created_at))
    )
    storyboards = result.scalars().all()

    return [build_storyboard_response(storyboard, script.title) for storyboard in storyboards]


@router.get("/{storyboard_id}", response_model=StoryboardResponse)
async def get_storyboard(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取单个分镜"""
    result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id))
    )
    storyboard = result.scalar_one_or_none()

    if not storyboard:
        raise HTTPException(status_code=404, detail="分镜不存在")

    script = await get_script_for_user(db, storyboard.script_id, user_id)
    return build_storyboard_response(storyboard, script.title)


@router.post("", response_model=StoryboardResponse, status_code=status.HTTP_201_CREATED)
async def create_storyboard(
    storyboard: StoryboardCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建分镜"""
    script = await get_script_for_user(db, storyboard.script_id, user_id)

    storyboard_id = str(uuid.uuid4())

    db_storyboard = Storyboard(
        id=storyboard_id,
        script_id=storyboard.script_id,
        user_id=user_id,
        title=storyboard.title,
        description=storyboard.description,
        content=storyboard.content or {},
        status="draft"
    )

    db.add(db_storyboard)
    await db.commit()
    await db.refresh(db_storyboard)

    return build_storyboard_response(db_storyboard, script.title)


@router.put("/{storyboard_id}", response_model=StoryboardResponse)
async def update_storyboard(
    storyboard_id: str,
    storyboard_update: StoryboardUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新分镜"""
    result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id))
    )
    db_storyboard = result.scalar_one_or_none()

    if not db_storyboard:
        raise HTTPException(status_code=404, detail="分镜不存在")

    update_data = storyboard_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_storyboard, key, value)

    await db.commit()
    await db.refresh(db_storyboard)

    script = await get_script_for_user(db, db_storyboard.script_id, user_id)
    return build_storyboard_response(db_storyboard, script.title)


@router.delete("/{storyboard_id}")
async def delete_storyboard(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除分镜"""
    result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id))
    )
    db_storyboard = result.scalar_one_or_none()

    if not db_storyboard:
        raise HTTPException(status_code=404, detail="分镜不存在")

    await db.delete(db_storyboard)
    await db.commit()

    return {"message": "分镜已删除"}


@router.post("/generate", response_model=StoryboardGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_storyboard(
    request: StoryboardGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """AI生成分镜 - 将剧本内容转换为详细的分镜列表（含镜头信息）"""
    # 获取剧本信息
    script = await get_script_for_user(db, request.script_id, user_id)

    if not script.content:
        raise HTTPException(status_code=400, detail="剧本内容为空，无法生成分镜")

    # 获取用户的API密钥
    api_key, provider_name, model_id, base_url = await get_user_qwen_api_key(db, user_id)

    if provider_name == "qianlian":
        from app.services.qianlian_service import QianlianService
        service = QianlianService(api_key, base_url)
    elif provider_name in ("dashscope", "qwen"):
        from app.services.dashscope_service import DashScopeService
        service = DashScopeService(api_key, base_url)
    else:
        from app.services.qianlian_service import QianlianService
        service = QianlianService(api_key, base_url)

    # 构建分镜生成提示词
    shot_count_hint = f"生成约{request.shot_count}个镜头" if request.shot_count else "自动确定镜头数量"
    style_hint = f"风格：{request.style}"

    # 风格详细配置
    style_configs = {
        "anime": "动画风格：鲜艳色彩、夸张表情、流畅动作、幻想元素，镜头节奏明快",
        "anime_cartoon": "动画卡通风格：简化造型、可爱角色，明快节奏，适合轻松剧情",
        "realistic": "写实风格：真实光影、细腻表演，自然对话，电影感镜头",
        "cyberpunk": "赛博朋克风格：霓虹光效、高科技设定，未来城市感，冷色调",
        "fantasy": "奇幻风格：魔法效果、异世界设定、史诗场景，大场面调度",
    }
    style_detail = style_configs.get(request.style, f"风格：{request.style or '默认'}")

    system_prompt = f"""你是一个专业的电影分镜导演。你需要将剧本内容转换为详细的、可执行的分镜列表。

【基本信息】
- 书名：《{script.title or '未知'}》
- 剧本风格：{style_detail}
- 镜头数量：{shot_count_hint}
- **全程使用中文输出所有内容**

【分镜要求】
每个镜头包含以下字段（严格JSON数组格式）：

1. shot_number: 镜头序号（从1开始）
2. duration: 镜头时长（秒），通常3-8秒
3. shot_type: 镜头类型（establishing/action/reaction/dialogue/transition/summary）
4. prompt: 视频生成Prompt（AI视频生成核心描述，20-50字，画面感强，中文）
5. dialogue: 台词/配音（如有，中文）
6. visual_description: 视觉描述（构图、光线、色彩、人物位置、表情、动作细节，50-100字，中文）
7. camera_angle: 镜头角度（wide/medium/close-up/extreme-close-up/over-shoulder/dutch/two-shot/aerial）
8. camera_movement: 运镜方式（固定/推/拉/摇/移/跟/手持/升降）
9. sound_effect: 音效提示（风声、雨声、脚步、武器碰撞等，中文）
10. music_mood: 配乐氛围（紧张悬疑/轻松愉悦/史诗大气/悲伤抒情/战斗激烈，中文）

【输出格式】
严格按JSON数组格式输出，不要包含markdown代码块或其他任何额外文字：
[{{"shot_number":1,...}},...]

【示例】
[{{"shot_number":1,"duration":5,"shot_type":"establishing","prompt":"清晨山顶，少年剑客负手而立，远眺云海翻涌","dialogue":"（旁白）江湖之大，何处是我归途？","visual_description":"远景镜头，少年剑客背对观众，白色长袍随风飘动，脚下云海翻涌，朝阳初升，光线金色","camera_angle":"wide","camera_movement":"缓慢拉远","sound_effect":"风声、山谷回响","music_mood":"史诗大气"}},...]

【创作要点】
1. **戏剧冲突优先**：每个镜头必须推动剧情，不能有冗余的过渡镜头
2. **视觉节奏**：紧张动作场景用短镜头（2-4秒），舒缓场景可用长镜头（8-12秒）
3. **画面连贯**：相邻镜头的角度和运动要有逻辑衔接
4. **玄幻特效**：修仙/奇幻类注意功法光效、灵气色彩、武器特效描写
5. **中文输出**：所有描述、台词、音效、氛围必须使用中文"""

    try:
        response = await service.safe_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请为以下剧本生成分镜：\n\n【剧本标题】{script.title}\n【剧本内容】\n{script.content}"}
            ],
            temperature=0.7,
            max_tokens=8000
        )

        content = response["choices"][0]["message"]["content"]

        # 解析JSON
        import json
        json_str = content.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:]
        if json_str.startswith("```"):
            json_str = json_str[3:]
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        json_str = json_str.strip()

        shots_data = json.loads(json_str)
        if not isinstance(shots_data, list):
            shots_data = [shots_data]

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI返回内容解析失败: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI生成分镜失败: {str(e)}"
        )

    # 创建分镜记录
    storyboard_id = str(uuid.uuid4())
    now = datetime.utcnow()
    storyboard_title = f"{script.title} - 分镜"
    total_duration = sum(s.get("duration", 4) for s in shots_data)

    db_storyboard = Storyboard(
        id=storyboard_id,
        script_id=request.script_id,
        user_id=user_id,
        title=storyboard_title,
        description=f"{style_hint}，共{len(shots_data)}个镜头",
        content={"shots_summary": f"共{len(shots_data)}个镜头"},
        shot_count=len(shots_data),
        total_duration=total_duration,
        status="draft"
    )
    db.add(db_storyboard)

    # 创建镜头记录
    created_shots = []
    for shot_data in shots_data:
        shot_id = str(uuid.uuid4())
        await db.execute(
            text("""
                INSERT INTO shots (
                    id, storyboard_id, user_id, shot_number, duration,
                    prompt, dialogue, visual_description, camera_angle,
                    video_status, audio_status, version,
                    created_at, updated_at
                )
                VALUES (
                    :id, :storyboard_id, :user_id, :shot_number, :duration,
                    :prompt, :dialogue, :visual_description, :camera_angle,
                    :video_status, :audio_status, :version,
                    :created_at, :updated_at
                )
            """),
            {
                "id": shot_id,
                "storyboard_id": storyboard_id,
                "user_id": user_id,
                "shot_number": shot_data.get("shot_number", 1),
                "duration": shot_data.get("duration", 4),
                "prompt": shot_data.get("prompt", ""),
                "dialogue": shot_data.get("dialogue"),
                "visual_description": shot_data.get("visual_description"),
                "camera_angle": shot_data.get("camera_angle"),
                "video_status": "pending",
                "audio_status": "pending",
                "version": 1,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )
        created_shots.append({
            "id": shot_id,
            "shot_number": shot_data.get("shot_number", 1),
            "duration": shot_data.get("duration", 4),
            "prompt": shot_data.get("prompt"),
            "dialogue": shot_data.get("dialogue"),
            "visual_description": shot_data.get("visual_description"),
            "camera_angle": shot_data.get("camera_angle"),
        })

    await db.commit()

    return StoryboardGenerateResponse(
        id=str(storyboard_id),
        script_id=str(request.script_id),
        user_id=str(user_id),
        title=storyboard_title,
        script_title=script.title,
        description=f"{style_hint}，共{len(shots_data)}个镜头",
        content={"shots_summary": f"共{len(shots_data)}个镜头"},
        shot_count=len(shots_data),
        total_duration=total_duration,
        status="draft",
        shots=[ShotBriefResponse(**s) for s in created_shots],
        created_at=str(now),
        updated_at=str(now)
    )


@router.post("/{storyboard_id}/shots/generate-images")
async def generate_storyboard_shot_images(
    storyboard_id: str,
    shot_ids: List[str] = Body(...),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """批量为指定镜头生成参考图"""
    result = await db.execute(
        select(Storyboard).where(and_(Storyboard.id == storyboard_id, Storyboard.user_id == user_id))
    )
    storyboard = result.scalar_one_or_none()
    if not storyboard:
        raise HTTPException(status_code=404, detail="分镜不存在")

    results = []
    for shot_id in shot_ids:
        shot_result = await db.execute(
            select(Shot).where(and_(Shot.id == shot_id, Shot.storyboard_id == storyboard_id))
        )
        shot = shot_result.scalar_one_or_none()
        if not shot:
            results.append({"shot_id": shot_id, "status": "skipped", "reason": "not found or not in this storyboard"})
            continue

        prompt_parts = []
        if shot.visual_description:
            prompt_parts.append(shot.visual_description)
        if shot.prompt:
            prompt_parts.append(shot.prompt)
        if shot.lighting:
            prompt_parts.append(f"lighting: {shot.lighting}")
        prompt = " ".join(prompt_parts) if prompt_parts else shot.visual_description or shot.prompt or "cinematic scene"

        try:
            from app.services.volcano_service import VolcanoService
            volcano = VolcanoService()
            result_img = await volcano.generate_image(prompt=prompt)
            task_id = result_img.get("task_id")

            shot.image_status = "generating"
            await db.commit()

            from app.services.image_poll_service import poll_and_update_shot_image
            asyncio.create_task(poll_and_update_shot_image(shot_id, task_id, user_id))

            results.append({"shot_id": shot_id, "task_id": task_id, "status": "generating"})
        except Exception as e:
            results.append({"shot_id": shot_id, "status": "error", "reason": str(e)})

    return {"storyboard_id": storyboard_id, "results": results}
