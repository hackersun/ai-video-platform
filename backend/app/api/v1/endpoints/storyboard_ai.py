"""
分镜AI辅助生成API
支持台词、视觉描述、镜头建议的AI生成
"""

import json
import re
from typing import Literal, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select
from pydantic import BaseModel, Field

from app.core.api_key_utils import get_user_text_generation_service
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Chapter, Script, Shot, Storyboard
from app.api.v1.endpoints.storyboards import extract_dialogue_speaker, strip_dialogue_speaker
from app.services.storyboard_template_service import plan_storyboard_shot_count

router = APIRouter(tags=["分镜AI生成"])


class GenerateDialogueRequest(BaseModel):
    """台词生成请求"""
    scene_description: str = Field(..., description="场景描述")
    chapter_content: Optional[str] = Field(None, description="章节内容（提供更多上下文）")
    script_content: Optional[str] = Field(None, description="剧本内容（优先用于提炼台词）")
    current_dialogue: Optional[str] = Field(None, description="当前已有台词")
    speaker_name: Optional[str] = Field(None, description="指定或已识别的说话人")
    dialogue_mode: Literal["extract", "polish", "rewrite", "suggest"] = Field("extract", description="台词处理方式")
    characters: Optional[List[dict]] = Field(None, description="角色列表")
    style: str = Field("anime", description="风格：anime, realistic, etc.")
    novel_id: Optional[str] = Field(None, description="关联小说ID")
    chapter_id: Optional[str] = Field(None, description="关联章节ID")
    script_id: Optional[str] = Field(None, description="关联剧本ID")
    storyboard_id: Optional[str] = Field(None, description="关联分镜ID")
    shot_id: Optional[str] = Field(None, description="关联的镜头ID")


class GenerateDialogueResponse(BaseModel):
    """台词生成响应"""
    dialogue: str
    visual_description: str
    camera_suggestion: str
    duration: int
    speaker_name: Optional[str] = None
    spoken_text: Optional[str] = None
    dialogue_source: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


def compact_text(text: Optional[str], limit: int = 1600) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def extract_json_object(content: str) -> dict:
    text = (content or "").strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]

    try:
        parsed = json.loads(text.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        parsed = json.loads(match.group(0))

    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("AI response is not a JSON object", text, 0)
    return parsed


def character_names(characters: Optional[List[dict]]) -> list[str]:
    names: list[str] = []
    for character in characters or []:
        if not isinstance(character, dict):
            continue
        for key in ("name", "character_name", "entity_name"):
            value = character.get(key)
            if isinstance(value, str) and value.strip():
                names.append(value.strip())
        for alias in character.get("aliases") or []:
            if isinstance(alias, str) and alias.strip():
                names.append(alias.strip())
    return list(dict.fromkeys(names))


def format_dialogue(speaker: Optional[str], spoken_text: str, fallback_dialogue: str = "") -> str:
    spoken = strip_dialogue_speaker(spoken_text or fallback_dialogue)
    if not spoken:
        return (fallback_dialogue or "").strip()
    if speaker:
        if speaker in {"旁白", "画外音", "解说", "系统"}:
            return f"（旁白）{spoken}"
        return f"{speaker}：{spoken}"
    return spoken


def normalize_dialogue_payload(
    payload: dict,
    request: GenerateDialogueRequest,
    characters: Optional[List[dict]] = None,
) -> GenerateDialogueResponse:
    warnings = [str(item).strip() for item in payload.get("warnings", []) if str(item).strip()] if isinstance(payload.get("warnings"), list) else []
    dialogue = str(payload.get("dialogue") or request.current_dialogue or "").strip()
    speaker = (
        str(payload.get("speaker_name") or "").strip()
        or str(payload.get("dialogue_speaker") or "").strip()
        or (request.speaker_name or "").strip()
        or extract_dialogue_speaker(dialogue)
        or extract_dialogue_speaker(request.current_dialogue)
    )
    spoken_text = str(payload.get("spoken_text") or "").strip() or strip_dialogue_speaker(dialogue)
    known_names = character_names(characters)

    if not speaker and len(known_names) == 1:
        speaker = known_names[0]
        warnings.append("已按当前镜头唯一出场角色补齐说话人。")

    if speaker in {"角色A", "角色B", "角色C", "某人"}:
        warnings.append("说话人仍是占位名称，请先绑定真实角色。")
    elif speaker and known_names and speaker not in known_names and speaker not in {"旁白", "画外音", "解说", "系统"}:
        warnings.append(f"说话人「{speaker}」未在当前镜头角色中找到，请确认角色绑定。")
    elif not speaker and known_names:
        warnings.append("未能明确说话人，建议从当前镜头角色中选择后再润色。")

    normalized_dialogue = format_dialogue(speaker, spoken_text, dialogue)
    source = str(payload.get("dialogue_source") or "").strip()
    if not source:
        source = {
            "extract": "script" if request.script_content or request.script_id else "chapter",
            "polish": "current_dialogue",
            "rewrite": "ai_rewrite",
            "suggest": "ai_suggest",
        }.get(request.dialogue_mode, "generated")

    duration = payload.get("duration", 4)
    try:
        duration_value = int(duration)
    except (TypeError, ValueError):
        duration_value = 4

    return GenerateDialogueResponse(
        dialogue=normalized_dialogue,
        visual_description=str(payload.get("visual_description") or "").strip(),
        camera_suggestion=str(payload.get("camera_suggestion") or payload.get("camera_angle") or "中景").strip(),
        duration=max(2, min(duration_value, 8)),
        speaker_name=speaker or None,
        spoken_text=strip_dialogue_speaker(normalized_dialogue) or None,
        dialogue_source=source,
        warnings=list(dict.fromkeys(warnings)),
    )


async def enrich_dialogue_context(
    db: AsyncSession,
    user_id: str,
    request: GenerateDialogueRequest,
) -> tuple[Optional[str], Optional[str], List[dict], Optional[str], Optional[str], Optional[str]]:
    script_content = request.script_content
    chapter_content = request.chapter_content
    characters = list(request.characters or [])
    current_dialogue = request.current_dialogue
    script_id = request.script_id
    chapter_id = request.chapter_id

    if request.shot_id:
        shot_result = await db.execute(select(Shot).where(and_(Shot.id == request.shot_id, Shot.user_id == user_id)))
        shot = shot_result.scalar_one_or_none()
        if shot:
            current_dialogue = current_dialogue or shot.dialogue
            if not characters and isinstance(shot.character_refs, list):
                characters = shot.character_refs
            storyboard_result = await db.execute(select(Storyboard).where(and_(Storyboard.id == shot.storyboard_id, Storyboard.user_id == user_id)))
            storyboard = storyboard_result.scalar_one_or_none()
            if storyboard:
                script_id = script_id or storyboard.script_id
                content = storyboard.content if isinstance(storyboard.content, dict) else {}
                chapter_id = chapter_id or content.get("chapter_id")

    if request.storyboard_id and not script_id:
        storyboard_result = await db.execute(select(Storyboard).where(and_(Storyboard.id == request.storyboard_id, Storyboard.user_id == user_id)))
        storyboard = storyboard_result.scalar_one_or_none()
        if storyboard:
            script_id = storyboard.script_id
            content = storyboard.content if isinstance(storyboard.content, dict) else {}
            chapter_id = chapter_id or content.get("chapter_id")

    if script_id and not script_content:
        script_result = await db.execute(select(Script).where(and_(Script.id == script_id, Script.user_id == user_id)))
        script = script_result.scalar_one_or_none()
        if script:
            script_content = script.content
            chapter_id = chapter_id or script.chapter_id

    if chapter_id and not chapter_content:
        chapter_result = await db.execute(select(Chapter).where(and_(Chapter.id == chapter_id, Chapter.user_id == user_id)))
        chapter = chapter_result.scalar_one_or_none()
        if chapter:
            chapter_content = chapter.content

    return script_content, chapter_content, characters, current_dialogue, script_id, chapter_id


class BatchGenerateShotsRequest(BaseModel):
    """批量生成镜头请求"""
    storyboard_id: str = Field(..., description="分镜ID")
    scene_description: str = Field(..., description="场景描述")
    shot_count: Optional[int] = Field(None, ge=1, le=20, description="生成镜头数量，不传则按上下文自动规划")
    style: str = Field("anime", description="风格")
    chapter_content: Optional[str] = Field(None, description="章节完整内容")
    script_content: Optional[str] = Field(None, description="剧本内容（优先用于台词和镜头拆分）")
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
        script_content, chapter_content, characters, current_dialogue, _script_id, _chapter_id = await enrich_dialogue_context(db, user_id, request)
        enriched_request_data = request.model_dump()
        enriched_request_data.update(
            {
                "script_content": script_content,
                "chapter_content": chapter_content,
                "current_dialogue": current_dialogue,
            }
        )
        enriched_request = GenerateDialogueRequest(**enriched_request_data)
        service, _provider_name, model_id, _base_url = await get_user_text_generation_service(db, user_id)

        # 构建提示词
        system_prompt = """你是一个专业的动画短剧分镜师和台词编辑，擅长从小说章节、剧本和镜头画面中提炼适合配音的短句。

创作规则：
1. 如果提供了剧本内容，优先从剧本原对白中提炼；可以压缩，但不能更换说话人，不能凭空改人物关系。
2. 如果没有剧本但有章节内容，必须承接章节剧情、人物动机和当前镜头画面，不写无关台词。
3. dialogue 必须使用“角色名：台词”格式；旁白使用“（旁白）台词”。禁止输出“角色A/角色B/某人”等占位名称。
4. 台词要适合短视频配音，优先 8-24 个中文字符，语气要符合角色身份和当前情绪。
5. 多镜头连续创作时，要保持人物称谓、事件、道具和场景前后一致。
6. 如果无法确认说话人或角色未绑定，请在 warnings 中说明，不要假装确定。

请以JSON格式输出：
{
  "dialogue": "角色名：适合配音的短句",
  "speaker_name": "角色名或旁白",
  "spoken_text": "不含说话人的台词正文",
  "dialogue_source": "script/chapter/current_dialogue/ai_rewrite/ai_suggest",
  "visual_description": "画面描述",
  "camera_suggestion": "镜头角度",
  "duration": 建议时长,
  "warnings": []
}"""

        mode_text = {
            "extract": "从剧本或章节中提炼最适合当前镜头的一句台词。",
            "polish": "保留原意和说话人，只把当前台词润色得更符合角色口吻。",
            "rewrite": "在不改变剧情和说话人的前提下，补写或重写一句更清晰的短句。",
            "suggest": "基于上下文建议一句台词，并说明必要提醒。",
        }.get(request.dialogue_mode, "从上下文提炼台词。")

        user_prompt = f"""处理方式：{mode_text}
场景/镜头描述：{request.scene_description}
当前已有台词：{current_dialogue or "无"}
指定说话人：{request.speaker_name or "未指定"}
风格：{request.style}
"""
        if script_content:
            user_prompt += f"\n\n剧本内容（优先依据）：\n{compact_text(script_content, 2200)}"
        if chapter_content:
            user_prompt += f"\n\n章节内容（承接剧情）：\n{compact_text(chapter_content, 1600)}"
        if characters:
            chars = ", ".join([
                c.get("name") or c.get("character_name") or c.get("entity_name") or "未知角色"
                for c in characters
                if isinstance(c, dict)
            ])
            chars_info = "\n".join([
                f"- {c.get('name') or c.get('character_name') or c.get('entity_name') or '未知角色'}: {c.get('description') or c.get('appearance') or c.get('role') or '无补充描述'}"
                for c in characters
                if isinstance(c, dict)
            ])
            user_prompt += f"\n\n当前镜头出场角色：{chars}\n{chars_info}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await service.chat_completion(
            model=model_id,
            messages=messages,
            temperature=0.8,
            max_tokens=500
        )

        content = response["choices"][0]["message"]["content"]

        # 尝试解析JSON响应
        try:
            data = extract_json_object(content)
            return normalize_dialogue_payload(data, enriched_request, characters)
        except json.JSONDecodeError:
            # 如果JSON解析失败，返回默认结构
            return normalize_dialogue_payload(
                {
                    "dialogue": content[:100] if len(content) > 100 else content,
                    "visual_description": "",
                    "camera_suggestion": "中景",
                    "duration": 4,
                    "warnings": ["AI返回格式不完整，已按文本结果回填。"],
                },
                enriched_request,
                characters,
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
        service, _provider_name, model_id, _base_url = await get_user_text_generation_service(db, user_id)
        source_content = request.script_content or request.chapter_content or request.scene_description
        shot_count_plan = plan_storyboard_shot_count(
            template={"shots": [{}, {}, {}, {}]},
            source_content=source_content,
            requested_shot_count=request.shot_count,
        )
        effective_shot_count = min(20, shot_count_plan["shot_count"])

        # 构建提示词 - 明确要求中文输出
        system_prompt = """你是一个专业的视频分镜师，擅长将场景描述转化为详细的分镜脚本。

【重要】你必须使用中文生成所有内容，包括JSON中的所有字段值。

请根据场景描述，生成N个镜头组成的分镜序列。每个镜头需要包含：
- shot_number: 镜头编号（整数）
- duration: 时长（秒，整数，如4、6、8）
- prompt: 视频生成Prompt（用于AI视频生成的详细画面描述，必须是中文）
- dialogue: 台词（中文对白，必须是“角色名：台词”或“（旁白）台词”；没有对白可为空字符串）
- visual_description: 视觉描述（画面构图、色彩，光影，中文描述）
- camera_angle: 镜头角度（使用中文，如：全景、中景、近景、特写、跟拍、摇镜头）

【重要】
1. JSON数组中的所有字符串值必须使用中文。
2. 有剧本内容时，台词优先从剧本原对白提炼，可以压缩但不得更换说话人。
3. 禁止使用“角色A/角色B/某人”等占位名称；只能使用角色列表中的真实角色名或旁白。
4. 多镜头之间要保持同一章节的人物称谓、道具、场景和事件连续。
5. 短视频节奏要清晰：开场有钩子，中段推进冲突，结尾留下一点悬念。

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
镜头数量：{effective_shot_count}个
"""

        if request.chapter_content:
            user_prompt += f"\n\n章节完整内容：\n{request.chapter_content[:2000]}..."

        if request.script_content:
            user_prompt += f"\n\n剧本内容（优先提炼对白与镜头）：\n{request.script_content[:2400]}..."

        if request.characters:
            chars_info = "\n".join([
                f"- {c.get('name', '未知')}: {c.get('description', '无描述')}"
                for c in request.characters
            ])
            user_prompt += f"\n\n角色列表：\n{chars_info}"

        user_prompt += "\n\n请生成" + str(effective_shot_count) + "个镜头，从开场到结尾，形成完整的分镜序列。"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await service.chat_completion(
            model=model_id,
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
