"""Provider-facing prompt safety helpers for video generation."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple


LOCAL_STATIC_PATH_RE = re.compile(r"/static/[^\s，,；;）)]+")
ASSET_VERSION_ENTRY_RE = re.compile(
    r"(?P<name>[^:：；;，,\n]+)\((?P<kind>character|scene|location|prop|object)\)\s*[:：]\s*[^；;\n]*"
)
LOCK_CONSTRAINT_RE = re.compile(
    r"^-\s*(?P<kind>character|scene|location|prop|object)\s*[:：]\s*(?P<name>[^,，:：\n]+)"
)

ASSET_KIND_LABELS = {
    "character": "角色",
    "scene": "场景",
    "location": "场景",
    "prop": "道具",
    "object": "道具",
}

BAD_CHARACTER_NAME_PREFIXES = ("是", "说")
BAD_FRAGMENT_MARKERS = ("门后", "不")


VIDEO_PROMPT_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
    ("已抹除名单", "隐藏记录"),
    ("抹除名单", "隐藏记录"),
    ("抹除", "隐藏"),
    ("删除", "归档"),
    ("失踪档案", "待查资料"),
    ("失踪", "待查"),
    ("档案", "资料"),
    ("名单", "记录"),
    ("消失", "离场"),
    ("牺牲别人", "付出代价"),
    ("牺牲", "高代价"),
    ("死亡", "离场"),
    ("尸体", "遗留物"),
    ("尸", "遗留物"),
    ("血液", "红色液体"),
    ("血迹", "红色痕迹"),
    ("血", "红色光效"),
    ("杀死", "击退"),
    ("杀", "击退"),
    ("悬疑", "奇幻调查"),
    ("阻止", "避免"),
    ("防线", "边界"),
    ("忘记", "记忆变得模糊"),
    ("阴影", "暗处"),
    ("倒转", "反向运转"),
    ("第四次", "下一次"),
    ("第四", "下一"),
    ("拒绝", "不同意"),
    ("警报", "提示"),
    ("异常", "特殊"),
    ("伤势", "状态"),
    ("破损", "磨损"),
    ("压迫", "强势"),
    ("审判", "评议"),
    ("追杀", "追逐"),
    ("威胁", "对峙"),
    ("秘密", "线索"),
    ("血脉", "传承"),
    ("事件", "动作节点"),
    ("要求", "请求"),
    ("规则识别", "结构化"),
)


def _replace_regex_section(prompt: str, pattern: str, replacement: str, replacements: List[Dict[str, str]]) -> str:
    safe_prompt, count = re.subn(pattern, replacement, prompt, flags=re.DOTALL)
    if count:
        replacements.append({"source": pattern, "target": replacement.strip()})
    return safe_prompt


def _compact_novel_continuity_lock(prompt: str, replacements: List[Dict[str, str]]) -> str:
    pattern = re.compile(
        r"\n- 整部小说连续性锁:.*?(?=\n- 小说级系列种子:|\n- 章节连续性种子:|\n- 分镜派生种子:|\n- 参考图:|\n视频一致性约束:|\Z)",
        flags=re.DOTALL,
    )

    def repl(match: re.Match[str]) -> str:
        section = match.group(0)
        markers: List[str] = []
        previous_match = re.search(r"上一章承接：第[^章]+章《([^》]+)》", section)
        if previous_match:
            markers.append(f"上一章承接：{previous_match.group(1)}")
        elif "上一章承接" in section:
            markers.append("上一章承接")
        if "上一章状态" in section:
            markers.append("上一章状态")
        if "当前章节" in section:
            markers.append("当前章节")
        if "当前章节状态" in section:
            markers.append("当前章节状态")
        if "下一章不可矛盾约束" in section:
            markers.append("后续章节约束")
        marker_note = f"；{'、'.join(markers)}已锁定" if markers else ""
        return f"\n- 整部小说连续性锁: 保持角色外观、服装、场景光影、道具外观和画风连续{marker_note}。\n"

    safe_prompt, count = pattern.subn(repl, prompt)
    if count:
        replacements.append({"source": "novel_continuity_lock_full_block", "target": "compact_novel_continuity_lock"})
    return safe_prompt


def _strip_provider_unnecessary_story_context(prompt: str, replacements: List[Dict[str, str]]) -> str:
    """Remove internal story-planning blocks that increase provider moderation risk."""
    safe_prompt = prompt
    safe_prompt = _replace_regex_section(
        safe_prompt,
        r"\n事件时间线:\n(?:- [^\n]*(?:\n|$))*",
        "\n事件时间线: 已省略内部事件线；供应商提示词仅保留当前镜头视觉信息。\n",
        replacements,
    )
    safe_prompt = _replace_regex_section(
        safe_prompt,
        r"\nStory Bible状态机:.*?(?=\n当前镜头:|\n补充要求:|\n视频一致性约束:|\Z)",
        "\nStory Bible状态机: 内部状态已锁定；供应商提示词仅使用当前镜头视觉信息。\n",
        replacements,
    )
    safe_prompt = _compact_novel_continuity_lock(safe_prompt, replacements)
    return safe_prompt


def _clean_asset_name(name: str) -> str:
    return re.sub(r"[《》『』\[\]（）()【】]", "", (name or "")).strip()


def _is_provider_safe_asset_name(kind: str, name: str) -> bool:
    clean_name = _clean_asset_name(name)
    if not clean_name or len(clean_name) > 8:
        return False
    if re.search(r"[，,。；;：:\s]", clean_name):
        return False
    if clean_name.startswith(BAD_CHARACTER_NAME_PREFIXES):
        return False
    if kind == "character" and any(marker in clean_name for marker in BAD_FRAGMENT_MARKERS):
        return False
    return True


def _dedupe_asset_entries(entries: List[Tuple[str, str]], max_entries: int = 8) -> List[Tuple[str, str]]:
    result: List[Tuple[str, str]] = []
    seen = set()
    for raw_kind, raw_name in entries:
        kind = raw_kind if raw_kind in ASSET_KIND_LABELS else "object"
        name = _clean_asset_name(raw_name)
        if not _is_provider_safe_asset_name(kind, name):
            continue
        key = (kind, name)
        if key in seen:
            continue
        seen.add(key)
        result.append(key)
        if len(result) >= max_entries:
            break
    return result


def _asset_entries_from_version_line(line: str) -> List[Tuple[str, str]]:
    return [(match.group("kind"), match.group("name")) for match in ASSET_VERSION_ENTRY_RE.finditer(line)]


def _asset_entry_from_constraint_line(line: str) -> Tuple[str, str] | None:
    match = LOCK_CONSTRAINT_RE.match(line.strip())
    if not match:
        return None
    return match.group("kind"), match.group("name")


def _format_asset_lock_summary(entries: List[Tuple[str, str]]) -> str:
    labels = [f"{ASSET_KIND_LABELS.get(kind, '资产')} {name}" for kind, name in entries]
    return "；".join(labels)


def _replace_local_static_paths(prompt: str, replacements: List[Dict[str, str]]) -> str:
    if not LOCAL_STATIC_PATH_RE.search(prompt):
        return prompt

    lines: List[str] = []
    for line in prompt.splitlines():
        if LOCAL_STATIC_PATH_RE.search(line) and line.strip().startswith("- 参考图:"):
            lines.append("- 参考图: 已通过独立参考图通道提交。")
        else:
            lines.append(LOCAL_STATIC_PATH_RE.sub("已锁定参考资产", line))
    replacements.append({"source": "local_static_paths", "target": "provider_safe_reference_labels"})
    return "\n".join(lines)


def _compact_asset_version_lock_lines(prompt: str, replacements: List[Dict[str, str]]) -> str:
    lines: List[str] = []
    changed = False
    for line in prompt.splitlines():
        if line.strip().startswith("- 资产版本锁:"):
            entries = _dedupe_asset_entries(_asset_entries_from_version_line(line))
            if entries:
                lines.append(f"- 资产版本锁: {_format_asset_lock_summary(entries)}")
            else:
                lines.append("- 资产版本锁: 已锁定当前镜头核心角色、场景、道具参考资产。")
            changed = True
            continue
        lines.append(line)
    if changed:
        replacements.append({"source": "asset_version_lock_paths", "target": "compact_asset_lock_names"})
    return "\n".join(lines)


def _compact_locked_asset_constraint_sections(prompt: str, replacements: List[Dict[str, str]]) -> str:
    lines = prompt.splitlines()
    output: List[str] = []
    changed = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == "【锁定资产一致性约束】":
            i += 1
            entries: List[Tuple[str, str]] = []
            while i < len(lines) and lines[i].lstrip().startswith("- "):
                entry = _asset_entry_from_constraint_line(lines[i])
                if entry:
                    entries.append(entry)
                i += 1
            safe_entries = _dedupe_asset_entries(entries)
            output.append("【锁定资产一致性约束】")
            if safe_entries:
                for kind, name in safe_entries:
                    output.append(f"- {ASSET_KIND_LABELS.get(kind, '资产')} {name}: 保持与已锁定参考资产一致")
            else:
                output.append("- 当前镜头核心角色、场景、道具保持与锁定参考资产一致")
            changed = True
            continue
        output.append(line)
        i += 1
    if changed:
        replacements.append({"source": "locked_asset_constraint_list", "target": "deduped_asset_constraint_summary"})
    return "\n".join(output)


def _normalize_dialogue_sync_speaker(prompt: str, replacements: List[Dict[str, str]]) -> str:
    def replace_line(match: re.Match[str]) -> str:
        speaker = match.group("speaker").strip()
        line = match.group(0)
        if _is_provider_safe_asset_name("character", speaker):
            return line
        replacement = "旁白" if "旁白" in line else "当前镜头主体"
        replacements.append({"source": f"dialogue_sync_speaker:{speaker}", "target": replacement})
        return line.replace(f"说话人：{speaker}", f"说话人：{replacement}")

    return re.sub(r"对白同步约束[^\n]*?说话人：(?P<speaker>[^；;，,\n]+)[^\n]*", replace_line, prompt)


def _dedupe_provider_prompt_lines(prompt: str, replacements: List[Dict[str, str]]) -> str:
    lines: List[str] = []
    seen = set()
    changed = False
    for line in prompt.splitlines():
        key = line.strip()
        if key and key in seen:
            changed = True
            continue
        seen.add(key)
        lines.append(line)
    if changed:
        replacements.append({"source": "duplicate_provider_prompt_lines", "target": "deduped_provider_prompt_lines"})
    return "\n".join(lines)


def _harden_provider_visual_prompt(prompt: str, replacements: List[Dict[str, str]]) -> str:
    safe_prompt = _compact_asset_version_lock_lines(prompt, replacements)
    safe_prompt = _replace_local_static_paths(safe_prompt, replacements)
    safe_prompt = _compact_locked_asset_constraint_sections(safe_prompt, replacements)
    safe_prompt = _normalize_dialogue_sync_speaker(safe_prompt, replacements)
    safe_prompt = _dedupe_provider_prompt_lines(safe_prompt, replacements)
    return safe_prompt


def _section_until(prompt: str, marker: str, stop_markers: Tuple[str, ...]) -> str:
    start = prompt.find(marker)
    if start < 0:
        return ""
    end = len(prompt)
    for stop_marker in stop_markers:
        stop = prompt.find(stop_marker, start + len(marker))
        if stop >= 0:
            end = min(end, stop)
    return prompt[start:end].strip()


def _compact_provider_video_prompt(prompt: str, replacements: List[Dict[str, str]]) -> str:
    """Keep only visual-production fields needed by video providers."""
    if "当前镜头:" not in prompt:
        return prompt

    lines: List[str] = []
    for line in prompt.splitlines():
        if line.startswith(("任务:", "故事风格:", "世界观:")):
            lines.append(line)

    current_shot = _section_until(
        prompt,
        "当前镜头:",
        ("\n补充要求:", "\n视频一致性约束:", "\n【锁定资产一致性约束】", "\n对白同步约束"),
    )
    if current_shot:
        lines.append(current_shot)

    allowed_prefixes = (
        "- 视频时长:",
        "- 分辨率:",
        "- 参考图:",
        "- 参考图来源:",
        "- 整部小说连续性锁:",
        "- 人物角色:",
        "- 角色视觉DNA锁:",
        "- 角色多视图参考:",
        "- 场景:",
        "- 道具:",
        "- 字幕/对白:",
        "- 环境连续性:",
        "- 资产版本锁:",
        "- 小说级风格锁:",
        "- 动漫连续性硬约束:",
    )
    for line in prompt.splitlines():
        if line.startswith(allowed_prefixes):
            lines.append(line)

    section_specs = (
        ("视频一致性约束:", ("\n【锁定资产一致性约束】", "\n对白同步约束")),
        ("【锁定资产一致性约束】", ("\n对白同步约束",)),
        ("对白同步约束", tuple()),
    )
    for marker, stop_markers in section_specs:
        section = _section_until(prompt, marker, stop_markers)
        if section:
            lines.append(section)

    compact = "\n".join(line for line in lines if line).strip()
    if compact and compact != prompt:
        replacements.append({"source": "provider_prompt_full_story_context", "target": "provider_visual_prompt_compact"})
        return compact
    return prompt


def build_provider_video_prompt_fallback() -> Dict[str, Any]:
    """Return an ultra-safe fallback prompt for provider moderation retries."""
    prompt = (
        "Anime cinematic shot. Use the reference image as the primary identity guide. "
        "Keep the character face, hairstyle, outfit, body proportions, scene lighting, "
        "and prop appearance consistent. Create a short silent performance with natural "
        "lip movement and gentle camera motion for later dubbing. No text overlays, no captions, no logos."
    )
    return {
        "prompt": prompt,
        "sanitized": True,
        "replacements": [
            {
                "source": "provider_text_moderation_retry",
                "target": "ultra_safe_visual_prompt",
            }
        ],
    }


def sanitize_provider_video_prompt(
    prompt: str, *, protected_texts: Iterable[str] = (),
) -> Dict[str, Any]:
    """Rewrite risky story terms only for provider-submitted video prompts."""
    safe_prompt = prompt or ""
    replacements: List[Dict[str, str]] = []
    protected: Dict[str, str] = {}
    for index, value in enumerate(protected_texts):
        text = str(value or "").strip()
        if not text or text not in safe_prompt:
            continue
        marker = f"__CANONICAL_SPOKEN_TEXT_{index}__"
        safe_prompt = safe_prompt.replace(text, marker)
        protected[marker] = text
    safe_prompt = _strip_provider_unnecessary_story_context(safe_prompt, replacements)
    safe_prompt = _compact_provider_video_prompt(safe_prompt, replacements)
    safe_prompt = _harden_provider_visual_prompt(safe_prompt, replacements)
    for source, target in VIDEO_PROMPT_REPLACEMENTS:
        if source in safe_prompt:
            safe_prompt = safe_prompt.replace(source, target)
            replacements.append({"source": source, "target": target})
    for marker, text in protected.items():
        safe_prompt = safe_prompt.replace(marker, text)
    return {
        "prompt": safe_prompt,
        "sanitized": bool(replacements),
        "replacements": replacements,
    }


def provider_text_safety_error_message(exc: Exception) -> str | None:
    """Map provider text moderation failures to an actionable API error."""
    error_text = str(exc)
    markers = (
        "InputTextSensitiveContentDetected",
        "sensitive information",
        "sensitive content",
        "Invalid content.text",
    )
    if not any(marker in error_text for marker in markers):
        return None
    return (
        "云端视频模型拒绝了提交的提示词内容。系统已对常见高风险词做安全改写；"
        "如果仍触发，请进一步减少供应商提示词中的悬疑/伤害/消失类直接措辞，"
        f"保留内部剧本不变后重试。原始错误：{error_text}"
    )
