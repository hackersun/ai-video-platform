"""
Prompt composer for consistent image/video/TTS generation.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def _stringify_rule(rule: Any) -> str:
    if isinstance(rule, dict):
        parts = []
        for key in ("name", "title", "description", "appearance", "state", "rule"):
            value = rule.get(key)
            if value:
                parts.append(f"{key}: {value}")
        return "; ".join(parts) if parts else str(rule)
    return str(rule)


def _limited_lines(title: str, values: Optional[Iterable[Any]], limit: int = 24) -> List[str]:
    items = [_stringify_rule(item) for item in (values or []) if item]
    if not items:
        return []
    lines = [f"{title}:"]
    lines.extend(f"- {item}" for item in items[:limit])
    if len(items) > limit:
        lines.append(f"- 其余{len(items) - limit}条已进入结构化资产/实体锁，生成时不得与已锁定设定矛盾。")
    return lines


def compose_generation_prompt(
    *,
    task: str,
    shot: Optional[Any] = None,
    story_bible: Optional[Any] = None,
    characters: Optional[Iterable[Any]] = None,
    project: Optional[Any] = None,
    extra_context: Optional[Dict[str, Any]] = None,
    locked_assets: Optional[List[Dict]] = None,
    skill_blocks: Optional[List[str]] = None,
) -> str:
    """Compose a deterministic prompt from consistency sources."""
    sections: List[str] = [f"任务: {task}"]

    if project is not None:
        project_style = getattr(project, "global_style", None)
        project_seed = getattr(project, "global_seed", None)
        project_negative = getattr(project, "global_negative_prompt", None)
        if project_style:
            sections.append(f"项目风格: {project_style}")
        if project_seed:
            sections.append(f"项目一致性种子: {project_seed}")
        if project_negative:
            sections.append(f"项目负面约束: {project_negative}")

    if story_bible is not None:
        for label, attr in (
            ("故事风格", "style"),
            ("世界观", "worldview"),
            ("负面约束", "negative_prompt"),
        ):
            value = getattr(story_bible, attr, None)
            if value:
                sections.append(f"{label}: {value}")
        sections.extend(_limited_lines("角色规则", getattr(story_bible, "character_rules", None)))
        sections.extend(_limited_lines("场景规则", getattr(story_bible, "scene_rules", None)))
        sections.extend(_limited_lines("道具规则", getattr(story_bible, "prop_rules", None)))
        sections.extend(_limited_lines("事件时间线", getattr(story_bible, "event_timeline", None)))
        extra_data = getattr(story_bible, "extra_data", None)
        state_machine = extra_data.get("state_machine") if isinstance(extra_data, dict) else None
        if isinstance(state_machine, dict):
            current_state = state_machine.get("current_state") if isinstance(state_machine.get("current_state"), dict) else {}
            summary = state_machine.get("summary") if isinstance(state_machine.get("summary"), dict) else {}
            sections.append(
                "Story Bible状态机: "
                f"人物{summary.get('characters', 0)}，场景{summary.get('scenes', 0)}，"
                f"道具{summary.get('props', 0)}，事件{summary.get('events', 0)}，"
                "后续生成必须继承当前状态。"
            )
            for label, key in (("人物当前状态", "characters"), ("场景当前状态", "scenes"), ("道具当前状态", "props")):
                values = current_state.get(key) if isinstance(current_state.get(key), dict) else {}
                lines = []
                for name, value in list(values.items())[:6]:
                    if not isinstance(value, dict):
                        continue
                    state = value.get("state") or value.get("costume") or value.get("weather") or value.get("lighting") or "已记录"
                    lines.append(f"{name}: {state}")
                if lines:
                    sections.append(f"{label}:")
                    sections.extend(f"- {line}" for line in lines)

    character_lines = []
    for character in characters or []:
        name = getattr(character, "name", None)
        if not name:
            continue
        parts = [name]
        for attr in ("appearance", "personality", "voice"):
            value = getattr(character, attr, None)
            if value:
                parts.append(f"{attr}: {value}")
        character_lines.append("; ".join(parts))
    if character_lines:
        sections.append("本镜头角色:")
        sections.extend(f"- {line}" for line in character_lines)

    if shot is not None:
        shot_parts = []
        for label, attr in (
            ("镜头描述", "prompt"),
            ("视觉描述", "visual_description"),
            ("对白", "dialogue"),
            ("机位", "camera_angle"),
            ("运镜", "camera_movement"),
            ("情绪", "emotion"),
            ("光影", "lighting"),
            ("色彩", "color_grading"),
        ):
            value = getattr(shot, attr, None)
            if value:
                shot_parts.append(f"{label}: {value}")
        if shot_parts:
            sections.append("当前镜头:")
            sections.extend(f"- {part}" for part in shot_parts)

    if extra_context:
        sections.append("补充要求:")
        for key, value in extra_context.items():
            if value is not None:
                sections.append(f"- {key}: {value}")

    if skill_blocks:
        sections.append("Prompt技能约束:")
        sections.extend(f"- {block}" for block in skill_blocks if block)

    if task in {"shot_video", "shot_audio_video"}:
        sections.append(
            "视频一致性约束: 严格保持以上人物身份、外貌、服装、场景环境、道具状态、事件关系和整体画风；"
            "同一角色不要更换发型、年龄、脸型或服饰，同一场景不要更换时代、天气、空间结构或光影基调。"
        )

    # 在视频任务中添加锁定资产约束
    if task in {"shot_video", "shot_audio_video"} and locked_assets:
        sections.append("【锁定资产一致性约束】")
        for asset in locked_assets:
            sections.append(
                f"- {asset.get('type', '资产')}: {asset.get('name', 'Unknown')}, "
                f"严格保持外观与锁定资产一致"
            )

    return "\n".join(sections)
