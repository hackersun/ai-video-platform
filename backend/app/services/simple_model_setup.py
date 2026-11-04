"""Simple model setup: the single product write surface for model configuration.

One API key (per provider), four capability cards (text/image/video/tts), a
global default per capability and optional per-novel overrides stored on
``Novel.extra_data["model_overrides"]``.

Storage: legacy ``LLMConfig`` rows stay the system of record for runs (run
bindings reference their ids); every save is additively projected into the
Model Center tables via :func:`backfill_model_center`.

Secrets are write-only: responses expose ``has_key`` only, and nothing here
logs a key.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.llm_config import LLMConfig, LLMModel, LLMProvider
from app.models.novel import Novel

logger = logging.getLogger(__name__)

CAPABILITY_ORDER = ("text", "image", "video", "tts")
CAPABILITY_LABELS = {"text": "文本", "image": "图像", "video": "视频", "tts": "语音"}
# Must stay aligned with live_canary_bindings.CAPABILITIES (run validation).
CAPABILITY_TAGS = {
    "text": {"chat", "completion", "text"},
    "image": {"text-to-image", "image", "image-generation"},
    "tts": {"text-to-speech", "tts", "speech"},
    "video": {"text-to-video", "image-to-video", "video", "video-generation"},
}
# Recommended api model ids per provider code; first match in the catalog wins.
PROVIDER_PRESETS: dict[str, dict[str, list[str]]] = {
    "volcano": {
        "text": ["doubao-seed-1-8-251228", "Doubao-Seed-2.0-pro", "doubao-pro-32k"],
        "image": ["doubao-seedream-5-0-260128", "Doubao-Seedream-4.5"],
        "video": ["doubao-seedance-2-0-260128", "doubao-seedance-2-0-fast-260128", "doubao-seedance-1-5-pro-251215"],
        "tts": [],
    },
    "minimax": {"text": ["MiniMax-M2.7", "MiniMax-M3"], "image": ["image-01"], "video": [], "tts": ["speech-2.6-hd"]},
    "deepseek": {"text": ["deepseek-v4-flash", "deepseek-v4-pro"], "image": [], "video": [], "tts": []},
    "qwen": {"text": ["qwen-plus", "qwen-max"], "image": [], "video": [], "tts": []},
    "openai": {"text": ["gpt-4o-mini", "gpt-4o"], "image": ["dall-e-3"], "video": ["sora"], "tts": []},
}
HIDDEN_PROVIDERS = {"deterministic-acceptance"}
ALLOWED_EXTRA_KEYS = {"app_id", "appid", "resource_id", "group_id", "cluster", "base_url", "region", "default_voice_id"}
FRESH_SECONDS = 900


class SimpleSetupError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _tags(model: LLMModel) -> set[str]:
    tags = {str(t).lower().replace("_", "-") for t in (model.capabilities or [])}
    tags.add(str(model.model_type or "").lower().replace("_", "-"))
    return tags


def model_capabilities(model: LLMModel) -> list[str]:
    tags = _tags(model)
    return [cap for cap in CAPABILITY_ORDER if tags & CAPABILITY_TAGS[cap]]


def _naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def is_fresh(config: LLMConfig, *, not_before: datetime | None = None) -> bool:
    tested = _naive(config.tested_at)
    if config.test_status != "success" or tested is None:
        return False
    cutoff = _now() - timedelta(seconds=FRESH_SECONDS - 60)  # 60s margin for queue latency
    if not_before is not None:
        cutoff = max(cutoff, _naive(not_before))
    return tested >= cutoff


async def _catalog(db: AsyncSession) -> tuple[list[LLMProvider], list[LLMModel]]:
    providers = list((await db.scalars(select(LLMProvider).where(LLMProvider.is_active == True))).all())  # noqa: E712
    providers = [p for p in providers if p.name not in HIDDEN_PROVIDERS]
    ids = {p.id for p in providers}
    models = [m for m in (await db.scalars(select(LLMModel).where(LLMModel.is_active == True))).all()  # noqa: E712
              if m.provider_id in ids]
    return providers, models


async def _user_configs(db: AsyncSession, user_id: str) -> list[tuple[LLMConfig, LLMModel]]:
    rows = await db.execute(
        select(LLMConfig, LLMModel).join(LLMModel, LLMModel.id == LLMConfig.model_id)
        .where(and_(LLMConfig.user_id == user_id, LLMConfig.is_active == True))  # noqa: E712
        .order_by(desc(LLMConfig.is_default), desc(LLMConfig.updated_at), desc(LLMConfig.created_at))
    )
    return [(c, m) for c, m in rows.all()]


def _pick_default(rows: list[tuple[LLMConfig, LLMModel]], cap: str):
    candidates = [(c, m) for c, m in rows if cap in model_capabilities(m)]
    defaults = [(c, m) for c, m in candidates if c.is_default]
    # simple-setup marks its own choice explicitly so a shared default cannot shadow it
    marked = [(c, m) for c, m in candidates if (c.extra_params or {}).get("simple_setup_capability") == cap]
    for group in (marked, defaults, candidates):
        if group:
            return group[0]
    return None


async def _novel_overrides(db: AsyncSession, user_id: str, novel_id: str | None) -> dict[str, str]:
    if not novel_id:
        return {}
    novel = await db.get(Novel, novel_id)
    if novel is None or novel.user_id != user_id:
        raise SimpleSetupError("novel_not_found", "小说不存在")
    raw = (novel.extra_data or {}).get("model_overrides") or {}
    return {k: str(v) for k, v in raw.items() if k in CAPABILITY_ORDER and v}


async def resolve_effective_configs(
    db: AsyncSession, user_id: str, novel_id: str | None,
) -> dict[str, tuple[LLMConfig, LLMModel] | None]:
    rows = await _user_configs(db, user_id)
    by_id = {c.id: (c, m) for c, m in rows}
    overrides = await _novel_overrides(db, user_id, novel_id) if novel_id else {}
    result: dict[str, Any] = {}
    for cap in CAPABILITY_ORDER:
        override = by_id.get(overrides.get(cap, ""))
        if override and cap in model_capabilities(override[1]):
            result[cap] = override
        else:
            result[cap] = _pick_default(rows, cap)
    return result


def _card(cap: str, pair, providers_by_id, options) -> dict[str, Any]:
    card: dict[str, Any] = {
        "capability": cap, "label": CAPABILITY_LABELS[cap], "config_id": None, "provider_id": None,
        "provider_name": None, "model_id": None, "model_name": None, "api_model_id": None, "has_key": False,
        "test_status": None, "test_message": None, "tested_at": None, "fresh": False, "extra_params": {},
        "options": options,
    }
    if pair:
        config, model = pair
        provider = providers_by_id.get(model.provider_id)
        extra = config.extra_params if isinstance(config.extra_params, dict) else {}
        card.update({
            "config_id": config.id, "provider_id": model.provider_id,
            "provider_name": (provider.name_cn or provider.name) if provider else None,
            "model_id": model.id, "model_name": model.model_name_cn or model.model_name or model.model_id, "api_model_id": model.model_id,
            "has_key": bool(config.api_key), "test_status": config.test_status,
            "test_message": config.test_message,
            "tested_at": _naive(config.tested_at).isoformat() + "Z" if config.tested_at else None,
            "fresh": is_fresh(config),
            "extra_params": {k: v for k, v in extra.items() if k in ALLOWED_EXTRA_KEYS},
        })
    return card


async def get_simple_setup(db: AsyncSession, user_id: str, *, novel_id: str | None = None) -> dict[str, Any]:
    providers, models = await _catalog(db)
    by_pid = {p.id: p for p in providers}
    options: dict[str, list[dict[str, Any]]] = {cap: [] for cap in CAPABILITY_ORDER}
    for model in models:
        for cap in model_capabilities(model):
            provider = by_pid[model.provider_id]
            options[cap].append({"model_id": model.id, "api_model_id": model.model_id,
                                 "name": model.model_name_cn or model.model_name or model.model_id, "provider_id": provider.id,
                                 "provider_name": provider.name_cn or provider.name})
    provider_items = []
    for provider in providers:
        preset_ids = PROVIDER_PRESETS.get(provider.name, {})
        own = [m for m in models if m.provider_id == provider.id]
        presets: dict[str, str | None] = {}
        for cap in CAPABILITY_ORDER:
            chosen = next((m.id for wanted in preset_ids.get(cap, []) for m in own if m.model_id == wanted), None)
            presets[cap] = chosen or next((m.id for m in own if cap in model_capabilities(m)), None)
        if any(presets.values()):
            provider_items.append({"id": provider.id, "code": provider.name,
                                   "name": provider.name_cn or provider.name, "presets": presets,
                                   "recommended": provider.name in PROVIDER_PRESETS})
    provider_items.sort(key=lambda x: (not x["recommended"], -sum(1 for v in x["presets"].values() if v)))
    resolved = await resolve_effective_configs(db, user_id, None)
    cards = {cap: _card(cap, resolved[cap], by_pid, options[cap]) for cap in CAPABILITY_ORDER}
    primary = next((cards[c]["provider_id"] for c in CAPABILITY_ORDER if cards[c]["provider_id"]), None)
    state: dict[str, Any] = {
        "providers": provider_items, "capabilities": cards, "primary_provider_id": primary,
        # Keyless providers (local/self-hosted) count as configured once a test passed.
        "configured": all(
            cards[c]["config_id"] and (cards[c]["has_key"] or cards[c]["test_status"] == "success")
            for c in CAPABILITY_ORDER
        ),
        "verified": all(cards[c]["test_status"] == "success" for c in CAPABILITY_ORDER),
    }
    if novel_id:
        overrides = await _novel_overrides(db, user_id, novel_id)
        effective = await resolve_effective_configs(db, user_id, novel_id)
        state["novel_id"] = novel_id
        state["novel_overrides"] = {cap: overrides.get(cap) for cap in CAPABILITY_ORDER}
        state["novel_effective"] = {cap: _card(cap, effective[cap], by_pid, []) for cap in CAPABILITY_ORDER}
        rows = await _user_configs(db, user_id)
        state["novel_choices"] = {
            cap: [{"config_id": c.id, "name": c.name, "model_name": m.model_name_cn or m.model_name or m.model_id,
                   "provider_name": (by_pid[m.provider_id].name_cn or by_pid[m.provider_id].name)
                   if m.provider_id in by_pid else None, "test_status": c.test_status}
                  for c, m in rows if cap in model_capabilities(m)]
            for cap in CAPABILITY_ORDER
        }
    return state


async def _existing_key_for_provider(db: AsyncSession, user_id: str, provider_id: str) -> LLMConfig | None:
    for config, model in await _user_configs(db, user_id):
        if model.provider_id == provider_id and config.api_key:
            return config
    return None


def _clean_extra(extra: Any) -> dict[str, Any]:
    if not isinstance(extra, dict):
        return {}
    return {k: str(v).strip() for k, v in extra.items() if k in ALLOWED_EXTRA_KEYS and v not in (None, "")}


async def save_simple_setup(db: AsyncSession, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from app.api.v1.endpoints.llm_config import clear_default_configs_for_model_group

    primary_provider = str(payload.get("provider_id") or "")
    primary_key = str(payload.get("api_key") or "").strip()
    cards = payload.get("capabilities") or {}
    if not isinstance(cards, dict) or not cards:
        raise SimpleSetupError("capabilities_required", "请至少选择一个能力的模型")
    planned = []
    for cap, card in cards.items():
        if cap not in CAPABILITY_ORDER:
            raise SimpleSetupError("unknown_capability", f"未知能力：{cap}")
        if not card or not card.get("model_id"):
            continue
        model = await db.get(LLMModel, str(card["model_id"]))
        if model is None or not model.is_active:
            raise SimpleSetupError("model_not_found", f"{CAPABILITY_LABELS[cap]}模型不存在或已下线")
        if cap not in model_capabilities(model):
            raise SimpleSetupError("capability_mismatch", f"所选模型不支持{CAPABILITY_LABELS[cap]}能力")
        key = str(card.get("api_key") or "").strip()
        if not key and model.provider_id == primary_provider:
            key = primary_key
        planned.append((cap, model, key, card))
    # resolve keys before writing anything (all-or-nothing)
    resolved_keys: dict[str, tuple[str | None, LLMConfig | None]] = {}
    for cap, model, key, _ in planned:
        if key:
            resolved_keys[cap] = (key, None)
            continue
        donor = await _existing_key_for_provider(db, user_id, model.provider_id)
        if donor is None:
            raise SimpleSetupError("api_key_required", f"请填写{CAPABILITY_LABELS[cap]}模型所属供应商的 API Key")
        resolved_keys[cap] = (None, donor)
    for cap, model, _, card in planned:
        plain, donor = resolved_keys[cap]
        config = (await db.scalars(
            select(LLMConfig).where(and_(LLMConfig.user_id == user_id, LLMConfig.model_id == model.id,
                                         LLMConfig.is_active == True))  # noqa: E712
            .order_by(desc(LLMConfig.updated_at))
        )).first()
        if config is None:
            config = LLMConfig(id=str(uuid4()), user_id=user_id, model_id=model.id,
                               name=f"{CAPABILITY_LABELS[cap]}默认 · {model.model_name_cn or model.model_name or model.model_id}",
                               is_active=True, test_status="pending", extra_params={})
            db.add(config)
            await db.flush()
        previous_key = config.api_key
        if plain is not None:
            config.set_api_key_encrypted(plain)
        elif donor is not None and donor.id != config.id:
            config.api_key = donor.api_key
            if donor.api_secret and not config.api_secret:
                config.api_secret = donor.api_secret
        extra = dict(config.extra_params or {}) if isinstance(config.extra_params, dict) else {}
        if "extra_params" in card:
            extra = {k: v for k, v in extra.items() if k not in ALLOWED_EXTRA_KEYS}
            extra.update(_clean_extra(card.get("extra_params")))
        # drop other configs' simple-setup marker for this capability
        for other, other_model in await _user_configs(db, user_id):
            if other.id != config.id and (other.extra_params or {}).get("simple_setup_capability") == cap:
                other_extra = dict(other.extra_params or {})
                other_extra.pop("simple_setup_capability", None)
                other.extra_params = other_extra
                flag_modified(other, "extra_params")
        extra["simple_setup_capability"] = cap
        config.extra_params = extra
        flag_modified(config, "extra_params")
        if config.api_key != previous_key:
            config.test_status = "pending"
            config.test_message = "配置已更新，请测试连接"
            config.tested_at = None
        await clear_default_configs_for_model_group(db, user_id, model, exclude_config_id=config.id)
        config.is_default = True
    await db.commit()
    await sync_model_center(db, user_id)
    logger.info("simple model setup saved", extra={"user_id": user_id, "capabilities": [p[0] for p in planned]})
    return await get_simple_setup(db, user_id)


async def sync_model_center(db: AsyncSession, user_id: str | None) -> bool:
    """Project legacy configs into Model Center tables. Best effort, never blocks saves."""
    from app.features.model_config.backfill import backfill_model_center

    try:
        await backfill_model_center(db, apply=True, user_id=user_id)
        await db.commit()
        return True
    except Exception as error:  # projection is additive; legacy rows remain authoritative
        await db.rollback()
        logger.warning("model center projection skipped: %s", type(error).__name__)
        return False


async def test_simple_setup(
    db: AsyncSession, user_id: str, capabilities: Iterable[str] | None = None,
) -> dict[str, Any]:
    from app.services.model_config_test_runner import run_saved_config_test

    caps = [c for c in (capabilities or CAPABILITY_ORDER) if c in CAPABILITY_ORDER]
    resolved = await resolve_effective_configs(db, user_id, None)
    results: dict[str, Any] = {}
    tested: dict[str, str] = {}
    for cap in caps:
        pair = resolved.get(cap)
        if not pair:
            results[cap] = {"success": False, "code": "not_configured",
                            "message": f"尚未配置{CAPABILITY_LABELS[cap]}模型", "response_time_ms": 0}
            continue
        config, model = pair
        if config.id in tested:  # same config serves several capabilities
            results[cap] = dict(results[tested[config.id]])
            continue
        try:
            outcome = await run_saved_config_test(db, config, model)
        except Exception as error:
            await db.rollback()
            outcome = {"success": False, "message": f"测试失败：{type(error).__name__}", "response_time_ms": 0}
        tested[config.id] = cap
        results[cap] = {"success": bool(outcome.get("success")), "code": "ok" if outcome.get("success") else "failed",
                        "message": str(outcome.get("message") or ""),
                        "response_time_ms": int(outcome.get("response_time_ms") or 0)}
    return {"results": results, "state": await get_simple_setup(db, user_id)}


async def set_novel_overrides(
    db: AsyncSession, user_id: str, novel_id: str, overrides: dict[str, str | None],
) -> dict[str, Any]:
    novel = await db.get(Novel, novel_id)
    if novel is None or novel.user_id != user_id:
        raise SimpleSetupError("novel_not_found", "小说不存在")
    rows = {c.id: (c, m) for c, m in await _user_configs(db, user_id)}
    extra = dict(novel.extra_data or {})
    current = dict(extra.get("model_overrides") or {})
    for cap, config_id in (overrides or {}).items():
        if cap not in CAPABILITY_ORDER:
            raise SimpleSetupError("unknown_capability", f"未知能力：{cap}")
        if not config_id:
            current.pop(cap, None)
            continue
        pair = rows.get(str(config_id))
        if pair is None or cap not in model_capabilities(pair[1]):
            raise SimpleSetupError("config_not_found", f"{CAPABILITY_LABELS[cap]}配置不存在或能力不匹配")
        current[cap] = str(config_id)
    extra["model_overrides"] = current
    novel.extra_data = extra
    flag_modified(novel, "extra_data")
    await db.commit()
    return await get_simple_setup(db, user_id, novel_id=novel_id)


async def ensure_fresh(
    db: AsyncSession, resolved: dict[str, Any], *, not_before: datetime | None = None,
) -> dict[str, str]:
    """Re-test stale configs; return {capability: human message} for failures."""
    from app.services.model_config_test_runner import run_saved_config_test

    failures: dict[str, str] = {}
    done: dict[str, bool] = {}
    for cap, pair in resolved.items():
        if not pair:
            failures[cap] = f"尚未配置{CAPABILITY_LABELS[cap]}模型"
            continue
        config, model = pair
        if config.id not in done:
            if is_fresh(config, not_before=not_before):
                done[config.id] = True
            else:
                try:
                    done[config.id] = bool((await run_saved_config_test(db, config, model)).get("success"))
                except Exception:
                    await db.rollback()
                    done[config.id] = False
        if not done[config.id]:
            failures[cap] = f"{CAPABILITY_LABELS[cap]}模型连接测试失败：{config.test_message or '请检查 API Key'}"
    return failures


__all__ = [
    "CAPABILITY_ORDER", "SimpleSetupError", "ensure_fresh", "get_simple_setup", "is_fresh",
    "resolve_effective_configs", "save_simple_setup", "set_novel_overrides", "sync_model_center",
    "test_simple_setup",
]
