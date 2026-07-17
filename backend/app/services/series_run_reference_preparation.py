"""Budgeted preparation of one composite series reference asset."""

from __future__ import annotations

from decimal import Decimal
import hashlib
from io import BytesIO
import json
import os
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
import httpx
from PIL import Image, UnidentifiedImageError

from app.core.time_utils import utc_now
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
    required_tested_at_for_run,
    settle_confirmed_provider_rejection,
    settle_provider_operation,
    settle_synchronous_provider_operation,
    validate_model_bindings,
)
from app.services.provider_asset_binding_service import upsert_provider_binding, verify_provider_binding
from app.services.media_delivery import resolve_provider_media_url
from app.services.reference_failure_evidence import record_reference_failure_evidence
from app.services.reference_layout_evaluator import (
    ReferenceLayoutValidationError, evaluate_reference_layout,
    reference_layout_prompt_instruction, validate_layout_evidence,
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


def _hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _binding_ids(run: SeriesProductionRun) -> dict[str, str]:
    capabilities = (run.model_bindings or {}).get("capabilities") or {}
    return {name: str((capabilities.get(name) or {}).get("config_id") or "") for name in ("text", "image", "tts", "video")}

async def _story_lock(db: AsyncSession, run: SeriesProductionRun) -> tuple[StoryBible, dict[str, Any]]:
    freshness = await inspect_story_lock_freshness(db, run, supersede=True)
    if not freshness.get("ready"):
        raise ReferencePreparationBlocked(f"story locks are not current: {freshness.get('code')}")
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


async def _fetch_and_verify_image(public_url: str) -> dict[str, Any]:
    max_bytes = 10 * 1024 * 1024
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(public_url, headers={"Accept": "image/*"})
            response.raise_for_status()
    except (httpx.HTTPError, ValueError) as error:
        raise ReferencePreparationBlocked("reference artifact URL is not fetchable") from error
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise ReferencePreparationBlocked("reference artifact content type is not an allowed image")
    content_length = response.headers.get("content-length")
    try:
        if content_length is not None and int(content_length) > max_bytes:
            raise ReferencePreparationBlocked("reference artifact exceeds size limit")
    except ValueError as error:
        raise ReferencePreparationBlocked("reference artifact content length is invalid") from error
    data = response.content
    if not data or len(data) > max_bytes:
        raise ReferencePreparationBlocked("reference artifact bytes are missing or oversized")
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
            width, height = image.size
            image_format = str(image.format or "").upper()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ReferencePreparationBlocked("reference artifact is not a decodable image") from error
    if width < 1024 or height < 768:
        raise ReferencePreparationBlocked("reference artifact pixel dimensions are too small")
    try:
        layout_evidence = evaluate_reference_layout(data)
    except ReferenceLayoutValidationError as error:
        raise ReferencePreparationBlocked(
            f"reference layout evidence failed: {error}", failure_evidence=error.summary,
        ) from error
    return {
        "sha256": hashlib.sha256(data).hexdigest(), "byte_size": len(data),
        "content_type": content_type, "width": width, "height": height, "format": image_format,
        "layout_evidence": layout_evidence,
    }


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


def _operation_payload(operation: LiveCanaryProviderOperation) -> dict[str, Any]:
    return {
        "id": operation.id,
        "status": operation.status,
        "provider_task_id": operation.provider_task_id,
        "reservation_id": operation.reservation_id,
        "actual_rmb": operation.actual_rmb,
        "cost_source": operation.cost_source,
    }


def _artifact_payload(asset: Asset) -> dict[str, Any]:
    evidence = (asset.generation_params or {}).get("evidence") or {}
    return {
        "id": asset.id,
        "url": asset.url,
        "checksum": evidence.get("checksum"),
        "layout_evidence": evidence.get("layout_evidence") or {},
        "width": evidence.get("width"),
        "height": evidence.get("height"),
        "byte_size": evidence.get("byte_size"),
        "public_url_expires_at": evidence.get("public_url_expires_at"),
        "storage_delivery": evidence.get("storage_delivery") or {},
    }


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
        or len(character_role_ids) != 1
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
        }
        run.run_metadata = metadata
        flag_modified(run, "run_metadata")
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
) -> dict[str, Any]:
    if run.status not in {"shots_ready", "anchor_ready", "media_running"} or (run.budget_policy or {}).get("live_canary") is not True:
        raise ReferencePreparationBlocked("owned live run is required")
    media_retry = run.status == "media_running"
    bible, story_lock = await _story_lock(db, run)
    required_characters = await _required_characters(db, run, list(story_lock.get("approved_entity_ids") or []))
    if len(required_characters) != 1:
        raise ReferencePreparationBlocked(
            "reference_capacity_exceeded: single composite reference supports exactly one required character"
        )
    protagonist = required_characters[0]

    ids = binding_ids or _binding_ids(run)
    try:
        await validate_model_bindings(
            db, run, ids, required_tested_at=required_tested_at_for_run(run), freshness_seconds=900,
        )
    except BindingValidationError as error:
        await db.rollback()
        raise ReferencePreparationBlocked(f"fresh image/video binding is required: {error}") from error

    metadata = run.run_metadata or {}
    completed = metadata.get("reference_preparation") or {}
    if completed.get("asset_id"):
        asset = await db.get(Asset, completed["asset_id"])
        binding = await _exact_binding(db, run, asset) if asset else None
        if asset and binding and asset.is_final and asset.is_locked and binding.upload_status == "ready" and binding.verified_at:
            if binding.public_url_expires_at and binding.public_url_expires_at <= utc_now():
                return await _refresh_candidate_delivery(db, run, asset)
            return {**(await _completed_result(db, run, asset, binding)), "idempotent": True, "resumed": False}

    existing_operations = list((await db.scalars(select(LiveCanaryProviderOperation).where(
        LiveCanaryProviderOperation.run_id == run.id,
        LiveCanaryProviderOperation.job_type == "series_composite_reference",
    ).order_by(LiveCanaryProviderOperation.created_at.desc()))).all())
    for operation in existing_operations:
        if operation.status == "reconciled" and operation.artifact_id:
            candidate = await db.get(Asset, operation.artifact_id)
            if candidate and candidate.is_active and (candidate.generation_params or {}).get("status") != "superseded":
                return await _finalize_candidate(db, run, candidate, resumed=True)
        if operation.status in {"reserved", "accepted", "unknown_manual_reconcile"}:
            raise ReferencePreparationBlocked(
                f"provider state {operation.status} requires recovery",
                operation=_operation_payload(operation),
            )

    if media_retry:
        raise ReferencePreparationBlocked("media retry may only refresh an existing reference artifact")

    plan = await build_live_preflight_plan(db, run)
    unsafe_codes = {
        "trusted_budget_policy_missing", "wave_one_budget_policy_invalid", "image_estimate_missing",
        "video_estimate_missing", "tts_estimate_missing", "projected_budget_exceeded", "model_bindings_not_fresh", "production_entities_unapproved", "production_entity_conflict",
    }
    present_unsafe = [code for code in plan["blocker_codes"] if code in unsafe_codes]
    if present_unsafe or Decimal(plan["budget"]["projected_total_rmb"]) > Decimal("10.00"):
        raise ReferencePreparationBlocked(f"server budget plan is not safe: {','.join(present_unsafe) or 'over budget'}")

    attempt = len(existing_operations) + 1
    estimate = ((run.budget_policy or {}).get("estimates_rmb") or {}).get("image")
    if estimate is None:
        raise ReferencePreparationBlocked("server image budget estimate is missing")
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

    character_names = "、".join(character.canonical_name or character.name for character in required_characters)
    prompt = (
        f"为《{bible.title}》制作一张单一复合动漫设定板。左侧是所需角色 {character_names} "
        "的正面、四分之三侧面和全身三视图；右侧是同一作品的全局动漫风格板、色板、线条和光影规则。"
        f"{reference_layout_prompt_instruction()}统一风格：{bible.style}。禁止拆成多个文件，禁止文字水印。"
    )
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
    except ReferencePreparationBlocked as error:
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
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id, entity_id=protagonist.id,
        entity_type="character", category="style", name=f"{protagonist.name} 角色与全局风格复合设定板",
        description="单一产物同时承载角色规范三视图与全局动漫风格板。",
        asset_type="image", url=public_url, version=1, is_active=True, is_final=False, is_locked=False,
        source_job_id=operation.id, source_prompt=prompt,
        generation_params={
            "composite_reference_rule": "single_artifact_dual_role_v1",
            "canonical_roles": ["front", "three_quarter", "full_body", "global_style_board"],
            "role_bindings": [
                {"role": "character_canonical", "entity_id": protagonist.id},
                {"role": "global_style_board", "novel_id": run.novel_id},
            ],
            "evidence": {
                "status": "completed", "checksum": checksum, "operation_id": operation.id,
                "reservation_id": operation.reservation_id, "provider_task_id": task_id,
                "story_bible_id": bible.id, "story_lock_version": story_lock.get("version"),
                "required_character_entity_ids": [protagonist.id],
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
    return await _finalize_candidate(db, run, asset, resumed=False)


__all__ = ["ConfiguredReferenceAdapter", "DeterministicReferenceAdapter", "ReferencePreparationBlocked",
           "ReferencePreSubmitRejected", "default_reference_adapter", "prepare_series_reference"]
