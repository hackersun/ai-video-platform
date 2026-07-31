import { useEffect, useState } from 'react';

import { apiClient, type AnchorDeliverable, type AnchorGenerationResponse, type AnchorMode, type SeriesProductionRun } from '@/lib/api-client';
import { pollAnchorGeneration } from './poll-anchor-generation';

type Inputs = {
  run: SeriesProductionRun | null;
  selected: string[];
  selectedMode?: AnchorMode;
  nativeAudio: boolean;
  preflightReady: boolean;
  setRun: (run: SeriesProductionRun) => void;
  setError: (message: string) => void;
  refreshPreflightPlan: (runId: string, nativeAudio?: boolean) => Promise<any>;
};

async function awaitPersistedReports(runId: string, expected: number, initial: SeriesProductionRun) {
  let current = initial;
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (Object.keys(current.run_metadata?.anchor_quality_reports || {}).length >= expected) return current;
    await new Promise((resolve) => setTimeout(resolve, 250));
    current = await apiClient.getSeriesRun(runId);
  }
  throw new Error('关键镜头已生成，但质量证据尚未完整持久化，请稍后重试。');
}

export function useAnchorGeneration({
  run, selected, selectedMode, nativeAudio, preflightReady, setRun, setError, refreshPreflightPlan,
}: Inputs) {
  const [generationBusy, setGenerationBusy] = useState(false);
  const [generationStatus, setGenerationStatus] = useState<AnchorGenerationResponse['status'] | ''>('');
  const [generationQuality, setGenerationQuality] = useState<any[]>([]);
  const [generationDeliveries, setGenerationDeliveries] = useState<AnchorDeliverable[]>([]);

  const finish = async (runId: string, initial: AnchorGenerationResponse) => {
    const generated = initial.status === 'provider_pending' || initial.status === 'provider_ready'
      ? await pollAnchorGeneration({ runId, initial, client: apiClient, onStatus: setGenerationStatus })
      : initial;
    setGenerationStatus(generated.status);
    setGenerationQuality(generated.quality_results || []);
    if (generated.status === 'failed') throw new Error('关键镜头云端视频或配音任务失败，未创建聚合产物。');
    const deliveries = await Promise.all((generated.media_job_ids || []).map((id) => apiClient.getMediaJob(id)));
    setGenerationDeliveries(deliveries.map((job) => ({
      id: job.id, shot_id: job.shot_id, title: job.title,
      output_video_url: job.output_video_url,
      public_video_url: job.extra_data?.subtitle_public_video_url,
      subtitle_track_id: job.subtitle_track_id,
      duration_seconds: job.duration_seconds, resolution: job.resolution, status: job.status,
      video_native_audio: Boolean(job.extra_data?.video_native_audio),
      subtitle_sync_status: job.extra_data?.subtitle_sync_status
        || (job.extra_data?.video_native_audio && job.extra_data?.subtitle_burned
          ? 'script_aligned_pending_audio_verification' : undefined),
      audio_verification_required: Boolean(
        job.extra_data?.audio_verification_required
        || (job.extra_data?.video_native_audio && job.extra_data?.subtitle_burned),
      ),
    })));
    let refreshed = await apiClient.getSeriesRun(runId);
    const waitingForTrustedEvaluation = generated.quality_results?.some(
      (result) => !result.ready && result.overall_readiness === 'trusted_multimodal_evaluation_required',
    );
    if (!waitingForTrustedEvaluation) refreshed = await awaitPersistedReports(runId, selected.length, refreshed);
    setRun(refreshed);
    await refreshPreflightPlan(runId, nativeAudio);
  };

  useEffect(() => {
    if (!run || run.status !== 'media_running' || generationBusy) return;
    setGenerationBusy(true);
    apiClient.reconcileSelectedSeriesRunAnchors(run.id)
      .then((response) => finish(run.id, response))
      .catch((reason: any) => {
        if (reason?.status !== 409) setError(reason?.message || '关键镜头任务恢复失败');
      })
      .finally(() => setGenerationBusy(false));
  }, [run?.id]);

  const generateSelected = async () => {
    if (!run) return;
    if (!preflightReady) { setError('实模前置准备尚未全部通过，禁止生成关键镜头。'); return; }
    if (!selectedMode) { setError('请先选择 2 镜头冒烟、3 镜头代表验证或 6 镜头完整验证模式'); return; }
    if (run.budget_policy?.profile !== 'isolated_live_canary' || run.budget_policy?.live_canary !== true) {
      setError('请先明确启用“实模关键镜头验证”；整书编排本身不会自动开启付费模型。'); return;
    }
    setGenerationBusy(true); setError('');
    try {
      const initial = await apiClient.generateSelectedSeriesRunAnchors(
        run.id, selected, selectedMode, nativeAudio,
      );
      await finish(run.id, initial);
    } catch (reason: any) {
      setError(reason?.message || '所选镜头生成失败');
    } finally {
      setGenerationBusy(false);
    }
  };

  const openDeliverable = (jobId: string) => {
    const playbackPage = `/media-player?job_id=${encodeURIComponent(jobId)}`;
    window.open(playbackPage, '_blank', 'noopener,noreferrer');
  };

  return { generationBusy, generationStatus, generationQuality, generationDeliveries, generateSelected, openDeliverable };
}
