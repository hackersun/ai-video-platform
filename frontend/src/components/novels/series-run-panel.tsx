'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { apiClient, type AnchorMode, type AnchorShotRecommendation, type ReferencePreparation, type SeriesProductionRun } from '@/lib/api-client';
import { getDefaultConfigForCapability, type SavedModelConfig } from '@/lib/model-configs';
import { SeriesRunView } from '@/features/series-runs/series-run-view';
import { useLivePreflight } from '@/features/series-runs/use-live-preflight';
import { useAnchorGeneration } from '@/features/series-runs/use-anchor-generation';
import { useSeriesRunRecovery } from '@/features/series-runs/hooks/use-series-run-recovery';
import { useSelectedFirstFrames } from '@/features/series-runs/use-selected-first-frames';
import { executeAndPollSeriesRun } from '@/features/series-runs/execute-and-poll';

type ChapterInput = { id: string; chapter_number: number; updated_at?: string; content?: string };
type PlanInput = { version?: number; updated_at?: string; episodes?: Array<{ episode_number?: number; episode_index?: number; chapter_ids?: string[]; chapters?: Array<{ id?: string }> }> };
export function SeriesRunPanel({ novelId, chapters, seriesPlan, modelConfigs, visualStyle }: {
  novelId: string;
  chapters: ChapterInput[];
  seriesPlan: PlanInput;
  modelConfigs: SavedModelConfig[];
  visualStyle: string;
}) {
  const [run, setRun] = useState<SeriesProductionRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [validatedBindings, setValidatedBindings] = useState<Record<string, any>>({});
  const [anchors, setAnchors] = useState<Record<AnchorMode, AnchorShotRecommendation[]>>({ smoke: [], representative: [], full: [] });
  const [anchorBlockers, setAnchorBlockers] = useState<Record<AnchorMode, { code: string; message: string } | null>>({ smoke: null, representative: null, full: null });
  const [anchorMode, setAnchorMode] = useState<AnchorMode>('smoke');
  const [selectedMode, setSelectedMode] = useState<AnchorMode>();
  const [selected, setSelected] = useState<string[]>([]);
  const [nativeAudio, setNativeAudio] = useState(false);
  const [liveBlocker, setLiveBlocker] = useState('');
  const [hydrating, setHydrating] = useState(false);
  const [storyLockBusy, setStoryLockBusy] = useState(false);
  const [referencePreparation, setReferencePreparation] = useState<ReferencePreparation | null>(null);
  const [preparationError, setPreparationError] = useState('');
  const hydratedRunId = useRef<string | null>(null);
  const { preflightPlan, preflightLoading, preflightError, selectedVoiceId,
    setSelectedVoiceId, refreshPreflightPlan } = useLivePreflight();
  const { generationBusy, generationStatus, generationQuality, generationDeliveries, generateSelected, openDeliverable } = useAnchorGeneration({
    run, selected, selectedMode, nativeAudio, preflightReady: preflightPlan?.ready === true,
    setRun, setError, refreshPreflightPlan,
  });
  const recovery = useSeriesRunRecovery({
    runId: run?.id, selectedShotCount: selected.length,
    projectedIncrement: preflightPlan?.budget.projected_increment_rmb,
    retryFailedStage: generateSelected,
    onReferenceRecovered: async (reference) => {
      setReferencePreparation(reference);
      if (run) await refreshPreflightPlan(run.id, nativeAudio);
    },
  });

  const configs = useMemo(() => ({
    text: getDefaultConfigForCapability(modelConfigs, 'text'),
    image: getDefaultConfigForCapability(modelConfigs, 'image'),
    tts: getDefaultConfigForCapability(modelConfigs, 'audio'),
    video: getDefaultConfigForCapability(modelConfigs, 'video'),
  }), [modelConfigs]);
  const firstFrames = useSelectedFirstFrames({
    runId: run?.id,
    selected,
    style: visualStyle,
    imageConfigId: configs.image?.id,
    refreshPreflight: () => run ? refreshPreflightPlan(run.id, nativeAudio) : Promise.resolve(),
  });

  const refreshAnchors = async (runId: string) => {
    const result = await apiClient.getSeriesRunAnchors(runId);
    setAnchors({ smoke: result.smoke, representative: result.representative, full: result.full });
    setAnchorBlockers(result.blockers || { smoke: null, representative: null, full: null });
    if (result.selected_shot_ids.length && result.selected_mode) {
      setSelected(result.selected_shot_ids);
      setSelectedMode(result.selected_mode);
      return;
    }
    if (!result.blockers?.smoke && result.smoke.length === 2) {
      const smokeIds = result.smoke.map((item) => item.shot_id);
      await apiClient.saveSeriesRunAnchors(runId, smokeIds, 'smoke');
      setSelected(smokeIds);
      setSelectedMode('smoke');
      return;
    }
    setSelected([]);
    setSelectedMode(undefined);
  };

  useEffect(() => {
    const runId = window.localStorage.getItem(`series-run:${novelId}`);
    if (!runId) return;
    if (hydratedRunId.current === runId) return;
    hydratedRunId.current = runId;
    setHydrating(true);
    apiClient.getSeriesRun(runId).then(async (value) => {
      setRun(value);
      const storedReference = value.run_metadata?.reference_preparation;
      setReferencePreparation(storedReference?.asset_id ? {
        run_id: value.id,
        asset_id: storedReference.asset_id,
        asset_version: storedReference.asset_version,
        provider_binding_id: storedReference.provider_binding_id,
        roles: storedReference.roles || [],
        status: 'locked',
        idempotent: true,
        resumed: true,
      } : null);
      try { await refreshAnchors(value.id); }
      catch (reason: any) { setError(reason?.message || '关键镜头状态读取失败'); }
      await refreshPreflightPlan(value.id, nativeAudio).catch(() => null);
      setHydrating(false);
    }).catch(() => {
      setHydrating(false);
      hydratedRunId.current = null;
      window.localStorage.removeItem(`series-run:${novelId}`);
    });
  }, [novelId]);

  const start = async (restartNonce?: string) => {
    setBusy(true); setError('');
    try {
      const episodes = [...(seriesPlan.episodes || [])].map((episode, index) => {
        const chapterIds = episode.chapter_ids?.length ? episode.chapter_ids : (episode.chapters || []).map((item) => item.id).filter(Boolean) as string[];
        const fallback = chapters[index]?.id ? [chapters[index].id] : [];
        const ids = chapterIds.length ? chapterIds : fallback;
        return { episode_number: index + 1, chapter_ids: ids, input_hash: ids.map((id) => `${id}:${chapters.find((item) => item.id === id)?.updated_at || ''}`).join('|') };
      });
      let current = await apiClient.createSeriesRun({
        novel_id: novelId,
        series_plan_version: String(seriesPlan.version || seriesPlan.updated_at || '1'),
        idempotency_key: `whole-book-${seriesPlan.version || seriesPlan.updated_at || '1'}-${chapters.map((item) => item.updated_at || item.id).join('|')}${restartNonce ? `-restart-${restartNonce}` : ''}`,
        requested_stages: ['workflow', 'script', 'storyboard', 'shots'], model_bindings: {}, budget_policy: {}, episodes,
      });
      window.localStorage.setItem(`series-run:${novelId}`, current.id);
      setRun(current);
      await refreshPreflightPlan(current.id, nativeAudio);
      current = await executeAndPollSeriesRun(current.id, setRun);
      await refreshAnchors(current.id);
    } catch (reason: any) {
      setError(reason?.message || '整书制作启动失败');
    } finally { setBusy(false); }
  };
  const restart = async () => {
    window.localStorage.removeItem(`series-run:${novelId}`);
    hydratedRunId.current = null;
    setRun(null);
    setValidatedBindings({});
    setAnchors({ smoke: [], representative: [], full: [] });
    setSelected([]);
    setSelectedMode(undefined);
    setError('');
    await start(String(Date.now()));
  };
  const prepareReference = async () => {
    if (!run) return;
    setBusy(true); setPreparationError('');
    try { setReferencePreparation(await apiClient.prepareSeriesRunReference(run.id, nativeAudio)); await refreshPreflightPlan(run.id, nativeAudio); }
    catch (reason: any) { setPreparationError(reason?.message || '参考图准备失败'); }
    finally { setBusy(false); }
  };
  const lockVoice = async () => {
    if (!run || !preflightPlan?.voice_options || !selectedVoiceId) return;
    setBusy(true); setPreparationError('');
    try {
      const voices = preflightPlan.voice_options;
      await apiClient.selectSeriesRunVoice(run.id, {
        config_id: voices.config_id,
        model_id: voices.model_id,
        voice_id: selectedVoiceId,
        version: (voices.selection?.version || 0) + 1,
      });
      await refreshPreflightPlan(run.id, nativeAudio);
    } catch (reason: any) { setPreparationError(reason?.message || '声线锁定失败'); }
    finally { setBusy(false); }
  };

  const act = async (kind: 'execute' | 'pause' | 'resume') => {
    if (!run) return;
    setBusy(true); setError('');
    try {
      let next = kind === 'pause' ? await apiClient.pauseSeriesRun(run.id) : kind === 'resume' ? await apiClient.resumeSeriesRun(run.id) : run;
      if (kind !== 'pause' && !['shots_ready', 'completed'].includes(next.status)) {
        next = await executeAndPollSeriesRun(run.id, setRun);
      }
      setRun(next); await refreshAnchors(next.id);
    } catch (reason: any) { setError(reason?.message || '操作失败'); } finally { setBusy(false); }
  };

  const saveSelection = async (ids: string[], mode?: AnchorMode) => {
    const previous = selected;
    const previousMode = selectedMode;
    const effectiveMode = mode || selectedMode || anchorMode;
    setSelected(ids);
    setSelectedMode(effectiveMode);
    if (!run || !ids.length) return;
    try { await apiClient.saveSeriesRunAnchors(run.id, ids, effectiveMode); }
    catch (reason: any) { setSelected(previous); setSelectedMode(previousMode); setError(reason?.message || '关键镜头选择不满足当前验证模式'); }
  };
  const chooseMode = (mode: AnchorMode) => { if (anchorBlockers[mode]) return; setAnchorMode(mode); void saveSelection(anchors[mode].map((item) => item.shot_id), mode); };
  const toggleNativeAudio = (enabled: boolean) => {
    setNativeAudio(enabled);
    if (run) void refreshPreflightPlan(run.id, enabled).catch(() => null);
  };
  const enableLiveCanary = async () => {
    if (!run) return;
    setBusy(true); setError(''); setLiveBlocker('');
    try {
      const configIds = Object.fromEntries(Object.entries(configs).map(([capability, config]) => [
        capability, config?.id || run.model_bindings?.capabilities?.[capability]?.config_id,
      ]));
      delete configIds.text;
      if (nativeAudio) delete configIds.tts;
      const videoOnlyContinuation = Boolean(
        run.run_metadata?.reference_preparation?.asset_id
        && preflightPlan?.anchor_dialogue_contracts?.length
        && preflightPlan.anchor_dialogue_contracts.every((item: any) => item.first_frame_ready),
      );
      if (videoOnlyContinuation) delete configIds.image;
      const missing = Object.entries(configIds).filter(([, configId]) => !configId).map(([capability]) => capability);
      if (missing.length) throw new Error(`缺少模型配置：${missing.join('、')}`);
      let current = run.budget_policy?.live_canary === true
        ? run
        : await apiClient.enableSeriesRunLiveCanary(run.id);
      const validated = await apiClient.validateSeriesRunBindings(current.id, {
        ...(configIds as { image?: string; video: string }), native_audio: nativeAudio,
      });
      setValidatedBindings(validated.model_bindings);
      current = { ...current, model_bindings: { capabilities: validated.model_bindings } };
      setRun(current);
      await refreshPreflightPlan(current.id, nativeAudio);
    }
    catch (reason: any) { setLiveBlocker(reason?.message || '服务端未配置受信实模预算，当前只能进行确定性整书编排'); }
    finally { setBusy(false); }
  };
  const qualityReports = Object.values(run?.run_metadata?.anchor_quality_reports || {}) as any[];
  const preflightBusy = busy || generationBusy || firstFrames.busy || hydrating || preflightLoading || storyLockBusy;
  return <SeriesRunView state={{
    run, busy, error, validatedBindings, anchors, anchorBlockers, anchorMode, selectedMode,
    selected, liveBlocker, preflightPlan, preflightLoading, hydrating, preflightError,
    referencePreparation, preparationError, selectedVoiceId, configs, qualityReports,
    generationStatus, generationQuality, generationDeliveries, nativeAudio,
    preflightBusy, chapters, recovery, firstFrames,
  }} actions={{
    start, restart, act, enableLiveCanary, refreshPreflightPlan, setSelectedVoiceId, lockVoice,
    prepareReference, setStoryLockBusy, chooseMode, saveSelection, generateSelected, setNativeAudio: toggleNativeAudio,
    executeRecovery: recovery.execute, openDeliverable,
    generateFirstFrames: () => firstFrames.generate(false),
    retryFailedFirstFrames: () => firstFrames.generate(true),
    regenerateShotFirstFrame: firstFrames.regenerateShot,
  }} />;
}
