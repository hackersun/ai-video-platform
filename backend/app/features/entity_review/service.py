from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.features.series_skill_execution.entity_stage import resolve_entity_candidates
from app.features.series_skill_execution.public import bind_series_stage_skill
from app.features.entity_review.repository import to_review_item
from app.features.entity_review.schemas import (
    BulkReviewRequest,
    BulkReviewResponse,
    BulkSkippedItem,
    ReviewSummary,
    ReanalysisRequest,
    ReanalysisResponse,
    RebuildCandidatesRequest,
    RebuildCandidatesResponse,
)
from app.models import Chapter, EntityExtractionRun, StoryEntity
from app.services.entity_review_service import (
    EntityApprovalEvidenceError,
    approve_review_entity,
    entity_has_duplicate_risk,
    get_entity_review_summary,
    reject_review_entity,
)
from app.services.story_entity_lifecycle import (
    APPROVED,
    ARCHIVED,
    CANDIDATE,
    LEGACY_ACTIVE,
    REJECTED,
    get_entity_review_status,
    set_entity_review_status,
)


class ProviderModelRequiredError(ValueError):
    """Raised when a destructive AI action would otherwise use fallback output."""


async def _review_one(
    db: AsyncSession,
    *,
    user_id: str,
    payload: BulkReviewRequest,
    entity_id: str,
) -> tuple[StoryEntity | None, BulkSkippedItem | None]:
    entity = await db.get(StoryEntity, entity_id)
    if entity is None or entity.user_id != user_id or entity.novel_id != payload.novel_id:
        return None, BulkSkippedItem(id=entity_id, reason="实体不存在或不属于当前小说")
    current_quality = to_review_item(entity).extra_data.get("quality", {})
    if payload.action == "approve" and current_quality.get("auto_decision") == "reject_noise":
        return None, BulkSkippedItem(id=entity_id, reason="当前候选被质量门判定为噪声", repair_action="修改实体或使用 AI 重新分析")
    if payload.action == "approve" and await entity_has_duplicate_risk(db, user_id=user_id, entity=entity):
        return None, BulkSkippedItem(id=entity_id, reason="存在高重复风险，不能批量定稿", repair_action="先合并重复实体")
    try:
        updated = (
            await approve_review_entity(db, user_id=user_id, entity_id=entity_id, reason=payload.reason)
            if payload.action == "approve"
            else await reject_review_entity(db, user_id=user_id, entity_id=entity_id, reason=payload.reason)
        )
        return updated, None
    except EntityApprovalEvidenceError as error:
        return None, BulkSkippedItem(id=entity_id, reason=str(error), repair_action="补充原文证据后再定稿")


async def bulk_review_entities(
    db: AsyncSession,
    *,
    user_id: str,
    payload: BulkReviewRequest,
) -> BulkReviewResponse:
    updated = []
    skipped = []
    for entity_id in dict.fromkeys(payload.entity_ids):
        entity, skip = await _review_one(db, user_id=user_id, payload=payload, entity_id=entity_id)
        if entity is not None:
            updated.append(to_review_item(entity))
        if skip is not None:
            skipped.append(skip)
    raw_summary = await get_entity_review_summary(db, user_id=user_id, novel_id=payload.novel_id)
    summary = ReviewSummary(total=sum(raw_summary.get("counts", {}).values()), **raw_summary)
    return BulkReviewResponse(updated=updated, skipped=skipped, summary=summary)


async def _run_model_candidate_preview(
    db: AsyncSession,
    *,
    user_id: str,
    source_text: str,
    entity_types: set[str],
    model_config_id: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    binding = await bind_series_stage_skill(
        db, user_id=user_id, task="entity_extraction", output_contract="json_array",
        stage="analysis", context={
            "entity_types": "、".join(sorted(entity_types)),
            "allowed_entity_types": ", ".join(sorted(entity_types)),
            "source_type": "entity_review", "source_content": source_text[:30000],
            "output_format": "JSON 数组",
        },
        internal_prompt="重新分析制作实体，只返回有原文证据的完整实体。",
        execution_mode="provider_model_required",
    )
    return await resolve_entity_candidates(
        db, user_id=user_id, rendered_prompt=binding.rendered_prompt,
        source_text=source_text, requested_types=entity_types, supplied=None,
        fallback=lambda: [], model_config_id=model_config_id,
    )


def _diff(current: StoryEntity, proposed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fields = ("entity_type", "name", "canonical_name", "aliases", "description", "appearance", "visual_prompt", "evidence")
    return {
        field: {"before": getattr(current, field), "after": proposed.get(field)}
        for field in fields if proposed.get(field) != getattr(current, field)
    }


def _preview_run(
    *, user_id: str, novel_id: str | None, source_type: str, source_id: str,
    source_text: str, items: list[dict[str, Any]], evidence: dict[str, Any],
    model_config_id: str | None,
) -> EntityExtractionRun:
    return EntityExtractionRun(
        id=str(uuid4()), user_id=user_id, novel_id=novel_id,
        source_type=source_type, source_id=source_id,
        text_hash=hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        entity_types=sorted({str(item.get("entity_type")) for item in items}),
        model_config_id=model_config_id, provider=evidence.get("provider"),
        model_id=evidence.get("model_id"), status="completed", completed_at=utc_now(),
        stats={"proposed": len(items)}, quality_summary={},
        extra_data={"proposed_candidates": items, "model_execution": evidence},
    )


def _require_preview(run: EntityExtractionRun | None, *, user_id: str, source_type: str, source_id: str) -> list[dict[str, Any]]:
    if run is None or run.user_id != user_id or run.source_type != source_type or run.source_id != source_id:
        raise ValueError("预览任务不存在或已失效")
    extra = run.extra_data if isinstance(run.extra_data, dict) else {}
    evidence = extra.get("model_execution") if isinstance(extra.get("model_execution"), dict) else {}
    if evidence.get("execution_mode") != "provider_model":
        raise ProviderModelRequiredError("模型未成功执行，未修改任何候选")
    items = extra.get("proposed_candidates")
    if not isinstance(items, list) or not items:
        raise ValueError("预览任务没有可应用的候选")
    return [dict(item) for item in items if isinstance(item, dict)]


async def reanalyze_entity(
    db: AsyncSession, *, user_id: str, entity_id: str, payload: ReanalysisRequest,
) -> ReanalysisResponse:
    entity = await db.get(StoryEntity, entity_id)
    if entity is None or entity.user_id != user_id:
        raise ValueError("实体不存在")
    if payload.mode == "preview":
        source_text = str(entity.evidence or entity.description or entity.name)
        items, evidence = await _run_model_candidate_preview(
            db, user_id=user_id, source_text=source_text,
            entity_types={entity.entity_type}, model_config_id=payload.model_config_id,
        )
        if evidence.get("execution_mode") != "provider_model":
            raise ProviderModelRequiredError("模型未成功执行，未修改实体")
        proposed = items[0]
        run = _preview_run(user_id=user_id, novel_id=entity.novel_id, source_type="entity_reanalysis_preview",
            source_id=entity.id, source_text=source_text, items=[proposed], evidence=evidence,
            model_config_id=payload.model_config_id)
        db.add(run)
        await db.commit()
        return ReanalysisResponse(mode="preview", preview_run_id=run.id, current=to_review_item(entity),
            proposed=proposed, differences=_diff(entity, proposed), model_execution=evidence)
    run = await db.get(EntityExtractionRun, payload.preview_run_id) if payload.preview_run_id else None
    proposed = _require_preview(run, user_id=user_id, source_type="entity_reanalysis_preview", source_id=entity.id)[0]
    before = to_review_item(entity)
    for field in ("entity_type", "name", "canonical_name", "aliases", "description", "appearance", "visual_prompt", "evidence", "attributes", "relations"):
        if field in proposed:
            setattr(entity, field, proposed[field])
    entity.source = "provider_model"
    set_entity_review_status(entity, CANDIDATE, changed_by=user_id, reason=f"reanalyze:{run.id}")
    await db.commit()
    await db.refresh(entity)
    evidence = dict((run.extra_data or {}).get("model_execution") or {})
    return ReanalysisResponse(mode="apply", preview_run_id=run.id, current=to_review_item(entity),
        proposed=proposed, differences=_diff_from_items(before.model_dump(), to_review_item(entity).model_dump()), model_execution=evidence)


def _diff_from_items(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {key: {"before": before.get(key), "after": after.get(key)} for key in after if before.get(key) != after.get(key)}


async def _summary(db: AsyncSession, user_id: str, novel_id: str) -> ReviewSummary:
    raw = await get_entity_review_summary(db, user_id=user_id, novel_id=novel_id)
    return ReviewSummary(total=sum(raw.get("counts", {}).values()), **raw)


async def rebuild_candidates(
    db: AsyncSession, *, user_id: str, novel_id: str, payload: RebuildCandidatesRequest,
) -> RebuildCandidatesResponse:
    if payload.mode == "preview":
        source_text = (payload.source_text or "").strip()
        if not source_text:
            chapters = list((await db.execute(select(Chapter).where(
                Chapter.user_id == user_id, Chapter.novel_id == novel_id,
            ).order_by(Chapter.chapter_number))).scalars().all())
            source_text = "\n".join(chapter.content or "" for chapter in chapters).strip()
        if not source_text:
            raise ValueError("小说没有可分析的正文")
        items, evidence = await _run_model_candidate_preview(db, user_id=user_id, source_text=source_text,
            entity_types={"character", "scene", "prop", "event"}, model_config_id=payload.model_config_id)
        if evidence.get("execution_mode") != "provider_model":
            raise ProviderModelRequiredError("模型未成功执行，未修改任何候选")
        run = _preview_run(user_id=user_id, novel_id=novel_id, source_type="novel_rebuild_preview",
            source_id=novel_id, source_text=source_text, items=items, evidence=evidence,
            model_config_id=payload.model_config_id)
        db.add(run)
        await db.commit()
        return RebuildCandidatesResponse(mode="preview", preview_run_id=run.id, proposed=items,
            model_execution=evidence, summary=await _summary(db, user_id, novel_id))
    run = await db.get(EntityExtractionRun, payload.preview_run_id) if payload.preview_run_id else None
    items = _require_preview(run, user_id=user_id, source_type="novel_rebuild_preview", source_id=novel_id)
    archived, created = await _apply_rebuild(db, user_id=user_id, novel_id=novel_id, run_id=run.id, items=items)
    evidence = dict((run.extra_data or {}).get("model_execution") or {})
    return RebuildCandidatesResponse(mode="apply", preview_run_id=run.id, proposed=items,
        archived_count=archived, created_count=created, model_execution=evidence,
        summary=await _summary(db, user_id, novel_id))


async def _apply_rebuild(
    db: AsyncSession, *, user_id: str, novel_id: str, run_id: str, items: list[dict[str, Any]],
) -> tuple[int, int]:
    rows = list((await db.execute(select(StoryEntity).where(
        StoryEntity.user_id == user_id, StoryEntity.novel_id == novel_id,
    ))).scalars().all())
    archived = 0
    protected = {(row.entity_type, row.canonical_name or row.name) for row in rows if get_entity_review_status(row) in {APPROVED, LEGACY_ACTIVE}}
    for row in rows:
        if get_entity_review_status(row) in {CANDIDATE, REJECTED}:
            set_entity_review_status(row, ARCHIVED, changed_by=user_id, reason=f"rebuild:{run_id}")
            archived += 1
    created = 0
    for item in items:
        if (item.get("entity_type"), item.get("canonical_name") or item.get("name")) in protected:
            continue
        entity = StoryEntity(id=str(uuid4()), user_id=user_id, novel_id=novel_id,
            entity_type=item["entity_type"], name=item["name"], canonical_name=item.get("canonical_name"),
            aliases=item.get("aliases") or [], description=item.get("description"), appearance=item.get("appearance"),
            visual_prompt=item.get("visual_prompt"), attributes=item.get("attributes") or {},
            relations=item.get("relations") or [], evidence=item.get("evidence"),
            confidence=item.get("confidence") or 80, source="provider_model")
        set_entity_review_status(entity, CANDIDATE, changed_by=user_id, reason=f"rebuild:{run_id}")
        db.add(entity)
        created += 1
    await db.commit()
    return archived, created
