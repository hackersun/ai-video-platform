'use client';

import Link from 'next/link';
import { AlertCircle, CheckCircle2, Loader2, Pause, Play, RefreshCw } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { StoryLockControl } from '@/features/series-story-locks/story-lock-control';
import { AnchorShotSelector } from '@/components/novels/anchor-shot-selector';
import { RecoveryCard } from './components/recovery-card';
import { SkillEvidenceGrid } from './components/skill-evidence-grid';
import { FirstFrameControls } from './components/first-frame-controls';

const STAGE_LABELS: Record<string, string> = {
  created: '等待启动', workflow_ready: '工程就绪', script_ready: '剧本就绪',
  storyboard_ready: '分镜就绪', shots_ready: '镜头就绪', media_running: '媒体生成中',
  completed: '已完成', blocked: '被阻塞', failed: '失败', paused: '已暂停',
};
const QUALITY_DIMENSIONS = ['narrative_truth', 'character_visual', 'scene_prop_state', 'style_cinematography', 'voice_dialogue', 'delivery_integrity'];
const qualityLabel: Record<string, string> = {
  narrative_truth: '剧情事件', character_visual: '人物角色', scene_prop_state: '场景道具',
  style_cinematography: '动漫风格', voice_dialogue: '配音对白', delivery_integrity: '交付完整性',
};

function blockerText(blocker: any) {
  if (!blocker) return '';
  return typeof blocker === 'string' ? blocker : blocker.message || blocker.code || JSON.stringify(blocker);
}

export function SeriesRunView({ state, actions }: { state: any; actions: any }) {
  const { run, busy, error, validatedBindings, anchors, anchorBlockers, anchorMode,
    selectedMode, selected, liveBlocker, preflightPlan, preflightLoading, hydrating,
    preflightError, referencePreparation, preparationError, selectedVoiceId, configs,
    qualityReports, generationStatus, generationQuality, generationDeliveries, nativeAudio, preflightBusy, chapters, recovery } = state;
  const { start, restart, act, enableLiveCanary, refreshPreflightPlan, setSelectedVoiceId,
    lockVoice, prepareReference, setStoryLockBusy, chooseMode, saveSelection,
    generateSelected, setNativeAudio, executeRecovery, openDeliverable,
    generateFirstFrames, retryFailedFirstFrames, regenerateShotFirstFrame } = actions;
  const typedConfigs = configs as Record<string, any>;
  const requiresTtsVoice = Boolean(
    preflightPlan?.anchor_dialogue_contracts?.some((item: any) => item.requires_tts),
  );
  const storyLockStale = Boolean(preflightPlan?.blocker_codes?.includes('story_lock_stale'));
  const hasExistingDeliveries = generationDeliveries?.length > 0;
  const referenceDeliveryNeedsRefresh = Boolean(
    (referencePreparation?.asset_id || run?.run_metadata?.reference_preparation?.asset_id)
    && preflightPlan?.blocker_codes?.includes('provider_binding_not_ready'),
  );
  const videoOnlyContinuation = Boolean(
    run?.run_metadata?.reference_preparation?.asset_id
    && preflightPlan?.anchor_dialogue_contracts?.length
    && preflightPlan.anchor_dialogue_contracts.every((item: any) => item.first_frame_ready),
  );

  return (
    <section className="space-y-4 rounded-xl border border-violet-400/20 bg-violet-500/5 p-4" data-testid="series-run-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h3 className="font-semibold text-white">整书自动制作</h3><p className="text-sm text-white/50">一次推进全部章节到镜头就绪，再选择跨章关键镜头验证一致性。</p></div>
        {!run ? <Button onClick={() => start()} disabled={busy || chapters.length < 2} className="bg-violet-600 hover:bg-violet-700">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}整书自动制作</Button> : (
          <div className="flex gap-2">
            {(run.status === 'failed' || storyLockStale) && <Button size="sm" onClick={restart} disabled={preflightBusy}>{storyLockStale ? '按最新章节重新开始' : '重新开始'}</Button>}
            <Button size="sm" variant="outline" onClick={() => act('execute')} disabled={preflightBusy}><RefreshCw className="mr-2 h-4 w-4" />继续推进</Button>
            {run.status === 'paused' ? <Button size="sm" onClick={() => act('resume')} disabled={busy}><Play className="mr-2 h-4 w-4" />恢复</Button> : <Button size="sm" variant="outline" onClick={() => act('pause')} disabled={busy}><Pause className="mr-2 h-4 w-4" />暂停</Button>}
          </div>
        )}
      </div>
      <div className={chapters.length < 2 ? 'text-sm text-amber-200' : 'text-sm text-white/50'}>{chapters.length < 2 ? '至少需要 2 章才能进行跨章验证。' : `本次共 ${chapters.length} 章，可选择不同覆盖强度的关键镜头。`}</div>
      {error && <div role="alert" className="flex gap-2 rounded-md bg-red-500/10 p-3 text-sm text-red-200"><AlertCircle className="h-4 w-4 shrink-0" />{error}</div>}
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {Object.entries(typedConfigs).map(([capability, config]) => { const serverTestedAt = validatedBindings[capability]?.tested_at || run?.model_bindings?.capabilities?.[capability]?.tested_at; return <div key={capability} className="rounded-md bg-black/15 p-3 text-sm"><div className="text-white/40">{capability.toUpperCase()}</div><div className="truncate text-white">{config?.name || '未配置'}</div><div className="text-xs text-emerald-200">{serverTestedAt ? `绑定快照：${serverTestedAt}` : config?.test_status === 'success' ? '历史验证通过，绑定时仍需服务端新鲜度验证' : '待服务端验证'}</div></div>; })}
      </div>
      {run && <SkillEvidenceGrid runMetadata={run.run_metadata} nativeAudio={nativeAudio} />}
      {run && <>
        <div className="flex flex-wrap gap-2 text-sm"><Badge variant="outline">整书状态：{STAGE_LABELS[run.status] || run.status}</Badge><Badge variant="outline">预计成本 ¥{run.cost_summary?.projected_rmb ?? run.budget_policy?.projected_rmb ?? 0}</Badge><Badge variant="outline">实际成本 ¥{run.cost_summary?.spent_rmb ?? run.cost_summary?.actual_rmb ?? 0}</Badge></div>
        <RecoveryCard {...recovery} onAction={executeRecovery} />
        <label className="flex items-start gap-3 rounded-lg border border-violet-400/20 bg-violet-500/5 p-3 text-sm text-white/70">
          <input aria-label="本次使用 Seedance 1.5 原生配音" type="checkbox" className="mt-1 h-4 w-4 accent-violet-500" checked={nativeAudio} onChange={(event) => setNativeAudio(event.target.checked)} disabled={preflightBusy} />
          <span><span className="block font-medium text-white">Seedance 1.5 原生配音（临时）</span><span className="text-xs text-white/50">可在模型绑定前选择；仅本次生成有效，并跳过独立 TTS。</span></span>
        </label>
        <div className="rounded-lg border border-amber-400/20 bg-amber-500/5 p-3">
          <div className="flex flex-wrap items-center gap-2">
            {run.budget_policy?.live_canary === true && <div className="text-sm text-emerald-200">实模关键镜头验证已启用 · 服务端预算上限 ¥{run.budget_policy.max_rmb}</div>}
            <Button size="sm" variant="outline" onClick={enableLiveCanary} disabled={preflightBusy}>{run.budget_policy?.live_canary === true ? (videoOnlyContinuation ? '重新验证视频绑定' : '重新验证模型绑定') : '启用实模关键镜头验证'}</Button>
          </div>
          {liveBlocker && <div role="alert" className="mt-2 text-sm text-amber-100">live_canary_unavailable：{liveBlocker}</div>}
        </div>
        {(hydrating || preflightLoading || preflightError) && <div className="flex flex-wrap items-center gap-2 rounded-lg border border-sky-400/20 bg-sky-500/5 p-3 text-sm">
          {(hydrating || preflightLoading) && <span className="text-sky-100">前置状态加载中…</span>}
          {preflightError && <><span role="alert" className="text-red-200">{preflightError}</span><Button size="sm" variant="outline" onClick={() => refreshPreflightPlan(run.id, nativeAudio).catch(() => null)}>刷新前置状态</Button></>}
        </div>}
        {preflightPlan && <div className="space-y-3 rounded-lg border border-sky-400/20 bg-sky-500/5 p-3" data-testid="live-preflight-plan">
          <div className="flex flex-wrap items-center justify-between gap-2"><div className="text-sm font-medium text-white">{hasExistingDeliveries ? '再次生成前置检查' : '实模前置准备'} · {preflightPlan.ready ? '已就绪' : '未就绪'}</div><Badge variant="outline">上限 ¥{preflightPlan.budget.maximum_rmb} · 剩余 ¥{preflightPlan.budget.remaining_rmb} · 本轮预计 ¥{preflightPlan.budget.projected_increment_rmb}</Badge></div>
          {hasExistingDeliveries && <div className="text-xs text-emerald-200">已有成片不受本检查影响；以下预算和阻塞项仅针对再次调用模型生成。</div>}
          <div className="grid gap-2 sm:grid-cols-3">{preflightPlan.cost_breakdown.map((item) => <div key={item.capability} className="rounded bg-black/15 p-2 text-xs text-white/70">{item.capability.toUpperCase()} × {item.quantity}：¥{item.subtotal_rmb}<div className="text-white/40">服务端可信估算</div></div>)}</div>
          <div className="space-y-1">{preflightPlan.anchor_dialogue_contracts.map((item) => <div key={item.shot_id} className="text-xs text-white/60">第 {item.episode_number} 章镜头 · {item.audio_route === 'video_native_audio' ? `视频模型原生配音${item.speaker ? `（${item.speaker}）` : ''}` : item.requires_tts ? `需要配音${item.speaker ? `（${item.speaker}）` : '（说话人未知）'}` : item.dialogue ? '对白已保留，不生成 TTS' : '无对白'}</div>)}</div>
          {requiresTtsVoice ? preflightPlan.voice_options ? <div className="flex flex-wrap items-end gap-2">
            <label className="space-y-1 text-xs text-white/60"><span className="block">配音声线</span><select aria-label="配音声线" className="h-9 min-w-48 rounded-md border border-white/15 bg-black/30 px-3 text-sm text-white" value={selectedVoiceId} onChange={(event) => setSelectedVoiceId(event.target.value)} disabled={preflightBusy || preflightPlan.voice_options.options.length === 0}>{preflightPlan.voice_options.options.map((voice) => <option key={voice.voice_id} value={voice.voice_id}>{voice.label}</option>)}</select></label>
            <Button size="sm" variant="outline" onClick={lockVoice} disabled={preflightBusy || !selectedVoiceId}>锁定声线</Button>
            {preflightPlan.voice_options.selection && <div className="pb-2 text-xs text-emerald-200">已锁定：{preflightPlan.voice_options.options.find((voice) => voice.voice_id === preflightPlan.voice_options.selection?.voice_id)?.label || preflightPlan.voice_options.selection.voice_id} · v{preflightPlan.voice_options.selection.version}</div>}
          </div> : <div className="text-xs text-amber-100">声线选项将在有效 TTS 绑定完成后显示。</div> : <div className="text-xs text-emerald-200">当前由视频模型原生配音，无需锁定 TTS 声线。</div>}
          {preflightPlan.blockers.length > 0 && <div className="space-y-1">{preflightPlan.blockers.map((item) => <div key={`${item.code}:${item.shot_id || ''}`} className="text-xs text-amber-100">{item.code}：{item.message}</div>)}</div>}
          <div className="flex flex-wrap gap-2"><StoryLockControl runId={run.id} disabled={preflightBusy} nativeAudio={nativeAudio} onPrepared={() => refreshPreflightPlan(run.id, nativeAudio)} onLoading={setStoryLockBusy} /><Button size="sm" variant="outline" onClick={prepareReference} disabled={preflightBusy || preflightPlan.blocker_codes.some((code) => ['story_bible_missing', 'state_machine_missing', 'story_lock_stale', 'trusted_budget_policy_missing', 'projected_budget_exceeded', 'model_bindings_not_fresh', 'production_entities_unapproved', 'production_entity_conflict'].includes(code))}>{referenceDeliveryNeedsRefresh ? '刷新参考图公网地址' : '生成并锁定参考图'}</Button><Button size="sm" variant="ghost" onClick={() => refreshPreflightPlan(run.id, nativeAudio)} disabled={preflightBusy}>刷新前置状态</Button></div>
          {referencePreparation && <div className="space-y-1 text-xs text-emerald-200"><div>参考图：{referencePreparation.status} · Asset {referencePreparation.asset_id} · v{referencePreparation.asset_version}</div><div>角色：{referencePreparation.roles.join('、')} · Binding {referencePreparation.provider_binding_id}</div>{referencePreparation.operation && <div>Operation {referencePreparation.operation.id} · {referencePreparation.operation.status}</div>}{referencePreparation.artifact && <div>Checksum {referencePreparation.artifact.checksum} · 布局证据（仅布局）{JSON.stringify(referencePreparation.artifact.layout_evidence || {})}</div>}</div>}
          {preparationError && <div role="alert" className="text-xs text-red-200">{preparationError}</div>}
        </div>}
        <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-4" data-testid="series-run-episodes">
          {run.episodes.map((episode) => <div key={episode.episode_number} className="rounded-lg border border-white/10 bg-black/15 p-3"><div className="flex justify-between"><span className="font-medium text-white">第 {episode.episode_number} 章</span>{episode.stage === 'shots_ready' && <CheckCircle2 className="h-4 w-4 text-emerald-300" />}</div><div className="text-sm text-white/60">{STAGE_LABELS[episode.stage] || episode.stage}</div>{episode.blocker && <div className="mt-2 text-xs text-red-200">阻塞：{blockerText(episode.blocker)}</div>}{episode.canonical_ids?.workflow_id && <Link className="mt-2 block text-xs text-blue-300" href={`/studio?workflow_id=${episode.canonical_ids.workflow_id}&source=series-run`}>打开本章 Studio</Link>}</div>)}
        </div>
        {anchors.smoke.length > 0 && <div className="space-y-3">
          <div className="flex flex-wrap gap-2"><Button size="sm" variant={anchorMode === 'smoke' ? 'default' : 'outline'} disabled={preflightBusy || Boolean(anchorBlockers.smoke)} onClick={() => chooseMode('smoke')}>2 镜头冒烟验证</Button><Button size="sm" variant={anchorMode === 'representative' ? 'default' : 'outline'} disabled={preflightBusy || Boolean(anchorBlockers.representative)} onClick={() => chooseMode('representative')}>3 镜头前中后代表验证</Button><Button size="sm" variant={anchorMode === 'full' ? 'default' : 'outline'} disabled={preflightBusy || Boolean(anchorBlockers.full)} onClick={() => chooseMode('full')}>6 镜头完整验证</Button></div>
          {anchorBlockers[anchorMode] && <div className="rounded-md bg-amber-500/10 p-3 text-sm text-amber-100">insufficient_anchor_coverage：{anchorBlockers[anchorMode]?.message}</div>}
          <FirstFrameControls selectedCount={selected.length} busy={state.firstFrames.busy}
            failures={state.firstFrames.failures} message={state.firstFrames.message}
            disabled={!typedConfigs.image?.id || preflightBusy}
            onGenerate={generateFirstFrames} onRetry={retryFailedFirstFrames} />
          <AnchorShotSelector
            recommendations={anchors[anchorMode]}
            selected={selected}
            onChange={(ids) => saveSelection(ids)}
            onGenerate={generateSelected}
            onRegenerateFirstFrame={regenerateShotFirstFrame}
            regeneratingShotId={state.firstFrames.regeneratingShotId}
            busy={preflightBusy || Boolean(anchorBlockers[anchorMode]) || !selectedMode}
          />
        </div>}
        {qualityReports.length > 0 && <div className="space-y-2"><h4 className="text-sm font-medium text-white">关键镜头一致性证据</h4>{qualityReports.map((report) => <div key={report.artifact_id || report.shot_id} className="rounded-md bg-black/15 p-3"><div className="text-sm text-white">镜头 {report.shot_id} · {report.ready ? '证据通过' : '证据未齐'}</div><div className="mt-2 grid gap-1 sm:grid-cols-3">{QUALITY_DIMENSIONS.map((dimension) => { const item = report.dimensions?.[dimension]; return <div key={dimension} className="text-xs text-white/60">{qualityLabel[dimension]}：{item ? `${item.score}/${item.threshold} · ${item.status}` : '缺少证据'}</div>; })}</div></div>)}</div>}
        {(generationStatus === 'provider_pending' || generationStatus === 'provider_ready') && <div role="status" className="rounded-md border border-amber-400/20 bg-amber-500/5 p-3 text-sm text-amber-100">{nativeAudio ? '等待云端原生有声视频完成' : '等待云端视频与配音任务完成'}；工作台只轮询既有任务，不会重复提交模型。</div>}
        {generationStatus === 'failed' && <div role="alert" className="rounded-md border border-red-400/20 bg-red-500/5 p-3 text-sm text-red-100">{nativeAudio ? '关键镜头原生有声视频任务失败' : '关键镜头视频或配音源任务失败'}，系统未创建聚合媒体产物。</div>}
        {generationDeliveries?.length > 0 && <div className="space-y-2 rounded-md border border-emerald-400/20 bg-emerald-500/5 p-3"><div className="text-sm font-medium text-emerald-100">关键镜头成片</div>{generationDeliveries.map((item: any, index: number) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded bg-black/15 p-2 text-xs text-white/70"><span>成片 {index + 1} · {item.resolution || '竖屏'} · {item.duration_seconds || 0}s · {item.audio_verification_required ? <span className="text-amber-200">原生语音 · 字幕已烧录，实际语音待核验</span> : '音视频字幕已核验'}</span><span className="flex gap-2"><button className="text-cyan-300 hover:text-cyan-200" onClick={() => openDeliverable(item.id)}>播放/下载</button>{item.subtitle_track_id && <Link className="text-violet-300 hover:text-violet-200" href={`/subtitles?novel_id=${run.novel_id}`}>维护字幕</Link>}</span></div>)}</div>}
        {generationQuality?.some((item) => item.overall_readiness === 'trusted_multimodal_evaluation_required') && <div role="status" className="rounded-md border border-sky-400/20 bg-sky-500/5 p-3 text-sm text-sky-100">关键镜头视频已生成，待可信多模态评估；当前不会把未评估结果标记为通过或失败。</div>}
      </>}
    </section>
  );
}
