"""Seedance reference payload contract registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


OFFICIAL_SEEDANCE_SOURCES = [
    "https://www.volcengine.com/docs/82379/1520757",
]

SEEDANCE_CONTRACT_VERSION = "seedance-2.0-ark-2026-07-11"
REQUIRED_CONFIRMATION_EVIDENCE = (
    "official_schema_url",
    "official_schema_accessed_at",
    "payload_contract_test",
    "live_canary_job_id",
    "pricing_url",
    "failure_retry_evidence",
)
SEEDANCE_2_EVIDENCE: dict[str, object] = {
    "official_schema_url": "https://www.volcengine.com/docs/82379/1520757",
    "official_schema_accessed_at": "2026-07-11",
    "payload_contract_test": (
        "tests/test_reference_package.py::"
        "test_provider_content_adapter_submits_multimodal_references"
    ),
    "live_canary_job_id": None,
    "pricing_url": "https://www.volcengine.com/activity/seedance2",
    "failure_retry_evidence": None,
}

SEEDANCE_2_MODEL_IDS = {
    "doubao-seedance-2-0-260128",
    "doubao-seedance-2-0-fast-260128",
    "doubao-seedance-2-0-mini-260615",
    "volcano.seedance.2_0",
    "volcano.seedance.2_0_fast",
    "doubao-seedance-2.0",
    "doubao-seedance-2.0-fast",
}
SEEDANCE_NATIVE_AUDIO_MODEL_IDS = frozenset(
    {*SEEDANCE_2_MODEL_IDS, "doubao-seedance-1-5-pro-251215"}
)


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
    contract_version: str
    verified_at: str | None
    verification_gaps: list[str]

    @property
    def contract_status(self) -> str:
        if self.model_family != "seedance_2":
            return "unavailable"
        return self.status

    @property
    def reference_limits(self) -> dict[str, int | bool]:
        return {
            "images": self.max_images,
            "videos": self.max_videos,
            "audios": self.max_audios,
            "at_reference": self.at_reference_syntax is not None,
            "native_audio": self.max_audios > 0,
        }


def contract_is_confirmed(evidence: Mapping[str, object] | None) -> bool:
    values = evidence if isinstance(evidence, Mapping) else {}
    return all(values.get(key) for key in REQUIRED_CONFIRMATION_EVIDENCE)


def _verification_gaps(evidence: Mapping[str, object] | None) -> list[str]:
    values = evidence if isinstance(evidence, Mapping) else {}
    return [key for key in REQUIRED_CONFIRMATION_EVIDENCE if not values.get(key)]


def _seedance_2_contract(
    model_id: str,
    provider: str,
    evidence: Mapping[str, object] | None = None,
) -> SeedanceContract:
    is_agent_plan = provider == "volcano_agent_plan"
    resolved_evidence = dict(SEEDANCE_2_EVIDENCE if evidence is None else evidence)
    confirmed = contract_is_confirmed(resolved_evidence)
    return SeedanceContract(
        model_id=model_id,
        provider=provider,
        model_family="seedance_2",
        status="confirmed" if confirmed else "experimental",
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
        contract_version=SEEDANCE_CONTRACT_VERSION,
        verified_at=(
            str(resolved_evidence["official_schema_accessed_at"])
            if confirmed
            else None
        ),
        verification_gaps=_verification_gaps(resolved_evidence),
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
        contract_version="legacy-single-reference-v1",
        verified_at=None,
        verification_gaps=["model_contract_not_registered"],
    )


def resolve_seedance_contract(
    model_id: str | None,
    provider: str | None = None,
    *,
    evidence: Mapping[str, object] | None = None,
) -> SeedanceContract:
    resolved_model_id = (model_id or "").strip()
    resolved_provider = (provider or "volcano").strip()

    if resolved_model_id.lower() in SEEDANCE_2_MODEL_IDS:
        return _seedance_2_contract(resolved_model_id, resolved_provider, evidence)

    return _legacy_contract(resolved_model_id, resolved_provider)


def get_seedance_contract(model_id: str | None, provider: str | None = None) -> SeedanceContract:
    """Backward-compatible alias for callers using the original registry API."""
    return resolve_seedance_contract(model_id, provider)
