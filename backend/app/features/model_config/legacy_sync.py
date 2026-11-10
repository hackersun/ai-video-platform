"""Keep model_config (Model Center) the runtime source of truth for default models.

Legacy ``LLMConfig`` rows remain as a compatibility mirror: legacy endpoints and
simple-setup still write them, then :func:`reconcile_user` projects the choice
into user-scope ``ModelBinding`` rows. Runtime reads go through
:func:`canonical_default_config_ids`. :func:`project_canonical_to_legacy` is the
reverse direction used for rollback (``MODEL_CENTER_READ_MODE=legacy``).

Secrets are only ever copied as Fernet ciphertext; nothing here logs them.
"""
from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.features.model_config.backfill import _TASK_BY_CAPABILITY, _canonical_id, backfill_model_center
from app.features.model_config.domain import normalize_capabilities
from app.features.model_config.settings import ModelCenterReadMode, model_center_read_mode
from app.models.llm_config import LLMConfig, LLMModel
from app.models.model_center import ModelBinding, ModelConnection

logger = logging.getLogger(__name__)

SIMPLE_TO_CANONICAL = {
    "text": "text_generation", "image": "image_generation",
    "video": "video_generation", "tts": "speech_generation",
}
MARKER = "simple_setup_capability"


def canonical_reads_enabled() -> bool:
    return model_center_read_mode() is not ModelCenterReadMode.LEGACY


async def connection_for_config(db: AsyncSession, config_id: str) -> ModelConnection | None:
    return await db.get(ModelConnection, _canonical_id("connection", config_id))


async def _user_bindings(db: AsyncSession, user_id: str, cap: str) -> list[ModelBinding]:
    canon = SIMPLE_TO_CANONICAL[cap]
    return list((await db.scalars(select(ModelBinding).where(and_(
        ModelBinding.user_id == user_id, ModelBinding.scope_type == "user",
        ModelBinding.scope_id == user_id, ModelBinding.task == _TASK_BY_CAPABILITY[canon],
        ModelBinding.capability == canon,
    )))).all())


async def _legacy_id_for_connection(db: AsyncSession, connection_id: str) -> str | None:
    conn = await db.get(ModelConnection, connection_id)
    if conn is None or conn.status == "disabled":
        return None
    return (conn.connection_params or {}).get("legacy_config_id")


async def canonical_default_config_ids(db: AsyncSession, user_id: str) -> dict[str, str]:
    """capability -> legacy config id, read from active user-scope bindings."""
    out: dict[str, str] = {}
    for cap in SIMPLE_TO_CANONICAL:
        active = [b for b in await _user_bindings(db, user_id, cap) if b.is_active]
        active.sort(key=lambda b: (b.priority, -b.version))
        for binding in active:
            legacy_id = await _legacy_id_for_connection(db, binding.connection_id)
            config = await db.get(LLMConfig, legacy_id) if legacy_id else None
            if config is not None and config.is_active and config.user_id == user_id:
                out[cap] = config.id
                break
    return out


async def has_canonical_bindings(db: AsyncSession, user_id: str) -> bool:
    return (await db.scalar(select(ModelBinding.id).where(and_(
        ModelBinding.user_id == user_id, ModelBinding.scope_type == "user",
        ModelBinding.is_active == True,  # noqa: E712
    )).limit(1))) is not None


async def _bind(db: AsyncSession, user_id: str, cap: str, config: LLMConfig, profile_version_id: str) -> bool:
    """Make ``config`` the single active binding for cap. Returns True if changed."""
    canon = SIMPLE_TO_CANONICAL[cap]
    connection_id = _canonical_id("connection", config.id)
    rows = await _user_bindings(db, user_id, cap)
    active = [b for b in rows if b.is_active]
    if len(active) == 1 and active[0].connection_id == connection_id and active[0].profile_version_id == profile_version_id:
        return False
    for b in active:
        b.is_active = False
    db.add(ModelBinding(
        id=str(uuid4()), user_id=user_id, scope_type="user", scope_id=user_id,
        task=_TASK_BY_CAPABILITY[canon], capability=canon, profile_version_id=profile_version_id,
        connection_id=connection_id, priority=100, route_policy="single",
        fallback_profile_version_ids=[], version=max((b.version for b in rows), default=0) + 1, is_active=True,
    ))
    return True


async def _unbind(db: AsyncSession, user_id: str, cap: str) -> None:
    for b in await _user_bindings(db, user_id, cap):
        b.is_active = False


def _sync_connection(conn: ModelConnection, config: LLMConfig) -> None:
    if not config.is_active:
        conn.status = "disabled"
        return
    params = dict(conn.connection_params or {})
    key_ok = not config.api_key or str(config.api_key).startswith("gAAAAA")
    if key_ok and conn.api_key != config.api_key:
        conn.api_key = config.api_key or ""
    if key_ok and config.api_secret and str(config.api_secret).startswith("gAAAAA") and conn.api_secret != config.api_secret:
        conn.api_secret = config.api_secret
    params["credential_reentry_required"] = not key_ok
    if params != conn.connection_params:
        conn.connection_params = params
        flag_modified(conn, "connection_params")
    status = "verified" if config.test_status == "success" and key_ok else "draft"
    if conn.status != status:
        conn.status = status
    if conn.tested_at != config.tested_at:
        conn.tested_at = config.tested_at


async def reconcile_user(db: AsyncSession, user_id: str) -> dict[str, str]:
    """Forward direction: legacy edits -> model_config. Returns cap -> config id."""
    from app.services.simple_model_setup import _pick_default, _user_configs

    report = await backfill_model_center(db, apply=True, user_id=user_id)
    await db.flush()
    all_configs = (await db.scalars(select(LLMConfig).where(LLMConfig.user_id == user_id))).all()
    for config in all_configs:
        conn = await connection_for_config(db, config.id)
        if conn is not None:
            _sync_connection(conn, config)
    rows = await _user_configs(db, user_id)
    picks: dict[str, str] = {}
    for cap, canon in SIMPLE_TO_CANONICAL.items():
        pick = _pick_default(rows, cap)
        if pick is None:
            await _unbind(db, user_id, cap)
            continue
        config, model = pick
        version_id = report.profile_version_ids.get(model.id)
        if version_id is None or canon not in normalize_capabilities(model.model_type, model.capabilities or []):
            continue
        if await connection_for_config(db, config.id) is None:
            continue
        await _bind(db, user_id, cap, config, version_id)
        picks[cap] = config.id
    await db.flush()
    return picks


async def set_canonical_default(db: AsyncSession, user_id: str, cap: str, config_id: str) -> None:
    """Change the source of truth directly (used by tests / admin tools)."""
    config = await db.get(LLMConfig, config_id)
    if config is None or config.user_id != user_id or not config.is_active:
        raise ValueError("config_not_found")
    report = await backfill_model_center(db, apply=True, user_id=user_id)
    await db.flush()
    version_id = report.profile_version_ids.get(config.model_id)
    if version_id is None:
        raise ValueError("profile_not_found")
    await _bind(db, user_id, cap, config, version_id)
    await db.flush()


async def project_canonical_to_legacy(db: AsyncSession, user_id: str) -> dict[str, str]:
    """Reverse direction: mark the canonical choice on legacy rows (rollback-safe)."""
    picks = await canonical_default_config_ids(db, user_id)
    configs = (await db.scalars(select(LLMConfig).where(LLMConfig.user_id == user_id))).all()
    for config in configs:
        extra = dict(config.extra_params or {}) if isinstance(config.extra_params, dict) else {}
        marked = extra.get(MARKER)
        wanted = next((cap for cap, cid in picks.items() if cid == config.id and cap == marked), None) \
            or next((cap for cap, cid in picks.items() if cid == config.id), None)
        if wanted != marked and (wanted is not None or marked in picks):
            if wanted is None:
                extra.pop(MARKER, None)
            else:
                extra[MARKER] = wanted
                config.is_default = True
            config.extra_params = extra
            flag_modified(config, "extra_params")
    await db.flush()
    return picks


async def migrate_all(db: AsyncSession) -> dict[str, int]:
    """Migrate every user with legacy configs. Idempotent; returns counts only."""
    user_ids = sorted({u for u in (await db.scalars(select(LLMConfig.user_id).distinct())).all() if u})
    for user_id in user_ids:
        await reconcile_user(db, user_id)
    await db.commit()
    active = (await db.scalars(select(ModelBinding.id).where(and_(
        ModelBinding.scope_type == "user", ModelBinding.is_active == True)))).all()  # noqa: E712
    return {"users": len(user_ids), "bindings_active": len(active)}


async def reconcile_user_lazily(db: AsyncSession, user_id: str) -> bool:
    """Read-path migration: runs in a SAVEPOINT and never commits the caller's transaction."""
    try:
        async with db.begin_nested():
            await reconcile_user(db, user_id)
        return True
    except Exception as error:
        logger.warning("model center lazy reconcile skipped: %s", type(error).__name__)
        return False


async def reconcile_user_safely(db: AsyncSession, user_id: str) -> bool:
    """Best-effort wrapper for write paths; commits on success."""
    try:
        await reconcile_user(db, user_id)
        await db.commit()
        return True
    except Exception as error:  # never block a legacy save; reads lazily retry
        await db.rollback()
        logger.warning("model center reconcile skipped: %s", type(error).__name__)
        return False


__all__ = [
    "SIMPLE_TO_CANONICAL", "canonical_default_config_ids", "canonical_reads_enabled",
    "connection_for_config", "has_canonical_bindings", "migrate_all", "project_canonical_to_legacy",
    "reconcile_user", "reconcile_user_lazily", "reconcile_user_safely", "set_canonical_default",
]
