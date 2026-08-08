"""Single-step image generation polling for durable task workers."""

from datetime import timedelta
import uuid

from app.core.database import AsyncSessionLocal
from app.features.task_execution.domain import FAILED, RETRY_WAIT, SUCCEEDED, TaskOutcome
from app.models.asset import Asset
from app.models.shot import Shot
from app.services.live_canary_budget import settle_provider_operation


async def _settle_shot_accounting(session, shot: Shot, task_id: str, status: str, actual_rmb=None) -> None:
    accounting = (shot.extra_data or {}).get("live_canary_image_accounting") if isinstance(shot.extra_data, dict) else None
    if not isinstance(accounting, dict) or not accounting.get("operation_id"):
        return
    await settle_provider_operation(
        session, operation_id=accounting["operation_id"], user_id=shot.user_id,
        run_id=accounting["series_run_id"], reservation_id=accounting["reservation_id"],
        capability="image", job_id=shot.id, provider_task_id=task_id,
        provider_status=status, actual_rmb=actual_rmb,
    )


async def load_shot_image_status(session, user_id: str, task_id: str) -> dict:
    from app.core.api_key_utils import get_user_volcano_api_key
    from app.services.volcano_service import VolcanoService

    api_key = await get_user_volcano_api_key(session, user_id)
    return await _get_image_status(VolcanoService(api_key), task_id)


async def poll_shot_image_once(session, *, shot_id: str, task_id: str, user_id: str) -> TaskOutcome:
    shot = await session.get(Shot, shot_id)
    if not shot or shot.user_id != user_id:
        return TaskOutcome(FAILED, "镜头不存在", error_code="shot_missing")
    if shot.image_status == "succeeded" and shot.image_url and shot.image_asset_id:
        return TaskOutcome(SUCCEEDED, "参考图已生成", {"image_url": shot.image_url})

    status_result = await load_shot_image_status(session, user_id, task_id)
    status = status_result.get("status")
    if status == "failed":
        await _settle_shot_accounting(session, shot, task_id, "failed")
        shot.image_status = "failed"
        return TaskOutcome(FAILED, "供应商返回参考图生成失败", error_code="provider_failed")
    image_url = status_result.get("image_url")
    if status != "succeeded" or not image_url:
        return TaskOutcome(
            RETRY_WAIT,
            "供应商仍在生成参考图，稍后继续查询",
            error_code="provider_pending",
            retry_after=timedelta(seconds=2),
        )

    await _settle_shot_accounting(
        session,
        shot,
        task_id,
        "succeeded",
        status_result.get("actual_cost_rmb", status_result.get("cost_rmb")),
    )
    try:
        from app.services.media_persistence import persist_remote_media_url

        image_url = await persist_remote_media_url(
            image_url,
            media_type="image",
            subdir="images",
            prefix=f"shot-{shot_id[:8]}",
            max_bytes=20 * 1024 * 1024,
        ) or image_url
    except Exception:
        pass

    extra_data = shot.extra_data if isinstance(shot.extra_data, dict) else {}
    asset = Asset(
        id=str(uuid.uuid4()),
        user_id=user_id,
        category="scene",
        name=f"镜头{shot.shot_number}参考图",
        asset_type="image",
        url=image_url,
        source_job_id=task_id,
        source_prompt=extra_data.get("image_generation_prompt"),
        generation_params={
            "shot_id": shot_id,
            "prompt": extra_data.get("image_generation_prompt"),
            "style": extra_data.get("image_generation_style"),
            "style_prompt": extra_data.get("image_generation_style_prompt"),
            "provider": extra_data.get("image_generation_provider"),
            "model": extra_data.get("image_generation_model"),
            "task_id": task_id,
        },
    )
    session.add(asset)
    shot.image_url = image_url
    shot.image_status = "succeeded"
    shot.image_asset_id = asset.id
    return TaskOutcome(SUCCEEDED, "参考图已生成", {"image_url": image_url, "asset_id": asset.id})


async def mark_shot_image_poll_exhausted(session, shot_id: str) -> None:
    shot = await session.get(Shot, shot_id)
    if not shot or shot.image_status != "generating":
        return
    shot.image_status = "failed"
    shot.extra_data = {
        **(shot.extra_data if isinstance(shot.extra_data, dict) else {}),
        "image_generation_error": "参考图生成等待超时，请检查供应商任务后手动重试",
    }


async def poll_and_update_shot_image(shot_id: str, task_id: str, user_id: str) -> TaskOutcome:
    """Compatibility wrapper; performs one durable polling step only."""
    async with AsyncSessionLocal() as session:
        outcome = await poll_shot_image_once(session, shot_id=shot_id, task_id=task_id, user_id=user_id)
        await session.commit()
        return outcome


async def _get_image_status(volcano_service, task_id: str) -> dict:
    """Query image generation status from Volcano Engine."""
    try:
        import aiohttp
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {volcano_service.api_key}",
        }
        url = f"{volcano_service.ARK_BASE_URL}/images/generations/{task_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    return _parse_image_response(await response.json())
                return {"status": "unknown", "image_url": None}
    except Exception:
        return {"status": "unknown", "image_url": None}


def _parse_image_response(result: dict) -> dict:
    """Parse Volcano Engine image generation response."""
    if "data" in result and result["data"]:
        items = result["data"]
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                if first.get("url"):
                    return {"status": "succeeded", "image_url": first.get("url")}
                if first.get("base64"):
                    return {"status": "succeeded", "image_url": f"data:image/png;base64,{first.get('base64')}"}

    return {"status": result.get("status", "unknown"), "image_url": None}
