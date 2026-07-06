"""Seedance reference payload contract registry."""

from __future__ import annotations

from dataclasses import dataclass


OFFICIAL_SEEDANCE_SOURCES = [
    "https://www.volcengine.com/docs/82379/1520757",
]

SEEDANCE_2_MODEL_IDS = {
    "doubao-seedance-2-0-260128",
    "doubao-seedance-2-0-fast-260128",
    "volcano.seedance.2_0",
    "volcano.seedance.2_0_fast",
    "doubao-seedance-2.0",
    "doubao-seedance-2.0-fast",
}


@dataclass(frozen=True)
class SeedanceReferenceRoles:
    image: str
    video: str
    audio: str


@dataclass(frozen=True)
class SeedanceContract:
    model_id: str
    provider: str
    model_family: str
    status: str
    roles: SeedanceReferenceRoles
    at_reference_syntax: str | None
    max_images: int
    max_videos: int
    max_audios: int
    pricing_status: str
    agent_plan_multireference: bool
    official_sources: list[str]


def _seedance_2_contract(model_id: str, provider: str) -> SeedanceContract:
    is_agent_plan = provider == "volcano_agent_plan"
    return SeedanceContract(
        model_id=model_id,
        provider=provider,
        model_family="seedance_2",
        status="experimental",
        roles=SeedanceReferenceRoles(
            image="reference_image",
            video="reference_video",
            audio="reference_audio",
        ),
        at_reference_syntax="@image{index}",
        max_images=1 if is_agent_plan else 9,
        max_videos=0 if is_agent_plan else 3,
        max_audios=0 if is_agent_plan else 3,
        pricing_status="unconfirmed",
        agent_plan_multireference=False,
        official_sources=list(OFFICIAL_SEEDANCE_SOURCES),
    )


def _legacy_contract(model_id: str, provider: str) -> SeedanceContract:
    return SeedanceContract(
        model_id=model_id,
        provider=provider,
        model_family="legacy",
        status="legacy_single_reference",
        roles=SeedanceReferenceRoles(
            image="image_url",
            video="unsupported",
            audio="unsupported",
        ),
        at_reference_syntax=None,
        max_images=1,
        max_videos=0,
        max_audios=0,
        pricing_status="not_applicable",
        agent_plan_multireference=False,
        official_sources=[],
    )


def get_seedance_contract(model_id: str | None, provider: str | None = None) -> SeedanceContract:
    resolved_model_id = (model_id or "").strip()
    resolved_provider = (provider or "volcano").strip()

    if resolved_model_id.lower() in SEEDANCE_2_MODEL_IDS:
        return _seedance_2_contract(resolved_model_id, resolved_provider)

    return _legacy_contract(resolved_model_id, resolved_provider)
