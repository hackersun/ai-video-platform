"""Append-only production graph projections and impact analysis."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Dict, Iterable, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models.production_state_event import ProductionStateEvent


APPROVAL_STATUSES = {"pending", "approved", "rejected"}
IMMUTABLE_ERROR = "Production state events are immutable; append a compensating event instead."
_MISSING = object()


def _json_dict(value: Any) -> Dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _event_hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _deep_merge(target: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(target)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _flatten(value: Dict[str, Any], prefix: str = "") -> Iterable[tuple[str, Any]]:
    for key in sorted(value):
        path = f"{prefix}.{key}" if prefix else key
        item = value[key]
        if isinstance(item, dict):
            yield from _flatten(item, path)
        else:
            yield path, item


def _get_path(value: Dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _event_episode_index(event: ProductionStateEvent) -> Optional[int]:
    if event.episode_index is not None:
        return event.episode_index
    story_time = event.story_time if isinstance(event.story_time, dict) else {}
    value = story_time.get("episode_index")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _scope_state(state: Dict[str, Any], entity_id: Optional[str]) -> Dict[str, Any]:
    if entity_id:
        return state["entities"].setdefault(entity_id, {})
    return state["world"]


def _apply_event(state: Dict[str, Any], event: ProductionStateEvent) -> Dict[str, Any]:
    if event.event_type == "restore_version":
        restored = _json_dict(event.after_state)
        return {
            "entities": _json_dict(restored.get("entities")),
            "world": _json_dict(restored.get("world")),
        }

    scoped = _scope_state(state, event.entity_id)
    merged = _deep_merge(scoped, _json_dict(event.after_state))
    if event.entity_id:
        state["entities"][event.entity_id] = merged
    else:
        state["world"] = merged
    return state


async def _load_events(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: str,
    max_version: Optional[int] = None,
) -> list[ProductionStateEvent]:
    query = select(ProductionStateEvent).where(
        ProductionStateEvent.user_id == user_id,
        ProductionStateEvent.novel_id == novel_id,
    )
    if max_version is not None:
        query = query.where(ProductionStateEvent.production_version <= max_version)
    result = await db.execute(query.order_by(ProductionStateEvent.production_version.asc()))
    return list(result.scalars().all())


def _project_events(events: Iterable[ProductionStateEvent]) -> Dict[str, Any]:
    state: Dict[str, Any] = {"entities": {}, "world": {}}
    applied_event_ids: list[str] = []
    ignored_event_ids: list[str] = []
    through_version = 0

    for event in events:
        through_version = max(through_version, event.production_version)
        if event.approval_status != "approved":
            ignored_event_ids.append(event.id)
            continue
        state = _apply_event(state, event)
        applied_event_ids.append(event.id)

    return {
        "state": state,
        "through_version": through_version,
        "applied_event_ids": applied_event_ids,
        "ignored_event_ids": ignored_event_ids,
    }


def _project_episode_state(
    events: list[ProductionStateEvent],
    *,
    episode_index: int,
    max_version: int,
) -> Dict[str, Any]:
    state: Dict[str, Any] = {"entities": {}, "world": {}}
    for event in events:
        if event.production_version > max_version:
            break
        event_episode = _event_episode_index(event)
        if (
            event.approval_status != "approved"
            or (event_episode is not None and event_episode > episode_index)
        ):
            continue
        if event.event_type == "restore_version":
            production_time = _json_dict(event.production_time)
            restored_from = production_time.get("restored_from_version")
            if isinstance(restored_from, int) and restored_from < event.production_version:
                state = _project_episode_state(
                    events,
                    episode_index=episode_index,
                    max_version=restored_from,
                )
                continue
        state = _apply_event(state, event)
    return state


async def project_story_state(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: str,
    max_version: Optional[int] = None,
) -> Dict[str, Any]:
    """Project approved append-only events into current story state."""

    events = await _load_events(
        db,
        user_id=user_id,
        novel_id=novel_id,
        max_version=max_version,
    )
    projection = _project_events(events)
    empty_hash = hashlib.sha256(
        _canonical_json({"novel_id": novel_id, "through_version": 0, "previous_event_hash": None}).encode("utf-8")
    ).hexdigest()
    return {
        "novel_id": novel_id,
        **projection,
        "graph_hash": events[-1].event_hash if events else empty_hash,
    }


async def append_state_event(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: str,
    event_type: str,
    story_time: Optional[Dict[str, Any]] = None,
    production_time: Optional[Dict[str, Any]] = None,
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
    chapter_id: Optional[str] = None,
    episode_index: Optional[int] = None,
    entity_id: Optional[str] = None,
    evidence: Any = None,
    approval_status: str = "pending",
    approved_by: Optional[str] = None,
    restore_version: Optional[int] = None,
    commit: bool = True,
) -> ProductionStateEvent:
    """Append one immutable event, optionally restoring an earlier projection."""

    if approval_status not in APPROVAL_STATUSES:
        raise ValueError(f"Unsupported approval status: {approval_status}")
    if not event_type.strip():
        raise ValueError("event_type is required")

    existing = await _load_events(db, user_id=user_id, novel_id=novel_id)
    last_event = existing[-1] if existing else None
    next_version = (last_event.production_version if last_event else 0) + 1
    normalized_production_time = _json_dict(production_time)
    normalized_before_state = _json_dict(before_state)
    normalized_after_state = _json_dict(after_state)

    if restore_version is not None:
        if event_type != "restore_version":
            raise ValueError("restore_version requires event_type='restore_version'")
        if restore_version < 0 or restore_version >= next_version:
            raise ValueError("restore_version must identify an earlier production version")
        current_projection = _project_events(existing)
        target_projection = _project_events(
            event for event in existing if event.production_version <= restore_version
        )
        normalized_before_state = current_projection["state"]
        normalized_after_state = target_projection["state"]
        normalized_production_time["restored_from_version"] = restore_version
        entity_id = None

    created_at = utc_now()
    approved_at = created_at if approval_status == "approved" else None
    event_id = str(uuid4())
    immutable_payload = {
        "id": event_id,
        "user_id": user_id,
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        "episode_index": episode_index,
        "entity_id": entity_id,
        "event_type": event_type,
        "story_time": _json_dict(story_time),
        "production_time": normalized_production_time,
        "before_state": normalized_before_state,
        "after_state": normalized_after_state,
        "evidence": evidence,
        "approval_status": approval_status,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "production_version": next_version,
        "previous_event_hash": last_event.event_hash if last_event else None,
        "created_at": created_at,
    }
    event = ProductionStateEvent(
        **immutable_payload,
        event_hash=_event_hash(immutable_payload),
    )
    db.add(event)
    if commit:
        await db.commit()
    else:
        await db.flush()
    await db.refresh(event)
    return event


async def update_state_event(
    db: AsyncSession,
    *,
    event_id: str,
    **changes: Any,
) -> None:
    """Reject mutation explicitly; corrections must be appended."""

    del db, event_id, changes
    raise ValueError(IMMUTABLE_ERROR)


def _conflict_payload(
    event: ProductionStateEvent,
    *,
    field_path: str,
    reason: str,
    expected_before: Any = None,
    actual_before: Any = None,
) -> Dict[str, Any]:
    return {
        "episode_index": _event_episode_index(event) or 0,
        "entity_id": event.entity_id,
        "event_id": event.id,
        "field_path": field_path,
        "reason": reason,
        "expected_before": expected_before,
        "actual_before": actual_before,
    }


async def build_episode_state_snapshot(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: str,
    episode_index: int,
) -> Dict[str, Any]:
    """Project an episode and report deterministic unresolved conflicts."""

    if episode_index < 1:
        raise ValueError("episode_index must be at least 1")
    all_events = await _load_events(db, user_id=user_id, novel_id=novel_id)
    events = [
        event
        for event in all_events
        if _event_episode_index(event) is None or _event_episode_index(event) <= episode_index
    ]
    state: Dict[str, Any] = {"entities": {}, "world": {}}
    applied_event_ids: list[str] = []
    ignored_event_ids: list[str] = []
    conflicts: list[Dict[str, Any]] = []
    writes: Dict[tuple[Any, ...], tuple[Any, str]] = {}

    for event in events:
        if event.approval_status != "approved":
            ignored_event_ids.append(event.id)
            continue
        if event.event_type == "restore_version":
            restored_from = _json_dict(event.production_time).get("restored_from_version")
            if isinstance(restored_from, int):
                state = _project_episode_state(
                    all_events,
                    episode_index=episode_index,
                    max_version=restored_from,
                )
            else:
                state = _apply_event(state, event)
            writes.clear()
            applied_event_ids.append(event.id)
            continue

        scoped = _scope_state(state, event.entity_id)
        for field_path, expected in _flatten(_json_dict(event.before_state)):
            actual = _get_path(scoped, field_path)
            if actual is _MISSING or actual != expected:
                conflicts.append(
                    _conflict_payload(
                        event,
                        field_path=field_path,
                        reason="before_state_mismatch",
                        expected_before=expected,
                        actual_before=None if actual is _MISSING else actual,
                    )
                )

        story_time_key = _canonical_json(_json_dict(event.story_time))
        for field_path, value in _flatten(_json_dict(event.after_state)):
            key = (story_time_key, event.entity_id, field_path)
            previous = writes.get(key)
            if previous is not None and previous[0] != value:
                conflicts.append(
                    _conflict_payload(
                        event,
                        field_path=field_path,
                        reason="competing_story_time_write",
                        expected_before=previous[0],
                        actual_before=value,
                    )
                )
            writes[key] = (deepcopy(value), event.id)

        state = _apply_event(state, event)
        applied_event_ids.append(event.id)

    conflicts.sort(
        key=lambda item: (
            item["episode_index"],
            item["entity_id"] or "",
            item["field_path"],
            item["event_id"],
        )
    )
    return {
        "novel_id": novel_id,
        "episode_index": episode_index,
        "status": "conflicted" if conflicts else "ready",
        "state": state,
        "applied_event_ids": applied_event_ids,
        "ignored_event_ids": ignored_event_ids,
        "unresolved_conflicts": conflicts,
    }


def _related_entity_ids(state: Dict[str, Any]) -> set[str]:
    related: set[str] = set()
    values = state.get("related_entity_ids")
    if isinstance(values, list):
        related.update(str(value) for value in values if value)
    relationships = state.get("relationships")
    if isinstance(relationships, dict):
        related.update(str(value) for value in relationships if value)
    return related


async def analyze_state_change_impact(
    db: AsyncSession,
    *,
    user_id: str,
    novel_id: str,
    event_id: str,
) -> Dict[str, Any]:
    """Return data-only downstream scope for a production state change."""

    events = await _load_events(db, user_id=user_id, novel_id=novel_id)
    source = next((event for event in events if event.id == event_id), None)
    if source is None:
        raise ValueError("Production state event does not exist")

    source_episode = _event_episode_index(source)
    entity_ids = ({source.entity_id} if source.entity_id else set()) | _related_entity_ids(
        _json_dict(source.after_state)
    )
    global_scope = not entity_ids
    eligible_events = [
        event
        for event in events
        if event.production_version >= source.production_version
        and (
            source_episode is None
            or _event_episode_index(event) is None
            or _event_episode_index(event) >= source_episode
        )
    ]
    affected_event_ids: set[str] = set()
    changed = True
    while changed:
        changed = False
        for event in eligible_events:
            if (
                event.id not in affected_event_ids
                and (event.id == source.id or global_scope or event.entity_id in entity_ids)
            ):
                affected_event_ids.add(event.id)
                if event.entity_id:
                    entity_ids.add(event.entity_id)
                entity_ids.update(_related_entity_ids(_json_dict(event.after_state)))
                changed = True

    affected_events = [event for event in eligible_events if event.id in affected_event_ids]

    episode_indices = sorted(
        {
            event_episode
            for event in affected_events
            if (event_episode := _event_episode_index(event)) is not None
        }
    )
    return {
        "source_event_id": source.id,
        "affected_episode_indices": episode_indices,
        "affected_entity_ids": sorted(entity_ids),
        "affected_event_ids": [event.id for event in affected_events],
    }


__all__ = [
    "analyze_state_change_impact",
    "append_state_event",
    "build_episode_state_snapshot",
    "project_story_state",
    "update_state_event",
]
