"""
TTS (文本转语音) API 端点
支持 MiniMax TTS（优先）、火山引擎 TTS
支持多角色对话分段生成
"""

import re
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, desc, or_, select
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.core.api_key_utils import get_user_api_key
from app.core.dev_generation import dev_audio_url, dev_tts_audio_url, estimate_tts_duration_seconds, is_dev_mode
from app.core.minimax_config import DEFAULT_TTS_VOICE
from app.core.time_utils import utc_now
from app.services.dialogue_parser import extract_character_from_text, parse_dialogue
from app.services.consistency_context import build_consistency_prompt
from app.services.consistency_preflight import build_generation_context_package, preflight_failure_detail
from app.models.tts_job import TTSJob
from app.models.shot import Shot
from app.models.character import Character
from app.models.asset import Asset
from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.services.minimax_service import MINIMAX_VOICE_CLONE_MODEL
from app.services.volcano_speech_tts import configure_volcano_speech_endpoint

router = APIRouter(tags=["语音合成"])
STATIC_ROOT = Path(__file__).resolve().parents[4] / "static"
VOICE_CLONE_DIR = STATIC_ROOT / "generated" / "voice-clones"
VOICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


# ============== 辅助函数 ==============

def is_multi_character(segments: List[Dict]) -> bool:
    """判断是否为多角色对话"""
    chars = set(s['character'] for s in segments if s['character'])
    return len(chars) > 1


def _preflight_summary(preflight_package: Optional[dict]) -> Optional[dict]:
    if preflight_package is None:
        return None
    return {
        "ready": preflight_package.get("ready"),
        "issues": preflight_package.get("issues") or [],
        "blocking_issue_count": preflight_package.get("blocking_issue_count") or 0,
    }


async def get_scoped_character_by_name(
    db: AsyncSession,
    user_id: str,
    *,
    name: str,
    novel_id: Optional[str],
    chapter_id: Optional[str],
) -> Optional[Character]:
    filters = [Character.user_id == user_id, Character.name == name]
    if novel_id:
        filters.append(or_(Character.novel_id == novel_id, Character.novel_id.is_(None)))
    elif chapter_id:
        filters.append(or_(Character.chapter_id == chapter_id, Character.novel_id.is_(None)))
    result = await db.execute(select(Character).where(and_(*filters)))
    characters = list(result.scalars().all())
    if not characters:
        return None

    def rank(character: Character) -> int:
        if chapter_id and character.chapter_id == chapter_id:
            return 3
        if novel_id and character.novel_id == novel_id:
            return 2
        if character.novel_id is None:
            return 1
        return 0

    return sorted(characters, key=rank, reverse=True)[0]


async def resolve_tts_segment_voice(
    db: AsyncSession,
    user_id: str,
    *,
    character_name: Optional[str],
    default_voice: str,
    default_speed: float,
    story_bible_id: Optional[str],
    use_story_bible_voice: bool,
    novel_id: Optional[str],
    chapter_id: Optional[str],
) -> Dict[str, Any]:
    voice_to_use = default_voice
    speed_to_use = default_speed
    voice_source = "request"

    if character_name and story_bible_id and use_story_bible_voice:
        from app.services.voice_service import get_character_voice_from_story_bible

        voice_config = await get_character_voice_from_story_bible(
            db, character_name, story_bible_id
        )
        if voice_config:
            story_bible_voice = voice_config.get("voice") or voice_config.get("voice_model")
            if story_bible_voice:
                voice_to_use = story_bible_voice
                voice_source = "story_bible"
            if voice_config.get("voice_speed") is not None:
                speed_to_use = voice_config.get("voice_speed")

    if character_name and voice_source != "story_bible":
        char = await get_scoped_character_by_name(
            db,
            user_id,
            name=character_name,
            novel_id=novel_id,
            chapter_id=chapter_id,
        )
        if char and char.voice:
            voice_to_use = char.voice
            voice_source = "character"

    return {
        "voice": voice_to_use,
        "speed": speed_to_use,
        "voice_source": voice_source,
        "character_name": character_name,
    }


# ============== 请求/响应模型 ==============

class TTSGenerateRequest(BaseModel):
    """TTS生成请求"""
    text_content: Optional[str] = Field(None, description="要转换的文本（支持多角色格式）")
    text: Optional[str] = Field(None, description="兼容旧字段：要转换的文本")
    title: Optional[str] = Field(None, description="任务标题")
    voice_model: str = Field(DEFAULT_TTS_VOICE, description="语音音色ID")
    voice: Optional[str] = Field(None, description="兼容旧字段：语音音色ID")
    speed: float = Field(1.0, description="语速")
    api_provider: Optional[str] = Field(None, description="API提供商: minimax, volcano")
    model_config_id: Optional[str] = Field(None, description="已保存的 TTS 模型配置ID")
    model_id: Optional[str] = Field(None, description="TTS API 模型ID，默认取所选配置的模型")
    api_key: Optional[str] = Field(None, description="兼容旧字段：直接传入API Key")
    project_id: Optional[str] = Field(None, description="关联的项目ID")
    workflow_id: Optional[str] = Field(None, description="关联的工作流ID")
    novel_id: Optional[str] = Field(None, description="关联的小说ID")
    chapter_id: Optional[str] = Field(None, description="关联的章节ID")
    script_id: Optional[str] = Field(None, description="关联的剧本ID")
    storyboard_id: Optional[str] = Field(None, description="关联的分镜ID")
    shot_id: Optional[str] = Field(None, description="关联的镜头ID")
    character_id: Optional[str] = Field(None, description="关联的角色ID")
    story_bible_id: Optional[str] = Field(None, description="用于一致性约束的 Story Bible ID")
    character_ids: List[str] = Field(default_factory=list, description="需要注入一致性设定的角色ID列表")
    use_consistency_context: bool = Field(True, description="是否记录 Story Bible/项目/镜头/角色一致性上下文")
    unsafe_skip_consistency_preflight: bool = Field(False, description="仅用于明确的生产降级调试：跳过一致性预检")
    use_story_bible_voice: bool = Field(True, description="是否使用 Story Bible 音色配置")


class TTSSegmentResponse(BaseModel):
    """单角色语音段"""
    character: str
    text: str
    voice: str
    audio_url: Optional[str] = None
    duration: Optional[float] = None


class TTSJobResponse(BaseModel):
    """TTS任务响应"""
    id: str
    job_id: Optional[str] = None
    task_id: Optional[str] = None
    user_id: str
    project_id: Optional[str] = None
    workflow_id: Optional[str] = None
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    storyboard_id: Optional[str] = None
    shot_id: Optional[str] = None
    character_id: Optional[str] = None
    title: Optional[str] = None
    text: Optional[str] = None
    voice: Optional[str] = None
    api_provider: Optional[str] = None
    status: str
    progress: int
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    cost: Optional[int] = 0
    error_message: Optional[str] = None
    extra_data: Optional[Dict] = {}
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class TTSPreviewRequest(BaseModel):
    text: str = Field("这是一段音色试听。", description="试听文本")
    voice_model: str = Field("female-shaonv", description="音色ID")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="语速")
    api_provider: str = Field("minimax", description="TTS提供商")
    model_config_id: Optional[str] = Field(None, description="已保存的 TTS 模型配置ID")
    model_id: Optional[str] = Field(None, description="TTS API 模型ID")


class TTSPreviewResponse(BaseModel):
    status: str
    audio_url: str
    voice: str
    provider: str
    duration_seconds: Optional[float] = None
    message: str


class VoiceCloneResponse(BaseModel):
    id: str
    voice_id: str
    name: str
    provider: str
    description: Optional[str] = None
    sample_audio_url: Optional[str] = None
    sample_source: Optional[str] = None
    character_id: Optional[str] = None
    novel_id: Optional[str] = None
    status: str
    is_custom: bool = True
    provider_ready: bool = False
    provider_file_id: Optional[str] = None
    provider_tts_model: Optional[str] = None
    provider_demo_audio_url: Optional[str] = None
    provider_error: Optional[str] = None
    created_at: datetime


def build_tts_response(job: TTSJob) -> TTSJobResponse:
    """Build a response that supports both current and legacy callers."""
    extra = dict(job.extra_data) if isinstance(job.extra_data, dict) else {}
    return TTSJobResponse(
        id=job.id,
        job_id=job.id,
        task_id=job.task_id,
        user_id=job.user_id,
        project_id=job.project_id,
        workflow_id=job.workflow_id,
        novel_id=job.novel_id,
        chapter_id=job.chapter_id,
        script_id=job.script_id,
        storyboard_id=job.storyboard_id,
        shot_id=job.shot_id,
        character_id=job.character_id,
        title=job.title,
        text=job.text,
        voice=job.voice,
        api_provider=job.api_provider,
        status=job.status,
        progress=job.progress,
        audio_url=job.audio_url,
        duration_seconds=job.duration_seconds,
        cost=job.cost,
        error_message=job.error_message,
        extra_data=extra,
        is_active=job.is_active,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _normalize_builtin_voice(item: dict, provider: str) -> dict:
    voice_id = item.get("voice_id") or item.get("id")
    return {
        "voice_id": voice_id,
        "id": voice_id,
        "name": item.get("name") or item.get("label") or voice_id,
        "label": item.get("label") or item.get("name") or voice_id,
        "gender": item.get("gender") or "unknown",
        "lang": item.get("lang") or "中文",
        "provider": provider,
        "is_custom": False,
        "sample_audio_url": item.get("sample_audio_url"),
        "status": "ready",
    }


def _voice_clone_response(asset: Asset) -> VoiceCloneResponse:
    params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
    clone_status = params.get("clone_status") or "ready"
    return VoiceCloneResponse(
        id=asset.id,
        voice_id=params.get("voice_id") or f"clone-{asset.id[:8]}",
        name=asset.name,
        provider=params.get("provider") or "custom",
        description=asset.description,
        sample_audio_url=asset.url,
        sample_source=params.get("sample_source") or params.get("clone_source"),
        character_id=asset.character_id,
        novel_id=asset.novel_id,
        status=clone_status,
        provider_ready=clone_status == "provider_ready",
        provider_file_id=params.get("provider_file_id"),
        provider_tts_model=_clone_tts_model_override(params),
        provider_demo_audio_url=params.get("provider_demo_audio_url"),
        provider_error=params.get("provider_error"),
        created_at=asset.created_at,
    )


async def _find_voice_clone_asset(db: AsyncSession, user_id: str, voice_id: str) -> Optional[Asset]:
    result = await db.execute(
        select(Asset)
        .where(
            Asset.user_id == user_id,
            Asset.category == "voice",
            Asset.asset_type == "audio",
            Asset.is_active == True,
        )
        .order_by(desc(Asset.created_at))
    )
    for asset in result.scalars().all():
        params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
        if (params.get("voice_id") or f"clone-{asset.id[:8]}") == voice_id:
            return asset
    return None


def _clone_tts_model_override(params: Optional[Dict[str, Any]]) -> Optional[str]:
    if params and params.get("clone_status") == "provider_ready":
        return params.get("provider_tts_model") or MINIMAX_VOICE_CLONE_MODEL
    return None


async def _ensure_minimax_voice_clone_ready(db: AsyncSession, user_id: str, voice_id: str) -> Optional[Dict[str, Any]]:
    asset = await _find_voice_clone_asset(db, user_id, voice_id)
    if not asset:
        return None

    params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
    clone_status = params.get("clone_status") or "ready"
    if clone_status in {"ready", "provider_ready"}:
        return params

    provider_error = params.get("provider_error")
    detail = f"MiniMax 克隆音色 {voice_id} 云端克隆未就绪，当前状态：{clone_status}"
    if provider_error:
        detail = f"{detail}；服务商错误：{provider_error}"
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


async def _resolve_preview_tts_config(
    db: AsyncSession,
    user_id: str,
    *,
    provider: str,
    model_config_id: Optional[str],
    model_id: Optional[str],
) -> tuple[Optional[str], str, Optional[str], Optional[str]]:
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    api_model_id = model_id
    resolved_provider = provider

    if model_config_id:
        config_result = await db.execute(
            select(LLMConfig, LLMModel, LLMProvider)
            .join(LLMModel, LLMConfig.model_id == LLMModel.id)
            .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
            .where(
                and_(
                    LLMConfig.id == model_config_id,
                    LLMConfig.user_id == user_id,
                    LLMConfig.is_active == True,
                    LLMModel.is_active == True,
                    LLMModel.model_type.in_(["tts", "audio", "speech"]),
                )
            )
        )
        row = config_result.first()
        if not row:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="所选 TTS 模型配置不可用")
        config, model, provider_row = row
        resolved_provider = provider_row.name or provider_row.id
        api_key = config.get_api_key_decrypted()
        extra = config.extra_params if isinstance(config.extra_params, dict) else {}
        base_url = configure_volcano_speech_endpoint(extra.get("base_url") or model.base_url or provider_row.base_url, extra)
        api_model_id = api_model_id or model.model_id
    else:
        if resolved_provider in {"minimax", "volcano"}:
            api_key, base_url = await get_user_api_key(db, user_id, resolved_provider, raise_if_missing=False)

    return api_key, resolved_provider, api_model_id, base_url


async def _save_voice_clone_upload(sample_audio: UploadFile, voice_id: str) -> str:
    filename = sample_audio.filename or "sample.wav"
    ext = Path(filename).suffix.lower()
    if ext not in {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".webm"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="仅支持 wav/mp3/m4a/aac/ogg/webm 音频样本")
    VOICE_CLONE_DIR.mkdir(parents=True, exist_ok=True)
    target = (VOICE_CLONE_DIR / f"{voice_id}{ext}").resolve()
    suffix = 1
    while target.exists():
        target = (VOICE_CLONE_DIR / f"{voice_id}-{suffix}{ext}").resolve()
        suffix += 1
    static_relative_path = target.relative_to(STATIC_ROOT.resolve()).as_posix()
    data = await sample_audio.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="声音样本不能为空")
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="声音样本不能超过 30MB")
    target.write_bytes(data)
    return f"/static/{static_relative_path}"


def _resolve_static_media_path(media_url: Optional[str]) -> Optional[str]:
    if not media_url or not media_url.startswith("/static/"):
        return None
    try:
        media_path = (STATIC_ROOT / media_url.removeprefix("/static/")).resolve()
        media_path.relative_to(STATIC_ROOT.resolve())
    except ValueError:
        return None
    if not media_path.exists() or not media_path.is_file():
        return None
    return str(media_path)


async def _activate_minimax_voice_clone(
    asset: Asset,
    db: AsyncSession,
    user_id: str,
    *,
    model_config_id: Optional[str] = None,
    preview_text: Optional[str] = None,
) -> None:
    params = dict(asset.generation_params) if isinstance(asset.generation_params, dict) else {}
    provider = params.get("provider") or "custom"
    if provider != "minimax":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="仅 MiniMax 声音克隆支持云端激活")
    voice_id = (params.get("voice_id") or "").strip()
    if not voice_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="声音资产缺少 voice_id")
    audio_path = _resolve_static_media_path(asset.url)
    if not audio_path:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="MiniMax 云端克隆需要本地上传的声音样本，请重新上传音频文件。",
        )

    api_key, _, model_id, base_url = await _resolve_preview_tts_config(
        db,
        user_id,
        provider="minimax",
        model_config_id=model_config_id,
        model_id=None,
    )
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="未配置 MiniMax 语音模型 API Key，无法执行云端声音克隆",
        )

    from app.services.minimax_service import MiniMaxService

    service = MiniMaxService(api_key, base_url)
    upload_result = await service.upload_voice_clone_audio(audio_path)
    file_id = str(upload_result.get("file_id") or "")
    if not file_id:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="MiniMax 声音样本上传未返回 file_id")
    clone_result = await service.clone_voice(
        file_id=file_id,
        voice_id=voice_id,
        text=(preview_text or f"这是 {asset.name} 的声音克隆试听。")[:200],
        model=MINIMAX_VOICE_CLONE_MODEL,
    )

    params.update({
        "clone_status": "provider_ready",
        "provider_file_id": file_id,
        "provider_tts_model": MINIMAX_VOICE_CLONE_MODEL,
        "provider_demo_audio_url": clone_result.get("demo_audio"),
        "provider_extra_info": clone_result.get("extra_info"),
        "provider_error": None,
        "cloud_activated_at": utc_now().isoformat(),
    })
    asset.generation_params = params


# ============== API 端点 ==============

@router.post("/generate", response_model=TTSJobResponse)
async def generate_tts(
    request: TTSGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    创建并执行 TTS 任务。

    支持多角色对话：文本中每行 "角色名: 对话内容" 会被解析为独立语音段，
    为每个角色单独调用 TTS API，保持音色一致性。
    """
    job_id = str(uuid4())
    if not request.text_content and request.text:
        request.text_content = request.text
    if request.voice and not request.voice_model:
        request.voice_model = request.voice
    request.api_provider = request.api_provider or ("volcano" if request.api_key else "minimax")

    # 解析对话，判断是否多角色
    segments = parse_dialogue(request.text_content or "")
    is_multi = is_multi_character(segments)

    # 如果指定了 shot_id，自动从镜头获取对话和角色信息
    if request.shot_id:
        shot_result = await db.execute(
            select(Shot).where(Shot.id == request.shot_id, Shot.user_id == user_id)
        )
        shot = shot_result.scalar_one_or_none()
        if not shot:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="镜头不存在")
        if not request.text_content and shot.dialogue:
            request.text_content = shot.dialogue
            segments = parse_dialogue(shot.dialogue)
            is_multi = is_multi_character(segments)
        if not request.storyboard_id and shot.storyboard_id:
            request.storyboard_id = shot.storyboard_id
        if not request.script_id and shot.storyboard_id:
            from app.models import Storyboard

            storyboard_result = await db.execute(
                select(Storyboard).where(Storyboard.id == shot.storyboard_id, Storyboard.user_id == user_id)
            )
            storyboard = storyboard_result.scalar_one_or_none()
            if storyboard:
                request.script_id = storyboard.script_id
                request.novel_id = request.novel_id or getattr(storyboard, "novel_id", None)
                storyboard_content = storyboard.content if isinstance(storyboard.content, dict) else {}
                request.chapter_id = request.chapter_id or storyboard_content.get("chapter_id")
                if request.script_id and (not request.novel_id or not request.chapter_id):
                    from app.models import Script

                    script_result = await db.execute(
                        select(Script).where(Script.id == request.script_id, Script.user_id == user_id)
                    )
                    script = script_result.scalar_one_or_none()
                    if script:
                        request.novel_id = request.novel_id or getattr(script, "novel_id", None)
                        script_extra = script.extra_data if isinstance(script.extra_data, dict) else {}
                        request.chapter_id = request.chapter_id or script_extra.get("chapter_id")

    if not request.text_content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="text_content 不能为空")

    if not is_dev_mode() and not request.use_consistency_context and not request.unsafe_skip_consistency_preflight:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="生产模式不能跳过一致性预检；如需降级调试，请显式开启 unsafe_skip_consistency_preflight 并记录原因。",
        )
    preflight_package = None
    if not is_dev_mode() and not request.unsafe_skip_consistency_preflight:
        preflight_package = await build_generation_context_package(
            db,
            user_id,
            task_type="tts_dialogue",
            model_config_id=request.model_config_id,
            production_mode=True,
            novel_id=request.novel_id,
            chapter_id=request.chapter_id,
            script_id=request.script_id,
            storyboard_id=request.storyboard_id,
            shot_id=request.shot_id,
        )
        if not preflight_package.get("ready"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=preflight_failure_detail(preflight_package),
            )

    consistency_metadata = {}
    if request.use_consistency_context:
        context = await build_consistency_prompt(
            db,
            user_id,
            task="tts_dialogue",
            base_prompt=request.text_content,
            story_bible_id=request.story_bible_id,
            project_id=request.project_id,
            novel_id=request.novel_id,
            shot_id=request.shot_id,
            character_ids=request.character_ids,
            fallback_character_id=request.character_id,
            extra_context={"音色": request.voice_model, "语速": request.speed},
        )
        consistency_metadata = context["metadata"]

    # 如果指定了 character_id，自动获取角色音色
    voice_to_use = request.voice_model
    speed_to_use = request.speed
    voice_source = "request"
    voice_character_name = None
    if request.character_id:
        char_result = await db.execute(
            select(Character).where(
                Character.id == request.character_id,
                Character.user_id == user_id
            )
        )
        char = char_result.scalar_one_or_none()
        if char and char.voice:
            voice_to_use = char.voice
            voice_source = "character"
            voice_character_name = char.name

    # 如果有 story_bible_id，尝试从 Story Bible 获取音色配置
    if request.story_bible_id and request.use_story_bible_voice:
        from app.services.voice_service import get_character_voice_from_story_bible
        # 尝试从对话中提取角色名
        character_name = extract_character_from_text(request.text_content or "")
        if character_name:
            voice_character_name = character_name
            voice_config = await get_character_voice_from_story_bible(
                db, character_name, request.story_bible_id
            )
            if voice_config and voice_config.get("voice"):
                voice_to_use = voice_config.get("voice", voice_to_use)
                speed_to_use = voice_config.get("voice_speed", speed_to_use)
                voice_source = "story_bible"

    # 获取用户 API Key
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    tts_model_id: Optional[str] = request.model_id
    selected_model_config_id: Optional[str] = request.model_config_id
    if request.api_key is not None:
        if not request.api_key.strip():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="api_key 不能为空")
        api_key = request.api_key
        base_url = None
    elif request.model_config_id:
        config_result = await db.execute(
            select(LLMConfig, LLMModel, LLMProvider)
            .join(LLMModel, LLMConfig.model_id == LLMModel.id)
            .join(LLMProvider, LLMModel.provider_id == LLMProvider.id)
            .where(
                and_(
                    LLMConfig.id == request.model_config_id,
                    LLMConfig.user_id == user_id,
                    LLMConfig.is_active == True,
                    LLMModel.is_active == True,
                    LLMModel.model_type.in_(["tts", "audio", "speech"]),
                )
            )
        )
        row = config_result.first()
        if not row:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="所选 TTS 模型配置不可用，请重新选择已保存的语音模型配置")
        config, model, provider = row
        request.api_provider = provider.name or provider.id
        api_key = config.get_api_key_decrypted()
        extra = config.extra_params if isinstance(config.extra_params, dict) else {}
        base_url = configure_volcano_speech_endpoint(extra.get("base_url") or model.base_url or provider.base_url, extra)
        tts_model_id = tts_model_id or model.model_id
    elif request.api_provider == "minimax":
        api_key, base_url = await get_user_api_key(
            db, user_id, "minimax", raise_if_missing=False
        )
    elif request.api_provider == "volcano":
        api_key, base_url = await get_user_api_key(
            db, user_id, "volcano", raise_if_missing=False
        )

    use_dev_generation = not api_key and is_dev_mode()
    if not api_key and not use_dev_generation:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"未配置 {request.api_provider} 语音模型 API Key，请在大模型配置页面配置并验证 TTS 模型"
        )

    # 创建 TTSJob 记录
    job = TTSJob(
        id=job_id,
        user_id=user_id,
        project_id=request.project_id,
        workflow_id=request.workflow_id,
        title=request.title or f"TTS任务_{job_id[:8]}",
        text=request.text_content or "",
        voice=voice_to_use,
        speed=speed_to_use,
        api_provider=request.api_provider,
        novel_id=request.novel_id,
        chapter_id=request.chapter_id,
        script_id=request.script_id,
        storyboard_id=request.storyboard_id,
        shot_id=request.shot_id,
        character_id=request.character_id,
        status="generating",
        progress=0
    )
    db.add(job)
    if request.workflow_id:
        from app.models import Workflow

        workflow_result = await db.execute(
            select(Workflow).where(Workflow.id == request.workflow_id, Workflow.user_id == user_id)
        )
        workflow = workflow_result.scalar_one_or_none()
        if workflow:
            workflow.tts_job_ids = list(dict.fromkeys((workflow.tts_job_ids or []) + [job.id]))
    await db.flush()  # 获取 job.id
    initial_extra = {
        "model_config_id": selected_model_config_id,
        "api_model_id": tts_model_id,
        "provider_id": request.api_provider,
        "voice_source": voice_source,
        "voice_character_name": voice_character_name,
        "story_bible_id": request.story_bible_id,
    }
    initial_preflight = _preflight_summary(preflight_package)
    if initial_preflight is not None:
        initial_extra["generation_preflight"] = initial_preflight
    job.extra_data = initial_extra

    all_segments = []
    all_audio_urls = []
    total_duration = 0.0

    try:
        if use_dev_generation:
            segment_rows = []
            for seg in (segments or [{"character": voice_character_name or "", "text": request.text_content or ""}]):
                resolved_segment = await resolve_tts_segment_voice(
                    db,
                    user_id,
                    character_name=seg.get("character") or voice_character_name,
                    default_voice=voice_to_use,
                    default_speed=speed_to_use,
                    story_bible_id=request.story_bible_id,
                    use_story_bible_voice=request.use_story_bible_voice,
                    novel_id=request.novel_id,
                    chapter_id=request.chapter_id,
                )
                segment_rows.append({
                    "character": seg.get("character", ""),
                    "text": seg.get("text", ""),
                    "voice": resolved_segment["voice"],
                    "voice_source": resolved_segment["voice_source"],
                    "speed": resolved_segment["speed"],
                    "audio_url": dev_tts_audio_url(f"{job.id}-{len(segment_rows)}"),
                    "duration": estimate_tts_duration_seconds(seg.get("text", ""), resolved_segment["speed"]),
                })
            if segment_rows:
                job.voice = segment_rows[0]["voice"]
                job.speed = segment_rows[0]["speed"]
            job.task_id = f"dev-tts-{job.id}"
            job.audio_url = dev_tts_audio_url(job.id)
            job.duration_seconds = sum(float(seg.get("duration") or 0.0) for seg in segment_rows) or estimate_tts_duration_seconds(request.text_content or "", speed_to_use)
            job.extra_data = {
                "segments": segment_rows,
                "dev_mode": True,
                "consistency": consistency_metadata,
                "model_config_id": selected_model_config_id,
                "api_model_id": tts_model_id,
                "voice_source": segment_rows[0]["voice_source"] if segment_rows else voice_source,
                "voice_character_name": segment_rows[0]["character"] if segment_rows else voice_character_name,
                "story_bible_id": request.story_bible_id,
            }
            total_duration = job.duration_seconds or 0.0
            all_audio_urls.append(job.audio_url)
            job.progress = 100
            job.status = "succeeded"

        elif request.api_provider == "minimax":
            from app.services.minimax_service import MiniMaxService
            svc = MiniMaxService(api_key, base_url)

            if is_multi and len(segments) > 1:
                # 多角色：为每个角色单独生成
                for i, seg in enumerate(segments):
                    resolved_segment = await resolve_tts_segment_voice(
                        db,
                        user_id,
                        character_name=seg.get("character") or voice_character_name,
                        default_voice=voice_to_use,
                        default_speed=speed_to_use,
                        story_bible_id=request.story_bible_id,
                        use_story_bible_voice=request.use_story_bible_voice,
                        novel_id=request.novel_id,
                        chapter_id=request.chapter_id,
                    )
                    seg_voice = resolved_segment["voice"]
                    seg_speed = resolved_segment["speed"]
                    voice_clone_params = await _ensure_minimax_voice_clone_ready(db, user_id, seg_voice)
                    seg_model_id = _clone_tts_model_override(voice_clone_params) or tts_model_id or "speech-2.6-hd"

                    try:
                        result = await svc.text_to_speech(
                            text=seg['text'],
                            model=seg_model_id,
                            voice_id=seg_voice,
                            speed=seg_speed
                        )
                        seg_audio_url = result.get('audio_url')
                        seg_duration = result.get('duration', 0.0)
                        all_segments.append({
                            'character': seg['character'],
                            'text': seg['text'],
                            'voice': seg_voice,
                            'voice_source': resolved_segment["voice_source"],
                            'speed': seg_speed,
                            'audio_url': seg_audio_url,
                            'duration': seg_duration,
                        })
                        if seg_audio_url:
                            all_audio_urls.append(seg_audio_url)
                        total_duration += seg_duration or 0.0
                    except Exception as e:
                        all_segments.append({
                            'character': seg['character'],
                            'text': seg['text'],
                            'voice': seg_voice,
                            'voice_source': resolved_segment["voice_source"],
                            'speed': seg_speed,
                            'audio_url': None,
                            'duration': 0.0,
                            'error': str(e),
                        })

                if all_segments:
                    job.voice = all_segments[0].get("voice", job.voice)
                    job.speed = all_segments[0].get("speed", job.speed)
                job.extra_data = {
                    'segments': all_segments,
                    "consistency": consistency_metadata,
                    "voice_source": all_segments[0].get("voice_source") if all_segments else voice_source,
                    "voice_character_name": all_segments[0].get("character") if all_segments else voice_character_name,
                    "story_bible_id": request.story_bible_id,
                }
                job.progress = 100
                job.status = "succeeded"
            else:
                # 单角色：整段生成
                try:
                    voice_clone_params = await _ensure_minimax_voice_clone_ready(db, user_id, voice_to_use)
                    effective_tts_model_id = _clone_tts_model_override(voice_clone_params) or tts_model_id or "speech-2.6-hd"
                    result = await svc.text_to_speech(
                        text=request.text_content,
                        model=effective_tts_model_id,
                        voice_id=voice_to_use,
                        speed=speed_to_use
                    )
                    job.audio_url = result.get('audio_url')
                    job.task_id = result.get('task_id')
                    job.duration_seconds = result.get('duration', 0.0)
                    total_duration = job.duration_seconds or 0.0
                    if job.audio_url:
                        all_audio_urls.append(job.audio_url)
                except Exception as e:
                    job.status = "failed"
                    job.error_message = str(e)
                    job.progress = 100
                    await db.commit()
                    raise

                job.progress = 100
                job.status = "succeeded"

        elif request.api_provider == "volcano":
            from app.services.volcano_service import VolcanoService
            svc = VolcanoService(api_key, base_url)

            if is_multi and len(segments) > 1:
                for seg in segments:
                    resolved_segment = await resolve_tts_segment_voice(
                        db,
                        user_id,
                        character_name=seg.get("character") or voice_character_name,
                        default_voice=voice_to_use,
                        default_speed=speed_to_use,
                        story_bible_id=request.story_bible_id,
                        use_story_bible_voice=request.use_story_bible_voice,
                        novel_id=request.novel_id,
                        chapter_id=request.chapter_id,
                    )
                    seg_voice = resolved_segment["voice"]
                    seg_speed = resolved_segment["speed"]
                    try:
                        result = await svc.text_to_speech(
                            text=seg['text'],
                            model=tts_model_id or "doubao-tts",
                            voice=seg_voice,
                            speed=seg_speed
                        )
                        seg_audio_url = result.get('audio_url')
                        seg_duration = result.get('duration', 0.0)
                        all_segments.append({
                            'character': seg['character'],
                            'text': seg['text'],
                            'voice': seg_voice,
                            'voice_source': resolved_segment["voice_source"],
                            'speed': seg_speed,
                            'audio_url': seg_audio_url,
                            'duration': seg_duration,
                        })
                        if seg_audio_url:
                            all_audio_urls.append(seg_audio_url)
                        total_duration += seg_duration or 0.0
                    except Exception as e:
                        all_segments.append({
                            'character': seg['character'],
                            'text': seg['text'],
                            'voice': seg_voice,
                            'voice_source': resolved_segment["voice_source"],
                            'speed': seg_speed,
                            'audio_url': None,
                            'duration': 0.0,
                            'error': str(e),
                        })
                if all_segments:
                    job.voice = all_segments[0].get("voice", job.voice)
                    job.speed = all_segments[0].get("speed", job.speed)
                job.extra_data = {
                    'segments': all_segments,
                    "consistency": consistency_metadata,
                    "voice_source": all_segments[0].get("voice_source") if all_segments else voice_source,
                    "voice_character_name": all_segments[0].get("character") if all_segments else voice_character_name,
                    "story_bible_id": request.story_bible_id,
                }
                job.progress = 100
                job.status = "succeeded"
            else:
                result = await svc.text_to_speech(
                    text=request.text_content,
                    model=tts_model_id or "doubao-tts",
                    voice=voice_to_use,
                    speed=speed_to_use
                )
                job.audio_url = result.get('audio_url')
                job.task_id = result.get('task_id')
                job.duration_seconds = result.get('duration', 0.0)
                total_duration = job.duration_seconds or 0.0
                if job.audio_url:
                    all_audio_urls.append(job.audio_url)
                job.progress = 100
                job.status = "succeeded"

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的 TTS 提供商: {request.api_provider}"
            )

    except HTTPException:
        raise
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        job.progress = 100
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS 生成失败: {str(e)}"
        )

    if not job.audio_url and all_audio_urls:
        job.audio_url = all_audio_urls[0]
    job.duration_seconds = total_duration if total_duration > 0 else None

    if request.shot_id:
        shot_result = await db.execute(
            select(Shot).where(Shot.id == request.shot_id, Shot.user_id == user_id)
        )
        shot = shot_result.scalar_one_or_none()
        if shot:
            shot.audio_url = job.audio_url
            shot.audio_status = "succeeded" if job.audio_url else job.status
    extra = dict(job.extra_data) if isinstance(job.extra_data, dict) else {}
    preflight_summary = _preflight_summary(preflight_package)
    if preflight_summary is not None:
        extra["generation_preflight"] = preflight_summary
    extra.update({
        "model_config_id": selected_model_config_id,
        "api_model_id": tts_model_id,
        "provider_id": request.api_provider,
        "voice_source": extra.get("voice_source") or voice_source,
        "voice_character_name": extra.get("voice_character_name") or voice_character_name,
        "story_bible_id": extra.get("story_bible_id") or request.story_bible_id,
    })
    job.extra_data = extra
    await db.commit()
    await db.refresh(job)

    return build_tts_response(job)


@router.post("/preview", response_model=TTSPreviewResponse)
async def preview_tts_voice(
    request: TTSPreviewRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """生成一段短音频用于试听当前音色，不写入 TTS 历史。"""
    text = (request.text or "").strip() or "这是一段音色试听。"
    text = text[:120]
    api_key, provider, model_id, base_url = await _resolve_preview_tts_config(
        db,
        user_id,
        provider=request.api_provider,
        model_config_id=request.model_config_id,
        model_id=request.model_id,
    )

    if not api_key and is_dev_mode():
        audio_url = dev_tts_audio_url(f"preview-{user_id}-{request.voice_model}-{request.speed}")
        return TTSPreviewResponse(
            status="succeeded",
            audio_url=audio_url,
            voice=request.voice_model,
            provider=provider,
            duration_seconds=estimate_tts_duration_seconds(text, request.speed),
            message="DEV_MODE 本地试听音频已生成，未调用云端 TTS 模型",
        )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"未配置 {provider} 语音模型 API Key，请在大模型配置页面配置并验证 TTS 模型",
        )

    try:
        if provider == "minimax":
            from app.services.minimax_service import MiniMaxService

            voice_clone_params = await _ensure_minimax_voice_clone_ready(db, user_id, request.voice_model)
            effective_model_id = _clone_tts_model_override(voice_clone_params) or model_id or "speech-2.6-hd"
            result = await MiniMaxService(api_key, base_url).text_to_speech(
                text=text,
                model=effective_model_id,
                voice_id=request.voice_model,
                speed=request.speed,
                output_dir="audio/previews",
            )
        elif provider == "volcano":
            from app.services.volcano_service import VolcanoService

            result = await VolcanoService(api_key, base_url).text_to_speech(
                text=text,
                model=model_id or "doubao-tts",
                voice=request.voice_model,
                speed=request.speed,
                output_dir="audio/previews",
            )
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的 TTS 提供商: {provider}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"音色试听失败: {str(exc)}")

    audio_url = result.get("audio_url")
    if not audio_url:
        if is_dev_mode():
            audio_url = dev_tts_audio_url(f"preview-{user_id}-{request.voice_model}-{request.speed}")
            return TTSPreviewResponse(
                status="succeeded",
                audio_url=audio_url,
                voice=request.voice_model,
                provider=provider,
                duration_seconds=estimate_tts_duration_seconds(text, request.speed),
                message="云端试听未返回音频，已使用 DEV_MODE 本地试听音频；请检查模型权限、模型ID或音色ID。",
            )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="音色试听失败：模型未返回音频地址")
    return TTSPreviewResponse(
        status=result.get("status") or "succeeded",
        audio_url=audio_url,
        voice=result.get("voice") or request.voice_model,
        provider=provider,
        duration_seconds=result.get("duration"),
        message=result.get("message") or "音色试听已生成",
    )


@router.post("/voice-clones", response_model=VoiceCloneResponse, status_code=status.HTTP_201_CREATED)
async def create_voice_clone_profile(
    name: str = Form(...),
    provider: str = Form("minimax"),
    voice_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    sample_audio_url: Optional[str] = Form(None),
    sample_source: Optional[str] = Form(None),
    model_config_id: Optional[str] = Form(None),
    activate_cloud: bool = Form(True),
    preview_text: Optional[str] = Form(None),
    character_id: Optional[str] = Form(None),
    novel_id: Optional[str] = Form(None),
    sample_audio: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """创建可复用的克隆音色配置。

    当前平台会持久化声音样本和克隆音色ID；如果服务商已创建云端克隆音色，
    可直接把该 voice_id 作为样本 URL/描述对应的配置使用。
    """
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="音色名称不能为空")
    clean_voice_id = (voice_id or "").strip() or None
    if clean_voice_id and not VOICE_ID_PATTERN.match(clean_voice_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="voice_id 仅支持字母、数字、点、下划线、冒号和短横线，最长 128 位",
        )

    if character_id:
        char_result = await db.execute(
            select(Character).where(Character.id == character_id, Character.user_id == user_id)
        )
        if not char_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")

    if clean_voice_id:
        existing_result = await db.execute(
            select(Asset).where(
                Asset.user_id == user_id,
                Asset.category == "voice",
                Asset.asset_type == "audio",
                Asset.is_active == True,
            )
        )
        for existing in existing_result.scalars().all():
            params = existing.generation_params if isinstance(existing.generation_params, dict) else {}
            if params.get("voice_id") == clean_voice_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"voice_id 已存在: {clean_voice_id}",
                )

    asset_id = str(uuid4())
    resolved_voice_id = clean_voice_id or f"clone-{asset_id[:8]}"
    stored_sample_url = (sample_audio_url or "").strip() or None
    clone_source = (sample_source or "").strip() or ("url" if stored_sample_url else "upload")
    if sample_audio:
        stored_sample_url = await _save_voice_clone_upload(sample_audio, resolved_voice_id)
        clone_source = "recording" if clone_source == "recording" else "upload"
    if not stored_sample_url:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="请上传声音样本或填写样本音频 URL")
    clone_status = "sample_uploaded" if clone_source in {"upload", "recording"} else "provider_pending"

    asset = Asset(
        id=asset_id,
        user_id=user_id,
        category="voice",
        name=clean_name,
        description=description,
        asset_type="audio",
        url=stored_sample_url,
        character_id=character_id,
        novel_id=novel_id,
        tags=["voice_clone", provider],
        style_tags=["custom_voice"],
        is_public=False,
        generation_params={
            "voice_id": resolved_voice_id,
            "provider": provider,
            "clone_status": clone_status,
            "sample_audio_url": stored_sample_url,
            "sample_source": clone_source,
            "note": "本地已登记克隆音色；云端克隆训练需在对应服务商完成或由生产适配器接入。",
        },
    )
    db.add(asset)
    await db.flush()
    if provider == "minimax" and sample_audio and activate_cloud:
        try:
            await _activate_minimax_voice_clone(
                asset,
                db,
                user_id,
                model_config_id=model_config_id,
                preview_text=preview_text,
            )
        except HTTPException as exc:
            params = dict(asset.generation_params) if isinstance(asset.generation_params, dict) else {}
            params.update({
                "clone_status": "provider_failed",
                "provider_error": exc.detail,
            })
            asset.generation_params = params
        except Exception as exc:
            params = dict(asset.generation_params) if isinstance(asset.generation_params, dict) else {}
            params.update({
                "clone_status": "provider_failed",
                "provider_error": str(exc),
            })
            asset.generation_params = params
    await db.commit()
    await db.refresh(asset)
    return _voice_clone_response(asset)


@router.post("/voice-clones/{asset_id}/activate", response_model=VoiceCloneResponse)
async def activate_voice_clone_profile(
    asset_id: str,
    model_config_id: Optional[str] = Form(None),
    preview_text: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Upload an existing local MiniMax voice sample and create the cloud voice_id."""
    result = await db.execute(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.user_id == user_id,
            Asset.category == "voice",
            Asset.asset_type == "audio",
            Asset.is_active == True,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="声音资产不存在")

    try:
        await _activate_minimax_voice_clone(
            asset,
            db,
            user_id,
            model_config_id=model_config_id,
            preview_text=preview_text,
        )
    except HTTPException:
        raise
    except Exception as exc:
        params = dict(asset.generation_params) if isinstance(asset.generation_params, dict) else {}
        params.update({
            "clone_status": "provider_failed",
            "provider_error": str(exc),
        })
        asset.generation_params = params
        await db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"MiniMax 云端声音克隆失败: {str(exc)}")

    await db.commit()
    await db.refresh(asset)
    return _voice_clone_response(asset)


@router.get("/jobs", response_model=List[TTSJobResponse])
async def list_tts_jobs(
    limit: int = 50,
    status_filter: Optional[str] = None,
    project_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    novel_id: Optional[str] = None,
    shot_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取用户的TTS任务列表"""
    query = select(TTSJob).where(TTSJob.user_id == user_id, TTSJob.is_active == True)

    if status_filter:
        query = query.where(TTSJob.status == status_filter)
    if project_id:
        query = query.where(TTSJob.project_id == project_id)
    if workflow_id:
        query = query.where(TTSJob.workflow_id == workflow_id)
    if novel_id:
        query = query.where(TTSJob.novel_id == novel_id)
    if shot_id:
        query = query.where(TTSJob.shot_id == shot_id)

    query = query.order_by(desc(TTSJob.created_at)).limit(limit)

    result = await db.execute(query)
    jobs = result.scalars().all()

    # 序列化 extra_data
    resp_jobs = []
    for job in jobs:
        resp_jobs.append(build_tts_response(job))
    return resp_jobs


@router.get("/jobs/{job_id}", response_model=TTSJobResponse)
async def get_tts_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取TTS任务详情"""
    query = select(TTSJob).where(
        TTSJob.id == job_id,
        TTSJob.user_id == user_id
    )

    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    return build_tts_response(job)


@router.put("/jobs/{job_id}", response_model=TTSJobResponse)
async def update_tts_job(
    job_id: str,
    status_update: Optional[str] = None,
    progress: Optional[int] = None,
    audio_url: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    error_message: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """更新TTS任务状态"""
    query = select(TTSJob).where(
        TTSJob.id == job_id,
        TTSJob.user_id == user_id
    )

    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    if status_update:
        job.status = status_update
    if progress is not None:
        job.progress = progress
    if audio_url:
        job.audio_url = audio_url
    if duration_seconds is not None:
        job.duration_seconds = duration_seconds
    if error_message:
        job.error_message = error_message

    await db.commit()
    await db.refresh(job)

    return build_tts_response(job)


@router.delete("/jobs/{job_id}")
async def delete_tts_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """删除TTS任务（软删除）"""
    query = select(TTSJob).where(
        TTSJob.id == job_id,
        TTSJob.user_id == user_id
    )

    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    job.is_active = False
    await db.commit()

    return {"message": "删除成功"}


@router.get("/voices")
async def list_available_voices(
    provider: str = "minimax",
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """获取可用的语音音色列表"""
    voices: list[dict] = []
    if provider == "minimax":
        try:
            from app.core.minimax_config import TTS_VOICES

            voices = [_normalize_builtin_voice(item, "minimax") for item in TTS_VOICES]
        except ImportError:
            pass
    elif provider == "volcano":
        voices = [
            _normalize_builtin_voice({"voice_id": "female_nvsheng", "name": "女声（nvsheng）", "gender": "female", "lang": "中文"}, "volcano"),
            _normalize_builtin_voice({"voice_id": "female_tianmei", "name": "甜美女声", "gender": "female", "lang": "中文"}, "volcano"),
            _normalize_builtin_voice({"voice_id": "male_jiaqi", "name": "男声嘉琪", "gender": "male", "lang": "中文"}, "volcano"),
            _normalize_builtin_voice({"voice_id": "male_zhichang", "name": "职场男声", "gender": "male", "lang": "中文"}, "volcano"),
            _normalize_builtin_voice({"voice_id": "male_dashu", "name": "大树（旁白）", "gender": "male", "lang": "中文"}, "volcano"),
        ]

    clone_result = await db.execute(
        select(Asset)
        .where(
            Asset.user_id == user_id,
            Asset.category == "voice",
            Asset.asset_type == "audio",
            Asset.is_active == True,
        )
        .order_by(desc(Asset.created_at))
    )
    for asset in clone_result.scalars().all():
        params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
        asset_provider = params.get("provider") or "custom"
        if provider and asset_provider not in {provider, "custom"}:
            continue
        voice_id = params.get("voice_id") or f"clone-{asset.id[:8]}"
        clone_status = params.get("clone_status") or "ready"
        voices.append({
            "voice_id": voice_id,
            "id": voice_id,
            "name": asset.name,
            "label": asset.name,
            "gender": "custom",
            "lang": "自定义",
            "provider": asset_provider,
            "is_custom": True,
            "sample_audio_url": asset.url,
            "sample_source": params.get("sample_source") or params.get("clone_source"),
            "character_id": asset.character_id,
            "novel_id": asset.novel_id,
            "status": clone_status,
            "provider_ready": clone_status == "provider_ready",
            "provider_file_id": params.get("provider_file_id"),
            "provider_tts_model": _clone_tts_model_override(params),
            "provider_demo_audio_url": params.get("provider_demo_audio_url"),
            "provider_error": params.get("provider_error"),
            "description": asset.description,
        })

    return {"provider": provider, "voices": voices}
