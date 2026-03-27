"""
剧本管理 API 端点
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.llm_config import LLMProvider, LLMModel, LLMConfig
from app.models import Script, Novel, Chapter
from app.api.v1.endpoints.dashboard import log_activity

router = APIRouter(tags=["剧本管理"])


# ============== Pydantic 模型 ==============

class ScriptCreate(BaseModel):
    """创建剧本"""
    novel_id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    content: Optional[str] = None
    genre: Optional[str] = None
    style: Optional[str] = None
    duration: Optional[int] = None

    @field_validator("novel_id", mode="before")
    @classmethod
    def validate_novel_id(cls, value):
        if value is None:
            return value
        if isinstance(value, str) and value.strip() == "":
            raise ValueError("novel_id cannot be blank")
        return value


class ScriptUpdate(BaseModel):
    """更新剧本"""
    novel_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    genre: Optional[str] = None
    style: Optional[str] = None
    duration: Optional[int] = None
    status: Optional[str] = None

    @field_validator("novel_id", mode="before")
    @classmethod
    def validate_novel_id(cls, value):
        if value is None:
            return value
        if isinstance(value, str) and value.strip() == "":
            raise ValueError("novel_id cannot be blank")
        return value


class ScriptResponse(BaseModel):
    """剧本响应"""
    id: str
    user_id: str
    novel_id: Optional[str]
    novel_title: Optional[str] = None
    title: str
    description: Optional[str]
    content: Optional[str]
    genre: Optional[str]
    style: Optional[str]
    duration: Optional[int]
    status: str
    created_at: datetime
    updated_at: datetime


class ScriptGenerateRequest(BaseModel):
    """AI生成剧本请求"""
    chapter_id: str = Field(..., description="章节ID")
    style: str = Field(default="anime", description="剧本风格（anime/anime_cartoon/realistic等）")
    genre: Optional[str] = Field(None, description="剧本类型（可选）")


# ============== LLM API Key 辅助函数 ==============

async def get_user_qwen_api_key(db: AsyncSession, user_id: str) -> tuple[str, str, str, Optional[str]]:
    """
    获取用户的千问/DashScope API密钥

    Returns:
        tuple: (api_key, provider_name, model_id)

    Raises:
        HTTPException: 如果未找到有效配置
    """
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
        .order_by(desc(LLMConfig.is_default), desc(LLMConfig.last_used_at))
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先配置千问/百炼大模型API密钥"
        )

    config, model, provider = row

    if not config.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="大模型API密钥未设置"
        )

    return config.api_key, provider.name, model.model_id, model.base_url




async def get_novel_for_user(db: AsyncSession, novel_id: str, user_id: str):
    from app.models import Novel

    result = await db.execute(
        select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id))
    )
    novel = result.scalar_one_or_none()
    if novel is None:
        raise HTTPException(status_code=404, detail="所属小说不存在")
    return novel


async def get_novel_title_map(db: AsyncSession, user_id: str, novel_ids: set[str]) -> dict[str, str]:
    if not novel_ids:
        return {}

    from app.models import Novel

    result = await db.execute(
        select(Novel).where(and_(Novel.user_id == user_id, Novel.id.in_(novel_ids)))
    )
    novels = result.scalars().all()
    return {novel.id: novel.title for novel in novels}


def build_script_response(script: Script, novel_title: Optional[str] = None) -> ScriptResponse:
    return ScriptResponse(
        id=script.id,
        user_id=script.user_id,
        novel_id=script.novel_id,
        novel_title=novel_title,
        title=script.title,
        description=script.description,
        content=script.content,
        genre=script.genre,
        style=script.style,
        duration=script.duration,
        status=script.status or "draft",
        created_at=script.created_at,
        updated_at=script.updated_at,
    )


# ============== API 端点 ==============

@router.get("", response_model=List[ScriptResponse])
async def list_scripts(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的所有剧本"""

    result = await db.execute(
        select(Script)
        .where(Script.user_id == user_id)
        .order_by(desc(Script.updated_at))
    )
    scripts = result.scalars().all()

    novel_title_map = await get_novel_title_map(
        db,
        user_id,
        {script.novel_id for script in scripts if script.novel_id},
    )

    return [
        build_script_response(script, novel_title_map.get(script.novel_id))
        for script in scripts
    ]


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(
    script_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取单个剧本"""

    result = await db.execute(
        select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
    )
    script = result.scalar_one_or_none()

    if not script:
        raise HTTPException(status_code=404, detail="剧本不存在")

    novel_title = None
    if script.novel_id:
        novel = await get_novel_for_user(db, script.novel_id, user_id)
        novel_title = novel.title

    return build_script_response(script, novel_title)


@router.post("", response_model=ScriptResponse, status_code=status.HTTP_201_CREATED)
async def create_script(
    script: ScriptCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建剧本"""

    novel_title = None
    if script.novel_id:
        novel = await get_novel_for_user(db, script.novel_id, user_id)
        novel_title = novel.title

    db_script = Script(
        id=str(uuid4()),
        user_id=user_id,
        novel_id=script.novel_id,
        title=script.title,
        description=script.description,
        content=script.content,
        genre=script.genre,
        style=script.style,
        duration=script.duration,
        status="draft"
    )
    db.add(db_script)
    await db.commit()
    await db.refresh(db_script)

    await log_activity(
        db=db,
        user_id=user_id,
        activity_type="created",
        entity_type="script",
        entity_id=db_script.id,
        title=f"创建剧本: {db_script.title}",
    )
    await db.commit()

    return build_script_response(db_script, novel_title)


@router.put("/{script_id}", response_model=ScriptResponse)
async def update_script(
    script_id: str,
    script_update: ScriptUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新剧本"""

    result = await db.execute(
        select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
    )
    db_script = result.scalar_one_or_none()

    if not db_script:
        raise HTTPException(status_code=404, detail="剧本不存在")

    update_data = script_update.model_dump(exclude_unset=True)
    if "novel_id" in update_data and update_data["novel_id"]:
        await get_novel_for_user(db, update_data["novel_id"], user_id)

    for key, value in update_data.items():
        setattr(db_script, key, value)

    await db.commit()
    await db.refresh(db_script)

    novel_title = None
    if db_script.novel_id:
        novel = await get_novel_for_user(db, db_script.novel_id, user_id)
        novel_title = novel.title

    return build_script_response(db_script, novel_title)


@router.delete("/{script_id}")
async def delete_script(
    script_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除剧本"""

    result = await db.execute(
        select(Script).where(and_(Script.id == script_id, Script.user_id == user_id))
    )
    db_script = result.scalar_one_or_none()

    if not db_script:
        raise HTTPException(status_code=404, detail="剧本不存在")

    await db.delete(db_script)
    await db.commit()

    return {"message": "剧本已删除"}


@router.post("/generate", response_model=ScriptResponse, status_code=status.HTTP_201_CREATED)
async def generate_script(
    request: ScriptGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """AI生成剧本 - 将章节内容转换为分镜头剧本"""

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

    # 获取章节内容
    chapter_result = await db.execute(
        select(Chapter).where(and_(Chapter.id == request.chapter_id, Chapter.user_id == user_id))
    )
    chapter = chapter_result.scalar_one_or_none()

    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    if not chapter.content:
        raise HTTPException(status_code=400, detail="章节内容为空，无法生成剧本")

    chapter_id = chapter.id
    novel_id = chapter.novel_id
    chapter_title = chapter.title
    chapter_content = chapter.content

    # 获取小说信息
    novel = None
    novel_title = None
    novel_description = None
    novel_genre = None
    if novel_id:
        novel_result = await db.execute(
            select(Novel).where(and_(Novel.id == novel_id, Novel.user_id == user_id)))
        novel = novel_result.scalar_one_or_none()
        if novel:
            novel_title = novel.title
            novel_description = novel.description
            novel_genre = novel.genre

    # 获取同小说其他章节（用于剧情上下文）
    other_chapters_context = ""
    if novel_id:
        other_result = await db.execute(
            select(Chapter)
            .where(and_(Chapter.novel_id == novel_id, Chapter.user_id == user_id, Chapter.id != chapter_id))
            .order_by(Chapter.chapter_number)
        )
        other_chapters = other_result.scalars().all()
        if other_chapters:
            prev_ch = other_chapters[-1] if other_chapters else None
            if prev_ch and prev_ch.content:
                other_chapters_context += f"\n\n【前情提要 - 第{prev_ch.chapter_number}章《{prev_ch.title}》】\n{prev_ch.content[:1500]}"

    # 风格配置
    style_configs = {
        "anime": "动画风格：鲜艳色彩、夸张表情、流畅动作、幻想元素，镜头节奏明快",
        "anime_cartoon": "动画卡通风格：简化造型、可爱角色，明快节奏，适合轻松剧情",
        "realistic": "写实风格：真实光影、细腻表演，自然对话，电影感镜头",
        "cyberpunk": "赛博朋克风格：霓虹光效、高科技设定，未来城市感，冷色调",
        "fantasy": "奇幻风格：魔法效果、异世界设定、史诗场景，大场面调度",
    }
    style_desc = style_configs.get(request.style, f"风格：{request.style or '默认'}")
    genre_hint = f"类型：{request.genre or novel_genre or '玄幻'}" if request.genre or novel_genre else ""

    # 截断过长内容
    max_chars = 20000
    chapter_for_prompt = chapter_content
    if len(chapter_content or "") > max_chars:
        chapter_for_prompt = (chapter_content or "")[:max_chars] + "\n\n[章节内容过长已截断]"

    # 构建增强版剧本生成提示词
    system_prompt = f"""你是一个专业的电影剧本作家和分镜导演。你需要将小说章节内容转换为专业的、有吸引力的分镜头剧本。

【基本信息】
小说名称：《{novel_title or '未知'}》
小说简介：{novel_description or '暂无'}
{genre_hint}
目标风格：{style_desc}

【前情提要】
{other_chapters_context if other_chapters_context else "（本章为故事开端，无前情）"}

【剧本创作核心要求】

一、整体结构
将章节分解为3-5个主要场景（Scene），每个场景要有明确的戏剧推动力，不能平铺直叙。

二、每个场景的剧本格式（严格按以下格式输出）：

【第N场】场景标题
- 场景类型：[内景/外景] [日/夜/晨/昏/黎明]
- 时长：约X秒
- 地点：[具体位置]
- 人物：[出场角色列表]
- 戏剧核心：[本场景的主要矛盾/冲突是什么]

【画面描述】
[详细的镜头画面描述：构图方式、光线色调、人物位置、表情、动作、环境氛围。注意玄幻类的功法特效、光效色彩]

【对话/旁白】
[本场景的对白]
- 角色A：（情绪/语气）"对白内容"
- 角色B：（情绪/语气）"对白内容"
- （旁白）"叙述性文字"

【镜头序列】（分解为3-8个具体镜头）
1. [镜头类型] - [景别：远/全/中/近/特] - [运镜方式：推/拉/摇/移/跟/固定] - [画面内容描述]
2. [镜头类型] - [景别] - [运镜方式] - [画面内容描述]
（依次列出所有镜头）

【音效/音乐提示】
- 环境音：[风声、雨声、人群嘈杂、山林鸟鸣、修炼场灵气涌动等]
- 背景音乐：[紧张悬疑、轻松愉悦、史诗大气、悲伤抒情、战斗激烈等]
- 特效提示：[灵气光芒、打斗光效、烟雾弥漫、水波荡漾等]

【戏剧张力评级】（1-5星）
⭐⭐⭐⭐☆

三、创作要点
1. **戏剧冲突优先**：每个场景必须有推动剧情的核心矛盾，不能流水账
2. **情感节奏**：有紧张场景也要有舒缓过渡，张弛有度
3. **视觉奇观**：玄幻/修仙类注意功法特效、灵气光效；战斗场景要有冲击力
4. **全程中文**：所有内容、描述、术语全部使用中文
5. **可执行性**：画面描述要能直接指导美术和摄影师执行

请输出完整的分镜头剧本："""

    user_prompt = f"""请将以下小说章节内容转换为专业的分镜头剧本。深入分析章节的戏剧冲突、高潮和情感节奏，每个场景要有明确的冲突推动力。

【章节标题】{chapter_title}

【章节正文】
{chapter_for_prompt}

请输出完整的分镜头剧本。**重要：输出格式**：
第一行必须是剧本标题，格式：「剧本标题：[自动生成的剧本标题]」（不用markdown）
第二行起是剧本正文内容。"""

    try:
        response = await service.safe_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,
            max_tokens=12000
        )

        script_content = response["choices"][0]["message"]["content"]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI生成剧本失败: {str(e)}"
        )

    # 从AI返回内容中提取标题
    # 格式：「剧本标题：xxx」或「剧本标题: xxx」
    import re
    title_match = re.search(r'「剧本标题[：:]\s*(.+?)」', script_content)
    if title_match:
        script_title = title_match.group(1).strip()
        # 从content中去掉标题行，只保留正文
        lines = script_content.split('\n')
        content_start = 0
        for i, line in enumerate(lines):
            if '「剧本标题' in line:
                content_start = i + 1
                break
        script_content = '\n'.join(lines[content_start:]).strip()
    else:
        script_title = f"第{chapter.chapter_number}章《{chapter_title}》剧本" if chapter else f"{chapter_title} - 剧本"

    # 创建剧本记录
    script_id = str(uuid4())

    db_script = Script(
        id=script_id,
        user_id=user_id,
        novel_id=novel_id,
        title=script_title,
        description=f"改编自《{chapter_title}》，{style_desc}",
        content=script_content,
        genre=request.genre or "unknown",
        style=request.style,
        status="draft"
    )
    db.add(db_script)
    await db.commit()
    await db.refresh(db_script)

    return build_script_response(db_script, novel_title)
