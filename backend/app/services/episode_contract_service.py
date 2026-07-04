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


def _canonicalize_hash_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _canonicalize_hash_payload(item)
            for key, item in value.items()
            if key not in VOLATILE_HASH_KEYS
        }
    if isinstance(value, list):
        return [_canonicalize_hash_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_canonicalize_hash_payload(item) for item in value]
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
