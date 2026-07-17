"""Translate reference packages into provider content payloads."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.features.video_generation.constants import PROVIDER_VIDEO_WATERMARK_ENABLED
from app.services.seedance_contract import get_seedance_contract


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 0)


def _bool_arg(value: bool) -> str:
    return "true" if value else "false"


def _text_content(
    prompt: str,
    *,
    duration: int,
    resolution: str,
    camera_fixed: bool,
    watermark: bool,
) -> Dict[str, Any]:
    return {
        "type": "text",
        "text": (
            f"{prompt} --duration {duration} --resolution {resolution} "
            f"--camerafixed {_bool_arg(camera_fixed)} --watermark {_bool_arg(watermark)}"
        ),
    }


def _content_url(item: Any) -> Optional[str]:
    if not isinstance(item, dict):
        return None
    url = item.get("url")
    return str(url) if url else None


def _is_provider_ready_item(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    return (
        not item.get("canonical_asset_id")
        or bool(item.get("provider_binding_id"))
        or item.get("provider_reference_source") == "canonical_public_fallback"
    )


def _model_limit(model_limits: Optional[Dict[str, Any]], key: str, default: int) -> int:
    limits = model_limits if isinstance(model_limits, dict) else {}
    return _positive_int(limits.get(key), default)


def _limits_with_contract_caps(
    model_limits: Optional[Dict[str, Any]],
    *,
    contract: Any,
    enforce_contract: bool,
) -> Dict[str, Any]:
    limits = dict(model_limits) if isinstance(model_limits, dict) else {}
    image_limit = _model_limit(limits, "images", 1)
    video_limit = _model_limit(limits, "videos", 0)
    audio_limit = _model_limit(limits, "audios", 0)

    if enforce_contract:
        image_limit = min(image_limit, contract.max_images)
        video_limit = min(video_limit, contract.max_videos)
        audio_limit = min(audio_limit, contract.max_audios)

    return {
        **limits,
        "images": image_limit,
        "videos": video_limit,
        "audios": audio_limit,
    }


def _contract_metadata(contract: Any) -> Dict[str, Any]:
    is_seedance_2 = contract.model_family == "seedance_2"
    return {
        "contract_status": contract.status if is_seedance_2 else contract.contract_status,
        "contract_version": contract.contract_version,
        "verified_at": contract.verified_at,
        "reference_limits": contract.reference_limits if is_seedance_2 else {},
        "verification_gaps": list(contract.verification_gaps),
        "contract_model_family": contract.model_family,
        "contract_roles": {
            "image": contract.roles.image,
            "video": contract.roles.video,
            "audio": contract.roles.audio,
        },
        "contract_pricing_status": contract.pricing_status,
        "contract_agent_plan_multireference": contract.agent_plan_multireference,
    }


def apply_seedance_contract_limits(
    model_limits: Optional[Dict[str, Any]],
    *,
    model_id: Optional[str] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Clamp registry limits only for recognized Seedance 2 contracts."""
    contract = get_seedance_contract(model_id, provider)
    return _limits_with_contract_caps(
        model_limits,
        contract=contract,
        enforce_contract=contract.model_family == "seedance_2",
    )


def requires_provider_bindings(model_limits: Optional[Dict[str, Any]]) -> bool:
    """Match the Production OS multi-reference binding boundary.

    Legacy single-image models continue to use the existing media-delivery
    fallback. A provider binding becomes mandatory only for a package that
    exceeds that legacy shape.
    """
    limits = model_limits if isinstance(model_limits, dict) else {}
    return (
        _model_limit(limits, "images", 1) > 1
        or _model_limit(limits, "videos", 0) > 0
        or _model_limit(limits, "audios", 0) > 0
    )


def build_video_provider_content(
    *,
    final_prompt: str,
    duration: int,
    resolution: str,
    provider_image_url: Optional[str] = None,
    reference_package: Optional[Dict[str, Any]] = None,
    model_limits: Optional[Dict[str, Any]] = None,
    model_id: Optional[str] = None,
    provider: Optional[str] = None,
    camera_fixed: bool = False,
    watermark: bool = PROVIDER_VIDEO_WATERMARK_ENABLED,
) -> Dict[str, Any]:
    """Build Ark content while preserving the legacy single-image shape."""
    package = reference_package if isinstance(reference_package, dict) else {}
    contract = get_seedance_contract(model_id, provider)
    effective_limits = _limits_with_contract_caps(
        model_limits,
        contract=contract,
        enforce_contract=contract.model_family == "seedance_2",
    )
    image_limit = _model_limit(effective_limits, "images", 1)
    video_limit = _model_limit(effective_limits, "videos", 0)
    audio_limit = _model_limit(effective_limits, "audios", 0)
    contract_metadata = _contract_metadata(contract)
    raw_items = [
        *[item for item in package.get("images") or [] if isinstance(item, dict)],
        *[item for item in package.get("videos") or [] if isinstance(item, dict)],
        *[item for item in package.get("audios") or [] if isinstance(item, dict)],
    ]
    unbound_canonical_reference_count = sum(
        1 for item in raw_items
        if item.get("canonical_asset_id")
        and not item.get("provider_binding_id")
        and item.get("provider_reference_source") != "canonical_public_fallback"
    )
    package_images = [item for item in package.get("images") or [] if _content_url(item) and _is_provider_ready_item(item)]
    package_videos = [item for item in package.get("videos") or [] if _content_url(item) and _is_provider_ready_item(item)]
    package_audios = [item for item in package.get("audios") or [] if _content_url(item) and _is_provider_ready_item(item)]

    if image_limit <= 0 and video_limit <= 0 and audio_limit <= 0:
        content = [
            _text_content(
                final_prompt,
                duration=duration,
                resolution=resolution,
                camera_fixed=camera_fixed,
                watermark=watermark,
            )
        ]
        return {
            "content": content,
            "mode": "text_only",
            "metadata": {
                "mode": "text_only",
                "image_count": 0,
                "video_count": 0,
                "audio_count": 0,
                "dropped_image_count": len(package_images) + (1 if provider_image_url else 0),
                **({"unbound_canonical_reference_count": unbound_canonical_reference_count} if unbound_canonical_reference_count else {}),
                **contract_metadata,
            },
        }

    images = package_images[:image_limit] if image_limit > 0 else []
    videos = package_videos[:video_limit] if video_limit > 0 else []
    audios = package_audios[:audio_limit] if audio_limit > 0 else []

    if (image_limit > 1 or video_limit > 0 or audio_limit > 0) and (images or videos or audios):
        content: List[Dict[str, Any]] = [
            {
                "type": "image_url",
                "image_url": {"url": _content_url(item)},
                "role": contract.roles.image,
            }
            for item in images
        ]
        content.extend(
            {
                "type": "video_url",
                "video_url": {"url": _content_url(item)},
                "role": contract.roles.video,
            }
            for item in videos
        )
        content.extend(
            {
                "type": "audio_url",
                "audio_url": {"url": _content_url(item)},
                "role": contract.roles.audio,
            }
            for item in audios
        )
        at_reference_text = package.get("at_reference_text")
        prompt = f"{at_reference_text}\n{final_prompt}" if at_reference_text else final_prompt
        content.append(
            _text_content(
                prompt,
                duration=duration,
                resolution=resolution,
                camera_fixed=camera_fixed,
                watermark=watermark,
            )
        )
        return {
            "content": content,
            "mode": "multimodal",
            "metadata": {
                "mode": "multimodal",
                "image_count": len(images),
                "video_count": len(videos),
                "audio_count": len(audios),
                **({"unbound_canonical_reference_count": unbound_canonical_reference_count} if unbound_canonical_reference_count else {}),
                **contract_metadata,
            },
        }

    content = []
    single_image_url = provider_image_url or (_content_url(images[0]) if images else None)
    if single_image_url:
        content.append({"type": "image_url", "image_url": {"url": single_image_url}})
    content.append(
        _text_content(
            final_prompt,
            duration=duration,
            resolution=resolution,
            camera_fixed=camera_fixed,
            watermark=watermark,
        )
    )
    return {
        "content": content,
        "mode": "single_image",
        "metadata": {
            "mode": "single_image",
            "image_count": 1 if single_image_url else 0,
            "video_count": 0,
            "audio_count": 0,
            **({"unbound_canonical_reference_count": unbound_canonical_reference_count} if unbound_canonical_reference_count else {}),
            **contract_metadata,
        },
    }


def build_reference_package_metadata(
    reference_package: Optional[Dict[str, Any]],
    provider_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Return the compact job metadata persisted with generation tasks."""
    package = reference_package if isinstance(reference_package, dict) else {}
    items: List[Dict[str, Any]] = []
    for item in package.get("images") or []:
        if isinstance(item, dict):
            items.append({"type": "image", **item})
    for item in package.get("videos") or []:
        if isinstance(item, dict):
            items.append({"type": "video", **item})
    for item in package.get("audios") or []:
        if isinstance(item, dict):
            items.append({"type": "audio", **item})

    dropped_items = [item for item in package.get("dropped") or [] if isinstance(item, dict)]
    canonical_asset_ids = list(dict.fromkeys(
        str(item["canonical_asset_id"])
        for item in [*items, *dropped_items]
        if item.get("canonical_asset_id")
    ))
    provider_binding_ids = list(dict.fromkeys(
        str(item["provider_binding_id"])
        for item in items
        if item.get("provider_binding_id")
    ))
    return {
        **dict(provider_metadata or {}),
        "items": items,
        "dropped": dropped_items,
        "canonical_asset_ids": canonical_asset_ids,
        "provider_binding_ids": provider_binding_ids,
    }


def enrich_prompt_parameters_with_reference_contract(
    parameters: Dict[str, Any],
    provider_metadata: Dict[str, Any],
    model_limits: Optional[Dict[str, Any]] = None,
    model_protocol: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Attach the actual provider reference payload shape to job parameters."""
    params = dict(parameters or {})
    metadata = provider_metadata if isinstance(provider_metadata, dict) else {}
    limits = model_limits if isinstance(model_limits, dict) else {}
    protocol = model_protocol if isinstance(model_protocol, dict) else {}
    image_limit = _model_limit(limits, "images", 1)
    image_count = _positive_int(metadata.get("image_count"), 0)
    video_count = _positive_int(metadata.get("video_count"), 0)
    audio_count = _positive_int(metadata.get("audio_count"), 0)

    params["model_input_mode"] = protocol.get("input_mode") or (
        "text" if image_limit <= 0 else "reference_images_text" if image_limit > 1 else "image_text"
    )
    params["provider_reference_image_count"] = image_count
    params["provider_reference_video_count"] = video_count
    params["provider_reference_audio_count"] = audio_count
    params["reference_image_capacity"] = image_limit
    params["image_url_sent"] = image_count > 0
    if not params["image_url_sent"]:
        params["provider_image_url"] = None
    if metadata.get("dropped_image_count"):
        params["dropped_reference_image_count"] = metadata["dropped_image_count"]
    return params
