"""Shared platform Publication creation (synthesis + publication pipeline)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models.publication import Publication
from app.models.synthesis_job import SynthesisJob
from app.services.media_delivery import resolve_provider_media_url
from app.services.publication_readiness import evaluate_publication_readiness


class PublicationNotReadyError(ValueError):
    """Raised when final media is not publishable."""

    def __init__(self, readiness: Dict[str, Any]):
        self.readiness = readiness
        super().__init__("publication_not_ready")


def write_local_export_artifact(export_id: str, payload: Dict[str, Any]) -> tuple[Path, str]:
    export_dir = Path(__file__).resolve().parents[2] / "static" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = export_dir / f"{export_id}.json"
    artifact_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return artifact_path, f"/static/exports/{artifact_path.name}"


def _publication_delivery_media_type(key: str) -> str:
    if key == "video_url":
        return "video"
    if key == "srt_url":
        return "subtitle"
    return "manifest"


def _publication_provider_from_delivery(current_provider: str, delivery: Dict[str, Any]) -> str:
    if delivery.get("delivery_method") == "qiniu_object_upload":
        return "qiniu"
    return current_provider


async def _resolve_publication_delivery(
    db: AsyncSession,
    user_id: str,
    media_url: Optional[str],
    *,
    media_type: str,
) -> Dict[str, Any]:
    if not media_url:
        return {
            "source_url": media_url,
            "provider_url": None,
            "delivery_method": None,
            "omitted_reason": None,
        }
    try:
        return await resolve_provider_media_url(db, user_id, media_url, media_type=media_type)
    except Exception as exc:  # pragma: no cover - storage optional
        return {
            "source_url": media_url,
            "provider_url": None,
            "delivery_method": None,
            "omitted_reason": str(exc) or "对象存储交付失败，保留本地发布产物",
        }


async def _apply_publication_storage_delivery(
    db: AsyncSession,
    user_id: str,
    artifact_payload: Dict[str, Any],
) -> str:
    provider = "local"
    storage_delivery: Dict[str, Any] = {}
    render_artifacts = (
        artifact_payload.get("render_artifacts")
        if isinstance(artifact_payload.get("render_artifacts"), dict)
        else {}
    )
    delivery_targets: Dict[str, Optional[str]] = {
        "video_url": artifact_payload.get("video_url"),
        "srt_url": artifact_payload.get("srt_url") or render_artifacts.get("srt_url"),
        "timeline_url": artifact_payload.get("timeline_url") or render_artifacts.get("timeline_url"),
        "render_manifest_url": artifact_payload.get("render_manifest_url")
        or render_artifacts.get("render_manifest_url"),
        "source_manifest_url": artifact_payload.get("source_manifest_url")
        or render_artifacts.get("source_manifest_url"),
    }
    for key, source_url in delivery_targets.items():
        delivery = await _resolve_publication_delivery(
            db,
            user_id,
            source_url,
            media_type=_publication_delivery_media_type(key),
        )
        storage_delivery[key] = delivery
        provider_url = delivery.get("provider_url")
        if provider_url:
            if key == "video_url":
                artifact_payload["video_url"] = provider_url
            else:
                artifact_payload[key] = provider_url
                render_artifacts[key] = provider_url
            provider = _publication_provider_from_delivery(provider, delivery)
    if render_artifacts:
        artifact_payload["render_artifacts"] = render_artifacts
    artifact_payload["storage_delivery"] = storage_delivery
    artifact_payload["provider"] = provider
    return provider


async def _apply_export_artifact_storage_delivery(
    db: AsyncSession,
    user_id: str,
    artifact_payload: Dict[str, Any],
    *,
    local_export_url: str,
    current_provider: str,
) -> tuple[str, str]:
    delivery = await _resolve_publication_delivery(
        db,
        user_id,
        local_export_url,
        media_type="manifest",
    )
    storage_delivery = artifact_payload.setdefault("storage_delivery", {})
    storage_delivery["export_url"] = delivery
    artifact_payload["local_export_url"] = local_export_url
    provider_url = delivery.get("provider_url")
    provider = _publication_provider_from_delivery(current_provider, delivery)
    return provider, provider_url or local_export_url


def _can_export_preview_package(
    readiness: Dict[str, Any],
    extra_data: Dict[str, Any],
    metadata: Dict[str, Any],
) -> bool:
    render_artifacts = (
        extra_data.get("render_artifacts") if isinstance(extra_data.get("render_artifacts"), dict) else {}
    )
    return (
        bool(metadata.get("allow_preview_export"))
        and readiness.get("output_kind") == "preview_package"
        and extra_data.get("render_backend") == "local_artifact_package"
        and extra_data.get("render_status") == "rendered"
        and bool(render_artifacts.get("preview_url"))
    )


async def create_platform_publication(
    db: AsyncSession,
    *,
    user_id: str,
    title: str,
    video_url: Optional[str] = None,
    synthesis_job: Optional[SynthesisJob] = None,
    project_id: Optional[str] = None,
    visibility: str = "private",
    status: str = "published",
    metadata: Optional[Dict[str, Any]] = None,
    allow_preview_export: bool = False,
    publication_id: Optional[str] = None,
) -> Publication:
    """Create a platform Publication after fail-closed readiness checks.

    Pipeline callers must keep ``allow_preview_export=False`` so preview packages
    never become the commercial success path.
    """
    metadata = dict(metadata or {})
    job_extra_data = (
        synthesis_job.extra_data if synthesis_job and isinstance(synthesis_job.extra_data, dict) else {}
    )
    render_artifacts = (
        job_extra_data.get("render_artifacts")
        if isinstance(job_extra_data.get("render_artifacts"), dict)
        else {}
    )
    playback_video_url = video_url
    if synthesis_job and not playback_video_url:
        playback_video_url = synthesis_job.output_url
    if not playback_video_url:
        playback_video_url = metadata.get("source_output_url")

    readiness_source = dict(job_extra_data)
    readiness_source.update({k: v for k, v in metadata.items() if k in {
        "render_status", "render_backend", "output_kind", "production_graph_status",
    }})
    readiness = evaluate_publication_readiness(playback_video_url, readiness_source)
    preview_export = False
    if allow_preview_export and synthesis_job:
        preview_export = _can_export_preview_package(readiness, job_extra_data, metadata)
    if not readiness["is_publishable"] and not preview_export:
        raise PublicationNotReadyError(readiness)

    if visibility not in {"private", "project", "public"}:
        visibility = "private"
    if status not in {"draft", "succeeded", "published", "archived"}:
        status = "published"

    export_id = publication_id or str(uuid4())
    project_id = project_id or (synthesis_job.project_id if synthesis_job else None)
    source_manifest_url = render_artifacts.get("source_manifest_url") or job_extra_data.get("manifest_url")
    artifact_payload: Dict[str, Any] = {
        "id": export_id,
        "title": title,
        "provider": "local",
        "project_id": project_id,
        "synthesis_job_id": synthesis_job.id if synthesis_job else None,
        "source_output_url": playback_video_url,
        "video_url": render_artifacts.get("preview_url") if preview_export else playback_video_url,
        "cover_url": synthesis_job.cover_url if synthesis_job else metadata.get("cover_url"),
        "duration_seconds": synthesis_job.duration_seconds if synthesis_job else metadata.get("duration_seconds"),
        "metadata": metadata,
        "created_at": utc_now().isoformat(),
        "is_publishable": False if preview_export else True,
        "output_kind": "preview_package" if preview_export else "final_video",
        "preview_export": preview_export,
    }
    if synthesis_job:
        artifact_payload.update(
            {
                "render_artifacts": render_artifacts,
                "preview_url": render_artifacts.get("preview_url"),
                "srt_url": render_artifacts.get("srt_url"),
                "timeline_url": render_artifacts.get("timeline_url"),
                "render_manifest_url": render_artifacts.get("render_manifest_url"),
                "source_manifest_url": source_manifest_url,
                "render_status": job_extra_data.get("render_status"),
                "render_backend": job_extra_data.get("render_backend"),
                "render_source": job_extra_data.get("render_source"),
                "timeline_id": job_extra_data.get("render_timeline_id") or job_extra_data.get("timeline_id"),
            }
        )

    publication_provider = await _apply_publication_storage_delivery(db, user_id, artifact_payload)
    publication_video_url = artifact_payload.get("video_url")
    artifact_path, local_export_url = write_local_export_artifact(export_id, artifact_payload)
    publication_provider, export_url = await _apply_export_artifact_storage_delivery(
        db,
        user_id,
        artifact_payload,
        local_export_url=local_export_url,
        current_provider=publication_provider,
    )
    artifact_payload["provider"] = publication_provider
    artifact_payload["export_url"] = export_url
    artifact_path.write_text(
        json.dumps(artifact_payload, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )

    publication = Publication(
        id=export_id,
        user_id=user_id,
        project_id=project_id,
        synthesis_job_id=synthesis_job.id if synthesis_job else None,
        title=title,
        status=status if not preview_export else "succeeded",
        visibility=visibility,
        video_url=publication_video_url,
        cover_url=synthesis_job.cover_url if synthesis_job else metadata.get("cover_url"),
        duration_seconds=synthesis_job.duration_seconds if synthesis_job else metadata.get("duration_seconds"),
        format=metadata.get("format") or ("html" if preview_export else "mp4"),
        resolution=metadata.get("resolution") or "1080p",
        export_url=export_url,
        artifact_path=str(artifact_path),
        provider=publication_provider,
        publication_metadata=artifact_payload,
    )
    db.add(publication)
    await db.flush()
    return publication


__all__ = [
    "PublicationNotReadyError",
    "create_platform_publication",
    "write_local_export_artifact",
]
