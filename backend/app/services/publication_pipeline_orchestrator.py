"""Layer-B NovelPublicationPipeline FSM — P1 post-tail + P2/P3/P4 one-click."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_utils import utc_now
from app.models.novel import Novel
from app.models.publication import Publication
from app.models.publication_pipeline import NovelPublicationPipeline
from app.models.series_production_run import SeriesProductionRun
from app.models.synthesis_job import SynthesisJob
from app.services.publication_export import PublicationNotReadyError, create_platform_publication
from app.services.publication_pipeline_front import (
    PipelineFrontBlocked,
    ensure_series_plan_for_pipeline,
    ensure_series_run_for_pipeline,
    run_front_to_shots,
)
from app.services.publication_pipeline_gates import (
    commercial_gates_env_enabled,
    commercial_gates_required,
    evaluate_commercial_gates,
)
from app.services.publication_pipeline_media import (
    PipelineMediaBlocked,
    run_media_quality_for_pipeline,
)
from app.services.publication_pipeline_render import (
    PipelineRenderBlocked,
    assemble_whole_book_mp4,
    ensure_episode_ffmpeg_local,
)
from app.services.publication_readiness import evaluate_publication_readiness, is_final_video_url

logger = logging.getLogger(__name__)

FORWARD_STAGES = (
    "accepted",
    "ensuring_plan",
    "ensuring_run",
    "run_front_to_shots",
    "run_media_quality",
    "episode_rendering",
    "book_assembling",
    "publication_gating",
    "publishing",
    "succeeded",
)

# Back-compat alias for P1 imports/tests
P1_FORWARD_STAGES = (
    "accepted",
    "episode_rendering",
    "book_assembling",
    "publication_gating",
    "publishing",
    "succeeded",
)

TERMINAL_STATUSES = {"succeeded", "failed", "blocked", "cancelled"}

FRONT_STAGES = {"accepted", "ensuring_plan", "ensuring_run", "run_front_to_shots", "run_media_quality"}


class InvalidPipelineTransition(ValueError):
    pass


class PublicationPipelineOrchestrator:
    def __init__(
        self,
        *,
        should_stop: Optional[Callable[[], Awaitable[bool]]] = None,
        ensure_episode_fn=ensure_episode_ffmpeg_local,
        assemble_fn=assemble_whole_book_mp4,
        create_publication_fn=create_platform_publication,
        ensure_plan_fn=ensure_series_plan_for_pipeline,
        ensure_run_fn=ensure_series_run_for_pipeline,
        run_front_fn=run_front_to_shots,
        run_media_fn=run_media_quality_for_pipeline,
    ):
        self._should_stop = should_stop
        self._ensure_episode = ensure_episode_fn
        self._assemble = assemble_fn
        self._create_publication = create_publication_fn
        self._ensure_plan = ensure_plan_fn
        self._ensure_run = ensure_run_fn
        self._run_front = run_front_fn
        self._run_media = run_media_fn

    async def _stop_requested(self) -> bool:
        if self._should_stop is None:
            return False
        return bool(await self._should_stop())

    def _mark_stage(self, pipeline: NovelPublicationPipeline, stage: str, *, result: str = "entered") -> None:
        summary = dict(pipeline.gate_summary or {})
        timings = list(summary.get("stage_timings") or [])
        timings.append({"stage": stage, "entered_at": utc_now().isoformat(), "result": result})
        summary["stage_timings"] = timings
        pipeline.gate_summary = summary
        pipeline.stage = stage

    def _block(self, pipeline: NovelPublicationPipeline, code: str, detail: str = "") -> NovelPublicationPipeline:
        pipeline.status = "blocked"
        pipeline.blocker_code = code
        pipeline.blocker_detail = detail or code
        summary = dict(pipeline.gate_summary or {})
        summary["blocker_code"] = code
        summary["blocker_detail"] = pipeline.blocker_detail
        pipeline.gate_summary = summary
        return pipeline

    def _fail(self, pipeline: NovelPublicationPipeline, code: str, detail: str = "") -> NovelPublicationPipeline:
        pipeline.status = "failed"
        pipeline.blocker_code = code
        pipeline.blocker_detail = detail or code
        return pipeline

    def _meta(self, pipeline: NovelPublicationPipeline) -> Dict[str, Any]:
        return dict(pipeline.pipeline_metadata or {})

    async def resolve_completed_run(
        self,
        db: AsyncSession,
        pipeline: NovelPublicationPipeline,
    ) -> Optional[SeriesProductionRun]:
        run: Optional[SeriesProductionRun] = None
        if pipeline.series_run_id:
            run = await db.scalar(
                select(SeriesProductionRun).where(
                    SeriesProductionRun.id == pipeline.series_run_id,
                    SeriesProductionRun.user_id == pipeline.user_id,
                    SeriesProductionRun.novel_id == pipeline.novel_id,
                )
            )
        else:
            rows = (
                await db.execute(
                    select(SeriesProductionRun).where(
                        SeriesProductionRun.user_id == pipeline.user_id,
                        SeriesProductionRun.novel_id == pipeline.novel_id,
                        SeriesProductionRun.series_plan_version == pipeline.series_plan_version,
                        SeriesProductionRun.status == "completed",
                    )
                )
            ).scalars().all()
            if len(rows) == 1:
                run = rows[0]
                pipeline.series_run_id = run.id
        return run

    def _run_ready_for_render(self, run: Optional[SeriesProductionRun]) -> bool:
        if run is None or run.status != "completed":
            return False
        media_tail = ((run.gate_summary or {}).get("media_tail") or {})
        # Allow completed runs without media_tail for P1 back-compat fixtures that only set completed.
        if media_tail and media_tail.get("result") not in {None, "passed"}:
            return False
        return True

    async def execute(
        self,
        db: AsyncSession,
        pipeline: NovelPublicationPipeline,
    ) -> NovelPublicationPipeline:
        if pipeline.status in {"cancelled", "succeeded"}:
            return pipeline
        if pipeline.status == "paused":
            return pipeline

        pipeline.status = "running"
        if pipeline.stage == "accepted":
            self._mark_stage(pipeline, "accepted", result="passed")

        run = await self.resolve_completed_run(db, pipeline)
        needs_front = not self._run_ready_for_render(run)

        if needs_front and pipeline.stage in FRONT_STAGES | {"accepted"}:
            pipeline = await self._execute_front_and_media(db, pipeline)
            if pipeline.status in TERMINAL_STATUSES or pipeline.status == "paused":
                return pipeline
            run = await self.resolve_completed_run(db, pipeline)
            if not self._run_ready_for_render(run):
                self._block(
                    pipeline,
                    "series_run_not_completed",
                    "front/media 阶段结束后仍无 completed SeriesProductionRun",
                )
                await db.commit()
                return pipeline

        if run is None or run.status != "completed":
            self._block(
                pipeline,
                "series_run_not_completed",
                "需要 completed SeriesProductionRun 才能进入渲染发布",
            )
            await db.commit()
            return pipeline

        summary = dict(pipeline.gate_summary or {})
        summary["series_run_ref"] = {
            "id": run.id,
            "status": run.status,
            "media_tail": (run.gate_summary or {}).get("media_tail"),
        }
        pipeline.gate_summary = summary
        await db.commit()

        if await self._stop_requested():
            pipeline.status = "paused"
            await db.commit()
            return pipeline

        # --- episode_rendering ---
        if pipeline.stage in {"accepted", "ensuring_plan", "ensuring_run", "run_front_to_shots", "run_media_quality", "episode_rendering"}:
            # After front/media, stage may still be run_media_quality — advance into rendering.
            if pipeline.stage != "episode_rendering":
                pipeline.stage = "episode_rendering"
            self._mark_stage(pipeline, "episode_rendering")
            await db.commit()
            try:
                episode_refs = await self._render_episodes(db, pipeline, run)
            except PipelineRenderBlocked as exc:
                if exc.code == "paused":
                    pipeline.status = "paused"
                    await db.commit()
                    return pipeline
                self._block(pipeline, exc.code, exc.message)
                await db.commit()
                return pipeline
            except Exception as exc:
                logger.exception("publication pipeline episode render failed", extra={"pipeline_id": pipeline.id})
                self._fail(pipeline, "episode_render_failed", str(exc))
                await db.commit()
                return pipeline
            summary = dict(pipeline.gate_summary or {})
            summary["episode_render_refs"] = episode_refs
            pipeline.gate_summary = summary
            pipeline.episodes = episode_refs
            self._mark_stage(pipeline, "episode_rendering", result="passed")
            pipeline.stage = "book_assembling"
            await db.commit()

        if await self._stop_requested():
            pipeline.status = "paused"
            await db.commit()
            return pipeline

        # --- book_assembling ---
        if pipeline.stage == "book_assembling":
            self._mark_stage(pipeline, "book_assembling")
            await db.commit()
            delivery = dict(pipeline.delivery or {})
            mode = str(delivery.get("mode") or "whole_book_single_mp4")
            episode_refs = list(pipeline.episodes or [])
            urls = [str(ep.get("output_url") or "") for ep in episode_refs]
            try:
                if mode == "primary_episode_only":
                    if not urls:
                        raise PipelineRenderBlocked("book_assemble_empty", "No episode urls for primary_episode_only")
                    final_url = urls[0]
                elif mode == "per_episode_publications":
                    final_url = self._assemble(urls, book_id=pipeline.id) if len(urls) > 1 else urls[0]
                else:
                    final_url = self._assemble(urls, book_id=pipeline.id)
            except PipelineRenderBlocked as exc:
                self._block(pipeline, exc.code, exc.message)
                await db.commit()
                return pipeline
            pipeline.final_video_url = final_url
            self._mark_stage(pipeline, "book_assembling", result="passed")
            pipeline.stage = "publication_gating"
            await db.commit()

        if await self._stop_requested():
            pipeline.status = "paused"
            await db.commit()
            return pipeline

        # --- publication_gating ---
        if pipeline.stage == "publication_gating":
            self._mark_stage(pipeline, "publication_gating")
            await db.commit()
            readiness = evaluate_publication_readiness(
                pipeline.final_video_url,
                {
                    "render_status": "rendered",
                    "render_backend": "ffmpeg_local",
                    "output_kind": "final_video",
                },
            )
            summary = dict(pipeline.gate_summary or {})
            summary["publication_readiness"] = readiness
            pipeline.gate_summary = summary
            if not readiness.get("is_publishable"):
                self._block(
                    pipeline,
                    "publication_not_ready",
                    "evaluate_publication_readiness rejected final video",
                )
                await db.commit()
                return pipeline
            if not is_final_video_url(pipeline.final_video_url):
                self._block(pipeline, "final_video_missing", "final_video_url is not mp4/mov/webm")
                await db.commit()
                return pipeline

            if commercial_gates_required(pipeline):
                gate_result = evaluate_commercial_gates(
                    pipeline,
                    run=run,
                    readiness=readiness,
                    queue_evidence=(pipeline.gate_summary or {}).get("queue"),
                )
                summary = dict(pipeline.gate_summary or {})
                summary["commercial_gates"] = gate_result
                summary["evidence_summary"] = gate_result.get("evidence_summary")
                pipeline.gate_summary = summary
                if not gate_result.get("passed"):
                    first = (gate_result.get("blockers") or [{}])[0]
                    self._block(
                        pipeline,
                        first.get("code") or "commercial_gate_failed",
                        first.get("message") or "commercial gates failed",
                    )
                    await db.commit()
                    return pipeline

            self._mark_stage(pipeline, "publication_gating", result="passed")
            pipeline.stage = "publishing"
            await db.commit()

        if await self._stop_requested():
            pipeline.status = "paused"
            await db.commit()
            return pipeline

        # --- publishing ---
        if pipeline.stage == "publishing":
            self._mark_stage(pipeline, "publishing")
            await db.commit()
            if pipeline.publication_id:
                existing = await db.scalar(
                    select(Publication).where(Publication.id == pipeline.publication_id)
                )
                if existing is not None:
                    self._mark_stage(pipeline, "publishing", result="passed")
                    pipeline.status = "succeeded"
                    pipeline.stage = "succeeded"
                    pipeline.blocker_code = None
                    pipeline.blocker_detail = None
                    await db.commit()
                    return pipeline

            novel = await db.scalar(
                select(Novel).where(Novel.id == pipeline.novel_id, Novel.user_id == pipeline.user_id)
            )
            delivery = dict(pipeline.delivery or {})
            title = delivery.get("title") or (novel.title if novel else None) or "整书成片"
            visibility = str(delivery.get("visibility") or "private")
            publish_status = str(delivery.get("publish_status") or "published")
            meta = {
                "pipeline_id": pipeline.id,
                "series_run_id": pipeline.series_run_id,
                "delivery_mode": delivery.get("mode") or "whole_book_single_mp4",
                "render_status": "rendered",
                "render_backend": "ffmpeg_local",
                "output_kind": "final_video",
                "source_output_url": pipeline.final_video_url,
                "format": "mp4",
            }
            synthesis_job = None
            refs = list(pipeline.episodes or [])
            if len(refs) == 1 and refs[0].get("synthesis_job_id"):
                synthesis_job = await db.scalar(
                    select(SynthesisJob).where(SynthesisJob.id == refs[0]["synthesis_job_id"])
                )
            try:
                publication = await self._create_publication(
                    db,
                    user_id=pipeline.user_id,
                    title=str(title),
                    video_url=pipeline.final_video_url,
                    synthesis_job=synthesis_job,
                    visibility=visibility,
                    status=publish_status,
                    metadata=meta,
                    allow_preview_export=False,
                )
            except PublicationNotReadyError as exc:
                self._block(pipeline, "publication_not_ready", "create_platform_publication rejected")
                summary = dict(pipeline.gate_summary or {})
                summary["publication_readiness"] = exc.readiness
                pipeline.gate_summary = summary
                await db.commit()
                return pipeline

            pipeline.publication_id = publication.id
            summary = dict(pipeline.gate_summary or {})
            summary["publication_ref"] = {
                "id": publication.id,
                "status": publication.status,
                "video_url": publication.video_url,
                "export_url": publication.export_url,
            }
            pipeline.gate_summary = summary
            self._mark_stage(pipeline, "publishing", result="passed")
            pipeline.status = "succeeded"
            pipeline.stage = "succeeded"
            pipeline.blocker_code = None
            pipeline.blocker_detail = None
            await db.commit()
            return pipeline

        if pipeline.stage == "succeeded":
            pipeline.status = "succeeded"
            await db.commit()
        return pipeline

    async def _load_bound_run(
        self, db: AsyncSession, pipeline: NovelPublicationPipeline
    ) -> Optional[SeriesProductionRun]:
        if not pipeline.series_run_id:
            return None
        return await db.scalar(
            select(SeriesProductionRun).where(
                SeriesProductionRun.id == pipeline.series_run_id,
                SeriesProductionRun.user_id == pipeline.user_id,
                SeriesProductionRun.novel_id == pipeline.novel_id,
            )
        )

    async def _execute_front_and_media(
        self,
        db: AsyncSession,
        pipeline: NovelPublicationPipeline,
    ) -> NovelPublicationPipeline:
        meta = self._meta(pipeline)
        ensure_plan = bool(meta.get("ensure_series_plan"))

        # Fast-forward when a Series Run is already bound past plan/create.
        bound = await self._load_bound_run(db, pipeline)
        if bound is not None and pipeline.stage in {"accepted", "ensuring_plan", "ensuring_run", "run_front_to_shots", "run_media_quality"}:
            summary = dict(pipeline.gate_summary or {})
            summary["series_run_ref"] = {
                "id": bound.id,
                "status": bound.status,
                "media_tail": (bound.gate_summary or {}).get("media_tail"),
            }
            pipeline.gate_summary = summary
            if bound.status in {"shots_ready", "anchor_ready", "media_running", "evaluating"}:
                if pipeline.stage in {"accepted", "ensuring_plan", "ensuring_run", "run_front_to_shots"}:
                    self._mark_stage(pipeline, "run_front_to_shots", result="passed")
                    pipeline.stage = "run_media_quality"
                    await db.commit()
            elif bound.status == "completed":
                # Incomplete media_tail handled by outer gate; treat as ready for media stage skip.
                self._mark_stage(pipeline, "run_media_quality", result="passed")
                await db.commit()
                return pipeline
            elif pipeline.stage in {"accepted", "ensuring_plan", "ensuring_run"}:
                # Existing early-stage run: skip plan/create, execute front on this run.
                self._mark_stage(pipeline, "ensuring_run", result="passed")
                pipeline.stage = "run_front_to_shots"
                await db.commit()

        # ensuring_plan
        if pipeline.stage in {"accepted", "ensuring_plan"}:
            self._mark_stage(pipeline, "ensuring_plan")
            await db.commit()
            try:
                plan_info = await self._ensure_plan(
                    db,
                    user_id=pipeline.user_id,
                    novel_id=pipeline.novel_id,
                    ensure=ensure_plan,
                    series_plan_version=pipeline.series_plan_version
                    if pipeline.series_plan_version != "unspecified"
                    else None,
                )
            except PipelineFrontBlocked as exc:
                self._block(pipeline, exc.code, exc.detail)
                await db.commit()
                return pipeline
            pipeline.series_plan_version = str(plan_info["series_plan_version"])
            meta["plan_episodes"] = plan_info["episodes"]
            pipeline.pipeline_metadata = meta
            self._mark_stage(pipeline, "ensuring_plan", result="passed")
            pipeline.stage = "ensuring_run"
            await db.commit()

        if await self._stop_requested():
            pipeline.status = "paused"
            await db.commit()
            return pipeline

        # ensuring_run
        if pipeline.stage == "ensuring_run":
            self._mark_stage(pipeline, "ensuring_run")
            await db.commit()
            episodes = list((pipeline.pipeline_metadata or {}).get("plan_episodes") or [])
            if not episodes:
                self._block(pipeline, "series_plan_episodes_missing", "ensuring_run 缺少 plan episodes")
                await db.commit()
                return pipeline
            try:
                run = await self._ensure_run(
                    db,
                    user_id=pipeline.user_id,
                    novel_id=pipeline.novel_id,
                    series_plan_version=pipeline.series_plan_version,
                    idempotency_key=pipeline.idempotency_key,
                    episodes=episodes,
                    model_bindings=meta.get("model_bindings") or {},
                    budget_policy=meta.get("budget_policy") or {},
                    requested_stages=meta.get("requested_stages"),
                )
            except PipelineFrontBlocked as exc:
                self._block(pipeline, exc.code, exc.detail)
                await db.commit()
                return pipeline
            pipeline.series_run_id = run.id
            summary = dict(pipeline.gate_summary or {})
            summary["series_run_ref"] = {"id": run.id, "status": run.status}
            pipeline.gate_summary = summary
            self._mark_stage(pipeline, "ensuring_run", result="passed")
            pipeline.stage = "run_front_to_shots"
            await db.commit()

        if await self._stop_requested():
            pipeline.status = "paused"
            await db.commit()
            return pipeline

        # run_front_to_shots
        if pipeline.stage == "run_front_to_shots":
            self._mark_stage(pipeline, "run_front_to_shots")
            await db.commit()
            run = await db.scalar(
                select(SeriesProductionRun).where(SeriesProductionRun.id == pipeline.series_run_id)
            )
            if run is None:
                self._block(pipeline, "series_run_missing", "ensuring_run 未绑定 series_run_id")
                await db.commit()
                return pipeline
            try:
                run = await self._run_front(db, run)
            except PipelineFrontBlocked as exc:
                self._block(pipeline, exc.code, exc.detail)
                await db.commit()
                return pipeline
            summary = dict(pipeline.gate_summary or {})
            summary["series_run_ref"] = {"id": run.id, "status": run.status}
            pipeline.gate_summary = summary
            self._mark_stage(pipeline, "run_front_to_shots", result="passed")
            pipeline.stage = "run_media_quality"
            await db.commit()

        if await self._stop_requested():
            pipeline.status = "paused"
            await db.commit()
            return pipeline

        # run_media_quality
        if pipeline.stage == "run_media_quality":
            self._mark_stage(pipeline, "run_media_quality")
            await db.commit()
            run = await db.scalar(
                select(SeriesProductionRun).where(SeriesProductionRun.id == pipeline.series_run_id)
            )
            if run is None:
                self._block(pipeline, "series_run_missing", "缺少 series run")
                await db.commit()
                return pipeline
            try:
                run = await self._run_media(
                    db,
                    run,
                    pipeline,
                    env_commercial=commercial_gates_env_enabled(),
                )
            except PipelineMediaBlocked as exc:
                # Media generation commits/rolls back the shared session, which
                # expires ORM objects; reload before touching attributes.
                await db.refresh(pipeline)
                self._block(pipeline, exc.code, exc.detail)
                await db.commit()
                return pipeline
            await db.refresh(pipeline)
            await db.refresh(run)
            summary = dict(pipeline.gate_summary or {})
            summary["series_run_ref"] = {
                "id": run.id,
                "status": run.status,
                "media_tail": (run.gate_summary or {}).get("media_tail"),
            }
            pipeline.gate_summary = summary
            self._mark_stage(pipeline, "run_media_quality", result="passed")
            # Leave stage as run_media_quality; outer execute advances to episode_rendering.
            await db.commit()

        return pipeline

    async def _render_episodes(
        self,
        db: AsyncSession,
        pipeline: NovelPublicationPipeline,
        run: SeriesProductionRun,
    ) -> List[Dict[str, Any]]:
        refs: List[Dict[str, Any]] = []
        episodes = list(run.episodes or [])
        if not episodes:
            raise PipelineRenderBlocked(
                "series_run_episodes_missing",
                "Completed series run has no episodes to render",
            )
        for episode in episodes:
            if await self._stop_requested():
                raise PipelineRenderBlocked("paused", "pause requested during episode rendering")
            episode_number = episode.get("episode_number")
            workflow_id = (episode.get("canonical_ids") or {}).get("workflow_id")
            if not workflow_id:
                raise PipelineRenderBlocked(
                    "episode_workflow_missing",
                    f"Episode {episode_number} missing workflow_id",
                    episode_number=episode_number,
                )
            rendered = await self._ensure_episode(db, user_id=pipeline.user_id, workflow_id=str(workflow_id))
            if not is_final_video_url(rendered.get("output_url")):
                raise PipelineRenderBlocked(
                    "final_video_missing",
                    f"Episode {episode_number} render did not produce final mp4",
                    episode_number=episode_number,
                )
            if rendered.get("render_status") != "rendered":
                raise PipelineRenderBlocked(
                    "render_status_not_rendered",
                    f"Episode {episode_number} render_status is not rendered",
                    episode_number=episode_number,
                )
            refs.append(
                {
                    "episode_number": episode_number,
                    "workflow_id": str(workflow_id),
                    "synthesis_job_id": rendered.get("synthesis_job_id"),
                    "render_backend": rendered.get("render_backend") or "ffmpeg_local",
                    "render_status": rendered.get("render_status"),
                    "output_url": rendered.get("output_url"),
                    "shots_ready": True,
                    "media_completed": True,
                    "blocker_code": None,
                }
            )
        return refs


__all__ = [
    "InvalidPipelineTransition",
    "FORWARD_STAGES",
    "P1_FORWARD_STAGES",
    "PublicationPipelineOrchestrator",
    "TERMINAL_STATUSES",
]
