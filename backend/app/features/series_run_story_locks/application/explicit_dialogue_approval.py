"""Strict explicit-dialogue approval before Story Lock persistence."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.time_utils import utc_now
from app.models import Chapter, LLMConfig, LLMModel, StoryEntity
from app.models.series_production_run import SeriesProductionRun
from app.services.dialogue_lineage_service import extract_explicit_dialogue
from app.services.story_entity_lifecycle import APPROVED, ARCHIVED, CANDIDATE, get_entity_review_status, set_entity_review_status
from app.services.deterministic_provider_fake import deterministic_provider_fake_enabled
from .dialogue_identity import _normalize_safe_dialogue_duplicates
from .voice_contract import provider_voice_allowlist, valid_voice_selection
from ..domain.scoped_reference import canonical_identity_sha256, sign_merge_edge
from ..public_errors import StoryLockPreparationBlocked


def locked_dialogue_entities_statement(user_id: str, novel_id: str):
    return select(StoryEntity).where(
        StoryEntity.user_id == user_id, StoryEntity.novel_id == novel_id,
        StoryEntity.entity_type == "character",
    ).with_for_update()


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _verified_single_candidate_evidence(
    candidate: StoryEntity, *, speaker: str, chapters: list[Chapter], dialogue_evidence: list[dict[str, Any]],
) -> list[str]:
    proofs = (candidate.attributes or {}).get("deterministic_dialogue_evidence")
    if not isinstance(proofs, list) or len(proofs) != 1 or not isinstance(proofs[0], dict):
        return []
    proof = dict(proofs[0])
    chapter = next((item for item in chapters if str(item.id) == str(proof.get("chapter_id"))), None)
    if chapter is None or int(proof.get("chapter_order") or 0) != int(chapter.chapter_number):
        return []
    content = str(chapter.content or "")
    if proof.get("content_sha256") != hashlib.sha256(content.encode("utf-8")).hexdigest():
        return []
    start, end = proof.get("span_start"), proof.get("span_end")
    if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start or end > len(content):
        return []
    if content[start:end] != proof.get("speaker_text") or proof.get("speaker") != speaker:
        return []
    parsed = [item for item in extract_explicit_dialogue(content)
              if item["speaker"] == speaker and item["source_span"] == [start, end]
              and item["spoken_text"] == proof.get("quote_text")]
    expected_lines = [item for item in dialogue_evidence if str(item["chapter_id"]) == str(chapter.id)
                      and item["source_span"] == [start, end] and item["spoken_text"] == proof.get("quote_text")]
    if len(parsed) != 1 or len(expected_lines) != 1 or proof.get("parser") != "explicit_dialogue" or proof.get("evidence_version") != "deterministic_dialogue_v1":
        return []
    supplied_hash = proof.pop("evidence_sha256", None)
    expected_hash = hashlib.sha256(json.dumps(
        proof, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    if supplied_hash != expected_hash:
        return []
    return [expected_hash]


@dataclass(frozen=True)
class VoiceApprovalContext:
    config: LLMConfig
    model: LLMModel
    provider_id: str
    allowlist: tuple[str, ...]
    selection: dict[str, Any]


@dataclass(frozen=True)
class RuleApprovalCommand:
    db: AsyncSession
    entity: StoryEntity
    matches: list[StoryEntity]
    evidence: list[dict[str, Any]]
    verified: list[str]
    evidence_hash: str
    voice: VoiceApprovalContext | None
    run: SeriesProductionRun
    chapters: list[Chapter]
    existing: list[StoryEntity]
    approved_at: str
    snapshot: dict[str, str] | None


def _dialogue_evidence(chapters: list[Chapter]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for chapter in chapters:
        for line in extract_explicit_dialogue(str(chapter.content or "")):
            grouped.setdefault(str(line["speaker"]), []).append({
                "chapter_id": chapter.id, "chapter_number": chapter.chapter_number,
                "source_span": line["source_span"], "spoken_text": line["spoken_text"],
            })
    return grouped


async def _voice_context(
    db: AsyncSession, run: SeriesProductionRun, snapshot: dict[str, str],
) -> VoiceApprovalContext:
    config = await db.get(LLMConfig, snapshot["config_id"])
    model = await db.get(LLMModel, config.model_id) if config else None
    provider_id = str((model.provider_id if model else "") or "")
    invalid = (config is None or model is None or config.user_id != run.user_id or not config.is_active
               or config.test_status != "success" or model.id != snapshot["db_model_id"]
               or model.model_id != snapshot["api_model_id"] or provider_id != snapshot["provider_id"])
    if invalid:
        raise StoryLockPreparationBlocked("TTS binding snapshot is stale or not owned")
    allowlist = provider_voice_allowlist(provider_id)
    selection = valid_voice_selection(run, snapshot, allowlist)
    if selection is None:
        raise StoryLockPreparationBlocked("voice selection is required for the current TTS binding snapshot")
    return VoiceApprovalContext(config, model, provider_id, allowlist, selection)


def _speaker_matches(existing: list[StoryEntity], speaker: str) -> list[StoryEntity]:
    return [item for item in existing if speaker in {
        str(item.name or "").strip(), str(item.canonical_name or "").strip(),
        *(str(alias).strip() for alias in (item.aliases or [])),
    }]


def _normalizable_single(
    candidate: StoryEntity | None, speaker: str, evidence: list[dict[str, Any]],
    verified: list[str],
) -> bool:
    if candidate is None:
        return False
    attrs = dict(candidate.attributes or {})
    return bool(candidate.source in {"system", "deterministic"}
        and get_entity_review_status(candidate) == CANDIDATE and candidate.entity_type == "character"
        and speaker in {str(candidate.name or "").strip(), str(candidate.canonical_name or "").strip()}
        and attrs.get("description_semantics_version") == "system_boilerplate_v1"
        and bool(attrs.get("extraction_notes")) and len(verified) == 1
        and str(candidate.chapter_id or candidate.first_seen_chapter_id or "") in {str(item["chapter_id"]) for item in evidence}
        and not attrs.get("voice_binding") and not attrs.get("merged_into_entity_id")
        and not (candidate.extra_data or {}).get("manual_review"))


def _resolve_entity(
    matches: list[StoryEntity], speaker: str, evidence: list[dict[str, Any]],
    evidence_hash: str, run: SeriesProductionRun, chapters: list[Chapter],
) -> tuple[StoryEntity, list[StoryEntity], list[str]]:
    active = [item for item in matches if not (get_entity_review_status(item) == ARCHIVED
        and ((item.extra_data or {}).get("normalized_merge") or {}).get("status") == "merged_superseded")]
    candidate = active[0] if len(active) == 1 else None
    verified = (_verified_single_candidate_evidence(
        candidate, speaker=speaker, chapters=chapters, dialogue_evidence=evidence,
    ) if candidate else [])
    if len(active) > 1 or _normalizable_single(candidate, speaker, evidence, verified):
        entity = _normalize_safe_dialogue_duplicates(
            active, speaker=speaker, evidence=evidence, evidence_hash=evidence_hash, user_id=run.user_id,
            chapter_order={str(chapter.id): index for index, chapter in enumerate(chapters, 1)},
        )
        return entity, [entity], verified
    entity = active[0] if active else matches[0] if matches else StoryEntity(
        id=str(uuid4()), user_id=run.user_id, novel_id=run.novel_id,
        chapter_id=evidence[0]["chapter_id"], first_seen_chapter_id=evidence[0]["chapter_id"],
        entity_type="character", name=speaker, canonical_name=speaker, source="system",
        version=1, aliases=[], relations=[], state_changes=[], tags=[], extra_data={},
    )
    return entity, matches, verified


def _accept_existing(
    entity: StoryEntity, matches: list[StoryEntity], voice: VoiceApprovalContext | None,
    snapshot: dict[str, str] | None, evidence_hash: str,
) -> bool:
    if not matches:
        return False
    attrs, status = dict(entity.attributes or {}), get_entity_review_status(entity)
    existing_voice = dict(attrs.get("voice_binding") or {})
    rule = dict((entity.extra_data or {}).get("explicit_dialogue_rule") or {})
    if voice is None:
        return bool(
            entity.source == "system" and status == APPROVED
            and rule.get("rule") == "rule_based_explicit_dialogue_native_audio_v1"
            and rule.get("evidence_hash") == evidence_hash
            and not existing_voice
        )
    if status == APPROVED and entity.source != "system":
        expected = {"config_id": voice.config.id, "provider_id": voice.provider_id,
                    "db_model_id": voice.model.id, "api_model_id": voice.model.model_id,
                    "tested_at": snapshot["tested_at"]}
        if existing_voice.get("voice_id") not in voice.allowlist or any(existing_voice.get(k) != v for k, v in expected.items()):
            raise StoryLockPreparationBlocked("manual approved character voice does not match the fresh TTS binding")
        return True
    if entity.source == "system" and status == APPROVED and rule.get("rule") == "rule_based_explicit_dialogue_v1" and rule.get("evidence_hash") == evidence_hash:
        expected = {"voice_id": voice.selection["voice_id"], "config_id": voice.config.id,
                    "provider_id": voice.provider_id, "tested_at": snapshot["tested_at"]}
        if any(existing_voice.get(k) != v for k, v in expected.items()):
            raise StoryLockPreparationBlocked("rule-created character voice binding snapshot is stale")
        return True
    fixture_evidence = dict(attrs.get("evidence_contract") or {})
    if (deterministic_provider_fake_enabled() and entity.source == "deterministic" and status == CANDIDATE
            and fixture_evidence.get("parser_version") in {
                "deterministic-acceptance-v1", "deterministic-extraction-v2"}):
        expected = {"voice_id": voice.selection["voice_id"], "config_id": voice.config.id,
                    "provider_id": voice.provider_id, "tested_at": snapshot["tested_at"]}
        if any(existing_voice.get(k) != v for k, v in expected.items()):
            raise StoryLockPreparationBlocked("deterministic acceptance voice binding snapshot is stale")
        return False
    if not (entity.source == "system" and status == CANDIDATE
            and rule.get("rule") == "rule_based_explicit_dialogue_v1" and rule.get("evidence_hash") == evidence_hash):
        raise StoryLockPreparationBlocked(f"existing character lifecycle requires review: {entity.name}")
    return False


def _apply_approval(command: RuleApprovalCommand) -> None:
    db, entity, matches = command.db, command.entity, command.matches
    evidence, verified, evidence_hash = command.evidence, command.verified, command.evidence_hash
    voice, run, chapters = command.voice, command.run, command.chapters
    existing, approved_at, snapshot = command.existing, command.approved_at, command.snapshot
    reason = "rule_based_explicit_dialogue_v1" if voice else "rule_based_explicit_dialogue_native_audio_v1"
    if not matches:
        set_entity_review_status(entity, CANDIDATE, changed_by=run.user_id, reason="rule_based_explicit_dialogue_v1")
        entity.extra_data = {**(entity.extra_data or {}), "explicit_dialogue_rule": {
            "rule": reason, "evidence_hash": evidence_hash}}
        db.add(entity)
        existing.append(entity)
    attrs = dict(entity.attributes or {})
    history = attrs.get("extraction_metadata_history") or []
    attrs.update({"approval_record": {"approved_by": run.user_id, "approved_at": approved_at,
        "reason": reason, "verified_evidence_hashes": verified,
        "candidate_source_hashes": sorted({_fingerprint({"source_entity_id": item.get("source_entity_id"),
            "chapter_id": item.get("chapter_id"), "evidence_hash": item.get("evidence_hash"),
            "metadata_hash": item.get("metadata_hash")}) for item in history})},
        "speaking": True, "dialogue_evidence": evidence, "dialogue_evidence_hash": evidence_hash})
    if voice and snapshot:
        attrs["voice_binding"] = {"voice_id": voice.selection["voice_id"], "version": int(voice.selection["version"]),
            "status": "locked", "provider_id": voice.provider_id, "config_id": voice.config.id,
            "db_model_id": voice.model.id, "api_model_id": voice.model.model_id,
            "tested_at": snapshot["tested_at"]}
    else:
        attrs.pop("voice_binding", None)
    chapter = next(item for item in chapters if item.id == evidence[0]["chapter_id"])
    attrs["evidence_contract"] = {"status": "verified", "chapter_id": chapter.id,
        "source_span": list(evidence[0]["source_span"]),
        "content_hash": hashlib.sha256(str(chapter.content or "").encode()).hexdigest(),
        "source_excerpt": str(chapter.content or "")[
            evidence[0]["source_span"][0]:evidence[0]["source_span"][1]],
        "parser_version": "explicit-dialogue-v1"}
    entity.attributes = attrs
    entity.evidence = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    set_entity_review_status(entity, APPROVED, changed_by=run.user_id, reason=reason)


def _chapter_evidence(line: dict[str, Any], chapter: Chapter) -> dict[str, Any]:
    content = str(chapter.content or "")
    start, end = line["source_span"]
    return {"status": "verified", "chapter_id": chapter.id,
        "source_span": [start, end], "content_hash": hashlib.sha256(content.encode()).hexdigest(),
        "source_excerpt": content[start:end], "parser_version": "explicit-dialogue-v1"}


def _ensure_local_mentions(
    db: AsyncSession, entity: StoryEntity, speaker: str, evidence: list[dict[str, Any]],
    chapters: list[Chapter], existing: list[StoryEntity], user_id: str,
) -> None:
    by_chapter = {str(chapter.id): chapter for chapter in chapters}
    for line in evidence:
        chapter_id = str(line["chapter_id"])
        if str(entity.chapter_id) == chapter_id:
            entity.attributes = {**(entity.attributes or {}),
                "evidence_contract": _chapter_evidence(line, by_chapter[chapter_id])}
            merged_ids = list(
                ((entity.extra_data or {}).get("entity_normalization") or {}).get("merged_entity_ids") or []
            )
            if len(evidence) == 1 and not merged_ids:
                continue
        local = [item for item in existing if item.id != entity.id
                 and item.entity_type == "character" and str(item.chapter_id) == chapter_id
                 and str(item.canonical_name or item.name or "").strip() == speaker]
        if len(local) > 1:
            raise StoryLockPreparationBlocked("explicit_dialogue_character_conflict")
        mention = local[0] if local else StoryEntity(
            id=str(uuid4()), user_id=entity.user_id, novel_id=entity.novel_id,
            chapter_id=chapter_id, first_seen_chapter_id=chapter_id,
            entity_type="character", name=speaker, canonical_name=speaker,
            source="system", version=1, aliases=[], relations=[], state_changes=[], tags=[],
            attributes={}, extra_data={},
        )
        edge = sign_merge_edge({"source_entity_id": mention.id,
            "canonical_entity_id": entity.id, "user_id": entity.user_id,
            "novel_id": entity.novel_id, "entity_type": "character",
            "canonical_identity_sha256": canonical_identity_sha256(
                entity_type="character", canonical_name=speaker)})
        existing_edges = [value for value in ((mention.extra_data or {}).get("merge_edges") or [])
                          if value.get("source_entity_id") == mention.id]
        if existing_edges and existing_edges != [edge]:
            raise StoryLockPreparationBlocked("explicit_dialogue_character_conflict")
        mention.attributes = {**(mention.attributes or {}),
            "evidence_contract": _chapter_evidence(line, by_chapter[chapter_id]),
            "merged_into_entity_id": entity.id}
        mention.chapter_id = chapter_id
        mention.first_seen_chapter_id = chapter_id
        mention.extra_data = {**(mention.extra_data or {}), "merge_edges": [edge],
            "normalized_merge": {"status": "merged_superseded", "canonical_entity_id": entity.id}}
        set_entity_review_status(mention, ARCHIVED, changed_by=user_id,
                                 reason="explicit_dialogue_chapter_local_mention")
        if not local:
            db.add(mention)
            existing.append(mention)


async def _prepare_explicit_dialogue_facts(
    db: AsyncSession, run: SeriesProductionRun, chapters: list[Chapter],
    tts_snapshot: dict[str, str] | None, *, native_audio: bool = False,
) -> list[StoryEntity]:
    grouped = _dialogue_evidence(chapters)
    if not grouped:
        return []
    if tts_snapshot is None and not native_audio:
        raise StoryLockPreparationBlocked("TTS binding is required when native audio is disabled")
    voice = await _voice_context(db, run, tts_snapshot) if tts_snapshot else None
    existing = list((await db.scalars(
        locked_dialogue_entities_statement(run.user_id, run.novel_id))).all())
    prepared: list[StoryEntity] = []
    approved_at = utc_now().isoformat()
    for speaker, evidence in grouped.items():
        evidence_hash = _fingerprint({"speaker": speaker, "evidence": evidence})
        entity, matches, verified = _resolve_entity(
            _speaker_matches(existing, speaker), speaker, evidence, evidence_hash, run, chapters)
        if _accept_existing(entity, matches, voice, tts_snapshot, evidence_hash):
            _ensure_local_mentions(db, entity, speaker, evidence, chapters, existing, run.user_id)
            prepared.append(entity)
            continue
        _apply_approval(RuleApprovalCommand(
            db, entity, matches, evidence, verified, evidence_hash, voice,
            run, chapters, existing, approved_at, tts_snapshot,
        ))
        _ensure_local_mentions(db, entity, speaker, evidence, chapters, existing, run.user_id)
        prepared.append(entity)
    await db.flush()
    return prepared
