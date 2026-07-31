"""Unified provider calls for image generation endpoints."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Optional

from fastapi import HTTPException

from app.core.dev_generation import is_dev_mode
from app.features.model_config.public import (
    ExecutionSnapshotCommand,
    ModelBindingError,
    create_execution_snapshot,
    resolve_generation_context,
)
from app.features.model_drivers import public as driver_kernel

MINIMAX_IMAGE_PROMPT_MAX_CHARS = 1450

_CRITICAL_IMAGE_PROMPT_KEYWORDS = (
    "作品",
    "题材",
    "简介",
    "角色姓名",
    "角色描述",
    "外貌特征",
    "生成对象",
    "设定描述",
    "角色设定",
    "场景设定",
    "道具设定",
    "视觉契约ID",
    "性别/年龄感",
    "参考视图",
    "视图要求",
    "画面风格",
    "封面画风要求",
    "画风标签",
    "硬约束",
    "禁止",
    "不要",
    "通用负面约束",
)


def _clip_text(value: str, limit: int) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip("，,；;、 ") + "…"


def _line_limit(line: str) -> int:
    if "通用负面约束" in line or "硬约束" in line or "禁止" in line or "不要" in line:
        return 360
    if "剧情上下文" in line or "已保存章节承接" in line or "章节" in line:
        return 220
    if "外貌特征" in line or "设定描述" in line or "角色设定" in line:
        return 260
    return 180


def _compact_minimax_image_prompt(prompt: str, max_chars: int = MINIMAX_IMAGE_PROMPT_MAX_CHARS) -> str:
    text = (prompt or "").strip()
    if len(text) < max_chars:
        return text

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    selected: list[str] = ["提示词已自动压缩，保留关键设定、主体外观和生成约束。"]
    seen: set[str] = set(selected)

    for index, line in enumerate(lines):
        is_critical = any(keyword in line for keyword in _CRITICAL_IMAGE_PROMPT_KEYWORDS)
        if not is_critical and index >= 2:
            continue
        clipped = _clip_text(line, _line_limit(line))
        if clipped and clipped not in seen:
            selected.append(clipped)
            seen.add(clipped)
        if len(selected) >= 14:
            break

    if "通用负面约束" in text and not any("通用负面约束" in line for line in selected):
        negative_line = next((line for line in lines if "通用负面约束" in line), "")
        if negative_line:
            selected.append(_clip_text(negative_line, 360))

    while len("\n".join(selected)) >= max_chars and len(selected) > 1:
        shrinkable = [
            (idx, len(line))
            for idx, line in enumerate(selected[1:], start=1)
            if len(line) > 90 and "通用负面约束" not in line
        ]
        if not shrinkable:
            break
        index, current_len = max(shrinkable, key=lambda item: item[1])
        selected[index] = _clip_text(selected[index], max(90, current_len - 120))

    compacted = "\n".join(selected)
    if len(compacted) < max_chars:
        return compacted

    constraints = "\n".join(
        line for line in selected if "硬约束" in line or "通用负面约束" in line
    )
    head_budget = max_chars - len(constraints) - 12
    head = _clip_text("\n".join(line for line in selected if line not in constraints), max(120, head_budget))
    return _clip_text(f"{head}\n{constraints}".strip(), max_chars - 1)


def _prepare_image_prompt_for_provider(provider_name: str, prompt: str) -> str:
    provider = (provider_name or "").lower()
    if provider == "minimax":
        return _compact_minimax_image_prompt(prompt)
    return prompt


async def _create_image_execution_snapshot(
    generation_context: Any, *, db: Any, user_id: str | None, run_id: str | None,
    job_id: str | None, aspect_ratio: str, image_count: int, image_size: str,
    prompt_compacted: bool, reference_image_count: int,
) -> str | None:
    if db is None or not user_id or getattr(generation_context, "binding", None) is None:
        return None
    snapshot = await create_execution_snapshot(
        db,
        ExecutionSnapshotCommand(
            user_id=user_id, run_id=run_id, job_id=job_id,
            task=generation_context.binding.task,
            capability=generation_context.binding.capability,
            binding=generation_context.binding,
            recipe_version_id=getattr(generation_context, "recipe_version_id", None),
            prompt_profile_version_id=getattr(generation_context, "prompt_profile_version_id", None),
            sanitized_params={
                "aspect_ratio": aspect_ratio, "image_count": image_count, "image_size": image_size,
                "reference_image_count": reference_image_count,
                "parameter_normalization": {"prompt_compacted": prompt_compacted},
            },
        ),
    )
    return snapshot.id


async def call_image_generation_provider(
    service: Any,
    *,
    provider_name: str,
    model_id: str,
    prompt: str,
    num: int = 1,
    size: str = "2K",
    aspect_ratio: str = "1:1",
    openai_size: str = "1024x1024",
    minimax_response_format: str = "base64",
    generation_context: Any = None,
    generation_params: Mapping[str, Any] | None = None,
    db: Any = None,
    user_id: str | None = None,
    config_id: str | None = None,
    job_id: str | None = None,
    run_id: str | None = None,
    recipe_version_id: str | None = None,
    prompt_profile_version_id: str | None = None,
    reference_images: list[str] | tuple[str, ...] = (),
) -> dict:
    """Call a configured image provider with stable endpoint semantics."""
    if generation_context is None and db is not None and user_id:
        try:
            generation_context = await resolve_generation_context(
                db, user_id=user_id, stage="image", explicit_config_id=config_id,
                recipe_version_id=recipe_version_id,
                prompt_profile_version_id=prompt_profile_version_id,
            )
        except ModelBindingError as error:
            if not is_dev_mode():
                raise HTTPException(status_code=422, detail=str(error)) from error
    if generation_context is not None:
        driver = generation_context.driver_context
        prepared_prompt = (
            _compact_minimax_image_prompt(prompt)
            if driver.driver_key == "minimax_image_v1" else prompt
        )
        params = {
            **dict(generation_context.profile.default_params),
            **_driver_image_params(driver.driver_key, num, size, aspect_ratio, minimax_response_format),
            **dict(generation_params or {}),
        }
        snapshot_id = await _create_image_execution_snapshot(
            generation_context, db=db, user_id=user_id, run_id=run_id, job_id=job_id,
            aspect_ratio=aspect_ratio, image_count=num, image_size=size,
            prompt_compacted=prepared_prompt != prompt,
            reference_image_count=len(reference_images),
        )
        submission = await driver_kernel.execute_generation(
            driver_kernel.build_builtin_driver_registry(),
            driver_kernel.ImageCommand(
                prompt=prepared_prompt,
                reference_images=tuple(reference_images),
                params=params,
            ),
            replace(driver, execution_snapshot_id=snapshot_id) if snapshot_id else driver,
        )
        output = dict(submission.output)
        if submission.provider_task_id and not output.get("task_id"):
            output["task_id"] = submission.provider_task_id
        if snapshot_id:
            output["execution_snapshot_id"] = snapshot_id
        return output
    provider = (provider_name or "").lower()
    prepared_prompt = _prepare_image_prompt_for_provider(provider, prompt)
    if provider in ("volcano", "volcano_agent_plan"):
        return await service.generate_image(
            prompt=prepared_prompt, model=model_id, size=size, num=num,
            watermark=False,
            **({"image": list(reference_images)} if reference_images else {}),
        )
    if provider == "minimax":
        return await service.generate_image(
            prompt=prepared_prompt,
            model=model_id,
            aspect_ratio=aspect_ratio,
            n=num,
            response_format=minimax_response_format,
        )
    if provider == "openai":
        return await service.generate_image(
            prompt=prepared_prompt,
            model=model_id,
            size=openai_size,
            n=num,
            save_local=False,
        )
    raise HTTPException(status_code=400, detail=f"不支持的图像模型服务商: {provider_name}")


def _driver_image_params(
    driver_key: str, num: int, size: str, aspect_ratio: str, response_format: str,
) -> dict[str, Any]:
    if driver_key == "minimax_image_v1":
        return {"aspect_ratio": aspect_ratio, "n": num, "response_format": response_format}
    if driver_key == "volcano_ark_image_v3":
        return {"size": size, "num": num}
    return {}


def provider_task_id(result: Any, provider_name: Optional[str] = None) -> Optional[str]:
    if not isinstance(result, dict):
        return None
    provider = (provider_name or "").lower()
    if provider == "minimax":
        task_id = result.get("task_id")
        data = result.get("data")
        if not task_id and isinstance(data, dict):
            task_id = data.get("task_id")
        if not task_id and ("base_resp" in result or "metadata" in result):
            task_id = result.get("id")
        return task_id
    return result.get("task_id") or result.get("id")


def missing_image_result_message(provider_name: str, task_id: Optional[str]) -> str:
    provider = provider_name or "图像模型"
    if task_id:
        return (
            f"{provider} 模型已返回任务ID但未返回图片URL或图片数据，"
            "当前接口未拿到可展示图片。请重试，或检查该图像模型是否支持同步返回 URL/base64。"
        )
    return f"{provider} 模型未返回图片URL或图片数据"
