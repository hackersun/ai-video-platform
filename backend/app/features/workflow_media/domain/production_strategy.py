"""Production-strategy rules owned by the workflow-media feature."""

from typing import Any, Dict, Optional


SUPPORTED_GENERATION_STRATEGIES = frozenset({"direct_av_first", "separate_video_tts"})

_STRATEGY_METADATA = {
    "draft_fast": ("Draft Fast", "draft", "Seedance-2.0-fast"),
    "final_quality": ("Final Quality", "final", "Seedance-2.0"),
    "low_cost": ("Low Cost", "draft", "low-cost configuration"),
    "separate_video_tts": ("Separate Video + TTS", "draft", None),
    "direct_av_first": ("Direct AV First", "draft", None),
}


def validate_generation_strategy(strategy: str) -> None:
    if strategy not in SUPPORTED_GENERATION_STRATEGIES:
        from app.features.workflow_media.errors import WorkflowMediaError

        raise WorkflowMediaError(422, "当前仅支持 direct_av_first 或 separate_video_tts 策略")


def validate_production_strategy(strategy: Optional[str]) -> None:
    if strategy and strategy not in _STRATEGY_METADATA:
        from app.features.workflow_media.errors import WorkflowMediaError

        raise WorkflowMediaError(422, "未知生产策略")


def production_strategy_metadata(strategy: Optional[str]) -> Dict[str, Any]:
    values = _STRATEGY_METADATA.get(strategy or "")
    if values is None:
        return {}
    label, intent, model_hint = values
    return {
        "production_strategy": strategy,
        "routing_enabled": True,
        "production_strategy_label": label,
        "production_strategy_intent": intent,
        "recommended_model_hint": model_hint,
    }


def production_strategy_job_extra(
    strategy: Optional[str], model_config_id: Optional[str],
) -> Dict[str, Any]:
    metadata = production_strategy_metadata(strategy)
    if model_config_id:
        metadata.pop("recommended_model_hint", None)
    return metadata


def merge_latest_production_strategy(
    metadata: Dict[str, Any], strategy: Optional[str],
) -> Dict[str, Any]:
    strategy_metadata = production_strategy_metadata(strategy)
    if not strategy_metadata:
        return metadata
    return {
        **metadata,
        "latest_production_strategy": strategy,
        "latest_production_strategy_label": strategy_metadata.get("production_strategy_label"),
        "latest_production_strategy_intent": strategy_metadata.get("production_strategy_intent"),
        "latest_recommended_model_hint": strategy_metadata.get("recommended_model_hint"),
        "production_strategy_metadata": strategy_metadata,
    }
