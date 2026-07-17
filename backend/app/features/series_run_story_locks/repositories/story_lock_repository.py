"""Owned reads and atomic persistence for selected-anchor Story Locks."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import hashlib
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.time_utils import utc_now
from app.models import Chapter, Novel, Shot, StoryBible, StoryEntity, Workflow
from app.models.series_production_run import SeriesProductionRun
from app.services.story_entity_lifecycle import get_entity_review_status

from ..domain import EntityFact, RequiredEntityClosure, StoryLockSourceStale


@dataclass(frozen=True)
class CaptureStoryLockResponseCommand:
    run: SeriesProductionRun
    status_code: int
    body: dict[str, Any]
    body_sha256: str
    captured_at: str


class StoryLockRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def selected_shots(self, run: SeriesProductionRun) -> list[Shot]:
        selected_ids = [str(value) for value in (run.run_metadata or {}).get("selected_anchor_shot_ids", [])]
        if not selected_ids or len(selected_ids) != len(set(selected_ids)):
            raise StoryLockSourceStale("selected_ids_missing_or_duplicate")
        run_shot_ids = {
            str(shot_id)
            for episode in (run.episodes or [])
            for shot_id in ((episode.get("canonical_ids") or {}).get("shot_ids") or [])
        }
        if not set(selected_ids).issubset(run_shot_ids):
            raise StoryLockSourceStale("selected_id_outside_run")
        rows = list((await self.db.scalars(select(Shot).where(
            Shot.id.in_(selected_ids), Shot.user_id == run.user_id,
        ))).all())
        by_id = {shot.id: shot for shot in rows}
        if set(by_id) != set(selected_ids):
            raise StoryLockSourceStale("selected_shot_missing_or_unowned")
        return [by_id[shot_id] for shot_id in selected_ids]

    async def candidate_entities(self, run: SeriesProductionRun) -> list[StoryEntity]:
        return list((await self.db.scalars(select(StoryEntity).where(
            StoryEntity.user_id == run.user_id,
            StoryEntity.novel_id == run.novel_id,
        ))).all())

    async def owned_chapters(self, run: SeriesProductionRun) -> list[Chapter]:
        chapter_ids = [str(chapter_id) for episode in (run.episodes or []) for chapter_id in (episode.get("chapter_ids") or [])]
        if not chapter_ids or len(chapter_ids) != len(set(chapter_ids)):
            raise StoryLockSourceStale("episode_chapter_shape_invalid")
        rows = list((await self.db.scalars(select(Chapter).where(
            Chapter.id.in_(chapter_ids), Chapter.user_id == run.user_id, Chapter.novel_id == run.novel_id,
        ))).all())
        by_id = {chapter.id: chapter for chapter in rows}
        if set(by_id) != set(chapter_ids):
            raise StoryLockSourceStale("run_chapter_missing_or_unowned")
        return [by_id[chapter_id] for chapter_id in chapter_ids]

    async def novel(self, run: SeriesProductionRun) -> Novel | None:
        return await self.db.scalar(select(Novel).where(
            Novel.id == run.novel_id, Novel.user_id == run.user_id,
        ))

    async def bibles(self, run: SeriesProductionRun) -> list[StoryBible]:
        return list((await self.db.scalars(select(StoryBible).where(
            StoryBible.user_id == run.user_id, StoryBible.novel_id == run.novel_id,
        ))).all())

    async def dialogue_shots(self, run: SeriesProductionRun) -> list[Shot]:
        workflow_ids = [str((item.get("canonical_ids") or {}).get("workflow_id"))
                        for item in (run.episodes or []) if (item.get("canonical_ids") or {}).get("workflow_id")]
        workflows = list((await self.db.scalars(select(Workflow).where(
            Workflow.id.in_(workflow_ids), Workflow.user_id == run.user_id,
        ))).all()) if workflow_ids else []
        storyboard_ids = [item.storyboard_id for item in workflows if item.storyboard_id]
        rows = list((await self.db.scalars(select(Shot).where(
            Shot.user_id == run.user_id, Shot.storyboard_id.in_(storyboard_ids), Shot.dialogue.is_not(None),
        ))).all()) if storyboard_ids else []
        return [shot for shot in rows if isinstance((shot.extra_data or {}).get("dialogue_source"), dict)]

    async def flush(self) -> None:
        await self.db.flush()

    def add_bible(self, bible: StoryBible) -> None:
        self.db.add(bible)

    async def commit_and_refresh(self, bible: StoryBible) -> None:
        await self.db.commit()
        await self.db.refresh(bible)

    @staticmethod
    def facts(
        entities: Sequence[StoryEntity],
        chapter_hashes: dict[str, str] | None = None,
        chapter_lengths: dict[str, int] | None = None,
    ) -> list[EntityFact]:
        return [StoryLockRepository._fact(entity, chapter_hashes or {}, chapter_lengths or {}) for entity in entities]

    async def capture_response(self, command: CaptureStoryLockResponseCommand) -> dict[str, object]:
        await self.db.refresh(command.run)
        capture = {
            "status_code": command.status_code, "body": command.body,
            "body_sha256": command.body_sha256, "captured_at": command.captured_at,
        }
        metadata = dict(command.run.run_metadata or {})
        metadata["story_lock_response_capture"] = capture
        command.run.run_metadata = metadata
        flag_modified(command.run, "run_metadata")
        await self.db.flush()
        return capture

    @staticmethod
    def _fact(
        entity: StoryEntity,
        chapter_hashes: dict[str, str],
        chapter_lengths: dict[str, int],
    ) -> EntityFact:
        evidence = ((entity.attributes or {}).get("evidence_contract") or {})
        span = evidence.get("source_span")
        canonical_key, identity_keys = StoryLockRepository._identity_keys(entity)
        return EntityFact(
            id=str(entity.id), entity_type=str(entity.entity_type), user_id=str(entity.user_id),
            novel_id=entity.novel_id, chapter_id=entity.chapter_id,
            lifecycle_status=get_entity_review_status(entity),
            evidence_status=str(evidence.get("status") or ""),
            evidence_chapter_id=evidence.get("chapter_id"),
            source_span=tuple(span) if isinstance(span, list) and len(span) == 2 else None,
            content_hash=str(evidence.get("content_hash") or ""),
            expected_content_hash=chapter_hashes.get(str(evidence.get("chapter_id") or ""), ""),
            chapter_content_length=chapter_lengths.get(str(evidence.get("chapter_id") or ""), 0),
            parser_version=str(evidence.get("parser_version") or ""),
            conflicting_values=tuple(evidence.get("conflicting_values") or ()),
            first_seen_chapter_id=entity.first_seen_chapter_id,
            identity=StoryLockRepository._identity(entity),
            relations=tuple(item for item in (entity.relations or ()) if isinstance(item, dict)),
            state_changes=tuple(item for item in (entity.state_changes or ()) if isinstance(item, dict)),
            tags=tuple(str(item) for item in (entity.tags or ())),
            provenance_chapter_ids=StoryLockRepository._provenance_chapters(entity),
            canonical_identity_key=canonical_key, identity_keys=identity_keys,
        )

    @staticmethod
    def _identity_keys(entity: StoryEntity) -> tuple[str, tuple[str, ...]]:
        attrs, extra = dict(entity.attributes or {}), dict(entity.extra_data or {})
        merged = dict(extra.get("normalized_merge") or {})
        explicit_id = merged.get("canonical_entity_id") or attrs.get("canonical_entity_id")
        entity_type = str(entity.entity_type or "unknown")
        canonical_value = str(explicit_id or entity.canonical_name or entity.name or entity.id)
        canonical = f"{entity_type}:canonical:{StoryLockRepository._normalized_identity(canonical_value)}"
        keys = [canonical]
        verified_aliases = attrs.get("verified_aliases")
        aliases = verified_aliases if isinstance(verified_aliases, list) else list(entity.aliases or [])
        keys.extend(f"{entity_type}:alias:{StoryLockRepository._normalized_identity(value)}" for value in aliases if value)
        speaker = attrs.get("speaker_ref") or attrs.get("dialogue_speaker")
        if speaker:
            keys.append(f"{entity_type}:speaker:{StoryLockRepository._normalized_identity(speaker)}")
        return canonical, tuple(dict.fromkeys(keys))

    @staticmethod
    def _normalized_identity(value: object) -> str:
        return " ".join(str(value or "").strip().casefold().split())

    @staticmethod
    def _provenance_chapters(entity: StoryEntity) -> tuple[str, ...]:
        attrs = dict(entity.attributes or {})
        values: list[str] = []
        for key in ("identity_fact_provenance", "tag_fact_provenance"):
            for chapters in dict(attrs.get(key) or {}).values():
                if isinstance(chapters, list):
                    values.extend(str(chapter_id) for chapter_id in chapters if chapter_id)
        return tuple(values)

    @staticmethod
    def _identity(entity: StoryEntity) -> dict[str, object]:
        attrs = dict(entity.attributes or {})
        identity = dict(attrs.get("identity_facts") or {})
        for key in ("role", "species"):
            if attrs.get(key) not in (None, "", [], {}):
                identity[key] = attrs[key]
        for key in ("description", "appearance", "visual_prompt"):
            value = getattr(entity, key, None)
            if value:
                identity[key] = value
        if attrs.get("voice_binding"):
            identity["voice_binding"] = attrs["voice_binding"]
        return identity

    @staticmethod
    def _entity_snapshot(entity: StoryEntity) -> dict[str, object]:
        evidence = dict((entity.attributes or {}).get("evidence_contract") or {})
        return {
            "entity_id": entity.id, "name": entity.canonical_name or entity.name,
            "entity_type": entity.entity_type, "chapter_id": entity.chapter_id,
            "first_seen_chapter_id": entity.first_seen_chapter_id, "evidence": entity.evidence,
            "evidence_contract": evidence, "aliases": list(entity.aliases or []),
            "identity": StoryLockRepository._identity(entity), "relations": list(entity.relations or []),
            "state_changes": list(entity.state_changes or []), "tags": list(entity.tags or []),
            "identity_provenance": dict((entity.attributes or {}).get("identity_fact_provenance") or {}),
            "tag_provenance": dict((entity.attributes or {}).get("tag_fact_provenance") or {}),
        }

    @staticmethod
    def _closure_edges(
        closure: RequiredEntityClosure,
        entities: Sequence[StoryEntity],
    ) -> list[dict[str, str]]:
        by_id = {entity.id: entity for entity in entities}
        edges = []
        for entity_type, entity_id in closure.dependency_edges:
            canonical, _keys = StoryLockRepository._identity_keys(by_id[entity_id])
            identity_hash = hashlib.sha256(canonical.encode()).hexdigest()
            edges.append({
                "entity_type": entity_type, "entity_id": entity_id,
                "identity_key_sha256": identity_hash, "required_by": "selected_anchor",
            })
        return edges
