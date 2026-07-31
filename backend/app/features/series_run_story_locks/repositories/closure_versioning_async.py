"""AsyncSession adapter for atomic closure-v2 production persistence."""

from __future__ import annotations

import copy
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models import StoryBible
from app.models.series_production_run import SeriesProductionRun

from ..application.closure_versioning import CLOSURE_VERSION, preview_v2_lock
from ..domain.scoped_reference import canonical_json_sha256


class ClosureVersionDrift(RuntimeError):
    """The caller's run version is no longer current."""


def _fail(fail_at: str | None, point: str) -> None:
    if fail_at == point:
        raise RuntimeError(f"injected failure at {point}")


def _fingerprint(request: Mapping[str, Any], preview: Mapping[str, Any]) -> str:
    return canonical_json_sha256({
        "closure_contract_version": CLOSURE_VERSION,
        "source_hash": preview["source_hash"],
        "closure_hash": preview["closure_hash"],
        "snapshot_hash": preview["snapshot_hash"],
        "entity_extraction_contract_version": request.get("entity_extraction_contract_version"),
        "subjects": request.get("subjects"),
        "evidence_edges": request.get("evidence_edges"),
        "candidate_counts": request.get("candidate_counts"),
    })


def _validate_run_authority(run: SeriesProductionRun, request: Mapping[str, Any]) -> None:
    inputs = list(request.get("scoped_inputs") or [])
    canonical_ids: set[tuple[str, str]] = set()
    for item in inputs:
        reference, owned = item.get("reference") or {}, item.get("owned") or {}
        if reference.get("run_id") != run.id or owned.get("run_id") != run.id:
            raise ValueError("run authority mismatch")
        if owned.get("user_id") != run.user_id:
            raise ValueError("owner authority mismatch")
        if owned.get("novel_id") != run.novel_id:
            raise ValueError("novel authority mismatch")
        rows = [*(owned.get("source_rows") or []), *(owned.get("canonical_subjects") or [])]
        if any(row.get("user_id") != run.user_id or row.get("novel_id") != run.novel_id
               or row.get("entity_type") != owned.get("entity_type") for row in rows):
            raise ValueError("authoritative entity owner novel or type mismatch")
        histories = list(owned.get("canonical_histories") or [])
        if any(row.get("owner_user_id") != run.user_id or row.get("owner_novel_id") != run.novel_id
               or row.get("owner_entity_type") != owned.get("entity_type") for row in histories):
            raise ValueError("authoritative history owner novel or type mismatch")
        merges = list(owned.get("merge_edges") or [])
        if any(row.get("user_id") != run.user_id or row.get("novel_id") != run.novel_id
               or row.get("entity_type") != owned.get("entity_type") for row in merges):
            raise ValueError("authoritative merge owner novel or type mismatch")
        canonical_ids.update((str(row.get("entity_type")), str(row.get("id")))
                             for row in owned.get("canonical_subjects") or [])
    if any((str(row.get("entity_type")), str(row.get("canonical_entity_id"))) not in canonical_ids
           for row in request.get("subjects") or []):
        raise ValueError("canonical subject authority mismatch")


def _lock_payload(
    run: SeriesProductionRun,
    bible_id: str,
    fingerprint: str,
    preview: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "run_id": run.id, "version": int(run.version) + 1,
        "closure_contract_version": CLOSURE_VERSION,
        "request_fingerprint": fingerprint,
        "source_hash": preview["source_hash"],
        "closure_hash": preview["closure_hash"],
        "snapshot_hash": preview["snapshot_hash"],
        "story_bible_id": bible_id,
    }


class AsyncClosureVersioningAdapter:
    """Transaction-neutral persistence used only inside the StoryLock owner."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def apply_in_transaction(
        self,
        run_id: str,
        request: Mapping[str, Any],
        *,
        expected_run_version: int,
        fail_at: str | None = None,
    ) -> dict[str, Any]:
        if not self.db.in_transaction():
            raise RuntimeError("StoryLock top-level transaction is required")
        run = await self._current_run(run_id, expected_run_version)
        _validate_run_authority(run, request)
        preview = preview_v2_lock(request)
        fingerprint = _fingerprint(request, preview)
        existing = await self._exact_bible(run, request, preview, fingerprint)
        if existing is not None:
            return self._result(existing.id, preview, idempotent=True)
        await self._supersede(run, fingerprint)
        _fail(fail_at, "after_supersede")
        version = await self._next_version(run)
        bible_id = f"bible-v{version}-{uuid4()}"
        bible = self._new_bible(run, bible_id, version, fingerprint, request, preview)
        self.db.add(bible)
        _fail(fail_at, "after_bible_insert")
        self._point_run(run, bible_id, version, fingerprint, request, preview)
        _fail(fail_at, "after_run_pointer")
        self._point_episodes(run, bible_id, preview)
        _fail(fail_at, "after_episode_contracts")
        _fail(fail_at, "before_commit")
        return self._result(bible_id, preview, idempotent=False)

    async def _current_run(self, run_id: str, expected_version: int) -> SeriesProductionRun:
        run = await self.db.scalar(select(SeriesProductionRun).where(
            SeriesProductionRun.id == run_id,
        ).with_for_update())
        if run is None:
            raise ClosureVersionDrift("run missing or version drift")
        if int(run.version) != int(expected_version):
            raise ClosureVersionDrift("run version drift")
        return run

    async def _exact_bible(
        self, run: SeriesProductionRun, request: Mapping[str, Any],
        preview: Mapping[str, Any], fingerprint: str,
    ) -> StoryBible | None:
        lock = dict((run.run_metadata or {}).get("story_locks") or {})
        if lock.get("closure_contract_version") != CLOSURE_VERSION:
            return None
        expected = {"closure_contract_version": CLOSURE_VERSION,
                    "entity_extraction_contract_version": request.get("entity_extraction_contract_version"),
                    "request_fingerprint": fingerprint,
                    "source_hash": preview["source_hash"], "closure_hash": preview["closure_hash"],
                    "snapshot_hash": preview["snapshot_hash"], "subjects": request.get("subjects"),
                    "evidence_edges": request.get("evidence_edges")}
        if any(lock.get(key) != value for key, value in expected.items()):
            return None
        bible_id = str(lock.get("story_bible_id") or "")
        bible = await self.db.get(StoryBible, bible_id) if bible_id else None
        persisted = dict((bible.extra_data or {}).get("series_story_lock") or {}) if bible else {}
        return bible if all(persisted.get(key) == value for key, value in expected.items()) else None

    async def _next_version(self, run: SeriesProductionRun) -> int:
        rows = list((await self.db.scalars(select(StoryBible).where(
            StoryBible.user_id == run.user_id, StoryBible.novel_id == run.novel_id,
        ))).all())
        return max((int(((item.extra_data or {}).get("series_story_lock") or {}).get("version", 0))
                    for item in rows), default=0) + 1

    async def _supersede(self, run: SeriesProductionRun, fingerprint: str) -> None:
        metadata = copy.deepcopy(run.run_metadata or {})
        current = dict(metadata.get("story_locks") or {})
        old_id = current.get("story_bible_id")
        if old_id:
            metadata.setdefault("superseded_story_locks", []).append({
                "story_bible_id": old_id,
                "closure_contract_version": CLOSURE_VERSION,
                "request_fingerprint": fingerprint,
            })
        run.run_metadata = metadata
        flag_modified(run, "run_metadata")

    @staticmethod
    def _new_bible(
        run: SeriesProductionRun,
        bible_id: str,
        version: int,
        fingerprint: str,
        request: Mapping[str, Any],
        preview: Mapping[str, Any],
    ) -> StoryBible:
        lock = {**_lock_payload(run, bible_id, fingerprint, preview), "version": version,
                "entity_extraction_contract_version": request.get("entity_extraction_contract_version"),
                "subjects": request.get("subjects"), "evidence_edges": request.get("evidence_edges")}
        return StoryBible(
            id=bible_id, user_id=run.user_id, novel_id=run.novel_id,
            title=f"Production Bible v{lock['version']}",
            style=str((request.get("drift_factors") or {}).get("visual_style") or ""),
            extra_data={"production_status": "locked", "series_story_lock": lock},
        )

    @staticmethod
    def _point_run(
        run: SeriesProductionRun,
        bible_id: str,
        version: int,
        fingerprint: str,
        request: Mapping[str, Any],
        preview: Mapping[str, Any],
    ) -> None:
        metadata = copy.deepcopy(run.run_metadata or {})
        metadata["story_locks"] = {**_lock_payload(run, bible_id, fingerprint, preview),
                                   "entity_extraction_contract_version": request.get("entity_extraction_contract_version"),
                                   "version": version, "subjects": request.get("subjects"),
                                   "evidence_edges": request.get("evidence_edges"),
                                   "required_entity_ids": [item["canonical_entity_id"]
                                       for item in request.get("subjects") or []]}
        metadata["shot_lineage"] = {
            "story_bible_id": bible_id,
            "closure_contract_version": CLOSURE_VERSION,
            "evidence_edge_count": preview["evidence_edge_count"],
            "snapshot_hash": preview["snapshot_hash"],
        }
        run.run_metadata = metadata
        flag_modified(run, "run_metadata")

    @staticmethod
    def _point_episodes(
        run: SeriesProductionRun,
        bible_id: str,
        preview: Mapping[str, Any],
    ) -> None:
        run.episodes = [{
            **episode, "story_bible_id": bible_id,
            "closure_contract_version": CLOSURE_VERSION,
            "contract_version": preview["snapshot_hash"],
        } for episode in (run.episodes or [])]
        flag_modified(run, "episodes")

    @staticmethod
    def _result(
        bible_id: str, preview: Mapping[str, Any], *, idempotent: bool,
    ) -> dict[str, Any]:
        return {
            "story_bible_id": bible_id, "idempotent": idempotent,
            "closure_contract_version": CLOSURE_VERSION,
            "source_hash": preview["source_hash"],
            "closure_hash": preview["closure_hash"],
            "snapshot_hash": preview["snapshot_hash"],
            "required_counts": preview["required_counts"],
            "evidence_edge_count": preview["evidence_edge_count"],
            "required_evidence_count": preview["required_evidence_count"],
        }
