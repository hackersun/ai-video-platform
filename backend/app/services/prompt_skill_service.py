"""Prompt 技能配置、渲染和预览服务。"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_key_utils import create_text_generation_service, get_user_text_model_config
from app.models import PromptSkill
from app.services.default_prompt_skills import ensure_standard_prompt_skills
from app.services.prompt_composer import compose_generation_prompt


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def prompt_skill_payload(skill: PromptSkill) -> Dict[str, Any]:
    return {
        "id": skill.id,
        "user_id": skill.user_id,
        "name": skill.name,
        "description": skill.description,
        "task": skill.task,
        "stage": skill.stage,
        "content": skill.content,
        "variables": skill.variables or {},
        "priority": skill.priority,
        "inject_position": skill.inject_position,
        "version": skill.version,
        "is_active": bool(skill.is_active),
        "is_builtin": bool(skill.is_builtin),
        "tags": skill.tags or [],
        "created_at": skill.created_at.isoformat() if skill.created_at else None,
        "updated_at": skill.updated_at.isoformat() if skill.updated_at else None,
    }


def _effective_prompt_skill_payloads(skills: List[PromptSkill], user_id: str) -> List[Dict[str, Any]]:
    user_active_by_task: Dict[str, str] = {}
    builtin_active_by_task: Dict[str, str] = {}
    for skill in skills:
        if not skill.is_active:
            continue
        if skill.is_builtin:
            builtin_active_by_task.setdefault(skill.task, skill.id)
        elif skill.user_id == user_id:
            user_active_by_task.setdefault(skill.task, skill.id)

    effective_ids = set(user_active_by_task.values())
    for task, skill_id in builtin_active_by_task.items():
        if task not in user_active_by_task:
            effective_ids.add(skill_id)

    payloads = []
    for skill in skills:
        payload = prompt_skill_payload(skill)
        payload["is_active"] = skill.id in effective_ids
        payloads.append(payload)
    return payloads


def render_prompt_skill(skill: PromptSkill, context: Optional[Dict[str, Any]] = None) -> str:
    values = _SafeFormatDict({**(skill.variables or {}), **(context or {})})
    try:
        rendered = (skill.content or "").format_map(values)
    except ValueError:
        rendered = skill.content or ""
    return rendered.strip()


def rendered_prompt_skill_entry(skill: PromptSkill, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    content = render_prompt_skill(skill, context)
    return {
        "id": skill.id,
        "name": skill.name,
        "task": skill.task,
        "stage": skill.stage,
        "version": skill.version or 1,
        "content": content,
    }


def _task_label(task: str) -> str:
    labels = {
        "novel_generation": "小说创建",
        "chapter_writing": "章节创建",
        "script_generation": "剧本创建",
        "storyboard_generation": "分镜创建",
        "entity_extraction": "实体/资产抽取",
        "shot_prompt": "镜头创建",
        "shot_video": "镜头视频",
        "character_image": "头像/角色图",
        "scene_reference_image": "场景图",
        "prop_image": "道具图",
        "novel_cover": "封面图",
        "tts_dialogue": "角色配音",
        "shot_audio_video": "音视频直生",
        "consistency_review": "一致性审查",
        "repair_suggestion": "返修建议",
    }
    return labels.get(task, task)


def _compact_prompt_skill_text(value: str, limit: int = 5000) -> str:
    compacted = re.sub(r"\n{3,}", "\n\n", value.strip())
    if len(compacted) <= limit:
        return compacted
    return f"{compacted[:limit].rstrip()}\n..."


def _extract_prompt_variables(content: str) -> List[str]:
    return sorted({match.group(1).strip() for match in re.finditer(r"\{([a-zA-Z0-9_\u4e00-\u9fff-]+)\}", content)})


def _parse_optimization_response(content: str) -> Dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(cleaned[start : end + 1])
        else:
            parsed = {"optimized_content": cleaned}
    if not isinstance(parsed, dict):
        return {"optimized_content": cleaned}
    return parsed


def _build_local_prompt_skill_optimization(data: Dict[str, Any], warning: Optional[str] = None) -> Dict[str, Any]:
    task = str(data.get("task") or "").strip()
    name = str(data.get("name") or "").strip() or f"{_task_label(task)}标准技能"
    description = str(data.get("description") or "").strip()
    content = _compact_prompt_skill_text(str(data.get("content") or ""))
    variables = _extract_prompt_variables(content)
    variable_line = "、".join(f"{{{item}}}" for item in variables) if variables else "无"
    description_line = f"\n适用说明：{description}" if description else ""
    mode = str(data.get("mode") or "polish")
    mode_goal = "压缩重复表达并保留关键约束" if mode == "tighten" else "强化生成可执行性和一致性边界"

    optimized = f"""优化目标：{mode_goal}，用于「{_task_label(task)}」环节的「{name}」。{description_line}

执行规则：
- 保留原始意图：{content}
- 明确主体、动作、场景、风格、连续性和可验证输出，避免只写抽象形容词。
- 变量占位保持可替换：{variable_line}。

禁止项：
- 不新增未声明角色、道具、地点或剧情结论。
- 不改变已锁定角色外观、资产状态、时代背景和镜头任务。
- 不输出水印、真实文字、无关镜头或无法生成的抽象要求。

验收标准：
- 生成前能看出任务目标、关键约束、禁止变化项和失败修复方向。
- 测试模式可预览，生产模式必须满足资产锁、模型配置和媒体产物等强制限制。"""

    warnings = ["本次使用本地规则优化；配置可用文本模型后可获得更细的 AI 润色。"]
    if warning:
        warnings.insert(0, warning)

    suggestions = [
        "补充具体主体、镜头动作和视觉风格",
        "把禁止变化项写成可检查的清单",
        "预览后再克隆/激活，避免直接覆盖当前生产规则",
    ]
    if variables:
        suggestions.append("检查变量占位是否能由当前任务上下文填充")

    return {
        "task": task,
        "source": "local_rules",
        "original_content": content,
        "optimized_content": optimized.strip(),
        "suggestions": suggestions,
        "warnings": warnings,
    }


async def get_prompt_skill(db: AsyncSession, user_id: str, skill_id: str) -> PromptSkill:
    result = await db.execute(
        select(PromptSkill).where(
            PromptSkill.id == skill_id,
            or_(PromptSkill.user_id == user_id, PromptSkill.is_builtin == True),
        )
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt 技能不存在")
    return skill


async def list_prompt_skills(
    db: AsyncSession,
    user_id: str,
    *,
    task: Optional[str] = None,
    stage: Optional[str] = None,
    active: Optional[bool] = None,
) -> Dict[str, Any]:
    await ensure_standard_prompt_skills(db)
    query = select(PromptSkill).where(or_(PromptSkill.user_id == user_id, PromptSkill.is_builtin == True))
    if task:
        query = query.where(PromptSkill.task == task)
    if stage:
        query = query.where(PromptSkill.stage == stage)
    query = query.order_by(PromptSkill.priority, PromptSkill.created_at)
    skills = list((await db.execute(query)).scalars().all())
    items = _effective_prompt_skill_payloads(skills, user_id)
    if active is not None:
        items = [item for item in items if item["is_active"] is active]
    return {"items": items, "count": len(items)}


async def _deactivate_user_task_skills(
    db: AsyncSession,
    user_id: str,
    task: str,
    *,
    exclude_skill_id: Optional[str] = None,
) -> None:
    result = await db.execute(
        select(PromptSkill).where(
            PromptSkill.user_id == user_id,
            PromptSkill.task == task,
            PromptSkill.is_active == True,
            PromptSkill.is_builtin == False,
        )
    )
    for skill in result.scalars().all():
        if exclude_skill_id and skill.id == exclude_skill_id:
            continue
        skill.is_active = False


async def create_prompt_skill(db: AsyncSession, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    if data.get("is_active", True):
        await _deactivate_user_task_skills(db, user_id, data["task"])
    skill = PromptSkill(
        id=str(uuid4()),
        user_id=user_id,
        name=data["name"],
        description=data.get("description"),
        task=data["task"],
        stage=data.get("stage"),
        content=data["content"],
        variables=data.get("variables") or {},
        priority=data.get("priority", 100),
        inject_position=data.get("inject_position") or "before_constraints",
        version=1,
        is_active=data.get("is_active", True),
        is_builtin=False,
        tags=data.get("tags") or [],
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return prompt_skill_payload(skill)


async def update_prompt_skill(db: AsyncSession, user_id: str, skill_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    skill = await get_prompt_skill(db, user_id, skill_id)
    if skill.is_builtin:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="内置 Prompt 技能不能直接修改，请先克隆")
    next_task = data.get("task", skill.task)
    if data.get("is_active") is True:
        await _deactivate_user_task_skills(db, user_id, next_task, exclude_skill_id=skill.id)
    for key in (
        "name",
        "description",
        "task",
        "stage",
        "content",
        "variables",
        "priority",
        "inject_position",
        "is_active",
        "tags",
    ):
        if key in data:
            setattr(skill, key, data[key])
    skill.version = int(skill.version or 1) + 1
    await db.commit()
    await db.refresh(skill)
    return prompt_skill_payload(skill)


async def activate_prompt_skill(db: AsyncSession, user_id: str, skill_id: str) -> Dict[str, Any]:
    skill = await get_prompt_skill(db, user_id, skill_id)
    if skill.is_builtin:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="内置 Prompt 技能请先克隆后激活")
    await _deactivate_user_task_skills(db, user_id, skill.task, exclude_skill_id=skill.id)
    skill.is_active = True
    await db.commit()
    await db.refresh(skill)
    return prompt_skill_payload(skill)


async def delete_prompt_skill(db: AsyncSession, user_id: str, skill_id: str) -> Dict[str, Any]:
    skill = await get_prompt_skill(db, user_id, skill_id)
    if skill.is_builtin:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="内置 Prompt 技能不能删除，请先克隆后编辑自定义版本")
    if skill.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="当前激活 Prompt 技能正在使用，不能删除。请先激活其它版本后再删除",
        )
    deleted_id = skill.id
    await db.delete(skill)
    await db.commit()
    return {"deleted": True, "id": deleted_id}


async def bulk_prompt_skill_action(db: AsyncSession, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    action = data.get("action")
    if action not in {"delete", "clone", "set_tags"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="不支持的 Prompt 技能批量动作")

    skill_ids = [skill_id for skill_id in data.get("skill_ids", []) if skill_id]
    if not skill_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="请先选择 Prompt 技能")

    updated: List[PromptSkill] = []
    created: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    deleted_count = 0

    for skill_id in skill_ids:
        try:
            skill = await get_prompt_skill(db, user_id, skill_id)
        except HTTPException:
            skipped.append({"id": skill_id, "reason": "Prompt 技能不存在", "repair_action": "刷新页面后重新选择"})
            continue

        if action == "clone":
            created.append(await clone_prompt_skill(db, user_id, skill_id))
            continue

        if skill.is_builtin:
            skipped.append({"id": skill.id, "reason": "内置 Prompt 技能不能直接维护", "repair_action": "先克隆为自定义版本"})
            continue

        if action == "delete":
            if skill.is_active:
                skipped.append({"id": skill.id, "reason": "激活中的 Prompt 技能正在使用", "repair_action": "先激活同任务下其它版本后再删除"})
                continue
            await db.delete(skill)
            deleted_count += 1
            continue

        if action == "set_tags":
            skill.tags = data.get("tags") or []
            updated.append(skill)

    if updated or deleted_count:
        await db.commit()
    for skill in updated:
        await db.refresh(skill)

    return {
        "updated_count": len(updated),
        "deleted_count": deleted_count,
        "created_count": len(created),
        "skipped": skipped,
        "warnings": [],
        "skills": [prompt_skill_payload(skill) for skill in updated] + created,
    }


async def clone_prompt_skill(db: AsyncSession, user_id: str, skill_id: str) -> Dict[str, Any]:
    source = await get_prompt_skill(db, user_id, skill_id)
    return await create_prompt_skill(
        db,
        user_id,
        {
            "name": f"{source.name} 副本",
            "description": source.description,
            "task": source.task,
            "stage": source.stage,
            "content": source.content,
            "variables": source.variables or {},
            "priority": source.priority,
            "inject_position": source.inject_position,
            "is_active": False,
            "tags": source.tags or [],
        },
    )


async def _skills_by_ids(db: AsyncSession, user_id: str, skill_ids: Iterable[str]) -> List[PromptSkill]:
    await ensure_standard_prompt_skills(db)
    ids = [skill_id for skill_id in skill_ids if skill_id]
    if not ids:
        return []
    result = await db.execute(
        select(PromptSkill)
        .where(
            PromptSkill.id.in_(ids),
            or_(PromptSkill.user_id == user_id, PromptSkill.is_builtin == True),
        )
        .order_by(PromptSkill.priority, PromptSkill.created_at)
    )
    return list(result.scalars().all())


async def active_prompt_skill_entries(
    db: AsyncSession,
    user_id: str,
    *,
    task: str,
    context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    await ensure_standard_prompt_skills(db)
    user_result = await db.execute(
        select(PromptSkill)
        .where(
            PromptSkill.task == task,
            PromptSkill.is_active == True,
            PromptSkill.user_id == user_id,
            PromptSkill.is_builtin == False,
        )
        .order_by(PromptSkill.priority, PromptSkill.created_at)
    )
    user_skills = list(user_result.scalars().all())
    if user_skills:
        entries = [rendered_prompt_skill_entry(skill, context) for skill in user_skills]
        return [entry for entry in entries if entry["content"]][:1]

    builtin_result = await db.execute(
        select(PromptSkill)
        .where(
            PromptSkill.task == task,
            PromptSkill.is_active == True,
            PromptSkill.is_builtin == True,
        )
        .order_by(PromptSkill.priority, PromptSkill.created_at)
    )
    entries = [rendered_prompt_skill_entry(skill, context) for skill in builtin_result.scalars().all()]
    return [entry for entry in entries if entry["content"]][:1]


async def active_prompt_skill_blocks(
    db: AsyncSession,
    user_id: str,
    *,
    task: str,
    context: Optional[Dict[str, Any]] = None,
) -> List[str]:
    entries = await active_prompt_skill_entries(db, user_id, task=task, context=context)
    return [entry["content"] for entry in entries]


async def apply_active_prompt_skill_template(
    db: AsyncSession,
    user_id: str,
    *,
    task: str,
    internal_prompt: str,
    context: Optional[Dict[str, Any]] = None,
    template_title: str = "激活提示词模板",
    internal_title: str = "内部逻辑提示词",
) -> Dict[str, Any]:
    """Wrap an existing internal prompt with the active Prompt skill template."""
    entries = await active_prompt_skill_entries(db, user_id, task=task, context=context)
    entries = [entry for entry in entries if str(entry.get("content") or "").strip()]
    internal = (internal_prompt or "").strip()
    if not entries:
        return {
            "prompt": internal,
            "skill_blocks": [],
            "prompt_skills": [],
            "prompt_skill_count": 0,
            "used_prompt_skill": False,
        }

    skill_blocks = [str(entry["content"]).strip() for entry in entries]
    template_block = "\n\n".join(skill_blocks).strip()
    if internal:
        prompt = f"【{template_title}】\n{template_block}\n\n【{internal_title}】\n{internal}"
    else:
        prompt = f"【{template_title}】\n{template_block}"

    return {
        "prompt": prompt.strip(),
        "skill_blocks": skill_blocks,
        "prompt_skills": [
            {key: entry[key] for key in ("id", "name", "task", "stage", "version")}
            for entry in entries
        ],
        "prompt_skill_count": len(entries),
        "used_prompt_skill": True,
    }


async def optimize_prompt_skill_content(
    db: AsyncSession,
    user_id: str,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    content = str(data.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先填写技能内容后再使用 AI 优化")

    task = str(data.get("task") or "").strip()
    mode = str(data.get("mode") or "polish").strip()
    model_config_id = data.get("model_config_id")

    system_prompt = """你是 AI 视频创作平台的 Prompt 技能编辑器，负责把用户写的技能片段润色为可复用、可测试、适合生产链路的中文提示词。

规则：
1. 只围绕用户原意优化，不发明新人物、剧情、模型能力或业务入口。
2. 必须保留原文中的 {变量占位}。
3. 输出 JSON，不要 markdown，不要解释。
4. JSON 字段必须包含 optimized_content、suggestions、warnings。
5. optimized_content 使用中文，结构包含优化目标、执行规则、禁止项、验收标准。"""

    user_prompt = f"""任务类型：{task}（{_task_label(task)}）
技能名称：{data.get('name') or '未命名'}
用途说明：{data.get('description') or '未填写'}
优化模式：{mode}
原始技能内容：
{_compact_prompt_skill_text(content)}

请返回：
{{
  "optimized_content": "优化后的完整 Prompt 技能内容",
  "suggestions": ["后续可补充项"],
  "warnings": ["需要用户确认的风险"]
}}"""

    try:
        api_key, provider_name, model_id, base_url = await get_user_text_model_config(
            db,
            user_id,
            raise_if_missing=False,
            config_id=model_config_id,
        )
        if not api_key or not provider_name or not model_id:
            return _build_local_prompt_skill_optimization(data)
        service = create_text_generation_service(api_key, provider_name, base_url)
        response = await service.safe_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.25,
            max_tokens=2200,
        )
        parsed = _parse_optimization_response(response["choices"][0]["message"]["content"])
        optimized_content = str(parsed.get("optimized_content") or "").strip()
        if not optimized_content:
            return _build_local_prompt_skill_optimization(data, warning="AI 返回内容为空，已改用本地规则优化。")
        suggestions = parsed.get("suggestions") if isinstance(parsed.get("suggestions"), list) else []
        warnings = parsed.get("warnings") if isinstance(parsed.get("warnings"), list) else []
        return {
            "task": task,
            "source": "ai_model",
            "original_content": _compact_prompt_skill_text(content),
            "optimized_content": optimized_content,
            "suggestions": [str(item).strip() for item in suggestions if str(item).strip()],
            "warnings": [str(item).strip() for item in warnings if str(item).strip()],
        }
    except Exception as exc:
        return _build_local_prompt_skill_optimization(data, warning=f"AI 优化暂不可用：{str(exc)[:120]}")


async def preview_prompt_skills(
    db: AsyncSession,
    user_id: str,
    *,
    task: str,
    skill_ids: Optional[List[str]] = None,
    context: Optional[Dict[str, Any]] = None,
    draft_name: Optional[str] = None,
    draft_content: Optional[str] = None,
    draft_stage: Optional[str] = None,
) -> Dict[str, Any]:
    if draft_content and draft_content.strip():
        content = render_prompt_skill(
            PromptSkill(
                id="draft",
                user_id=user_id,
                name=draft_name or "当前编辑草稿",
                task=task,
                stage=draft_stage or "draft",
                content=draft_content,
                variables={},
                priority=0,
                inject_position="before_constraints",
                version=0,
                is_active=False,
                is_builtin=False,
                tags=[],
            ),
            context,
        )
        entries = [
            {
                "id": "draft",
                "name": draft_name or "当前编辑草稿",
                "task": task,
                "stage": draft_stage or "draft",
                "version": 0,
                "content": content,
            }
        ]
    elif skill_ids:
        skills = await _skills_by_ids(db, user_id, skill_ids)
        selected_skills = [skill for skill in skills if skill.task == task]
        entries = [rendered_prompt_skill_entry(skill, context) for skill in selected_skills]
    else:
        skills_result = await list_prompt_skills(db, user_id, task=task, active=True)
        skills = [await get_prompt_skill(db, user_id, item["id"]) for item in skills_result["items"]]
        selected_skills = [skill for skill in skills if skill.task == task and skill.is_active]
        entries = [rendered_prompt_skill_entry(skill, context) for skill in selected_skills]
    entries = [entry for entry in entries if entry["content"]]
    blocks = [entry["content"] for entry in entries]
    prompt = compose_generation_prompt(task=task, extra_context=context or {}, skill_blocks=blocks)
    return {
        "task": task,
        "skill_count": len(entries),
        "skills": [{key: entry[key] for key in ("id", "name", "task", "stage", "version")} for entry in entries],
        "skill_blocks": blocks,
        "prompt": prompt,
    }
