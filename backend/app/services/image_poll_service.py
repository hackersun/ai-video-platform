"""
Background image generation polling service.
"""
import uuid
import asyncio

from app.core.database import AsyncSessionLocal
from app.models.shot import Shot
from app.models.asset import Asset
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


async def poll_and_update_shot_image(shot_id: str, task_id: str, user_id: str):
    """
    Background polling: creates its own DB session. Call with asyncio.create_task().

    Note: VolcanoService generate_image is synchronous (returns immediately),
    but we still use a background task pattern so the HTTP response is returned
    quickly and the DB update happens after.
    """
    from app.core.api_key_utils import get_user_volcano_api_key
    from app.services.volcano_service import VolcanoService

    max_attempts = 60  # 2 min max polling (for future async models)

    for _ in range(max_attempts):
        await asyncio.sleep(2)
        try:
            async with AsyncSessionLocal() as session:
                # Try to get API key and check image generation status
                api_key = await get_user_volcano_api_key(session, user_id)
                volcano = VolcanoService(api_key)

                # Poll image status
                status_result = await _get_image_status(volcano, task_id)
                status = status_result.get("status")

                if status == "succeeded":
                    image_url = status_result.get("image_url")

                    shot = await session.get(Shot, shot_id)
                    if shot:
                        await _settle_shot_accounting(
                            session, shot, task_id, "succeeded",
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
                        shot.image_url = image_url
                        shot.image_status = "succeeded"

                        # Create asset
                        asset = Asset(
                            id=str(uuid.uuid4()),
                            user_id=user_id,
                            category="scene",
                            name=f"镜头{shot.shot_number}参考图",
                            asset_type="image",
                            url=image_url,
                            extra_data={"shot_id": shot_id},
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
                        shot.image_asset_id = asset.id
                        await session.commit()
                    return

                elif status == "failed":
                    shot = await session.get(Shot, shot_id)
                    if shot:
                        await _settle_shot_accounting(session, shot, task_id, "failed")
                        shot.image_status = "failed"
                        await session.commit()
                    return

        except Exception:
            continue

    async with AsyncSessionLocal() as session:
        shot = await session.get(Shot, shot_id)
        if shot and shot.image_status == "generating":
            shot.image_status = "failed"
            shot.extra_data = {
                **(shot.extra_data if isinstance(shot.extra_data, dict) else {}),
                "image_generation_error": "参考图生成超时：后台轮询未拿到图片URL，请重新生成或更换图像模型。",
                "image_generation_task_id": task_id,
            }
            await session.commit()


async def _get_image_status(volcano_service, task_id: str) -> dict:
    """
    Query image generation status from Volcano Engine.
    Falls back to synchronous result interpretation.
    """
    try:
        # Try the images status endpoint
        import aiohttp
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {volcano_service.api_key}"
        }
        url = f"{volcano_service.ARK_BASE_URL}/images/generations/{task_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    # Parse status from response
                    return _parse_image_response(result)
                else:
                    # Fallback: assume succeeded if the task_id is valid
                    # (for synchronous API responses embedded in the task)
                    return {"status": "unknown", "image_url": None}

    except Exception:
        # For synchronous API responses, the task_id might be the actual response
        # containing the image URL directly
        return {"status": "unknown", "image_url": None}


def _parse_image_response(result: dict) -> dict:
    """Parse Volcano Engine image generation response."""
    if "data" in result and result["data"]:
        items = result["data"]
        if isinstance(items, list) and len(items) > 0:
            first = items[0]
            if isinstance(first, dict):
                if first.get("url"):
                    return {"status": "succeeded", "image_url": first.get("url")}
                elif first.get("base64"):
                    return {"status": "succeeded", "image_url": f"data:image/png;base64,{first.get('base64')}"}

    status = result.get("status", "unknown")
    return {"status": status, "image_url": None}
