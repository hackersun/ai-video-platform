"""Deterministic six-dimensional quality evaluation orchestration."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from math import isfinite
from typing import Any, Mapping
from uuid import uuid4

from app.core.time_utils import utc_now
from app.models.quality_evaluation import (
    QUALITY_DIMENSIONS,
    QualityEvaluation,
    QualityEvaluationSet,
    QualityIssue,
)


USER_FACING_DIMENSIONS = (
    "narrative_truth",
    "character_visual",
    "scene_prop_state",
    "style_cinematography",
    "voice_dialogue",
    "delivery_integrity",
)

_INTERNAL_DIMENSION = {
    "narrative_truth": "narrative_truth",
    "character_visual": "character_visual",
    "scene_prop_state": "scene_prop_state",
    "style_cinematography": "motion_camera",
    "voice_dialogue": "voice_lipsync",
    "delivery_integrity": "delivery_integrity",
}

_TRUSTED_EVIDENCE_SOURCES = {
    "server_evaluator", "trusted_model_evaluator", "deterministic_probe",
}

AUTHORITATIVE_DIMENSION_POLICY = {
    dimension: {
        "threshold": 80.0,
        "threshold_version": "threshold-v1",
        "evaluator_version": "anchor-evaluator-v2",
    }
    for dimension in QUALITY_DIMENSIONS
}


class ArtifactBindingError(ValueError):
    """The evaluator evidence is not bound to the current generated artifact."""


DEFAULT_THRESHOLD_VERSION = "quality-thresholds-v1"
DEFAULT_EVALUATOR_VERSION = "quality-evaluator-v1"
DEFAULT_DIMENSION_THRESHOLDS = {
    dimension: {"warning": 80.0, "blocking": 60.0}
    for dimension in QUALITY_DIMENSIONS
}

_REPAIR_ACTIONS = {
    "main_character_identity_mismatch": "regenerate_shot_video",
    "future_episode_leakage": "revise_shot_prompt",
    "wrong_prop_owner": "regenerate_shot_video",
    "wrong_speaker": "regenerate_tts",
    "missing_subtitle": "generate_subtitles",
    "corrupt_mp4": "rerender_video",
    "background_variation": "review_visual_variation",
    "ambient_difference": "review_ambient_audio",
    "background_unverified": "review_visual_evidence",
    "ambient_audio_unverified": "review_audio_evidence",
}

_MESSAGES = {
    "main_character_identity_mismatch": "Main-character identity does not match the locked character.",
    "future_episode_leakage": "Artifact contains story facts from a future episode.",
    "wrong_prop_owner": "Observed prop owner does not match the expected story state.",
    "wrong_speaker": "Observed speaker does not match the expected speaker.",
    "missing_subtitle": "Required subtitle track is missing.",
    "corrupt_mp4": "Rendered MP4 failed deterministic integrity validation.",
    "background_variation": "Background contains a noncritical visual variation.",
    "ambient_difference": "Ambient audio differs without changing story meaning.",
    "background_unverified": "Background observation evidence is missing.",
    "ambient_audio_unverified": "Ambient-audio observation evidence is missing.",
}


def _issue(
    code: str,
    dimension: str,
    *,
    blocking: bool,
    evidence: Mapping[str, Any],
) -> QualityIssue:
    return QualityIssue(
        code=code,
        dimension=dimension,
        severity="blocking" if blocking else "warning",
        blocking=blocking,
        message=_MESSAGES[code],
        evidence=deepcopy(dict(evidence)),
        repair_action={"code": _REPAIR_ACTIONS[code]},
    )


def _deterministic_issues(
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> tuple[QualityIssue, ...]:
    issues: list[QualityIssue] = []

    expected_character = expected.get("main_character_id")
    observed_character = observed.get("main_character_id")
    if expected_character and observed_character != expected_character:
        issues.append(
            _issue(
                "main_character_identity_mismatch",
                "character_visual",
                blocking=True,
                evidence={"expected": expected_character, "observed": observed_character},
            )
        )

    episode_index = expected.get("episode_index")
    source_indices = observed.get("source_episode_indices")
    future_indices = (
        [index for index in source_indices if isinstance(index, int) and index > episode_index]
        if isinstance(episode_index, int) and isinstance(source_indices, list)
        else []
    )
    if observed.get("future_episode_leakage") is True or future_indices:
        issues.append(
            _issue(
                "future_episode_leakage",
                "narrative_truth",
                blocking=True,
                evidence={"episode_index": episode_index, "future_episode_indices": future_indices},
            )
        )

    expected_owners = expected.get("prop_owners")
    observed_owners = observed.get("prop_owners")
    owner_mismatches = {
        prop_id: {"expected": owner_id, "observed": (observed_owners or {}).get(prop_id)}
        for prop_id, owner_id in (expected_owners or {}).items()
        if not isinstance(observed_owners, Mapping) or observed_owners.get(prop_id) != owner_id
    }
    if owner_mismatches:
        issues.append(
            _issue(
                "wrong_prop_owner",
                "scene_prop_state",
                blocking=True,
                evidence={"prop_owner_mismatches": owner_mismatches},
            )
        )

    expected_speaker = expected.get("speaker_id")
    observed_speaker = observed.get("speaker_id")
    if expected_speaker and observed_speaker != expected_speaker:
        issues.append(
            _issue(
                "wrong_speaker",
                "voice_lipsync",
                blocking=True,
                evidence={"expected": expected_speaker, "observed": observed_speaker},
            )
        )

    if expected.get("subtitle_required") is True and observed.get("subtitle_present") is not True:
        issues.append(
            _issue(
                "missing_subtitle",
                "delivery_integrity",
                blocking=True,
                evidence={"subtitle_present": observed.get("subtitle_present")},
            )
        )

    if expected.get("mp4_required") is True and observed.get("mp4_valid") is not True:
        issues.append(
            _issue(
                "corrupt_mp4",
                "delivery_integrity",
                blocking=True,
                evidence={"mp4_valid": observed.get("mp4_valid")},
            )
        )

    expected_background = expected.get("background")
    observed_background = observed.get("background")
    if expected_background and not observed_background:
        issues.append(_issue("background_unverified", "scene_prop_state", blocking=False, evidence={"expected": expected_background, "observed": None}))
    elif expected_background and observed_background != expected_background:
        issues.append(
            _issue(
                "background_variation",
                "scene_prop_state",
                blocking=False,
                evidence={"expected": expected_background, "observed": observed_background},
            )
        )

    expected_ambient = expected.get("ambient_audio")
    observed_ambient = observed.get("ambient_audio")
    if expected_ambient and not observed_ambient:
        issues.append(_issue("ambient_audio_unverified", "voice_lipsync", blocking=False, evidence={"expected": expected_ambient, "observed": None}))
    elif expected_ambient and observed_ambient != expected_ambient:
        issues.append(
            _issue(
                "ambient_difference",
                "voice_lipsync",
                blocking=False,
                evidence={"expected": expected_ambient, "observed": observed_ambient},
            )
        )

    return tuple(issues)


def _semantic_signal(
    semantic_scores: Mapping[str, Any],
    dimension: str,
) -> tuple[float, float, dict[str, Any]]:
    value = semantic_scores.get(dimension)
    if isinstance(value, Mapping):
        score = value.get("score", 100)
        confidence = value.get("confidence", 1.0)
        semantic_evidence = value.get("evidence")
    elif isinstance(value, (int, float)):
        score = value
        confidence = 1.0
        semantic_evidence = None
    else:
        score = 100
        confidence = 1.0
        semantic_evidence = None
    return (
        max(0.0, min(100.0, float(score))),
        max(0.0, min(1.0, float(confidence))),
        deepcopy(semantic_evidence) if isinstance(semantic_evidence, dict) else {},
    )


def _thresholds_for_dimension(
    dimension: str,
    dimension_thresholds: Mapping[str, Any],
) -> tuple[float, float]:
    configured = dimension_thresholds.get(dimension)
    defaults = DEFAULT_DIMENSION_THRESHOLDS[dimension]
    if isinstance(configured, Mapping):
        warning = float(configured.get("warning", defaults["warning"]))
        blocking = float(configured.get("blocking", defaults["blocking"]))
    else:
        warning = defaults["warning"]
        blocking = defaults["blocking"]
    if not 0 <= blocking <= warning <= 100:
        raise ValueError(
            f"invalid semantic thresholds for {dimension}: "
            "expected 0 <= blocking <= warning <= 100"
        )
    return warning, blocking


def _semantic_threshold_issue(
    dimension: str,
    *,
    score: float,
    threshold: float,
    blocking: bool,
) -> QualityIssue:
    return QualityIssue(
        code="semantic_score_below_blocking" if blocking else "semantic_score_below_warning",
        dimension=dimension,
        severity="blocking" if blocking else "warning",
        blocking=blocking,
        message=(
            "Semantic quality score is below the hard dimension threshold."
            if blocking
            else "Semantic quality score is below the warning dimension threshold."
        ),
        evidence={"score": score, "threshold": threshold},
        repair_action={"code": "review_quality_evidence"},
    )


def evaluate_artifact(
    *,
    artifact_id: str,
    artifact_type: str,
    expected_state: Mapping[str, Any],
    observed_state: Mapping[str, Any],
    evidence: Mapping[str, Any] | None = None,
    workflow_id: str | None = None,
    shot_id: str | None = None,
    provider_id: str | None = None,
    model_id: str | None = None,
    semantic_scores: Mapping[str, Any] | None = None,
    dimension_thresholds: Mapping[str, Any] | None = None,
    threshold_version: str = DEFAULT_THRESHOLD_VERSION,
    evaluator_version: str = DEFAULT_EVALUATOR_VERSION,
    evaluated_at: datetime | None = None,
) -> QualityEvaluationSet:
    """Evaluate injected observations without invoking a model or network service."""

    expected = deepcopy(dict(expected_state))
    observed = deepcopy(dict(observed_state))
    base_evidence = deepcopy(dict(evidence or {}))
    semantic_scores = semantic_scores or {}
    dimension_thresholds = dimension_thresholds or {}
    evaluated_at = evaluated_at or utc_now()
    deterministic_issues = _deterministic_issues(expected, observed)
    semantic_signals = {
        dimension: _semantic_signal(semantic_scores, dimension)
        for dimension in QUALITY_DIMENSIONS
    }
    semantic_issues: list[QualityIssue] = []
    for dimension in QUALITY_DIMENSIONS:
        if dimension not in semantic_scores:
            continue
        score, _, _ = semantic_signals[dimension]
        warning_threshold, blocking_threshold = _thresholds_for_dimension(
            dimension,
            dimension_thresholds,
        )
        if score < blocking_threshold:
            semantic_issues.append(
                _semantic_threshold_issue(
                    dimension,
                    score=score,
                    threshold=blocking_threshold,
                    blocking=True,
                )
            )
        elif score < warning_threshold:
            semantic_issues.append(
                _semantic_threshold_issue(
                    dimension,
                    score=score,
                    threshold=warning_threshold,
                    blocking=False,
                )
            )
    issues = (*deterministic_issues, *semantic_issues)
    blockers = tuple(item for item in issues if item.blocking)
    warnings = tuple(item for item in issues if not item.blocking)
    dimension_results: list[QualityEvaluation] = []

    for dimension in QUALITY_DIMENSIONS:
        dimension_deterministic_issues = tuple(
            item for item in deterministic_issues if item.dimension == dimension
        )
        dimension_semantic_issues = tuple(
            item for item in semantic_issues if item.dimension == dimension
        )
        dimension_issues = (*dimension_deterministic_issues, *dimension_semantic_issues)
        dimension_blockers = tuple(item for item in dimension_issues if item.blocking)
        dimension_warnings = tuple(item for item in dimension_issues if not item.blocking)
        score, confidence, semantic_evidence = semantic_signals[dimension]
        if dimension_blockers:
            if any(item in deterministic_issues for item in dimension_blockers):
                score = 0.0
            severity = "blocking"
        elif dimension_warnings:
            if any(item in deterministic_issues for item in dimension_warnings):
                score = min(score, 79.0)
            severity = "warning"
        else:
            severity = "pass"

        dimension_results.append(
            QualityEvaluation(
                id=str(uuid4()),
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                workflow_id=workflow_id,
                shot_id=shot_id,
                provider_id=provider_id,
                model_id=model_id,
                dimension=dimension,
                expected_state=deepcopy(expected),
                observed_state=deepcopy(observed),
                evidence={
                    **deepcopy(base_evidence),
                    "semantic": semantic_evidence,
                    "issue_codes": [item.code for item in dimension_issues],
                    "deterministic": [
                        {"code": item.code, "evidence": deepcopy(item.evidence)}
                        for item in dimension_deterministic_issues
                    ],
                    "semantic_thresholds": [
                        {"code": item.code, "evidence": deepcopy(item.evidence)}
                        for item in dimension_semantic_issues
                    ],
                },
                score=score,
                confidence=confidence,
                severity=severity,
                blocking=bool(dimension_blockers),
                threshold_version=threshold_version,
                evaluator_version=evaluator_version,
                repair_action=(
                    deepcopy(
                        (dimension_blockers or dimension_warnings)[0].repair_action
                    )
                    if dimension_blockers or dimension_warnings
                    else None
                ),
                evaluated_at=evaluated_at,
                created_at=evaluated_at,
            )
        )

    ready = not blockers
    overall_readiness = "blocked" if blockers else "warning" if warnings else "ready"
    return QualityEvaluationSet(
        artifact_id=artifact_id,
        dimension_results=tuple(dimension_results),
        blockers=blockers,
        warnings=warnings,
        ready=ready,
        overall_readiness=overall_readiness,
        evaluated_at=evaluated_at,
    )


def _aware_datetime(value: Any, field: str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise ArtifactBindingError(f"{field} must be a datetime")
    # The repository deliberately persists UTC as naive values for SQLite
    # compatibility. Normalize both representations before strict comparison.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _validate_bound_evidence(
    *,
    binding: Mapping[str, Any],
    dimension_evidence: Mapping[str, Any],
) -> None:
    required_binding = (
        "artifact_id", "job_id", "shot_id", "episode_number",
        "episode_contract_version", "evaluator_version",
        "artifact_created_at", "evaluated_at",
    )
    missing_binding = [key for key in required_binding if not binding.get(key)]
    if missing_binding:
        raise ArtifactBindingError(f"missing artifact binding: {', '.join(missing_binding)}")
    artifact_created_at = _aware_datetime(binding["artifact_created_at"], "artifact creation time")
    evaluated_at = _aware_datetime(binding["evaluated_at"], "evaluation creation time")
    if evaluated_at < artifact_created_at:
        raise ArtifactBindingError("evaluation creation time predates the artifact")

    for dimension in USER_FACING_DIMENSIONS:
        evidence = dimension_evidence.get(dimension)
        if not isinstance(evidence, Mapping):
            raise ArtifactBindingError(f"missing evidence for {dimension}")
        for key in (
            "artifact_id", "job_id", "shot_id", "episode_contract_version",
            "evaluator_version",
        ):
            if str(evidence.get(key) or "") != str(binding[key]):
                raise ArtifactBindingError(f"{dimension} evidence {key} does not match current artifact")
        evidence_created_at = _aware_datetime(evidence.get("created_at"), "evidence creation time")
        if evidence_created_at != evaluated_at:
            raise ArtifactBindingError(f"{dimension} evidence creation time does not match the new evaluation")
        if evidence.get("source") not in _TRUSTED_EVIDENCE_SOURCES or not evidence.get("references"):
            raise ArtifactBindingError(f"{dimension} requires trusted evidence references")


def _comparison_findings(
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
    reference: Mapping[str, Any],
    *,
    comparison: str,
) -> dict[str, list[dict[str, Any]]]:
    fields = {
        "character_visual": ("main_character_id", "character_traits"),
        "scene_prop_state": ("scene_id", "prop_states"),
        "style_cinematography": ("style_profile", "shot_grammar"),
        "voice_dialogue": ("speaker_id", "voice_binding_id", "language"),
    }
    findings = {dimension: [] for dimension in USER_FACING_DIMENSIONS}
    for dimension, names in fields.items():
        scoped = reference.get(dimension)
        source = scoped if isinstance(scoped, Mapping) else reference
        for field in names:
            expected_value = source.get(field, expected.get(field))
            if expected_value is not None and observed.get(field) != expected_value:
                findings[dimension].append({
                    "code": f"{field}_mismatch",
                    "comparison": comparison,
                    "field": field,
                    "expected": deepcopy(expected_value),
                    "observed": deepcopy(observed.get(field)),
                })
    return findings


def evaluate_bound_anchor(
    *,
    binding: Mapping[str, Any],
    expected_state: Mapping[str, Any],
    observed_state: Mapping[str, Any],
    dimension_evidence: Mapping[str, Any],
    dimension_scores: Mapping[str, Any],
    canonical_reference: Mapping[str, Any] | None = None,
    preceding_accepted_anchor: Mapping[str, Any] | None = None,
    threshold: float = 80.0,
) -> dict[str, Any]:
    """Strictly evaluate one anchor; missing or stale evidence fails closed."""

    _validate_bound_evidence(binding=binding, dimension_evidence=dimension_evidence)
    missing_scores = [dimension for dimension in USER_FACING_DIMENSIONS if dimension not in dimension_scores]
    if missing_scores:
        raise ArtifactBindingError(f"missing evaluator scores: {', '.join(missing_scores)}")
    if str(expected_state.get("as_of_contract_version") or "") != str(binding["episode_contract_version"]):
        raise ArtifactBindingError("expected state episode_contract_version does not match binding")
    if preceding_accepted_anchor is not None:
        if preceding_accepted_anchor.get("accepted") is not True:
            raise ArtifactBindingError("preceding anchor must be accepted")
        if int(preceding_accepted_anchor.get("episode_number") or 0) > int(binding["episode_number"]):
            raise ArtifactBindingError("preceding anchor cannot belong to a later episode")
    if not isinstance(canonical_reference, Mapping):
        raise ArtifactBindingError("locked canonical reference is required for every episode")
    if not canonical_reference.get("reference_id") or not canonical_reference.get("version"):
        raise ArtifactBindingError("canonical reference identity and version are required")
    if int(binding["episode_number"]) > 1:
        if not isinstance(preceding_accepted_anchor, Mapping):
            raise ArtifactBindingError("preceding accepted anchor is required after episode one")

    expected = deepcopy(dict(expected_state))
    observed = deepcopy(dict(observed_state))
    findings = {dimension: [] for dimension in USER_FACING_DIMENSIONS}
    episode_number = int(binding["episode_number"])
    future = [
        value for value in observed.get("source_episode_indices") or []
        if isinstance(value, int) and value > episode_number
    ]
    if future:
        findings["narrative_truth"].append({
            "code": "future_episode_leakage",
            "comparison": "as_of_chapter_contract",
            "future_episode_indices": future,
        })
    for field in ("chapter_event_ids", "dialogue_meaning"):
        if expected.get(field) is not None and observed.get(field) != expected.get(field):
            findings["narrative_truth"].append({
                "code": f"{field}_mismatch",
                "comparison": "as_of_chapter_contract",
                "expected": deepcopy(expected.get(field)),
                "observed": deepcopy(observed.get(field)),
            })
    delivery_checks = {
        "mp4_valid": expected.get("mp4_required") is not True or observed.get("mp4_valid") is True,
        "subtitle_present": expected.get("subtitle_required") is not True or observed.get("subtitle_present") is True,
        "playable": observed.get("playable") is True,
        "duration_seconds": isinstance(observed.get("duration_seconds"), (int, float)) and observed.get("duration_seconds") > 0,
        "resolution": bool(observed.get("resolution")),
        "audio_stream_present": observed.get("audio_stream_present") is True,
        "manifest_lineage_valid": observed.get("manifest_lineage_valid") is True,
    }
    for field, valid in delivery_checks.items():
        if not valid:
            findings["delivery_integrity"].append({"code": f"{field}_invalid", "comparison": "artifact_probe"})
    voice_checks = ("dialogue_timing_valid", "intelligible")
    for field in voice_checks:
        if observed.get(field) is not True:
            findings["voice_dialogue"].append({"code": f"{field}_invalid", "comparison": "artifact_probe"})

    references = [(canonical_reference, "canonical")]
    if preceding_accepted_anchor is not None:
        references.append((preceding_accepted_anchor, "preceding_anchor"))
    elif canonical_reference is None:
        references = [(expected, "episode_contract")]
    for reference, comparison in references:
        if reference is None:
            continue
        compared = _comparison_findings(expected, observed, reference, comparison=comparison)
        for dimension in USER_FACING_DIMENSIONS:
            findings[dimension].extend(compared[dimension])

    dimensions: dict[str, Any] = {}
    for dimension in USER_FACING_DIMENSIONS:
        raw = dimension_scores[dimension]
        score = float(raw.get("score")) if isinstance(raw, Mapping) else float(raw)
        confidence = float(raw.get("confidence", 1.0)) if isinstance(raw, Mapping) else 1.0
        if not 0 <= score <= 100 or not 0 <= confidence <= 1:
            raise ValueError(f"invalid score or confidence for {dimension}")
        row_findings = findings[dimension]
        blocking = bool(row_findings) or score < threshold
        if score < threshold:
            row_findings.append({
                "code": "score_below_threshold",
                "comparison": "dimension_threshold",
                "score": score,
                "threshold": threshold,
            })
        evidence = deepcopy(dict(dimension_evidence[dimension]))
        evidence["as_of_contract_version"] = binding["episode_contract_version"]
        if preceding_accepted_anchor is not None:
            evidence["preceding_artifact_id"] = preceding_accepted_anchor.get("artifact_id")
        dimensions[dimension] = {
            "internal_dimension": _INTERNAL_DIMENSION[dimension],
            "score": score,
            "confidence": confidence,
            "threshold": threshold,
            "findings": row_findings,
            "evidence": evidence,
            "blocking": blocking,
            "status": "blocking" if blocking else "pass",
        }
    return {
        "artifact_id": binding["artifact_id"],
        "job_id": binding["job_id"],
        "shot_id": binding["shot_id"],
        "episode_number": episode_number,
        "episode_contract_version": binding["episode_contract_version"],
        "evaluator_version": binding["evaluator_version"],
        "evaluated_at": _aware_datetime(binding["evaluated_at"], "evaluation creation time").isoformat(),
        "ready": not any(row["blocking"] for row in dimensions.values()),
        "dimensions": dimensions,
    }


def validate_persisted_anchor_evaluations(
    rows: list[QualityEvaluation],
    *,
    allowed_workflow_ids: set[str],
    expected_shot_id: str,
    expected_episode_number: int,
    expected_canonical_reference_id: str,
    expected_preceding_artifact_id: str | None,
    expected_evaluator_version: str,
    artifact_completed_at: datetime,
    accepted_at: datetime,
) -> dict[str, Any]:
    """Validate one immutable six-row evaluation generation before series acceptance."""
    if len(rows) != len(QUALITY_DIMENSIONS):
        raise ArtifactBindingError("exactly six persisted dimension evaluations are required")
    by_dimension = {str(row.dimension): row for row in rows}
    if set(by_dimension) != set(QUALITY_DIMENSIONS):
        raise ArtifactBindingError("persisted evaluations do not cover the exact six dimensions")
    first = rows[0]
    first_evidence = first.evidence if isinstance(first.evidence, dict) else {}
    required = {
        "artifact_id": first.artifact_id,
        "job_id": first_evidence.get("job_id"),
        "shot_id": expected_shot_id,
        "episode_contract_version": first_evidence.get("episode_contract_version"),
        "evaluator_version": first.evaluator_version,
        "evaluated_at": first.evaluated_at,
    }
    if not all(required.values()):
        raise ArtifactBindingError("persisted evaluation lineage is incomplete")
    if first.workflow_id not in allowed_workflow_ids:
        raise ArtifactBindingError("evaluation workflow is outside this series run")
    if not expected_canonical_reference_id:
        raise ArtifactBindingError("server-resolved locked canonical reference is required for every episode")
    if expected_episode_number > 1 and not expected_preceding_artifact_id:
        raise ArtifactBindingError("server-resolved preceding accepted anchor is required after episode one")
    evaluated_at = _aware_datetime(first.evaluated_at, "evaluation creation time")
    if evaluated_at < _aware_datetime(artifact_completed_at, "artifact completion time"):
        raise ArtifactBindingError("evaluation predates artifact completion")
    if evaluated_at > _aware_datetime(accepted_at, "acceptance time"):
        raise ArtifactBindingError("evaluation creation time is unexpectedly in the future")
    if first.evaluator_version != expected_evaluator_version:
        raise ArtifactBindingError("evaluation does not use the server-authorized evaluator version")
    for row in rows:
        evidence = row.evidence if isinstance(row.evidence, dict) else {}
        policy = AUTHORITATIVE_DIMENSION_POLICY[str(row.dimension)]
        if row.workflow_id not in allowed_workflow_ids or row.workflow_id != first.workflow_id:
            raise ArtifactBindingError("evaluation workflow is outside this series run")
        if row.shot_id != expected_shot_id or row.artifact_id != required["artifact_id"]:
            raise ArtifactBindingError("evaluation artifact or shot does not match")
        if row.evaluator_version != required["evaluator_version"] or row.evaluated_at != required["evaluated_at"]:
            raise ArtifactBindingError("stale evaluator generation cannot be accepted")
        if row.evaluator_version != policy["evaluator_version"] or row.threshold_version != policy["threshold_version"]:
            raise ArtifactBindingError(f"{row.dimension} does not match the authoritative evaluator policy")
        if evidence.get("evaluator_version") != policy["evaluator_version"] or evidence.get("threshold_version") != policy["threshold_version"]:
            raise ArtifactBindingError(f"{row.dimension} evidence evaluator policy does not match the server registry")
        if row.created_at != row.evaluated_at:
            raise ArtifactBindingError("evaluation creation time does not match the new evaluator generation")
        evidence_created_at = evidence.get("created_at")
        if evidence_created_at and _aware_datetime(evidence_created_at, "evidence creation time") != _aware_datetime(row.evaluated_at, "evaluation creation time"):
            raise ArtifactBindingError("evidence creation time does not match the new evaluator generation")
        if evidence.get("job_id") != required["job_id"] or evidence.get("episode_contract_version") != required["episode_contract_version"]:
            raise ArtifactBindingError("evaluation job or episode contract does not match")
        if evidence.get("source") not in _TRUSTED_EVIDENCE_SOURCES or not evidence.get("references"):
            raise ArtifactBindingError("persisted evaluation lacks trusted evidence")
        if int(evidence.get("episode_number") or 0) != expected_episode_number:
            raise ArtifactBindingError("evidence episode number does not match the owned run episode")
        if row.dimension == "narrative_truth" and evidence.get("as_of_contract_version") != required["episode_contract_version"]:
            raise ArtifactBindingError("narrative evidence is not bound to the as-of-chapter contract")
        if row.dimension in {"character_visual", "scene_prop_state", "motion_camera", "voice_lipsync"}:
            if evidence.get("canonical_reference_id") != expected_canonical_reference_id:
                raise ArtifactBindingError(f"{row.dimension} canonical comparison does not match the locked reference")
            if expected_episode_number > 1 and evidence.get("preceding_artifact_id") != expected_preceding_artifact_id:
                raise ArtifactBindingError(f"{row.dimension} lacks the server-resolved preceding-anchor comparison evidence")
    inverse = {value: key for key, value in _INTERNAL_DIMENSION.items()}
    user_dimensions = {}
    for internal, row in by_dimension.items():
        evidence = deepcopy(row.evidence or {})
        policy = AUTHORITATIVE_DIMENSION_POLICY[internal]
        try:
            threshold = float(evidence.get("threshold"))
            score = float(row.score)
        except (TypeError, ValueError) as error:
            raise ArtifactBindingError(f"invalid threshold or score for {internal}") from error
        if not isfinite(threshold) or not 0 <= threshold <= 100 or not isfinite(score) or not 0 <= score <= 100:
            raise ArtifactBindingError(f"invalid threshold or score for {internal}")
        if threshold != policy["threshold"]:
            raise ArtifactBindingError(f"{internal} threshold does not match the server registry")
        findings = deepcopy(evidence.get("findings") or [])
        if not isinstance(findings, list):
            raise ArtifactBindingError(f"invalid findings for {internal}")
        blocking = score < threshold or bool(findings)
        user_dimensions[inverse[internal]] = {
            "evaluation_id": row.id,
            "score": score,
            "threshold": threshold,
            "findings": findings,
            "evidence": evidence,
            "blocking": blocking,
            "status": "blocking" if blocking else "pass",
        }
    return {
        **required,
        "evaluated_at": first.evaluated_at.isoformat(),
        "ready": not any(row["blocking"] for row in user_dimensions.values()),
        "dimensions": user_dimensions,
        "evaluation_ids": sorted(row.id for row in rows),
    }


__all__ = [
    "ArtifactBindingError",
    "AUTHORITATIVE_DIMENSION_POLICY",
    "USER_FACING_DIMENSIONS",
    "evaluate_artifact",
    "evaluate_bound_anchor",
    "validate_persisted_anchor_evaluations",
]
