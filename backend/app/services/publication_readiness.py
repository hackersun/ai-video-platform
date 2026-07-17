"""
Publication readiness helpers for final rendered media.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


FINAL_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}
NON_FINAL_RENDER_STATUSES = {"adapter_ready", "cloud_pending", "preflight_failed"}


def is_final_video_url(url: Optional[str]) -> bool:
    if not url:
        return False
    parsed = urlparse(str(url))
    path = parsed.path or str(url)
    return any(path.lower().endswith(extension) for extension in FINAL_VIDEO_EXTENSIONS)


def evaluate_publication_readiness(
    output_url: Optional[str],
    extra_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    extra = extra_data if isinstance(extra_data, dict) else {}
    render_status = extra.get("render_status")
    render_backend = extra.get("render_backend")
    output_kind = extra.get("output_kind")
    issues: List[Dict[str, Any]] = []

    if extra.get("production_graph_status") == "superseded_review_required":
        issues.append({
            "code": "production_graph_superseded",
            "message": "Production Graph 已变更，该成片需要复审或重新生成后才能再次发布",
            "source_event_id": extra.get("source_event_id"),
            "source_event_version": extra.get("source_event_version"),
        })

    if render_backend == "local_artifact_package" or output_kind == "preview_package":
        issues.append({
            "code": "preview_package_not_publishable",
            "message": "当前只有本地审阅包，需要生成真实视频文件后才能发布",
        })

    if render_status in NON_FINAL_RENDER_STATUSES:
        issues.append({
            "code": "render_not_final",
            "message": "渲染任务尚未产出最终视频文件",
        })
    elif render_status != "rendered":
        issues.append({
            "code": "render_status_not_rendered",
            "message": "缺少最终渲染完成状态，不能把占位合成记录当作生产成片发布",
        })

    if not is_final_video_url(output_url):
        issues.append({
            "code": "final_video_missing",
            "message": "缺少 mp4/mov/webm 最终视频 output_url",
        })

    is_publishable = not issues
    if is_publishable:
        normalized_output_kind = "final_video"
    elif output_kind:
        normalized_output_kind = str(output_kind)
    elif render_backend == "local_artifact_package":
        normalized_output_kind = "preview_package"
    elif render_backend == "ffmpeg_cloud":
        normalized_output_kind = "cloud_request"
    else:
        normalized_output_kind = "missing_final_video"

    if is_publishable:
        action = None
    elif render_status in {"adapter_ready", "cloud_pending"}:
        action = "wait_cloud_render"
    elif render_status == "preflight_failed":
        action = "fix_render_preflight"
    else:
        action = "render_final_video"

    return {
        "is_publishable": is_publishable,
        "output_kind": normalized_output_kind,
        "publication_blockers": issues,
        "action": action,
        "render_status": render_status,
    }
