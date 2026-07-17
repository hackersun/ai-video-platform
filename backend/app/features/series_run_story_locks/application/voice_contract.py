"""Voice-selection snapshot contract used by Story Lock preparation."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def provider_voice_allowlist(provider_id: str) -> tuple[str, ...]:
    if provider_id == "minimax":
        from app.core.minimax_voice_contract import minimax_live_canary_voice_ids
        return minimax_live_canary_voice_ids()
    if provider_id == "volcano":
        from app.core.volcano_voice_contract import volcano_live_canary_voice_ids
        return volcano_live_canary_voice_ids()
    if provider_id == "deterministic-acceptance":
        return ("deterministic-protagonist-voice",)
    return ()


def selection_hash(selection: dict[str, Any]) -> str:
    keys = ("config_id", "db_model_id", "api_model_id", "provider_id", "tested_at", "voice_id", "version")
    payload = {key: selection.get(key) for key in keys}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def valid_voice_selection(
    run: object, snapshot: dict[str, str], allowlist: tuple[str, ...],
) -> dict[str, Any] | None:
    selection = dict((getattr(run, "run_metadata", None) or {}).get("voice_selection") or {})
    if not selection:
        return None
    expected = {key: snapshot[key] for key in ("config_id", "db_model_id", "api_model_id", "provider_id", "tested_at")}
    if any(selection.get(key) != value for key, value in expected.items()):
        return None
    if selection.get("voice_id") not in allowlist or int(selection.get("version") or 0) < 1:
        return None
    return selection if selection.get("selection_hash") == selection_hash(selection) else None
