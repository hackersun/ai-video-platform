"""Canonical schemas for extracted story entity candidates."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


EntityType = Literal["character", "scene", "prop", "event"]
ReviewState = Literal["candidate", "approved", "rejected", "legacy_active"]


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


class CanonicalEntityMention(BaseModel):
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    mention_text: Optional[str] = None
    evidence: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    confidence: int = Field(default=80, ge=0, le=100)

    @field_validator("source_type", "source_id", "novel_id", "chapter_id", "script_id", "mention_text", "evidence", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> Optional[str]:
        text = _clean_text(value)
        return text or None


class CanonicalEntityCandidate(BaseModel):
    entity_type: EntityType
    name: str = Field(min_length=1, max_length=200)
    canonical_name: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
    description: Optional[str] = None
    appearance: Optional[str] = None
    visual_prompt: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    relations: list[dict[str, Any]] = Field(default_factory=list)
    state_changes: list[dict[str, Any]] = Field(default_factory=list)
    evidence: Optional[str] = None
    evidence_span: Optional[str] = None
    source_chapter_id: Optional[str] = None
    source_chapter_index: Optional[int] = Field(default=None, ge=1)
    source_chapter_number: Optional[int] = Field(default=None, ge=1)
    char_start: Optional[int] = Field(default=None, ge=0)
    char_end: Optional[int] = Field(default=None, ge=0)
    source_scope: dict[str, Any] = Field(default_factory=dict)
    confidence: int = Field(default=80, ge=0, le=100)
    source: str = "deterministic"
    extraction_model: str = "deterministic-v2"
    extraction_config: dict[str, Any] = Field(default_factory=dict)
    review_state: ReviewState = "candidate"
    actor: Optional[str] = None
    action: Optional[str] = None
    object: Optional[str] = None
    outcome: Optional[str] = None
    current_state: dict[str, Any] = Field(default_factory=dict)
    known_to_characters: list[str] = Field(default_factory=list)
    introduced_at: Optional[int] = Field(default=None, ge=1)
    resolved_at: Optional[int] = Field(default=None, ge=1)
    future_intent: Optional[str] = None
    foreshadowing: Optional[str] = None
    mentions: list[CanonicalEntityMention] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_complete_event_shape(self):
        if self.char_start is not None and self.char_end is not None and self.char_end < self.char_start:
            raise ValueError("char_end must be greater than or equal to char_start")
        if self.entity_type == "event" and not all((self.actor, self.action, self.object, self.outcome)):
            raise ValueError("event requires actor action object outcome")
        return self

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: Any) -> str:
        return _clean_text(value)

    @field_validator("canonical_name", "description", "appearance", "visual_prompt", "evidence", "evidence_span", "source_chapter_id", "actor", "action", "object", "outcome", "future_intent", "foreshadowing", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> Optional[str]:
        text = _clean_text(value)
        return text or None

    @field_validator("source", mode="before")
    @classmethod
    def normalize_source(cls, value: Any) -> str:
        return _clean_text(value) or "deterministic"

    @field_validator("aliases", mode="before")
    @classmethod
    def normalize_aliases(cls, value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            values = [value]
        elif isinstance(value, list):
            values = value
        else:
            return []
        result: list[str] = []
        for item in values:
            text = _clean_text(item)
            if text and text not in result:
                result.append(text)
        return result

    @field_validator("attributes", "source_scope", "extraction_config", "current_state", mode="before")
    @classmethod
    def normalize_dict(cls, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @field_validator("known_to_characters", mode="before")
    @classmethod
    def normalize_known_characters(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [text for item in value if (text := _clean_text(item))]

    @field_validator("relations", "state_changes", mode="before")
    @classmethod
    def normalize_dict_list(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]
