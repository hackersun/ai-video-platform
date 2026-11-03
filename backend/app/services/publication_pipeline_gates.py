"""P4: commercial fail-closed gates for publication pipelines (in-scope for one-click)."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from app.core.time_utils import utc_now
from app.models.publication_pipeline import NovelPublicationPipeline
from app.models.series_production_run import SeriesProductionRun
from app.services.publication_readiness import is_final_video_url


def commercial_gates_env_enabled() -> bool:
    return (os.getenv("PUBLICATION_PIPELINE_REQUIRE_COMMERCIAL_GATES") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def commercial_gates_required(pipeline: NovelPublicationPipeline) -> bool:
    gates = pipeline.gates if isinstance(pipeline.gates, dict) else {}
    if gates.get("require_commercial_gates") is True:
        return True
    return commercial_gates_env_enabled()


def evaluate_commercial_gates(
    pipeline: NovelPublicationPipeline,
    *,
    run: Optional[SeriesProductionRun],
    readiness: Optional[Dict[str, Any]],
    queue_evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    blockers: List[Dict[str, str]] = []

    if not pipeline.user_id or not pipeline.novel_id:
        blockers.append({"code": "identity_missing", "message": "缺少 user_id/novel_id 归属"})

    delivery = pipeline.delivery if isinstance(pipeline.delivery, dict) else {}
    visibility = str(delivery.get("visibility") or "private").lower()
    if visibility != "private":
        blockers.append(
            {
                "code": "private_media_required",
                "message": "商用门禁要求 delivery.visibility=private（已脚手架默认）",
            }
        )

    if not pipeline.final_video_url or not is_final_video_url(pipeline.final_video_url):
        blockers.append({"code": "final_video_missing", "message": "缺少最终 mp4/mov/webm"})

    readiness = readiness if isinstance(readiness, dict) else {}
    if readiness.get("is_publishable") is not True:
        blockers.append(
            {
                "code": "publication_not_ready",
                "message": "publication_readiness 未通过",
            }
        )

    media_tail: Dict[str, Any] = {}
    budget_policy: Dict[str, Any] = {}
    if run is not None:
        media_tail = ((run.gate_summary or {}).get("media_tail") or {})
        budget_policy = run.budget_policy if isinstance(run.budget_policy, dict) else {}
        if media_tail.get("result") != "passed":
            blockers.append(
                {
                    "code": "media_tail_not_passed",
                    "message": "Series Run media_tail 未通过",
                }
            )
        if budget_policy.get("live_canary") is True:
            # Read existing budget fields; do not invent a ledger.
            if not budget_policy:
                blockers.append({"code": "budget_policy_missing", "message": "缺少预算策略字段"})
    else:
        blockers.append({"code": "series_run_missing", "message": "商用门禁需要关联 Series Run"})

    media_policy = pipeline.media_policy if isinstance(pipeline.media_policy, dict) else {}
    if media_policy.get("shot_scope") == "anchor_shots_only":
        blockers.append(
            {
                "code": "anchor_shots_only_forbidden",
                "message": "商用门禁拒绝 anchor_shots_only",
            }
        )

    queue_evidence = queue_evidence if isinstance(queue_evidence, dict) else (
        (pipeline.gate_summary or {}).get("queue") if isinstance(pipeline.gate_summary, dict) else None
    )
    # Soft evidence: prefer present; if completely absent still pass but mark incomplete evidence.
    evidence_summary = {
        "pipeline_id": pipeline.id,
        "novel_id": pipeline.novel_id,
        "series_run_id": pipeline.series_run_id or (run.id if run else None),
        "final_video_url": pipeline.final_video_url,
        "publication_readiness": {
            "is_publishable": readiness.get("is_publishable"),
            "output_kind": readiness.get("output_kind"),
        },
        "media_tail": {
            "result": media_tail.get("result"),
            "closed_at": media_tail.get("closed_at"),
        },
        "delivery_visibility": visibility,
        "private_media": visibility == "private",
        "budget_policy_profile": budget_policy.get("profile"),
        "queue": queue_evidence or {},
        "evaluated_at": utc_now().isoformat(),
        "gate_blockers": blockers,
    }

    return {
        "passed": not blockers,
        "blockers": blockers,
        "evidence_summary": evidence_summary,
    }


__all__ = [
    "commercial_gates_env_enabled",
    "commercial_gates_required",
    "evaluate_commercial_gates",
]
