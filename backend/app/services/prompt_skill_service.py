"""Prompt 技能配置、渲染和预览服务。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PromptSkill
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
    query = select(PromptSkill).where(or_(PromptSkill.user_id == user_id, PromptSkill.is_builtin == True))
    if task:
        query = query.where(PromptSkill.task == task)
    if stage:
        query = query.where(PromptSkill.stage == stage)
    if active is not None:
        query = query.where(PromptSkill.is_active == active)
    query = query.order_by(PromptSkill.priority, PromptSkill.created_at)
    skills = list((await db.execute(query)).scalars().all())
    return {"items": [prompt_skill_payload(skill) for skill in skills], "count": len(skills)}


async def create_prompt_skill(db: AsyncSession, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
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


async def deactivate_prompt_skill(db: AsyncSession, user_id: str, skill_id: str) -> Dict[str, Any]:
    skill = await get_prompt_skill(db, user_id, skill_id)
    if skill.is_builtin:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="内置 Prompt 技能不能停用")
    skill.is_active = False
    await db.commit()
    await db.refresh(skill)
    return prompt_skill_payload(skill)


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
    result = await db.execute(
        select(PromptSkill)
        .where(
            PromptSkill.task == task,
            PromptSkill.is_active == True,
            or_(PromptSkill.user_id == user_id, PromptSkill.is_builtin == True),
        )
        .order_by(PromptSkill.priority, PromptSkill.created_at)
    )
    entries = [rendered_prompt_skill_entry(skill, context) for skill in result.scalars().all()]
    return [entry for entry in entries if entry["content"]]


async def active_prompt_skill_blocks(
    db: AsyncSession,
    user_id: str,
    *,
    task: str,
    context: Optional[Dict[str, Any]] = None,
) -> List[str]:
    entries = await active_prompt_skill_entries(db, user_id, task=task, context=context)
    return [entry["content"] for entry in entries]


async def preview_prompt_skills(
    db: AsyncSession,
    user_id: str,
    *,
    task: str,
    skill_ids: Optional[List[str]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if skill_ids:
        skills = await _skills_by_ids(db, user_id, skill_ids)
        selected_skills = [skill for skill in skills if skill.task == task]
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
