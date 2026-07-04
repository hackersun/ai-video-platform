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


async def lock_episode_contract(db: AsyncSession, user_id: str, workflow_id: str) -> Dict[str, Any]:
    workflow = (
        await db.execute(select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user_id))
    ).scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作流不存在")
    if not workflow.novel_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="工作流没有绑定小说")

    bible = await build_production_bible_summary(db, user_id, workflow.novel_id)
    contract = {
        "contract_id": f"contract-{uuid4()}",
        "workflow_id": workflow.id,
        "novel_id": workflow.novel_id,
        "chapter_id": workflow.chapter_id,
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
    }

    metadata = workflow.metadata_ if isinstance(workflow.metadata_, dict) else {}
    metadata["episode_contract"] = contract
    workflow.metadata_ = metadata
    flag_modified(workflow, "metadata_")
    await db.commit()
    return contract
