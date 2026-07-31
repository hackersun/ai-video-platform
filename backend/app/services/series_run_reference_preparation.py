"""Budgeted preparation of one composite series reference asset."""

from __future__ import annotations

from decimal import Decimal
import os
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.time_utils import utc_now
from app.features.series_reference_skill.public import bind_series_reference_skill
from app.models import Asset, ProviderAssetBinding, StoryBible, StoryEntity
from app.models.live_canary_provider_operation import LiveCanaryProviderOperation
from app.models.series_production_run import SeriesProductionRun
from app.services.deterministic_provider_fake import deterministic_provider_fake_enabled
from app.services.live_canary_budget import (
    BindingValidationError,
    BudgetExceeded,
    bind_provider_operation_task,
    mark_operation_manual_reconcile,
    prepare_provider_operation,
    settle_confirmed_provider_rejection,
    settle_provider_operation,
    settle_synchronous_provider_operation,
)
from app.services.live_canary_bindings import validate_persisted_model_bindings
from app.services.provider_asset_binding_service import upsert_provider_binding, verify_provider_binding
from app.services.media_delivery import resolve_provider_media_url
from app.services.reference_failure_evidence import record_reference_failure_evidence
from app.services.reference_layout_evaluator import validate_layout_evidence
from app.services.series_reference_artifact_validation import (
    ReferenceArtifactValidationError,
    fetch_and_verify_reference_image as _fetch_and_verify_image,
)
from app.services.series_reference_budget import reference_budget_plan_is_safe
from app.services.series_reference_contract import (
    canonical_hash as _hash,
    character_role_bindings as _character_role_bindings,
    model_binding_ids as _binding_ids,
    provider_operation_payload as _operation_payload,
    reference_artifact_payload as _artifact_payload,
    reference_visual_contract_hash,
    reference_visual_contract_matches as _reference_visual_contract_matches,
)
from app.services.series_reference_rebinding import (
    rebind_run_shots_reference as _rebind_run_shots_reference,
    rebind_shot_reference_context,
)
from app.services.series_reference_provider import (
    ConfiguredReferenceAdapter,
    ReferenceAdapterStageError,
    ReferencePreSubmitRejected,
    _signed_url_expiry,
    parse_public_url_expiry,
    persist_qiniu_reference as _persist_qiniu_reference,
)
from app.services.series_run_live_preflight import build_live_preflight_plan, inspect_story_lock_freshness


class ReferencePreparationBlocked(ValueError):
    def __init__(
        self, message: str, *, operation: dict[str, Any] | None = None,
        failure_evidence: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.operation = operation
        self.failure_evidence = failure_evidence


class ReferencePreparationAdapter(Protocol):
    async def generate(
        self, *, db: AsyncSession, run: SeriesProductionRun, prompt: str,
        image_config_id: str, operation: LiveCanaryProviderOperation,
    ) -> dict[str, Any]: ...


async def _story_lock(db: AsyncSession, run: SeriesProductionRun) -> tuple[StoryBible, dict[str, Any]]:
    freshness = await inspect_story_lock_freshness(db, run, supersede=True)
    if not freshness.get("ready"):
        raise ReferencePreparationBlocked(f"story locks are not current: {freshness.get('story_blocker_code') or freshness.get('code')}")
    lock = (run.run_metadata or {}).get("story_locks") or {}
    bible_id = str(lock.get("story_bible_id") or "")
    bible = await db.get(StoryBible, bible_id) if bible_id else None
    bible_extra = bible.extra_data if bible else {}
    preparation = (bible_extra or {}).get("series_story_lock") or {}
    machine = (bible_extra or {}).get("state_machine") or {}
    closure_v2 = preparation.get("closure_contract_version") == "required_entity_closure_v2"
    if (
        bible is None
        or bible.user_id != run.user_id
        or bible.novel_id != run.novel_id
        or (bible_extra or {}).get("production_status") != "locked"
        or (not closure_v2 and machine.get("status") != "locked")
        or preparation.get("run_id") != run.id
        or preparation.get("source_hash") != lock.get("source_hash")
    ):
        raise ReferencePreparationBlocked("story locks are not ready")
    if closure_v2:
        preparation = {**preparation, "approved_entity_ids": [
            item["canonical_entity_id"] for item in preparation.get("subjects") or []
            if item.get("entity_type") == "character"]}
    return bible, preparation


async def _required_characters(db: AsyncSession, run: SeriesProductionRun, approved_ids: list[str]) -> list[StoryEntity]:
    rows = list((await db.scalars(select(StoryEntity).where(
        StoryEntity.id.in_(approved_ids),
        StoryEntity.user_id == run.user_id,
        StoryEntity.novel_id == run.novel_id,
        StoryEntity.entity_type == "character",
        StoryEntity.is_approved.is_(True),
    ))).all())
    rows = [item for item in rows if bool((item.attributes or {}).get("approval_record"))]
    if not rows:
        raise ReferencePreparationBlocked("story locks have no approved required characters")
    return sorted(rows, key=lambda item: (item.chapter_id or "", item.id))


async def _completed_result(
    db: AsyncSession, run: SeriesProductionRun, asset: Asset, binding: ProviderAssetBinding,
) -> dict[str, Any]:
    operation = await db.scalar(select(LiveCanaryProviderOperation).where(
        LiveCanaryProviderOperation.artifact_id == asset.id,
        LiveCanaryProviderOperation.run_id == run.id,
    ))
    if operation is None:
        raise ReferencePreparationBlocked("reference operation evidence is missing")
    return {
        "run_id": run.id,
        "asset_id": asset.id,
        "asset_version": int(asset.version or 1),
        "provider_binding_id": binding.id,
        "roles": ["character_canonical", "global_style_board"],
        "status": "locked",
        "operation": _operation_payload(operation),
        "artifact": _artifact_payload(asset),
    }


async def _exact_binding(db: AsyncSession, run: SeriesProductionRun, asset: Asset) -> ProviderAssetBinding | None:
    video = ((run.model_bindings or {}).get("capabilities") or {}).get("video") or {}
    return await db.scalar(select(ProviderAssetBinding).where(
        ProviderAssetBinding.asset_id == asset.id,
        ProviderAssetBinding.asset_version == int(asset.version or 1),
        ProviderAssetBinding.provider_id == str(video.get("provider_id") or ""),
        ProviderAssetBinding.model_id == str(video.get("api_model_id") or ""),
        ProviderAssetBinding.binding_kind == "reference_image",
        ProviderAssetBinding.is_active.is_(True),
    ))


async def _finalize_candidate(
    db: AsyncSession, run: SeriesProductionRun, asset: Asset, *, resumed: bool,
    superseded_asset_id: str | None = None,
) -> dict[str, Any]:
    params = dict(asset.generation_params or {})
    evidence = params.get("evidence") or {}
    roles = params.get("role_bindings") or []
    character_role_ids = [
        str(item.get("entity_id") or "") for item in roles
        if isinstance(item, dict) and item.get("role") == "character_canonical"
    ]
    global_roles = [item for item in roles if isinstance(item, dict) and item.get("role") == "global_style_board"]
    if (
        params.get("composite_reference_rule") != "single_artifact_dual_role_v1"
        or {item.get("role") for item in roles if isinstance(item, dict)} != {"character_canonical", "global_style_board"}
        or not character_role_ids
        or len(character_role_ids) != len(set(character_role_ids))
        or set(character_role_ids) != set(evidence.get("required_character_entity_ids") or [])
        or len(global_roles) != 1
        or str(global_roles[0].get("novel_id") or "") != run.novel_id
        or evidence.get("status") != "completed"
        or not str(asset.url or "").startswith(("https://", "http://"))
        or not evidence.get("checksum")
    ):
        raise ReferencePreparationBlocked("completed composite reference evidence is invalid")
    try:
        validate_layout_evidence(
            evidence.get("layout_evidence") or {}, expected_bytes_sha256=str(evidence.get("checksum") or ""),
        )
    except ValueError as error:
        raise ReferencePreparationBlocked(f"completed composite layout evidence is invalid: {error}") from error
    video = ((run.model_bindings or {}).get("capabilities") or {}).get("video") or {}
    if not video.get("provider_id") or not video.get("api_model_id"):
        raise ReferencePreparationBlocked("fresh video binding is required")
    try:
        public_url_expires_at = parse_public_url_expiry(evidence.get("public_url_expires_at"))
    except ValueError as error:
        raise ReferencePreparationBlocked(f"completed reference expiry evidence is invalid: {error}") from error
    try:
        binding = await upsert_provider_binding(
            db,
            asset_id=asset.id,
            asset_version=int(asset.version or 1),
            provider_id=str(video["provider_id"]),
            model_id=str(video["api_model_id"]),
            binding_kind="reference_image",
            public_url=asset.url,
            public_url_expires_at=public_url_expires_at,
            checksum=str(evidence["checksum"]),
            width=evidence.get("width"),
            height=evidence.get("height"),
            upload_status="ready",
        )
        binding = await verify_provider_binding(db, binding.id, expected_checksum=str(evidence["checksum"]))
        now = utc_now()
        asset.is_final = True
        asset.is_locked = True
        asset.locked_by = run.user_id
        asset.locked_at = now
        params["locked_at"] = now.isoformat()
        asset.generation_params = params
        flag_modified(asset, "generation_params")
        metadata = dict(run.run_metadata or {})
        metadata["reference_preparation"] = {
            "asset_id": asset.id, "asset_version": int(asset.version or 1),
            "provider_binding_id": binding.id, "evidence_hash": _hash(evidence),
            "roles": ["character_canonical", "global_style_board"], "completed_at": now.isoformat(),
            "prompt_skill": params.get("prompt_skill") or {},
        }
        run.run_metadata = metadata
        flag_modified(run, "run_metadata")
        if superseded_asset_id:
            await _rebind_run_shots_reference(
                db, run,
                superseded_asset_id=superseded_asset_id,
                replacement_asset=asset,
                rebound_at=now.isoformat(),
            )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {**(await _completed_result(db, run, asset, binding)), "idempotent": False, "resumed": resumed}


async def _refresh_candidate_delivery(
    db: AsyncSession, run: SeriesProductionRun, asset: Asset,
) -> dict[str, Any]:
    params = dict(asset.generation_params or {})
    evidence = dict(params.get("evidence") or {})
    storage = dict(evidence.get("storage_delivery") or {})
    local_url = str(storage.get("canonical_local_url") or "")
    if not local_url:
        raise ReferencePreparationBlocked("expired reference has no canonical local artifact")
    delivery = await resolve_provider_media_url(
        db, run.user_id, local_url, media_type="图",
        storage_config_id=str(storage.get("storage_config_id") or "") or None,
    )
    public_url = str(delivery.get("provider_url") or "")
    expiry = _signed_url_expiry(public_url)
    if delivery.get("delivery_method") != "qiniu_object_upload" or not public_url or not expiry:
        raise ReferencePreparationBlocked("expired reference Qiniu URL refresh failed")
    evidence["public_url_expires_at"] = expiry
    evidence["storage_delivery"] = {
        **storage,
        "delivery_method": delivery["delivery_method"],
        "storage_config_id": delivery.get("storage_config_id") or storage.get("storage_config_id"),
        "object_key": delivery.get("object_key") or storage.get("object_key"),
        "canonical_local_url": local_url,
    }
    asset.url = public_url
    asset.generation_params = {**params, "evidence": evidence}
    flag_modified(asset, "generation_params")
    result = await _finalize_candidate(db, run, asset, resumed=True)
    return {**result, "idempotent": True, "delivery_refreshed": True}


class DeterministicReferenceAdapter:
    async def generate(self, *, db, run, prompt, image_config_id, operation):
        if not deterministic_provider_fake_enabled():
            raise RuntimeError("deterministic provider fake is disabled")
        reference_url = str(os.getenv("DETERMINISTIC_REFERENCE_URL") or "").strip()
        if not reference_url.startswith(("http://", "https://")):
            raise ReferencePreSubmitRejected("deterministic reference HTTP fixture is not configured")
        return {
            "status": "completed",
            "public_url": reference_url,
            "provider_task_id": f"deterministic:{operation.id}",
            "actual_cost_rmb": None,
            "width": 1536,
            "height": 1024,
        }


def default_reference_adapter() -> ReferencePreparationAdapter:
    return DeterministicReferenceAdapter() if deterministic_provider_fake_enabled() else ConfiguredReferenceAdapter()


async def prepare_series_reference(
    db: AsyncSession,
    run: SeriesProductionRun,
    *,
    adapter: ReferencePreparationAdapter,
    binding_ids: dict[str, str] | None = None,
    native_audio: bool = False,
    recovery_operation_id: str | None = None,
) -> dict[str, Any]:
    if run.status not in {"shots_ready", "anchor_ready", "media_running"} or (run.budget_policy or {}).get("live_canary") is not True:
        raise ReferencePreparationBlocked("owned live run is required")
    media_retry = run.status == "media_running"
    bible, story_lock = await _story_lock(db, run)
    required_characters = await _required_characters(db, run, list(story_lock.get("approved_entity_ids") or []))
    protagonist = required_characters[0]

    ids = binding_ids or _binding_ids(run)
    metadata = run.run_metadata or {}
    completed = metadata.get("reference_preparation") or {}
    completed_asset = await db.get(Asset, completed["asset_id"]) if completed.get("asset_id") else None
    stale_asset = completed_asset if (
        completed_asset and not _reference_visual_contract_matches(completed_asset, required_characters)
    ) else None
    if stale_asset:
        completed = {}
    required_capabilities = {"video"} if completed.get("asset_id") else {"image", "video"}
    try:
        await validate_persisted_model_bindings(
            db, run, required_capabilities=required_capabilities, persist_missing=True,
        )
    except BindingValidationError as error:
        await db.rollback()
        raise ReferencePreparationBlocked(f"fresh image/video binding is required: {error}") from error

    if stale_asset:
        params = dict(stale_asset.generation_params or {})
        stale_asset.is_active = False
        stale_asset.is_final = False
        stale_asset.is_locked = False
        stale_asset.generation_params = {
            **params, "status": "superseded", "superseded_reason": "visual_contract_stale",
        }
        metadata = dict(run.run_metadata or {})
        metadata.pop("reference_preparation", None)
        run.run_metadata = metadata
        flag_modified(stale_asset, "generation_params")
        flag_modified(run, "run_metadata")
        await db.commit()

    if completed.get("asset_id"):
        asset = completed_asset
        binding = await _exact_binding(db, run, asset) if asset else None
        if asset and binding and asset.is_final and asset.is_locked and binding.upload_status == "ready" and binding.verified_at:
            if binding.public_url_expires_at and binding.public_url_expires_at <= utc_now():
                return await _refresh_candidate_delivery(db, run, asset)
            return {**(await _completed_result(db, run, asset, binding)), "idempotent": True, "resumed": False}

    existing_operations = list((await db.scalars(select(LiveCanaryProviderOperation).where(
        LiveCanaryProviderOperation.run_id == run.id,
        LiveCanaryProviderOperation.job_type == "series_composite_reference",
    ).order_by(LiveCanaryProviderOperation.created_at.desc()))).all())
    superseded_artifact = False
    recovery_operation: LiveCanaryProviderOperation | None = None
    for operation in existing_operations:
        if recovery_operation_id == operation.id:
            if (
                operation.status != "unknown_manual_reconcile"
                or operation.recovery_reason != "reference_artifact_unverified"
                or operation.artifact_id
            ):
                raise ReferencePreparationBlocked("reference operation is not recoverable")
            recovery_operation = operation
            continue
        if operation.status == "reconciled" and operation.artifact_id:
            candidate = await db.get(Asset, operation.artifact_id)
            if candidate and candidate.is_active and (candidate.generation_params or {}).get("status") != "superseded":
                return await _finalize_candidate(db, run, candidate, resumed=True)
            superseded_artifact = bool(candidate) and (
                not candidate.is_active or (candidate.generation_params or {}).get("status") == "superseded"
            )
        if operation.status in {"reserved", "accepted", "unknown_manual_reconcile"}:
            raise ReferencePreparationBlocked(
                f"provider state {operation.status} requires recovery",
                operation=_operation_payload(operation),
            )

    if recovery_operation_id and recovery_operation is None:
        raise ReferencePreparationBlocked("reference recovery operation was not found")

    if media_retry and not superseded_artifact and recovery_operation is None:
        raise ReferencePreparationBlocked("media retry may only refresh an existing reference artifact")

    if recovery_operation is not None:
        operation = recovery_operation
    else:
        estimate = ((run.budget_policy or {}).get("estimates_rmb") or {}).get("image")
        if estimate is None:
            raise ReferencePreparationBlocked("server image budget estimate is missing")
        plan = await build_live_preflight_plan(db, run, native_audio=native_audio)
        repair = (run.run_metadata or {}).get("repair_budget_extension") or {}
        scoped_repair = (
            Decimal(str(estimate))
            if repair.get("status") == "approved" and repair.get("artifact_ids")
            else None
        )
        if not reference_budget_plan_is_safe(
            plan, scoped_repair_reservation_rmb=scoped_repair,
        ):
            present_unsafe = [
                code for code in plan["blocker_codes"]
                if code != "provider_binding_not_ready"
            ]
            raise ReferencePreparationBlocked(f"server budget plan is not safe: {','.join(present_unsafe) or 'over budget'}")

        attempt = len(existing_operations) + 1
        job_id = f"series-reference:{run.id}:{attempt}"
        reservation_id = f"series-reference:{run.id}:{story_lock['source_hash'][:16]}:{attempt}"
        try:
            operation = await prepare_provider_operation(
                db, run, capability="image", job_type="series_composite_reference",
                job_id=job_id, reservation_id=reservation_id, estimate_rmb=Decimal(str(estimate)),
            )
        except BudgetExceeded as error:
            await db.rollback()
            raise ReferencePreparationBlocked(f"budget reservation failed: {error}") from error

    character_bindings = _character_role_bindings(required_characters)
    asset_id = str(uuid4())
    reference_skill = await bind_series_reference_skill(
        db, run=run, bible=bible, characters=required_characters, asset_id=asset_id,
    )
    prompt = reference_skill.rendered_prompt
    try:
        result = await adapter.generate(
            db=db, run=run, prompt=prompt, image_config_id=ids["image"], operation=operation,
        )
    except ReferencePreSubmitRejected as error:
        await settle_confirmed_provider_rejection(db, run, reservation_id=operation.reservation_id)
        await db.refresh(operation)
        raise ReferencePreparationBlocked(
            "provider rejected before submission", operation=_operation_payload(operation),
        ) from error
    except ReferenceAdapterStageError as error:
        if error.provider_task_id:
            operation = await bind_provider_operation_task(
                db, operation, provider_task_id=error.provider_task_id,
            )
        await mark_operation_manual_reconcile(
            db, operation, reason=f"reference_adapter_{error.stage}",
        )
        failure_evidence = await record_reference_failure_evidence(db, run, operation.id, {
            "schema_version": "reference-adapter-stage-v1",
            "failure_stage": error.stage,
            "provider_task_id_present": bool(error.provider_task_id),
            "provider_completed": error.provider_completed,
            "safe_retry": False,
        })
        await db.refresh(operation)
        payload = _operation_payload(operation)
        payload["failure_evidence"] = failure_evidence
        raise ReferencePreparationBlocked(
            f"provider status unknown during {error.stage}", operation=payload,
            failure_evidence=failure_evidence,
        ) from error
    except Exception as error:
        await mark_operation_manual_reconcile(db, operation, reason="reference_adapter_exception")
        await db.refresh(operation)
        raise ReferencePreparationBlocked(
            "provider status unknown after adapter exception", operation=_operation_payload(operation),
        ) from error

    provider_status = str(result.get("status") or "unknown").lower()
    task_id = str(result.get("provider_task_id") or "").strip()
    if provider_status in {"failed", "rejected", "cancelled"}:
        if task_id:
            operation = await bind_provider_operation_task(db, operation, provider_task_id=task_id)
            await settle_provider_operation(
                db, operation_id=operation.id, user_id=run.user_id, run_id=run.id,
                reservation_id=operation.reservation_id, capability="image", job_id=operation.job_id,
                provider_task_id=task_id, provider_status=provider_status,
            )
        else:
            await settle_confirmed_provider_rejection(db, run, reservation_id=operation.reservation_id)
        await db.refresh(operation)
        raise ReferencePreparationBlocked(
            f"provider {provider_status}", operation=_operation_payload(operation),
        )
    public_url = str(result.get("public_url") or "").strip()
    if provider_status not in {"completed", "succeeded"} or not public_url.startswith(("https://", "http://")):
        if task_id:
            operation = await bind_provider_operation_task(db, operation, provider_task_id=task_id)
        await mark_operation_manual_reconcile(db, operation, reason=f"reference_{provider_status[:40]}")
        await db.refresh(operation)
        raise ReferencePreparationBlocked(
            f"provider {provider_status} is not a completed artifact",
            operation=_operation_payload(operation),
        )

    try:
        artifact_evidence = await _fetch_and_verify_image(public_url)
    except ReferenceArtifactValidationError as error:
        if task_id:
            operation = await bind_provider_operation_task(db, operation, provider_task_id=task_id)
        await mark_operation_manual_reconcile(db, operation, reason="reference_artifact_unverified")
        if error.failure_evidence:
            await record_reference_failure_evidence(db, run, operation.id, error.failure_evidence)
        await db.refresh(operation)
        payload = _operation_payload(operation)
        if error.failure_evidence:
            payload["failure_evidence"] = error.failure_evidence
        raise ReferencePreparationBlocked(str(error), operation=payload) from error

    if not task_id:
        task_id = f"sync:{operation.id}"
    operation = await bind_provider_operation_task(db, operation, provider_task_id=task_id)
    checksum = artifact_evidence["sha256"]
    now = utc_now()
    asset = Asset(
        id=asset_id, user_id=run.user_id, novel_id=run.novel_id, entity_id=protagonist.id,
        entity_type="character", category="style", name=f"{protagonist.name} 角色与全局风格复合设定板",
        description="单一产物同时承载角色规范三视图与全局动漫风格板。",
        asset_type="image", url=public_url, version=1, is_active=True, is_final=False, is_locked=False,
        source_job_id=operation.id, source_prompt=prompt,
        generation_params={
            "prompt_skill": reference_skill.evidence,
            "composite_reference_rule": "single_artifact_dual_role_v1",
            "canonical_roles": ["front", "three_quarter", "full_body", "global_style_board"],
            "role_bindings": [
                *character_bindings,
                {"role": "global_style_board", "novel_id": run.novel_id},
            ],
            "evidence": {
                "status": "completed", "checksum": checksum, "operation_id": operation.id,
                "reservation_id": operation.reservation_id, "provider_task_id": task_id,
                "story_bible_id": bible.id, "story_lock_version": story_lock.get("version"),
                "required_character_entity_ids": [item["entity_id"] for item in character_bindings],
                "visual_contract_hash": reference_visual_contract_hash(required_characters),
                "image_config_id": ids["image"], "generated_at": now.isoformat(),
                "width": artifact_evidence["width"], "height": artifact_evidence["height"],
                "byte_size": artifact_evidence["byte_size"], "content_type": artifact_evidence["content_type"],
                "image_format": artifact_evidence["format"], "layout_evidence": artifact_evidence["layout_evidence"],
                "public_url_expires_at": result.get("public_url_expires_at"),
                "storage_delivery": result.get("storage_delivery") or {},
            },
        },
    )
    operation.artifact_id = asset.id
    db.add(asset)
    await db.commit()
    await settle_synchronous_provider_operation(db, operation, provider_actual_rmb=result.get("actual_cost_rmb"))
    if recovery_operation is not None:
        policy = dict(run.budget_policy or {})
        policy.pop("blocked", None)
        policy.pop("blocked_reason", None)
        run.budget_policy = policy
        flag_modified(run, "budget_policy")
        await db.commit()
    return await _finalize_candidate(
        db, run, asset, resumed=False,
        superseded_asset_id=str(stale_asset.id) if stale_asset else None,
    )


__all__ = ["ConfiguredReferenceAdapter", "DeterministicReferenceAdapter", "ReferencePreparationBlocked",
           "ReferencePreSubmitRejected", "default_reference_adapter", "prepare_series_reference",
           "rebind_shot_reference_context", "reference_budget_plan_is_safe",
           "reference_visual_contract_hash"]
