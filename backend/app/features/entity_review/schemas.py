from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ReviewEntityItem(BaseModel):
    id: str
    novel_id: str | None = None
    chapter_id: str | None = None
    script_id: str | None = None
    entity_type: str
    name: str
    canonical_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    appearance: str | None = None
    visual_prompt: str | None = None
    evidence: str | None = None
    confidence: int = 0
    source: str = "deterministic"
    review_status: str
    is_approved: bool = False
    attributes: dict[str, Any] = Field(default_factory=dict)
    relations: list[dict[str, Any]] = Field(default_factory=list)
    extra_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReviewSummary(BaseModel):
    total: int
    counts: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    candidate_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    duplicate_risk_count: int = 0
    missing_evidence_count: int = 0
    rejected_noise_count: int = 0
    asset_gap_count: int = 0
    recommended_next_action: str = "run_analysis"


class PagedReviewEntities(BaseModel):
    items: list[ReviewEntityItem]
    page: int
    page_size: int
    total: int
    total_pages: int
    summary: ReviewSummary


ReviewStatus = Literal["candidate", "approved", "rejected", "legacy_active", "archived"]
ReviewSort = Literal["updated_desc", "updated_asc", "name_asc", "quality_desc"]
