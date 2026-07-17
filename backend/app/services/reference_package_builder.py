"""Build provider-safe multimodal reference packages for shot video generation."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset, Novel, Shot, StoryEntity
from app.services.entity_ref_normalizer import normalize_entity_refs
from app.services.story_entity_lifecycle import is_entity_production_visible
from app.services.media_delivery import is_cloud_accessible_http_url
from app.services.provider_asset_binding_service import (
    ProviderBindingChecksumMismatchError,
    ProviderBindingModelIncompatibleError,
    ProviderBindingNotFoundError,
    ProviderBindingNotVerifiedError,
    ProviderBindingUploadError,
    resolve_provider_binding,
)


VIEW_LABELS = {
    "front": "正面",
    "side": "侧面",
    "back": "背面",
    "establishing": "全景",
    "layout": "空间布局",
    "detail": "细节",
    "lighting": "光影",
    "main": "主视图",
}


@dataclass(frozen=True)
class ReferenceCandidate:
    source_url: Optional[str]
    role_tag: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None
    view_key: Optional[str] = None
    source: Optional[str] = None
    canonical_asset_id: Optional[str] = None
    canonical_asset_version: Optional[int] = None
    canonical_checksum: Optional[str] = None


def _json_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 0)


def _ref_entity_id(ref: Dict[str, Any]) -> Optional[str]:
    value = ref.get("entity_id") or ref.get("id") or ref.get("story_entity_id") or ref.get("character_id")
    return str(value) if value else None


def _ref_name(ref: Dict[str, Any]) -> Optional[str]:
    value = ref.get("name") or ref.get("entity_name") or ref.get("canonical_name")
    return str(value) if value else None


def _normalize_refs(refs: Iterable[Any], entity_type: str) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in refs:
        if isinstance(item, str):
            ref = {"entity_id": item, "entity_type": entity_type}
        elif isinstance(item, dict):
            ref = dict(item)
            entity_id = _ref_entity_id(ref)
            if entity_id:
                ref["entity_id"] = entity_id
            ref.setdefault("entity_type", entity_type)
        else:
            continue
        key = str(ref.get("entity_id") or ref.get("name") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        normalized.append(ref)
    return normalized


def _merge_refs(primary: List[Dict[str, Any]], secondary: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for ref in [*primary, *secondary]:
        key = str(ref.get("entity_id") or ref.get("name") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        merged.append(ref)
    return merged


async def _entity_names(db: AsyncSession, user_id: str, refs: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    ids = [str(ref["entity_id"]) for ref in refs if ref.get("entity_id")]
    if not ids:
        return {}
    result = await db.execute(
        select(StoryEntity).where(
            and_(
                StoryEntity.user_id == user_id,
                StoryEntity.id.in_(ids),
            )
        )
    )
    return {entity.id: entity.name for entity in result.scalars().all() if entity.name}


async def _production_entity_names(
    db: AsyncSession,
    user_id: str,
    refs: Iterable[Dict[str, Any]],
) -> tuple[Dict[str, str], set[str]]:
    ids = [str(ref["entity_id"]) for ref in refs if ref.get("entity_id")]
    if not ids:
        return {}, set()
    result = await db.execute(
        select(StoryEntity).where(
            and_(
                StoryEntity.user_id == user_id,
                StoryEntity.id.in_(ids),
            )
        )
    )
    visible_names: Dict[str, str] = {}
    hidden_ids: set[str] = set()
    for entity in result.scalars().all():
        if is_entity_production_visible(entity):
            if entity.name:
                visible_names[entity.id] = entity.name
        else:
            hidden_ids.add(entity.id)
    return visible_names, hidden_ids


def _name_for(ref: Dict[str, Any], names: Dict[str, str]) -> Optional[str]:
    entity_id = str(ref.get("entity_id")) if ref.get("entity_id") else None
    return _ref_name(ref) or (names.get(entity_id) if entity_id else None)


def _asset_view_key(asset: Asset) -> Optional[str]:
    params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
    value = params.get("view_key") or params.get("asset_subtype")
    return str(value) if value else None


def _asset_checksum(asset: Asset) -> Optional[str]:
    params = asset.generation_params if isinstance(asset.generation_params, dict) else {}
    value = params.get("checksum") or params.get("content_checksum") or params.get("sha256")
    return str(value) if value else None


async def _find_locked_view_asset(
    db: AsyncSession,
    user_id: str,
    *,
    entity_type: str,
    entity_id: str,
    view_key: str,
) -> Optional[Asset]:
    entity_filter = Asset.entity_id == entity_id
    if entity_type == "character":
        entity_filter = or_(Asset.entity_id == entity_id, Asset.character_id == entity_id)

    result = await db.execute(
        select(Asset)
        .where(
            and_(
                Asset.is_active == True,
                Asset.is_locked == True,
                or_(Asset.user_id == user_id, Asset.is_public == True),
                Asset.category == entity_type,
                entity_filter,
            )
        )
        .order_by(desc(Asset.is_final), desc(Asset.is_locked), desc(Asset.version), desc(Asset.updated_at), Asset.id)
        .limit(50)
    )
    for asset in result.scalars().all():
        if _asset_view_key(asset) == view_key and (asset.url or asset.thumbnail_url):
            return asset
    return None


async def _style_anchor_candidate(
    db: AsyncSession,
    user_id: str,
    lineage: Dict[str, Any],
) -> Optional[ReferenceCandidate]:
    novel = lineage.get("novel")
    if not novel and lineage.get("novel_id"):
        novel = await db.get(Novel, str(lineage["novel_id"]))
    cover_url = getattr(novel, "cover_url", None)
    if cover_url:
        return ReferenceCandidate(
            source_url=cover_url,
            role_tag="style_anchor",
            entity_type="style",
            entity_id=getattr(novel, "id", None),
            entity_name=getattr(novel, "title", None),
            view_key="cover",
            source="novel_cover",
        )

    result = await db.execute(
        select(Asset)
        .where(
            and_(
                Asset.is_active == True,
                or_(Asset.user_id == user_id, Asset.is_public == True),
                Asset.category == "style",
                or_(Asset.is_locked == True, Asset.is_final == True),
            )
        )
        .order_by(desc(Asset.is_final), desc(Asset.is_locked), desc(Asset.version), desc(Asset.updated_at), Asset.id)
        .limit(1)
    )
    asset = result.scalar_one_or_none()
    if not asset or not (asset.url or asset.thumbnail_url):
        return None
    return ReferenceCandidate(
        source_url=asset.url or asset.thumbnail_url,
        role_tag="style_anchor",
        entity_type="style",
        entity_id=asset.entity_id or asset.id,
        entity_name=asset.name,
        view_key=_asset_view_key(asset) or "style",
        source="style_asset",
        canonical_asset_id=asset.id,
        canonical_asset_version=asset.version or 1,
        canonical_checksum=_asset_checksum(asset),
    )


async def _image_candidates(
    db: AsyncSession,
    user_id: str,
    *,
    shot: Shot,
    lineage: Dict[str, Any],
) -> List[ReferenceCandidate]:
    extra = _json_dict(getattr(shot, "extra_data", None))
    entity_refs = normalize_entity_refs(extra.get("entity_refs"))
    shot_character_refs = _normalize_refs(_json_list(getattr(shot, "character_refs", None)), "character")
    character_refs = _merge_refs(shot_character_refs, entity_refs.get("characters", []))
    scene_refs = entity_refs.get("scenes", [])
    prop_refs = entity_refs.get("props", [])

    all_refs = [*character_refs, *scene_refs, *prop_refs]
    names, hidden_entity_ids = await _production_entity_names(db, user_id, all_refs)
    character_refs = [ref for ref in character_refs if str(ref.get("entity_id")) not in hidden_entity_ids]
    scene_refs = [ref for ref in scene_refs if str(ref.get("entity_id")) not in hidden_entity_ids]
    prop_refs = [ref for ref in prop_refs if str(ref.get("entity_id")) not in hidden_entity_ids]
    candidates: List[ReferenceCandidate] = []

    protagonist = character_refs[0] if character_refs else None
    protagonist_id = str(protagonist.get("entity_id")) if protagonist and protagonist.get("entity_id") else None
    if protagonist_id:
        for view_key in ("front", "side", "back"):
            asset = await _find_locked_view_asset(
                db,
                user_id,
                entity_type="character",
                entity_id=protagonist_id,
                view_key=view_key,
            )
            if asset:
                candidates.append(
                    ReferenceCandidate(
                        source_url=asset.url or asset.thumbnail_url,
                        role_tag="protagonist",
                        entity_type="character",
                        entity_id=protagonist_id,
                        entity_name=_name_for(protagonist, names) or asset.name,
                        view_key=view_key,
                        source="locked_asset",
                        canonical_asset_id=asset.id,
                        canonical_asset_version=asset.version or 1,
                        canonical_checksum=_asset_checksum(asset),
                    )
                )

    for scene_ref in scene_refs[:1]:
        scene_id = str(scene_ref.get("entity_id")) if scene_ref.get("entity_id") else None
        if not scene_id:
            continue
        asset = await _find_locked_view_asset(
            db,
            user_id,
            entity_type="scene",
            entity_id=scene_id,
            view_key="establishing",
        )
        if asset:
            candidates.append(
                ReferenceCandidate(
                    source_url=asset.url or asset.thumbnail_url,
                    role_tag="scene",
                    entity_type="scene",
                    entity_id=scene_id,
                    entity_name=_name_for(scene_ref, names) or asset.name,
                    view_key="establishing",
                    source="locked_asset",
                    canonical_asset_id=asset.id,
                    canonical_asset_version=asset.version or 1,
                    canonical_checksum=_asset_checksum(asset),
                )
            )

    for prop_ref in prop_refs[:2]:
        prop_id = str(prop_ref.get("entity_id")) if prop_ref.get("entity_id") else None
        if not prop_id:
            continue
        asset = await _find_locked_view_asset(
            db,
            user_id,
            entity_type="prop",
            entity_id=prop_id,
            view_key="main",
        )
        if asset:
            candidates.append(
                ReferenceCandidate(
                    source_url=asset.url or asset.thumbnail_url,
                    role_tag="prop",
                    entity_type="prop",
                    entity_id=prop_id,
                    entity_name=_name_for(prop_ref, names) or asset.name,
                    view_key="main",
                    source="locked_asset",
                    canonical_asset_id=asset.id,
                    canonical_asset_version=asset.version or 1,
                    canonical_checksum=_asset_checksum(asset),
                )
            )

    for character_ref in character_refs:
        entity_id = str(character_ref.get("entity_id")) if character_ref.get("entity_id") else None
        if not entity_id or entity_id == protagonist_id:
            continue
        asset = await _find_locked_view_asset(
            db,
            user_id,
            entity_type="character",
            entity_id=entity_id,
            view_key="front",
        )
        if asset:
            candidates.append(
                ReferenceCandidate(
                    source_url=asset.url or asset.thumbnail_url,
                    role_tag="character",
                    entity_type="character",
                    entity_id=entity_id,
                    entity_name=_name_for(character_ref, names) or asset.name,
                    view_key="front",
                    source="locked_asset",
                    canonical_asset_id=asset.id,
                    canonical_asset_version=asset.version or 1,
                    canonical_checksum=_asset_checksum(asset),
                )
            )

    style_anchor = await _style_anchor_candidate(db, user_id, lineage)
    if style_anchor:
        candidates.append(style_anchor)

    return candidates


async def _resolve_public_url(
    resolve_public_url: Callable[..., Any],
    db: AsyncSession,
    user_id: str,
    source_url: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    if not source_url:
        return None, "参考资源缺少 URL"

    result = resolve_public_url(db, user_id, source_url)
    if inspect.isawaitable(result):
        result = await result

    reason: Optional[str] = None
    public_url: Optional[str] = None
    if isinstance(result, str):
        public_url = result
    elif isinstance(result, dict):
        public_url = (
            result.get("provider_url")
            or result.get("provider_image_url")
            or result.get("public_url")
            or result.get("url")
        )
        reason = (
            result.get("omitted_reason")
            or result.get("image_url_omitted_reason")
            or result.get("reason")
        )

    if public_url and is_cloud_accessible_http_url(public_url):
        return public_url, None
    if public_url:
        return None, "解析后的参考资源不是公网 http(s) URL"
    return None, reason or "参考资源不是公网 URL"


def _drop(candidate: ReferenceCandidate, reason: str) -> Dict[str, Any]:
    return {
        "reason": reason,
        "entity_name": candidate.entity_name,
        "view_key": candidate.view_key,
        "entity_type": candidate.entity_type,
        "entity_id": candidate.entity_id,
        "role_tag": candidate.role_tag,
        "source": candidate.source,
    }


def _image_item(candidate: ReferenceCandidate, public_url: str, at_index: int) -> Dict[str, Any]:
    item = {
        "url": public_url,
        "role_tag": candidate.role_tag,
        "entity_type": candidate.entity_type,
        "entity_id": candidate.entity_id,
        "view_key": candidate.view_key,
        "at_index": at_index,
    }
    if candidate.canonical_asset_id:
        item["canonical_asset_id"] = candidate.canonical_asset_id
        item["canonical_asset_version"] = candidate.canonical_asset_version or 1
        if candidate.canonical_checksum:
            item["canonical_checksum"] = candidate.canonical_checksum
    return item


def _binding_kind(media_type: str) -> str:
    return {
        "image": "reference_image",
        "video": "reference_video",
        "audio": "reference_audio",
    }[media_type]


async def bind_reference_package(
    db: AsyncSession,
    reference_package: Dict[str, Any],
    *,
    provider_id: str,
    model_id: str,
    allow_canonical_public_fallback: bool = False,
) -> Dict[str, Any]:
    """Resolve canonical references into verified model-specific references.

    The input is copied and never mutated, preserving canonical selection as a
    provider-neutral artifact that can be reused for another model.
    """
    package = reference_package if isinstance(reference_package, dict) else {}
    converted: Dict[str, Any] = {
        **package,
        "images": [],
        "videos": [],
        "audios": [],
        "dropped": [dict(item) for item in package.get("dropped") or [] if isinstance(item, dict)],
        "provider_id": provider_id,
        "model_id": model_id,
    }
    error_reasons = {
        ProviderBindingNotFoundError: "provider_binding_not_found",
        ProviderBindingNotVerifiedError: "provider_binding_not_verified",
        ProviderBindingChecksumMismatchError: "provider_binding_checksum_mismatch",
        ProviderBindingModelIncompatibleError: "provider_binding_model_incompatible",
        ProviderBindingUploadError: "provider_binding_upload_failed",
    }
    for media_key, media_type in (("images", "image"), ("videos", "video"), ("audios", "audio")):
        for original in package.get(media_key) or []:
            if not isinstance(original, dict):
                continue
            item = dict(original)
            asset_id = item.get("canonical_asset_id")
            asset_version = item.get("canonical_asset_version")
            if not asset_id or asset_version is None:
                if item.get("url"):
                    converted[media_key].append(item)
                continue
            try:
                binding = await resolve_provider_binding(
                    db,
                    asset_id=str(asset_id),
                    asset_version=int(asset_version),
                    provider_id=provider_id,
                    model_id=model_id,
                    binding_kind=_binding_kind(media_type),
                    asset_checksum=item.get("canonical_checksum"),
                )
            except tuple(error_reasons) as exc:
                if (
                    allow_canonical_public_fallback
                    and isinstance(exc, (ProviderBindingNotFoundError, ProviderBindingModelIncompatibleError))
                    and is_cloud_accessible_http_url(item.get("url"))
                ):
                    converted[media_key].append({
                        **item,
                        "provider_reference_source": "canonical_public_fallback",
                    })
                    continue
                reason = next(value for error_type, value in error_reasons.items() if isinstance(exc, error_type))
                converted["dropped"].append({
                    **{key: value for key, value in item.items() if key != "url"},
                    "reason": reason,
                })
                continue
            # Current provider payload adapters accept public URLs, not opaque
            # provider asset IDs. Never substitute the canonical URL here: it
            # has not been verified as the selected model's provider binding.
            provider_url = binding.public_url
            if not provider_url:
                converted["dropped"].append({
                    **{key: value for key, value in item.items() if key != "url"},
                    "reason": "provider_binding_public_url_required",
                })
                continue
            converted[media_key].append({
                **item,
                "url": provider_url,
                "provider_asset_id": binding.provider_asset_id,
                "provider_binding_id": binding.id,
            })
    converted["reference_image"] = converted["images"][0].get("url") if converted["images"] else None
    return converted


def _reference_phrase(item: Dict[str, Any], candidate: ReferenceCandidate) -> str:
    entity_name = candidate.entity_name or "参考对象"
    view_label = VIEW_LABELS.get(str(candidate.view_key), str(candidate.view_key or "参考"))
    if candidate.role_tag == "protagonist":
        return f"@图{item['at_index']}为主角{entity_name}{view_label}形象基准"
    if candidate.role_tag == "scene":
        return f"@图{item['at_index']}为场景{entity_name}{view_label}基准"
    if candidate.role_tag == "prop":
        return f"@图{item['at_index']}为道具{entity_name}{view_label}基准"
    if candidate.role_tag == "style_anchor":
        return f"@图{item['at_index']}为作品{entity_name}风格基准"
    return f"@图{item['at_index']}为角色{entity_name}{view_label}形象基准"


async def _previous_video_candidates(
    db: AsyncSession,
    user_id: str,
    *,
    shot: Shot,
) -> List[ReferenceCandidate]:
    storyboard_id = getattr(shot, "storyboard_id", None)
    shot_number = getattr(shot, "shot_number", None)
    if not storyboard_id or shot_number is None:
        return []

    result = await db.execute(
        select(Shot)
        .where(
            and_(
                Shot.user_id == user_id,
                Shot.storyboard_id == storyboard_id,
                Shot.shot_number < shot_number,
                Shot.video_status == "succeeded",
                Shot.video_url.is_not(None),
            )
        )
        .order_by(desc(Shot.shot_number), desc(Shot.updated_at), Shot.id)
        .limit(1)
    )
    previous_shot = result.scalar_one_or_none()
    if not previous_shot:
        return []
    return [
        ReferenceCandidate(
            source_url=previous_shot.video_url,
            role_tag="previous_shot",
            entity_type="video",
            entity_id=previous_shot.id,
            entity_name=None,
            view_key=None,
            source="previous_shot",
        )
    ]


async def _audio_candidates(
    db: AsyncSession,
    user_id: str,
    *,
    shot: Shot,
) -> List[ReferenceCandidate]:
    candidates: List[ReferenceCandidate] = []
    if getattr(shot, "audio_url", None):
        candidates.append(
            ReferenceCandidate(
                source_url=shot.audio_url,
                role_tag="shot_audio",
                entity_type="audio",
                entity_id=shot.id,
                source="shot_audio",
            )
        )

    result = await db.execute(
        select(Asset)
        .where(
            and_(
                Asset.is_active == True,
                Asset.is_locked == True,
                or_(Asset.user_id == user_id, Asset.is_public == True),
                or_(Asset.asset_type == "audio", Asset.category.in_(["voice", "music", "sfx"])),
            )
        )
        .order_by(desc(Asset.is_final), desc(Asset.is_locked), desc(Asset.version), desc(Asset.updated_at), Asset.id)
        .limit(10)
    )
    for asset in result.scalars().all():
        if not asset.url:
            continue
        candidates.append(
            ReferenceCandidate(
                source_url=asset.url,
                role_tag=asset.category or "audio",
                entity_type="audio",
                entity_id=asset.entity_id or asset.id,
                entity_name=asset.name,
                source="locked_asset",
                canonical_asset_id=asset.id,
                canonical_asset_version=asset.version or 1,
                canonical_checksum=_asset_checksum(asset),
            )
        )
    return candidates


async def _build_single_image_package(
    db: AsyncSession,
    user_id: str,
    *,
    shot: Shot,
    lineage: Dict[str, Any],
    resolve_public_url: Callable[..., Any],
) -> Dict[str, Any]:
    dropped: List[Dict[str, Any]] = []
    candidate = None
    source = getattr(shot, "image_url", None)
    if source:
        candidate = ReferenceCandidate(
            source_url=source,
            role_tag="reference_image",
            source="shot_image",
        )
    else:
        candidates = await _image_candidates(db, user_id, shot=shot, lineage=lineage)
        candidate = candidates[0] if candidates else None

    images: List[Dict[str, Any]] = []
    reference_image = None
    reference_image_source = None
    if candidate:
        public_url, reason = await _resolve_public_url(resolve_public_url, db, user_id, candidate.source_url)
        if public_url:
            images.append(_image_item(candidate, public_url, 1))
            reference_image = public_url
            reference_image_source = candidate.source
        else:
            dropped.append(_drop(candidate, reason or "参考资源不是公网 URL"))

    return {
        "images": images,
        "videos": [],
        "audios": [],
        "at_reference_text": None,
        "dropped": dropped,
        "mode": "single_image",
        "reference_image": reference_image,
        "reference_image_source": reference_image_source,
    }


async def build_reference_package(
    db: AsyncSession,
    user_id: str,
    *,
    shot: Shot,
    lineage: Dict[str, Any],
    model_limits: Dict[str, Any],
    resolve_public_url: Callable[..., Any],
) -> Dict[str, Any]:
    """Assemble a provider-safe reference package without calling providers."""
    limits = model_limits if isinstance(model_limits, dict) else {}
    image_limit = _positive_int(limits.get("images"), 1)
    video_limit = _positive_int(limits.get("videos"), 0)
    audio_limit = _positive_int(limits.get("audios"), 0)
    supports_at_reference = bool(limits.get("at_reference"))

    if image_limit <= 1 and video_limit <= 0 and audio_limit <= 0:
        return await _build_single_image_package(
            db,
            user_id,
            shot=shot,
            lineage=lineage or {},
            resolve_public_url=resolve_public_url,
        )

    dropped: List[Dict[str, Any]] = []
    images: List[Dict[str, Any]] = []
    accepted_candidates: List[ReferenceCandidate] = []
    if 0 < image_limit <= 1:
        single_image_package = await _build_single_image_package(
            db,
            user_id,
            shot=shot,
            lineage=lineage or {},
            resolve_public_url=resolve_public_url,
        )
        images = single_image_package.get("images") or []
        dropped.extend(single_image_package.get("dropped") or [])
    elif image_limit > 1:
        for candidate in await _image_candidates(db, user_id, shot=shot, lineage=lineage or {}):
            if len(images) >= image_limit:
                dropped.append(_drop(candidate, "exceeds_model_reference_image_limit"))
                continue
            public_url, reason = await _resolve_public_url(resolve_public_url, db, user_id, candidate.source_url)
            if not public_url:
                dropped.append(_drop(candidate, reason or "参考资源不是公网 URL"))
                continue
            item = _image_item(candidate, public_url, len(images) + 1)
            images.append(item)
            accepted_candidates.append(candidate)

    videos: List[Dict[str, Any]] = []
    if video_limit > 0:
        for candidate in await _previous_video_candidates(db, user_id, shot=shot):
            if len(videos) >= video_limit:
                dropped.append(_drop(candidate, "exceeds_model_reference_video_limit"))
                continue
            public_url, reason = await _resolve_public_url(resolve_public_url, db, user_id, candidate.source_url)
            if not public_url:
                dropped.append(_drop(candidate, reason or "参考视频不是公网 URL"))
                continue
            videos.append(
                {
                    "url": public_url,
                    "role_tag": candidate.role_tag,
                    "source_shot_id": candidate.entity_id,
                    "at_index": len(videos) + 1,
                }
            )

    audios: List[Dict[str, Any]] = []
    if audio_limit > 0:
        for candidate in await _audio_candidates(db, user_id, shot=shot):
            if len(audios) >= audio_limit:
                dropped.append(_drop(candidate, "exceeds_model_reference_audio_limit"))
                continue
            public_url, reason = await _resolve_public_url(resolve_public_url, db, user_id, candidate.source_url)
            if not public_url:
                dropped.append(_drop(candidate, reason or "参考音频不是公网 URL"))
                continue
            audios.append(
                {
                    "url": public_url,
                    "role_tag": candidate.role_tag,
                    "source_id": candidate.entity_id,
                    "at_index": len(audios) + 1,
                }
            )

    at_reference_text = None
    if supports_at_reference and images:
        at_reference_text = "；".join(
            _reference_phrase(item, candidate)
            for item, candidate in zip(images, accepted_candidates)
        )

    return {
        "images": images,
        "videos": videos,
        "audios": audios,
        "at_reference_text": at_reference_text,
        "dropped": dropped,
        "mode": "multimodal",
        "reference_image": images[0]["url"] if images else None,
        "reference_image_source": images[0]["role_tag"] if images else None,
    }
