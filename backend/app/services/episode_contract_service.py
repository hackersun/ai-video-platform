from __future__ import annotations

import hashlib
import json
from typing import Any, Dict
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.time_utils import utc_now
from app.models import Workflow
from app.services.production_bible import build_production_bible_summary
from app.services.production_graph_service import build_episode_state_snapshot, project_story_state


VOLATILE_HASH_KEYS = {
    "generated_at",
    "snapshot_at",
    "locked_at",
    "updated_at",
    "created_at",
    "approved_at",
}
UNORDERED_TOP_LEVEL_LIST_KEYS = {
    "characters",
    "scenes",
    "props",
    "events",
    "voices",
    "missing_requirements",
}
UNORDERED_NESTED_LIST_KEYS = {"asset_ids"}


def _hash_sort_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _should_sort_hash_list(path: tuple[str, ...]) -> bool:
    if not path:
        return False
    key = path[-1]
    if len(path) == 1 and key in UNORDERED_TOP_LEVEL_LIST_KEYS:
        return True
    if key in UNORDERED_NESTED_LIST_KEYS:
        return True
    if key == "items" and "missing_requirements" in path:
        return True
    return False


def _canonicalize_hash_payload(value: Any, path: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        return {
            key: _canonicalize_hash_payload(item, (*path, key))
            for key, item in value.items()
            if key not in VOLATILE_HASH_KEYS
        }
    if isinstance(value, list):
        items = [_canonicalize_hash_payload(item, (*path, "[]")) for item in value]
        return sorted(items, key=_hash_sort_key) if _should_sort_hash_list(path) else items
    if isinstance(value, tuple):
        items = [_canonicalize_hash_payload(item, (*path, "[]")) for item in value]
        return sorted(items, key=_hash_sort_key) if _should_sort_hash_list(path) else items
    return value


def stable_hash(value: Dict[str, Any]) -> str:
    payload = json.dumps(
        _canonicalize_hash_payload(value),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _episode_index(workflow: Workflow) -> int:
    metadata = workflow.metadata_ if isinstance(workflow.metadata_, dict) else {}
    value = metadata.get("episode_index") or metadata.get("episode_number") or 1
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


async def lock_episode_contract(
    db: AsyncSession,
    user_id: str,
    workflow_id: str,
    *,
    commit: bool = True,
    exact_preflight_snapshot: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    workflow = (
        await db.execute(select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id))
    ).scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")
    if not workflow.novel_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="工作流没有绑定小说")

    bible = await build_production_bible_summary(
        db, user_id, workflow.novel_id, as_of_chapter_id=workflow.chapter_id
    )
    episode_index = _episode_index(workflow)
    opening_snapshot = (
        await build_episode_state_snapshot(
            db,
            user_id=user_id,
            novel_id=workflow.novel_id,
            episode_index=episode_index - 1,
        )
        if episode_index > 1
        else {"state": {"entities": {}, "world": {}}, "applied_event_ids": [], "unresolved_conflicts": []}
    )
    closing_snapshot = await build_episode_state_snapshot(
        db,
        user_id=user_id,
        novel_id=workflow.novel_id,
        episode_index=episode_index,
    )
    if closing_snapshot["unresolved_conflicts"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "production_graph_conflicted",
                "message": "本集 Production Graph 存在未解决状态冲突，不能锁定 Episode Contract",
                "episode_index": episode_index,
                "unresolved_conflicts": closing_snapshot["unresolved_conflicts"],
            },
        )
    graph_projection = await project_story_state(db, user_id=user_id, novel_id=workflow.novel_id)
    exact = exact_preflight_snapshot or {}
    snapshot_hash = exact.get("snapshot_hash") or stable_hash({
        "production_bible_hash": stable_hash(bible),
        "production_graph_hash": graph_projection["graph_hash"],
    })
    metadata = workflow.metadata_ if isinstance(workflow.metadata_, dict) else {}
    existing = metadata.get("episode_contract") if isinstance(metadata.get("episode_contract"), dict) else {}
    if existing.get("status") == "locked" and existing.get("snapshot_hash") == snapshot_hash:
        return existing
    contract = {
        "contract_id": f"contract-{uuid4()}",
        "workflow_id": workflow.id,
        "novel_id": workflow.novel_id,
        "chapter_id": workflow.chapter_id,
        "episode_index": episode_index,
        "locked_at": utc_now().isoformat(),
        "production_bible_hash": stable_hash(bible),
        "style_lock": bible.get("style") or {},
        "entity_locks": [
            {
                "entity_id": item["entity_id"],
                "entity_type": key[:-1],
                "name": item["name"],
                "asset_ids": item.get("asset_ids", []),
            }
            for key in ("characters", "scenes", "props", "events")
            for item in bible.get(key, [])
        ],
        "required_checks": ["style", "characters", "scenes", "props", "voices", "reference_package"],
        "production_graph_version": graph_projection["through_version"],
        "production_graph_hash": graph_projection["graph_hash"],
        "opening_state": opening_snapshot["state"],
        "expected_closing_state": closing_snapshot["state"],
        "relevant_event_ids": closing_snapshot["applied_event_ids"],
        "status": "locked",
        "snapshot_hash": snapshot_hash,
        "as_of_facts": {
            "chapter_id": workflow.chapter_id,
            "production_bible_hash": stable_hash(bible),
            "production_graph_version": graph_projection["through_version"],
            "production_graph_hash": graph_projection["graph_hash"],
        },
        "carry_over_state": opening_snapshot["state"],
        "asset_version_locks": list(exact.get("asset_locks") or [
            {"entity_id": item["entity_id"], "asset_id": asset_id, "asset_version": next(
                (
                    int(asset.get("version") or 1)
                    for asset in bible.get("asset_lock_snapshots", [])
                    if asset.get("asset_id") == asset_id
                ),
                1,
            )}
            for key in ("characters", "scenes", "props")
            for item in bible.get(key, [])
            for asset_id in item.get("asset_ids", [])
        ]),
        "voice_version_locks": list(exact.get("voice_locks") or [
            {
                "entity_id": item.get("entity_id"),
                "voice_id": item.get("voice_id") or item.get("voice"),
                "voice_version": item.get("voice_version") or item.get("version") or 1,
            }
            for item in bible.get("voices", [])
        ]),
        "provider_bindings": list(exact.get("provider_bindings") or []),
        "story_bible_snapshot": dict(exact.get("story_bible") or {}),
        "preflight_graph_snapshot": dict(exact.get("production_graph") or {}),
    }

    if existing:
        previous = {**existing, "status": "superseded_review_required", "superseded_reason": "input_snapshot_changed"}
        metadata["episode_contract_versions"] = [*(metadata.get("episode_contract_versions") or []), previous]
    metadata["episode_contract"] = contract
    workflow.metadata_ = metadata
    flag_modified(workflow, "metadata_")
    if commit:
        await db.commit()
    else:
        await db.flush()
    return contract
