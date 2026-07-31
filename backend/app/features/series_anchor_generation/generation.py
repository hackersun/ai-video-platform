"""Fail-closed selected-anchor generation orchestration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import hashlib
import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.features.series_run_media_preflight.public import evaluate_media_preflight
from app.models.media_generation_job import MediaGenerationJob
from app.models.series_anchor_generation_submission import SeriesAnchorGenerationSubmission
from app.models.series_production_run import SeriesProductionRun
from app.models.shot import Shot
from app.models.workflow import Workflow
from app.services.anchor_shot_service import anchor_coverage_blocker, recommend_anchor_shots, validate_anchor_selection
from app.services.deterministic_provider_fake import deterministic_provider_fake_enabled
from app.services.live_canary_bindings import BindingValidationError, validate_persisted_model_bindings
from app.services.series_run_live_preflight import build_live_preflight_plan
from app.services.series_run_orchestrator import InvalidRunTransition, SeriesRunOrchestrator, SeriesRunPreflightBlocked

from .deterministic_quality import evaluate_deterministic_anchors
from .errors import SeriesAnchorError
from .media_reconciliation import pending_source_response
from .quality_status import unevaluated_quality_results
from .skill_evidence import record_anchor_skill_evidence


MediaBatch = Callable[[str, list[str], str | None, str | None], Awaitable[dict]]
AcceptQuality = Callable[[object, MediaGenerationJob, list[str]], Awaitable[dict]]


def deterministic_quality_identity(run: SeriesProductionRun, jobs: list[MediaGenerationJob], selected: list[str]) -> bool:
    capabilities = (run.model_bindings or {}).get("capabilities") or {}
    expected = {f"deterministic-{name}" for name in ("text", "image", "tts", "video")}
    bound_models = {
        str(binding.get("api_model_id") or binding.get("db_model_id") or "")
        for binding in capabilities.values() if isinstance(binding, dict)
    }
    bindings_match = len(capabilities) == 4 and bound_models == expected and all(
        binding.get("provider_id") == "deterministic-acceptance"
        for binding in capabilities.values() if isinstance(binding, dict)
    )
    by_shot = {str(job.shot_id): job for job in jobs}
    jobs_match = set(by_shot) == set(selected) and all(
        job.provider_id == "deterministic-acceptance"
        and str(job.model_id or "").startswith("deterministic-")
        and (job.extra_data or {}).get("deterministic_provider_fake") is True
        for job in jobs
    )
    return bindings_match and jobs_match


async def _deterministic_quality_allowed(
    db: AsyncSession, *, run: SeriesProductionRun, user_id: str, selected: list[str],
) -> bool:
    jobs = list((await db.scalars(select(MediaGenerationJob).where(
        MediaGenerationJob.user_id == user_id,
        MediaGenerationJob.shot_id.in_(selected),
        MediaGenerationJob.is_active.is_(True),
        MediaGenerationJob.status.in_(("succeeded", "completed")),
    ))).all())
    return deterministic_quality_identity(run, jobs, selected)


def _selected_ids(run: SeriesProductionRun, shots: list, requested: list[str], mode: str) -> list[str]:
    try:
        selected = validate_anchor_selection(requested, {shot.id for shot in shots})
    except ValueError as error:
        raise SeriesAnchorError(422, str(error)) from error
    metadata = run.run_metadata or {}
    if selected != (metadata.get("selected_anchor_shot_ids") or []) or mode != metadata.get("selected_anchor_mode"):
        raise SeriesAnchorError(409, "generation selection must match the persisted anchor mode and order")
    recommendations = recommend_anchor_shots([shot for shot in shots if shot.id in set(selected)], mode=mode)
    blocker = anchor_coverage_blocker(recommendations, mode=mode)
    if blocker:
        raise SeriesAnchorError(409, blocker)
    if set(selected) != {item["shot_id"] for item in recommendations}:
        raise SeriesAnchorError(422, "locked selection no longer satisfies anchor mode coverage")
    return selected


async def _preflight(db: AsyncSession, run: SeriesProductionRun, *, native_audio: bool = False) -> dict:
    plan = await build_live_preflight_plan(db, run, native_audio=native_audio)
    media = await evaluate_media_preflight(db, run, native_audio=native_audio)
    if not plan.get("ready") or not media.get("ready"):
        raise SeriesAnchorError(409, {"code": "generation_preflight_blocked",
            "message": "生成提交前置条件已变化或仍有阻塞",
            "blocker_codes": list(dict.fromkeys([*(plan.get("blocker_codes") or []), *(media.get("codes") or [])]))})
    policy = run.budget_policy or {}
    if policy.get("profile") != "isolated_live_canary" or policy.get("live_canary") is not True:
        raise SeriesAnchorError(409, {"code": "live_canary_policy_required",
                                     "message": "真实关键镜头生成必须使用服务端受信 live canary 预算策略"})
    try:
        await validate_persisted_model_bindings(db, run, required_capabilities={"video"})
    except BindingValidationError as error:
        await db.rollback()
        raise SeriesAnchorError(409, {"code": "model_bindings_not_fresh",
                                     "message": "模型绑定无效或测试状态已过期"}) from error
    return media


async def _quality_contexts(
    db: AsyncSession, *, run: SeriesProductionRun, selected: list[str],
    workflow_for_shot: dict[str, str], media: dict,
) -> tuple[list[Shot], dict[str, dict], dict[str, dict]]:
    rows = list((await db.scalars(select(Shot).where(Shot.id.in_(selected), Shot.user_id == run.user_id))).all())
    by_id = {row.id: row for row in rows}
    if set(by_id) != set(selected):
        raise SeriesAnchorError(409, {"code": "generation_quality_lineage_missing", "message": "关键镜头不存在或不属于当前用户"})
    reference = (run.run_metadata or {}).get("reference_preparation") or {}
    story_bible_id = str(((run.run_metadata or {}).get("story_locks") or {}).get("story_bible_id") or "")
    episodes = {str((item.get("canonical_ids") or {}).get("workflow_id")): item for item in run.episodes or []}
    contexts = {}
    for shot_id in selected:
        workflow_id = workflow_for_shot.get(shot_id)
        workflow = await db.get(Workflow, workflow_id) if workflow_id else None
        contract = ((workflow.metadata_ or {}).get("episode_contract") or {}) if workflow else {}
        episode = episodes.get(str(workflow_id)) or {}
        context = {**dict((by_id[shot_id].extra_data or {}).get("production_context") or {}),
            "asset_version_locks": [dict(item) for item in media.get("asset_locks") or []],
            "story_bible_id": story_bible_id, "series_run_id": run.id,
            "preflight_snapshot_hash": media.get("snapshot_hash"), "episode_number": int(episode.get("episode_number") or 0),
            "episode_contract_version": str(contract.get("snapshot_hash") or episode.get("contract_version") or ""),
            "canonical_reference_id": str(reference.get("asset_id") or ""),
            "canonical_reference_version": int(reference.get("asset_version") or 0),
            "as_of_chapter_id": str(contract.get("chapter_id") or ((episode.get("chapter_ids") or [""])[0])),
            "as_of_chapter_hash": str(episode.get("input_hash") or ""),
            "shot_input_fingerprint": _shot_input_fingerprint(by_id[shot_id])}
        required = ("episode_number", "episode_contract_version", "canonical_reference_id",
                    "canonical_reference_version", "as_of_chapter_id", "as_of_chapter_hash")
        if any(not context.get(key) for key in required):
            raise SeriesAnchorError(409, {"code": "generation_quality_lineage_missing",
                                         "message": "关键镜头缺少服务端锁定的质量谱系", "shot_id": shot_id})
        contexts[shot_id] = context
    return [by_id[item] for item in selected], episodes, contexts


def _shot_input_fingerprint(shot: Shot) -> str:
    extra = shot.extra_data if isinstance(shot.extra_data, dict) else {}
    value = {
        "shot_id": shot.id,
        "prompt": shot.prompt,
        "visual_description": shot.visual_description,
        "dialogue": shot.dialogue,
        "subtitle_text": extra.get("subtitle_text"),
    }
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _generation_key(
    run: SeriesProductionRun, selected: list[str], mode: str, native_audio: bool,
    selected_shots: list[Shot] | None = None,
) -> str:
    metadata = run.run_metadata or {}; story = metadata.get("story_locks") or {}; reference = metadata.get("reference_preparation") or {}
    if not story.get("source_hash") or not (story.get("snapshot_hash") or story.get("bible_snapshot_hash")) or not reference.get("evidence_hash"):
        raise SeriesAnchorError(409, {"code": "generation_snapshot_missing", "message": "缺少当前故事或参考资产快照"})
    value = {"run_id": run.id, "selection_revision": int(metadata.get("anchor_selection_revision") or 0),
        "mode": mode, "shot_ids": selected, "native_audio": native_audio,
        "episode_input_hashes": [str(item.get("input_hash") or "") for item in run.episodes or []],
        "story_source_hash": story["source_hash"],
        "bible_snapshot_hash": story.get("snapshot_hash") or story["bible_snapshot_hash"],
        "reference_evidence_hash": reference["evidence_hash"]}
    if selected_shots is not None:
        by_id = {shot.id: shot for shot in selected_shots}
        value["shot_input_fingerprints"] = [_shot_input_fingerprint(by_id[item]) for item in selected]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


async def _submission(db: AsyncSession, run: SeriesProductionRun, user_id: str, key: str):
    existing = await db.scalar(select(SeriesAnchorGenerationSubmission).where(
        SeriesAnchorGenerationSubmission.run_id == run.id,
        SeriesAnchorGenerationSubmission.generation_key == key))
    if existing and existing.status in {"completed", "provider_pending", "provider_ready"}:
        return existing, existing.response_payload, False
    if existing and existing.status not in {"partial", "failed"}:
        raise SeriesAnchorError(409, {"code": "generation_submission_busy", "message": "相同生成输入正在处理",
                                     "generation_key": key})
    return (existing or SeriesAnchorGenerationSubmission(id=str(uuid4()), run_id=run.id, user_id=user_id,
                                                           generation_key=key, status="pending", response_payload={}),
            None, existing is None)


async def _generation_groups(
    db: AsyncSession, *, user_id: str, selected: list[str], workflow_for_shot: dict[str, str],
    selected_by_id: dict[str, Shot], contexts: dict[str, dict] | None = None,
) -> tuple[dict[str, list[str]], list[str]]:
    groups, reused = {}, []
    for shot_id in selected:
        workflow_id = workflow_for_shot.get(shot_id)
        if not workflow_id:
            raise SeriesAnchorError(409, "selected shot has no canonical workflow")
        latest = await db.scalar(select(MediaGenerationJob).where(
            MediaGenerationJob.user_id == user_id, MediaGenerationJob.workflow_id == workflow_id,
            MediaGenerationJob.shot_id == shot_id, MediaGenerationJob.is_active.is_(True),
        ).order_by(MediaGenerationJob.created_at.desc()).limit(1))
        if latest is not None and latest.status in {"unknown", "reserved", "accepted", "processing", "pending"}:
            raise SeriesAnchorError(409, {"code": "provider_state_reconciliation_required", "job_id": latest.id})
        context = dict((selected_by_id[shot_id].extra_data or {}).get("production_context") or {})
        fresh_fingerprint = ((contexts or {}).get(shot_id) or {}).get("shot_input_fingerprint")
        if fresh_fingerprint:
            context["shot_input_fingerprint"] = fresh_fingerprint
        extra = latest.extra_data if latest and isinstance(latest.extra_data, dict) else {}
        match_keys = [
            "episode_number", "episode_contract_version", "canonical_reference_id",
            "canonical_reference_version", "as_of_chapter_id", "as_of_chapter_hash",
        ]
        if not deterministic_provider_fake_enabled():
            match_keys.append("shot_input_fingerprint")
        matches = latest is not None and latest.status in {"succeeded", "completed"} and all(
            str(extra.get(key) or "") == str(context.get(key) or "") for key in (
                match_keys))
        (reused if matches else groups.setdefault(workflow_id, [])).append(latest.id if matches else shot_id)
    return groups, reused


async def _activate(
    db: AsyncSession, *, run: SeriesProductionRun, submission: SeriesAnchorGenerationSubmission,
    contexts: dict[str, dict], selected_by_id: dict[str, Shot], is_new: bool,
    media_preflight: dict | None = None,
    native_audio: bool = False,
) -> None:
    try:
        if run.status != "media_running":
            await SeriesRunOrchestrator().enter_media_running(
                db, run, native_audio=native_audio,
            )
    except (BindingValidationError, SeriesRunPreflightBlocked, InvalidRunTransition) as error:
        await db.rollback()
        detail = error.detail if isinstance(error, SeriesRunPreflightBlocked) else {
            "code": "generation_transition_blocked", "message": "生成状态切换未通过服务端校验"}
        raise SeriesAnchorError(409, detail) from error
    for shot_id, context in contexts.items():
        selected_by_id[shot_id].extra_data = {
            **(selected_by_id[shot_id].extra_data or {}), "production_context": context,
        }
        flag_modified(selected_by_id[shot_id], "extra_data")
    submission.status = "pending"
    if media_preflight is not None:
        run.gate_summary = {**(run.gate_summary or {}), "media_preflight": media_preflight}
    if is_new: db.add(submission)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise SeriesAnchorError(409, {"code": "generation_submission_busy", "message": "相同生成输入已由另一请求占用"}) from error


async def _evaluate_quality(
    db: AsyncSession, *, run: SeriesProductionRun, user_id: str, selected: list[str],
    selected_rows: list[Shot], workflow_for_shot: dict[str, str], episodes: dict[str, dict],
    batches: list[dict], submission: SeriesAnchorGenerationSubmission,
    accept_quality: AcceptQuality | None,
) -> list[dict]:
    deterministic = deterministic_provider_fake_enabled() and await _deterministic_quality_allowed(
        db, run=run, user_id=user_id, selected=selected,
    )
    if deterministic:
        try:
            return await evaluate_deterministic_anchors(
                db, run=run, user_id=user_id, selected_shots=selected_rows,
                workflow_for_shot=workflow_for_shot, episode_by_workflow=episodes,
                accept=accept_quality,
            )
        except Exception:
            reports = (run.run_metadata or {}).get("anchor_quality_reports") or {}
            submission.status = "partial" if reports else "failed"
            submission.response_payload = {
                "selected_shot_ids": selected, "workflow_batches": batches,
                "quality_results": [], "error_code": "deterministic_evaluation_interrupted",
            }
            await db.commit()
            raise
    try:
        return await unevaluated_quality_results(
            db, user_id=user_id, selected_shots=selected_rows,
            workflow_for_shot=workflow_for_shot, episode_by_workflow=episodes,
        )
    except Exception as error:
        submission.status = "failed"
        submission.response_payload = {
            "selected_shot_ids": selected, "workflow_batches": batches,
            "quality_results": [], "error_code": "trusted_multimodal_evaluation_required",
        }
        await db.commit()
        raise SeriesAnchorError(409, {
            "code": "generated_artifact_not_ready", "message": "关键镜头产物尚未形成可验证交付",
        }) from error


async def generate_selected(
    db: AsyncSession, *, run: SeriesProductionRun, user_id: str, shots: list,
    workflow_for_shot: dict[str, str], requested: list[str], mode: str, generate_batch: MediaBatch,
    native_audio: bool = False,
    accept_quality: AcceptQuality | None = None,
) -> dict:
    selected = _selected_ids(run, shots, requested, mode)
    media = await _preflight(db, run, native_audio=native_audio)
    selected_rows, episodes, contexts = await _quality_contexts(
        db, run=run, selected=selected, workflow_for_shot=workflow_for_shot, media=media)
    key = _generation_key(run, selected, mode, native_audio, selected_rows)
    submission, completed, is_new = await _submission(db, run, user_id, key)
    if completed is not None: return completed
    selected_by_id = {shot.id: shot for shot in selected_rows}
    groups, reused = await _generation_groups(db, user_id=user_id, selected=selected,
        workflow_for_shot=workflow_for_shot, selected_by_id=selected_by_id, contexts=contexts)
    run_id = run.id
    submission_id = submission.id
    await db.rollback()
    run = await db.get(SeriesProductionRun, run_id)
    selected_rows = list((await db.scalars(select(Shot).where(Shot.id.in_(selected), Shot.user_id == user_id))).all())
    selected_by_id = {shot.id: shot for shot in selected_rows}
    submission = None if is_new else await db.get(SeriesAnchorGenerationSubmission, submission_id)
    if submission is None:
        submission = SeriesAnchorGenerationSubmission(id=submission_id, run_id=run.id, user_id=user_id,
            generation_key=key, status="pending", response_payload={})
    await _activate(db, run=run, submission=submission, contexts=contexts, selected_by_id=selected_by_id,
                    is_new=is_new, media_preflight=media, native_audio=native_audio)
    bindings = (run.model_bindings or {}).get("capabilities") or {}
    try:
        batches = [await generate_batch(
            workflow_id, shot_ids, (bindings.get("video") or {}).get("config_id"),
            (bindings.get("tts") or {}).get("config_id"),
        ) for workflow_id, shot_ids in groups.items()]
    except Exception:
        submission.status = "failed"
        submission.response_payload = {
            "selected_shot_ids": selected,
            "workflow_batches": [],
            "quality_results": [],
            "error_code": "media_batch_submission_failed",
        }
        await db.commit()
        raise
    if reused: batches.append({"reused": True, "media_job_ids": reused})
    await record_anchor_skill_evidence(db, run, batches)
    pending = pending_source_response(selected, batches)
    if pending is not None:
        submission.status, submission.response_payload = pending["status"], pending
        await db.commit()
        return pending
    quality = await _evaluate_quality(
        db, run=run, user_id=user_id, selected=selected, selected_rows=selected_rows,
        workflow_for_shot=workflow_for_shot, episodes=episodes, batches=batches,
        submission=submission, accept_quality=accept_quality,
    )
    response = {"status": "completed", "selected_shot_ids": selected,
                "workflow_batches": batches, "quality_results": quality}
    submission.status, submission.response_payload = "completed", response
    await db.commit()
    return response


__all__ = ["deterministic_quality_identity", "generate_selected"]
