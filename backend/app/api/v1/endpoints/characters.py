"""
角色管理 API 端点
"""

from typing import List, Optional
from datetime import datetime
from uuid import uuid4
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.character import Character
from app.models.llm_config import LLMProvider, LLMModel, LLMConfig
from app.api.v1.endpoints.dashboard import log_activity

router = APIRouter(tags=["角色管理"])


# ============== 数据模型 ==============

class CharacterCreate(BaseModel):
    """创建角色请求"""
    name: str = Field(..., min_length=1, max_length=100, description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    appearance: Optional[str] = Field(None, description="外貌特征")
    personality: Optional[str] = Field(None, description="性格特点")
    voice: Optional[str] = Field(None, description="声音特征")
    avatar: Optional[str] = Field(None, description="头像URL")
    tags: List[str] = Field(default_factory=list, description="标签")


class CharacterUpdate(BaseModel):
    """更新角色请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    appearance: Optional[str] = None
    personality: Optional[str] = None
    voice: Optional[str] = None
    avatar: Optional[str] = None
    tags: Optional[List[str]] = None


class CharacterResponse(BaseModel):
    """角色响应"""
    id: str
    user_id: str
    name: str
    description: Optional[str]
    appearance: Optional[str]
    personality: Optional[str]
    voice: Optional[str]
    avatar: Optional[str]
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_orm(cls, character: Character) -> "CharacterResponse":
        tags = []
        if character.tags:
            try:
                tags = json.loads(character.tags) if isinstance(character.tags, str) else character.tags
            except:
                tags = []
        return cls(
            id=character.id,
            user_id=character.user_id,
            name=character.name,
            description=character.description,
            appearance=character.appearance,
            personality=character.personality,
            voice=character.voice,
            avatar=character.avatar,
            tags=tags,
            created_at=character.created_at,
            updated_at=character.updated_at
        )


class CharacterExtractRequest(BaseModel):
    """AI提取角色请求"""
    novel_id: Optional[str] = Field(None, description="小说ID（优先使用，会自动获取小说和章节内容）")
    chapter_id: Optional[str] = Field(None, description="章节ID（可选，单独提取某章角色）")
    text: Optional[str] = Field(None, description="待分析文本（直接传入文本时使用）")
    character_count: int = Field(default=10, ge=1, le=30, description="提取角色数量")
    auto_generate_avatar: bool = Field(default=True, description="提取后自动生成头像图片")


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
            detail="请先配置千问/百炼大模型API密钥（LLM配置页面）"
        )

    config, model, provider = row

    if not config.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="大模型API密钥未设置，请在LLM配置中填入有效的API Key"
        )

    model_id_str = model.model_id
    base_url = model.base_url
    return config.api_key, provider.name, model_id_str, base_url


# ============== 模拟数据库（开发阶段使用）==============

# 内存存储，生产环境应使用真实数据库
CHARACTERS_DB = {}


# ============== API端点 ==============

@router.get("", response_model=List[CharacterResponse])
async def list_characters(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的所有角色"""
    result = await db.execute(
        select(Character).where(Character.user_id == user_id).order_by(desc(Character.created_at))
    )
    characters = result.scalars().all()
    return [CharacterResponse.from_orm(char) for char in characters]


@router.get("/count")
async def get_character_count(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取角色数量（用于Dashboard统计）"""
    result = await db.execute(
        select(Character).where(Character.user_id == user_id)
    )
    characters = result.scalars().all()
    
    return {"count": len(characters)}


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取单个角色详情"""
    result = await db.execute(
        select(Character).where(
            and_(Character.id == character_id, Character.user_id == user_id)
        )
    )
    character = result.scalar_one_or_none()
    
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    return CharacterResponse.from_orm(character)


@router.post("", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character(
    character: CharacterCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """创建新角色"""
    new_character = Character(
        id=str(uuid4()),
        user_id=user_id,
        name=character.name,
        description=character.description,
        appearance=character.appearance,
        personality=character.personality,
        voice=character.voice,
        avatar=character.avatar,
        tags=json.dumps(character.tags) if character.tags else "[]",
    )
    
    db.add(new_character)
    await db.commit()
    await db.refresh(new_character)

    await log_activity(
        db=db,
        user_id=user_id,
        activity_type="created",
        entity_type="character",
        entity_id=new_character.id,
        title=f"创建角色: {new_character.name}",
    )
    await db.commit()


@router.put("/{character_id}", response_model=CharacterResponse)
async def update_character(
    character_id: str,
    character: CharacterUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新角色信息"""
    result = await db.execute(
        select(Character).where(
            and_(Character.id == character_id, Character.user_id == user_id)
        )
    )
    db_character = result.scalar_one_or_none()
    
    if not db_character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    # 更新非空字段
    update_data = character.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == 'tags' and value is not None:
            setattr(db_character, field, json.dumps(value))
        else:
            setattr(db_character, field, value)
    
    db_character.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(db_character)
    
    return CharacterResponse.from_orm(db_character)


@router.delete("/{character_id}")
async def delete_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除角色"""
    result = await db.execute(
        select(Character).where(
            and_(Character.id == character_id, Character.user_id == user_id)
        )
    )
    character = result.scalar_one_or_none()
    
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色不存在"
        )
    
    await db.delete(character)
    await db.commit()

    return {"message": "角色已删除"}


# ============== 头像生成辅助函数 ==============

def build_avatar_prompt(char: Character) -> str:
    """Construct an image generation prompt from character data."""
    parts = []
    if char.name:
        parts.append(f"character: {char.name}")
    if char.appearance:
        parts.append(f"appearance: {char.appearance}")
    if char.personality:
        parts.append(f"personality: {char.personality}")
    parts.append("anime style, high quality, portrait")
    return ", ".join(parts)


@router.post("/extract", response_model=List[CharacterResponse], status_code=status.HTTP_201_CREATED)
async def extract_characters(
    request: CharacterExtractRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """AI提取角色 - 从小说/章节文本中分析并提取角色信息"""
    # 获取待分析的文本内容
    analysis_text = request.text
    novel_title = "未知小说"

    if not analysis_text and request.novel_id:
        # 根据小说ID获取小说信息和所有章节内容
        from app.models import Novel, Chapter

        # 获取小说信息
        novel_result = await db.execute(
            select(Novel).where(and_(Novel.id == request.novel_id, Novel.user_id == user_id))
        )
        novel = novel_result.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="小说不存在")

        novel_title = novel.title

        # 获取所有章节内容
        chapters_result = await db.execute(
            select(Chapter)
            .where(and_(Chapter.novel_id == request.novel_id, Chapter.user_id == user_id))
            .order_by(Chapter.chapter_number)
        )
        chapters = chapters_result.scalars().all()

        if not chapters:
            raise HTTPException(status_code=400, detail="该小说暂无章节内容，请先生成或编写章节后再提取角色")

        # 拼接小说简介和所有章节内容
        parts = []
        if novel.description:
            parts.append(f"【小说简介】{novel.description}")
        if novel.genre:
            parts.append(f"【小说类型】{novel.genre}")

        for ch in chapters:
            if ch.content:
                parts.append(f"\n=== 第{ch.chapter_number}章《{ch.title}》 ===\n{ch.content}")

        analysis_text = "\n".join(parts)

    elif not analysis_text and request.chapter_id:
        # 根据章节ID获取内容
        from app.models import Novel, Chapter

        chapter_result = await db.execute(
            select(Chapter, Novel)
            .join(Novel, Chapter.novel_id == Novel.id)
            .where(and_(Chapter.id == request.chapter_id, Chapter.user_id == user_id))
        )
        row = chapter_result.first()
        if not row:
            raise HTTPException(status_code=404, detail="章节不存在")
        chapter, novel = row
        novel_title = novel.title

        parts = []
        if novel.description:
            parts.append(f"【小说简介】{novel.description}")
        parts.append(f"\n=== 第{chapter.chapter_number}章《{chapter.title}》 ===\n{chapter.content or ''}")
        analysis_text = "\n".join(parts)

    elif not analysis_text:
        raise HTTPException(status_code=400, detail="请提供 novel_id、chapter_id 或 text 参数")

    if len(analysis_text) < 50:
        raise HTTPException(status_code=400, detail="文本内容太少，无法提取角色，请先生成章节内容")

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

    # 构建提取提示词
    system_prompt = f"""你是一个专业的小说角色分析专家。你需要从给定的小说文本中识别和提取所有重要角色。

【小说信息】
书名：《{novel_title}》

【任务要求】
请为每个识别出的角色提取以下信息：
1. name: 角色名称（中文）
2. description: 角色背景、身份、与主角的关系等描述（中文）
3. appearance: 外貌特征描述（中文）
4. personality: 性格特点描述（中文）
5. voice: 声音、语言风格特征描述（中文）
6. tags: 角色标签列表，如：主角、女主角、反派、师父、妖兽等（中文标签）

【重要】
1. **必须全程使用中文输出**，包括所有角色名称、描述、标签
2. 严格按照JSON数组格式输出，不要包含任何额外文字、解释或markdown标记
3. 仔细分析文本中出现的每个人物，包括主角、配角、反派、路人等
4. 同一角色不要重复出现
5. tags数组中的标签必须全部是中文

【输出格式】
直接输出JSON数组，不要用markdown代码块包裹："""

    # 截断过长的文本（模型上下文有限）
    max_chars = 30000
    if len(analysis_text) > max_chars:
        analysis_text = analysis_text[:max_chars] + "\n\n[内容已截断]"

    try:
        response = await service.safe_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请从以下文本中提取角色信息（最多{request.character_count}个重要角色），直接输出JSON数组：\n\n{analysis_text}"}
            ],
            temperature=0.3,
            max_tokens=4000
        )

        content = response["choices"][0]["message"]["content"]

        # 解析JSON
        import json
        json_str = content.strip()
        # 去掉可能的markdown代码块
        if "```json" in json_str:
            json_str = json_str.split("```json")[1]
        elif "```" in json_str:
            json_str = json_str.split("```")[1]
        if "```" in json_str:
            json_str = json_str.split("```")[0]
        json_str = json_str.strip()

        characters_data = json.loads(json_str)

        # 限制数量
        if not isinstance(characters_data, list):
            characters_data = [characters_data]
        characters_data = characters_data[:request.character_count]

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI返回内容解析失败: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI角色提取失败: {str(e)}"
        )

    # 创建角色记录
    created_characters = []
    for char_data in characters_data:
        new_character = Character(
            id=str(uuid4()),
            user_id=user_id,
            name=char_data.get("name", "未知角色"),
            description=char_data.get("description"),
            appearance=char_data.get("appearance"),
            personality=char_data.get("personality"),
            voice=char_data.get("voice"),
            tags=json.dumps(char_data.get("tags", [])),
        )
        db.add(new_character)
        created_characters.append(new_character)

    await db.commit()

    # 自动生成头像（使用异步轮询，60s超时）
    avatar_errors = []
    if request.auto_generate_avatar and created_characters:
        try:
            from app.core.api_key_utils import get_user_volcano_api_key
            from app.services.volcano_service import VolcanoService
            api_key = await get_user_volcano_api_key(db, user_id)
            volcano = VolcanoService(api_key)
            for char in created_characters:
                try:
                    prompt = build_avatar_prompt(char)
                    result = await volcano.generate_image(
                        prompt=prompt,
                        model="Doubao-Seedream-5.0-lite",
                        size="2K",
                        num=1
                    )
                    image_url = None
                    if "data" in result and result["data"]:
                        item = result["data"][0]
                        if isinstance(item, dict) and "url" in item:
                            image_url = item["url"]
                    if image_url:
                        char.avatar = image_url
                        db.add(char)
                        await db.commit()
                    else:
                        avatar_errors.append(f"{char.name}: 未获取到头像URL")
                except Exception as e:
                    avatar_errors.append(f"{char.name}: {str(e)}")
        except HTTPException:
            # 没有配置火山引擎API Key
            avatar_errors.append("未配置火山引擎API Key（请在LLM配置中添加）")
        except Exception as e:
            avatar_errors.append(f"头像生成服务异常: {str(e)}")

    # 刷新并返回
    for char in created_characters:
        await db.refresh(char)

    return [CharacterResponse.from_orm(char) for char in created_characters]