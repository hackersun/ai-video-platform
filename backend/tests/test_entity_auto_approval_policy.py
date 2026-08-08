from types import SimpleNamespace

from app.features.entity_review.approval_policy import (
    can_auto_approve_candidate,
    mention_has_approval_evidence,
)


def test_approval_evidence_requires_source_excerpt_and_confidence() -> None:
    assert mention_has_approval_evidence(SimpleNamespace(
        source_id="chapter-1",
        evidence="林澈",
        confidence=100,
    ))
    assert not mention_has_approval_evidence(SimpleNamespace(
        source_id="chapter-1",
        evidence="",
        confidence=100,
    ))


def test_explicit_opt_in_accepts_verified_high_quality_deterministic_candidate() -> None:
    quality = {
        "score": 100,
        "auto_decision": "needs_review",
        "flags": ["deterministic_requires_review"],
    }

    assert can_auto_approve_candidate(
        quality,
        allow_auto_approve=True,
        has_approval_evidence=True,
    )


def test_deterministic_candidate_stays_pending_without_all_safety_conditions() -> None:
    quality = {
        "score": 100,
        "auto_decision": "needs_review",
        "flags": ["deterministic_requires_review"],
    }

    assert not can_auto_approve_candidate(
        quality,
        allow_auto_approve=False,
        has_approval_evidence=True,
    )
    assert not can_auto_approve_candidate(
        quality,
        allow_auto_approve=True,
        has_approval_evidence=False,
    )
    assert not can_auto_approve_candidate(
        {**quality, "flags": ["deterministic_requires_review", "noise:character_event_phrase"]},
        allow_auto_approve=True,
        has_approval_evidence=True,
    )
