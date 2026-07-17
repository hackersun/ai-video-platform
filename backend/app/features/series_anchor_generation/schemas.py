"""HTTP-neutral request and evidence schemas for series-run routes."""

from pydantic import BaseModel, Field, model_validator


class EpisodeInput(BaseModel):
    episode_number: int = Field(ge=1)
    chapter_ids: list[str] = Field(min_length=1)
    input_hash: str = Field(min_length=1)


class CreateSeriesRunRequest(BaseModel):
    novel_id: str
    series_plan_version: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    requested_stages: list[str] = Field(default_factory=list)
    model_bindings: dict = Field(default_factory=dict)
    budget_policy: dict = Field(default_factory=dict)
    episodes: list[EpisodeInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_episode_numbers(self):
        if [item.episode_number for item in self.episodes] != list(range(1, len(self.episodes) + 1)):
            raise ValueError("episode_number must be strictly contiguous from 1")
        return self


class ValidateLiveBindingsRequest(BaseModel):
    text: str; image: str; tts: str; video: str


class AnchorSelectionRequest(BaseModel):
    shot_ids: list[str] = Field(min_length=1, max_length=20)
    mode: str = Field(pattern="^(smoke|full)$")


class GenerateSelectedRequest(AnchorSelectionRequest):
    native_audio: bool = Field(False, description="仅本次关键镜头生成启用 Seedance 1.5 Pro 原生配音")


class VoiceSelectionRequest(BaseModel):
    config_id: str = Field(min_length=1); model_id: str = Field(min_length=1)
    voice_id: str = Field(min_length=1); version: int = Field(ge=1)


class DeterministicAcceptanceSetupRequest(BaseModel):
    novel_id: str = Field(min_length=1)


class RecoveryActionRequest(BaseModel):
    operation_id: str = Field(min_length=1)
    expected_run_version: int = Field(ge=1)


class AcceptAnchorQualityRequest(BaseModel):
    shot_id: str = Field(min_length=1); job_id: str = Field(min_length=1)
    evaluation_ids: list[str] = Field(min_length=6, max_length=6)


class PlanAnchorRepairRequest(BaseModel):
    artifact_id: str = Field(min_length=1); issue_code: str = Field(min_length=1)
    repair_key: str = Field(min_length=1)


class ReferenceOperationEvidence(BaseModel):
    id: str; status: str; provider_task_id: str | None = None; reservation_id: str
    actual_rmb: str | None = None; cost_source: str | None = None


class ReferenceArtifactEvidence(BaseModel):
    id: str; url: str; checksum: str; layout_evidence: dict; width: int; height: int; byte_size: int


class PrepareReferenceResponse(BaseModel):
    run_id: str; asset_id: str; asset_version: int; provider_binding_id: str; roles: list[str]
    status: str; idempotent: bool; resumed: bool
    operation: ReferenceOperationEvidence; artifact: ReferenceArtifactEvidence


__all__ = [name for name in globals() if name.endswith("Request") or name.endswith("Response")]
