import { apiClient } from '@/lib/api-client';
import {
  DEFAULT_PRODUCTION_STRATEGY,
  getGenerationStrategyForProduction,
  getProductionStrategyCopy,
  GenerationStrategy,
  ProductionStrategy,
} from '@/lib/production-strategy';

export type EpisodePreviewStageStatus = 'pending' | 'running' | 'done' | 'failed' | 'waiting';

export type EpisodePreviewStageKey =
  | 'workflow'
  | 'script'
  | 'storyboard'
  | 'assistant'
  | 'contracts'
  | 'media'
  | 'concatenate'
  | 'preflight'
  | 'render';

export type EpisodePreviewStage = {
  key: EpisodePreviewStageKey;
  label: string;
  status: EpisodePreviewStageStatus;
  message: string;
};

export type EpisodePreviewStageUpdate = Partial<EpisodePreviewStage> & {
  key: EpisodePreviewStageKey;
};

export type EpisodePreviewProductionResult = {
  workflowId: string;
  novelId: string;
  chapterId: string;
  productionStrategy: ProductionStrategy;
  productionStrategyLabel: string;
  productionStrategyContract: string;
  requiresFinalLocks: boolean;
  allowsDraftGaps: boolean;
  scriptId?: string;
  storyboardId?: string;
  videoJobIds: string[];
  ttsJobIds: string[];
  mediaJobIds: string[];
  subtitleTrackIds: string[];
  readyForConcatenate?: boolean;
  pendingVideoJobIds?: string[];
  pendingTtsJobIds?: string[];
  cloudWaitTimedOut?: boolean;
  synthesisJobId?: string;
  outputUrl?: string;
  manifestUrl?: string;
  previewUrl?: string;
  srtUrl?: string;
  timelineUrl?: string;
  renderManifestUrl?: string;
  preflight?: any;
  render?: any;
};

export type EpisodePreviewAudioMode = 'model_audio' | 'none';

export const EPISODE_PREVIEW_STAGE_DEFS: EpisodePreviewStage[] = [
  { key: 'workflow', label: '工程链路', status: 'pending', message: '确认小说、章节和工作流' },
  { key: 'script', label: '剧本', status: 'pending', message: '选择或生成章节剧本' },
  { key: 'storyboard', label: '分镜镜头', status: 'pending', message: '选择或生成分镜和镜头' },
  { key: 'assistant', label: '制片检查', status: 'pending', message: '补齐安全生产缺口' },
  { key: 'contracts', label: '资产合约', status: 'pending', message: '锁定角色、场景、道具和字幕' },
  { key: 'media', label: '音视频草稿', status: 'pending', message: '按镜头批量生成音视频和字幕' },
  { key: 'concatenate', label: '连续成片', status: 'pending', message: '按镜头顺序生成成片清单' },
  { key: 'preflight', label: '渲染预检', status: 'pending', message: '检查字幕、时间线和媒体可用性' },
  { key: 'render', label: '渲染包', status: 'pending', message: '输出预览、SRT 和时间线文件' },
];

export function createInitialEpisodePreviewStages(): EpisodePreviewStage[] {
  return EPISODE_PREVIEW_STAGE_DEFS.map((stage) => ({ ...stage }));
}

function normalizeList<T = any>(data: any): T[] {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.data)) return data.data;
  return [];
}

function firstByUpdatedAt<T extends { updated_at?: string; created_at?: string }>(items: T[]): T | undefined {
  return [...items].sort((a, b) => {
    const left = new Date(a.updated_at || a.created_at || 0).getTime();
    const right = new Date(b.updated_at || b.created_at || 0).getTime();
    return right - left;
  })[0];
}

function issueMessage(preflight: any) {
  const issues = Array.isArray(preflight?.issues) ? preflight.issues : [];
  return issues
    .slice(0, 3)
    .map((issue: any) => issue.message || issue.detail || issue.code)
    .filter(Boolean)
    .join('；');
}

function getStrategyContractFlags(strategy: ProductionStrategy) {
  return {
    requiresFinalLocks: strategy === 'final_quality',
    allowsDraftGaps: strategy === 'draft_fast' || strategy === 'low_cost',
  };
}

function shouldRequireProviderMedia(strategy: ProductionStrategy, videoModelConfigId?: string) {
  return strategy === 'final_quality' || Boolean(videoModelConfigId);
}

const VIDEO_JOB_DONE_STATUSES = new Set(['succeeded', 'completed']);
const VIDEO_JOB_FAILED_STATUSES = new Set(['failed', 'cancelled', 'canceled', 'error']);
const DEFAULT_CLOUD_VIDEO_WAIT_MS = 12 * 60 * 1000;
const DEFAULT_CLOUD_VIDEO_POLL_MS = 15 * 1000;

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeStatus(value: unknown) {
  return String(value || '').trim().toLowerCase();
}

function jobErrorMessage(job: any) {
  return job?.error_message || job?.error || job?.detail || job?.message || job?.status || '未知错误';
}

async function mark(
  onStage: ((stage: EpisodePreviewStageUpdate) => void) | undefined,
  key: EpisodePreviewStageKey,
  status: EpisodePreviewStageStatus,
  message: string
) {
  onStage?.({ key, status, message });
}

async function refreshVideoJob(jobId: string) {
  try {
    return await apiClient.refreshVideoJob(jobId);
  } catch (error) {
    const current = await apiClient.getVideoJobStatus(jobId).catch(() => null);
    if (current) return current;
    throw error;
  }
}

async function waitForCloudVideoJobs(params: {
  jobIds: string[];
  onStage?: (stage: EpisodePreviewStageUpdate) => void;
  timeoutMs?: number;
  pollMs?: number;
}) {
  const jobIds = Array.from(new Set(params.jobIds.filter(Boolean)));
  if (jobIds.length === 0) return { completed: true, timedOut: false, pendingJobIds: [] as string[] };

  const timeoutAt = Date.now() + (params.timeoutMs || DEFAULT_CLOUD_VIDEO_WAIT_MS);
  const pollMs = params.pollMs || DEFAULT_CLOUD_VIDEO_POLL_MS;

  while (true) {
    const jobs = await Promise.all(jobIds.map((jobId) => refreshVideoJob(jobId)));
    const failed = jobs.find((job) => VIDEO_JOB_FAILED_STATUSES.has(normalizeStatus(job?.status)));
    if (failed) {
      const shortId = String(failed.id || failed.job_id || '').slice(0, 8) || '未知任务';
      throw new Error(`云端视频任务 ${shortId} 失败：${jobErrorMessage(failed)}`);
    }

    const pendingJobs = jobs.filter((job) => !VIDEO_JOB_DONE_STATUSES.has(normalizeStatus(job?.status)));
    if (pendingJobs.length === 0) {
      await mark(params.onStage, 'concatenate', 'running', '云端视频已完成，正在继续合成');
      return { completed: true, timedOut: false, pendingJobIds: [] as string[] };
    }

    const doneCount = jobs.length - pendingJobs.length;
    const pendingJobIds = pendingJobs.map((job) => String(job.id || job.job_id)).filter(Boolean);
    await mark(
      params.onStage,
      'concatenate',
      'waiting',
      `云端视频生成中 ${doneCount}/${jobs.length}，正在自动刷新任务状态`
    );

    if (Date.now() >= timeoutAt) {
      return { completed: false, timedOut: true, pendingJobIds };
    }

    await sleep(pollMs);
  }
}

async function waitForTtsJobsIfNeeded(params: {
  jobIds: string[];
  onStage?: (stage: EpisodePreviewStageUpdate) => void;
}) {
  const jobIds = Array.from(new Set(params.jobIds.filter(Boolean)));
  if (jobIds.length === 0) return { completed: true, pendingJobIds: [] as string[] };

  const jobs = await Promise.all(jobIds.map((jobId) => apiClient.getTTSJob(jobId)));
  const failed = jobs.find((job: any) => VIDEO_JOB_FAILED_STATUSES.has(normalizeStatus(job?.status)));
  if (failed) {
    const shortId = String(failed.id || '').slice(0, 8) || '未知任务';
    throw new Error(`TTS 任务 ${shortId} 失败：${jobErrorMessage(failed)}`);
  }
  const pendingJobs = jobs.filter((job: any) => !VIDEO_JOB_DONE_STATUSES.has(normalizeStatus(job?.status)));
  if (pendingJobs.length > 0) {
    await mark(params.onStage, 'concatenate', 'waiting', `仍有 ${pendingJobs.length} 个声音任务未完成，暂不合成`);
    return { completed: false, pendingJobIds: pendingJobs.map((job: any) => String(job.id)).filter(Boolean) };
  }
  return { completed: true, pendingJobIds: [] as string[] };
}

export async function resumeEpisodePreviewFromConcatenate(params: {
  workflowId: string;
  videoJobIds?: string[];
  mediaJobIds?: string[];
  ttsJobIds?: string[];
  title?: string;
  onStage?: (stage: EpisodePreviewStageUpdate) => void;
}) {
  const videoJobIds = params.videoJobIds || [];
  const mediaJobIds = params.mediaJobIds || [];
  const ttsJobIds = params.ttsJobIds || [];

  await mark(params.onStage, 'concatenate', 'running', '正在按分镜顺序编排连续成片清单');
  const sequence = await apiClient.concatenateVideos(params.workflowId, {
    video_job_ids: videoJobIds,
    media_job_ids: mediaJobIds,
    tts_job_ids: ttsJobIds,
    title: params.title || '本集预览草片',
    transition_style: 'cut',
    include_subtitles: true,
    subtitle_mode: 'dialogue',
    audio_mix_strategy: 'match_by_shot',
    quality_profile: 'review',
  });
  await mark(params.onStage, 'concatenate', 'done', `已编排 ${sequence.segment_count || 0} 个连续段落`);

  await mark(params.onStage, 'preflight', 'running', '正在执行渲染预检');
  const preflight = await apiClient.preflightWorkflowRender(params.workflowId, sequence.job_id, {
    use_editable_timeline: true,
  });
  if (!preflight.ready) {
    const message = issueMessage(preflight) || '渲染预检未通过，请先处理阻断项';
    await mark(params.onStage, 'preflight', 'failed', message);
    throw new Error(message);
  }
  await mark(params.onStage, 'preflight', 'done', '渲染预检已通过');

  await mark(params.onStage, 'render', 'running', '正在生成本地预览、字幕和时间线包');
  const render = await apiClient.renderWorkflowPackage(params.workflowId, {
    synthesis_job_id: sequence.job_id,
    force: true,
    quality_profile: 'review',
    render_backend: 'local_artifact_package',
    burn_subtitles: false,
    use_editable_timeline: true,
  });
  if (render.status === 'preflight_failed') {
    const message = issueMessage(render) || render.message || '渲染包生成前预检失败';
    await mark(params.onStage, 'render', 'failed', message);
    throw new Error(message);
  }
  await mark(params.onStage, 'render', 'done', render.message || '本集草片渲染包已生成');

  return {
    synthesisJobId: sequence.job_id,
    outputUrl: sequence.output_url,
    manifestUrl: sequence.manifest_url,
    previewUrl: render.preview_url,
    srtUrl: render.srt_url,
    timelineUrl: render.timeline_url,
    renderManifestUrl: render.render_manifest_url,
    preflight,
    render,
  };
}

export async function runEpisodePreviewProduction(params: {
  workflowId: string;
  novelId?: string;
  chapterId?: string;
  scriptId?: string;
  storyboardId?: string;
  shotIds?: string[];
  title?: string;
  textModelConfigId?: string;
  videoModelConfigId?: string;
  audioModelConfigId?: string;
  audioMode?: EpisodePreviewAudioMode;
  productionStrategy?: ProductionStrategy;
  generationStrategy?: GenerationStrategy;
  onStage?: (stage: EpisodePreviewStageUpdate) => void;
}): Promise<EpisodePreviewProductionResult> {
  const { workflowId, onStage } = params;
  if (!workflowId) throw new Error('缺少工作流，无法生成本集草片');

  await mark(onStage, 'workflow', 'running', '正在读取工作流链路');
  const status = await apiClient.getWorkflowStatus(workflowId);
  const novelId = params.novelId || status.novel_id;
  const chapterId = params.chapterId || status.chapter_id;
  if (!novelId || !chapterId) {
    await mark(onStage, 'workflow', 'failed', '请先选择小说和章节');
    throw new Error('请先选择小说和章节，再生成本集草片');
  }
  await mark(onStage, 'workflow', 'done', '已绑定小说、章节和工作流');

  let scriptId = params.scriptId || status.script_id;
  let storyboardId = params.storyboardId || status.storyboard_id;

  await mark(onStage, 'script', 'running', '正在确认章节剧本');
  if (!scriptId) {
    const scripts = normalizeList<any>(await apiClient.getScripts({ novel_id: novelId, chapter_id: chapterId, page_size: 20 }));
    const existingScript = firstByUpdatedAt(scripts);
    if (existingScript?.id) {
      scriptId = existingScript.id;
      await mark(onStage, 'script', 'done', '已复用当前章节已有剧本');
    } else {
      await mark(onStage, 'script', 'done', '暂无现成剧本，将由智能分镜基于章节创建草稿脚本');
    }
  } else {
    await mark(onStage, 'script', 'done', '已绑定工作流剧本');
  }

  await mark(onStage, 'storyboard', 'running', '正在确认分镜和镜头');
  if (!storyboardId) {
    const storyboards = normalizeList<any>(
      scriptId
        ? await apiClient.getStoryboards(scriptId)
        : await apiClient.getStoryboards({ novel_id: novelId, chapter_id: chapterId })
    ).filter((storyboard: any) => {
      const boardChapterId = storyboard.chapter_id || storyboard.content?.chapter_id;
      return !boardChapterId || boardChapterId === chapterId;
    });
    const existingStoryboard = firstByUpdatedAt(storyboards);
    if (existingStoryboard?.id) {
      storyboardId = existingStoryboard.id;
      scriptId = existingStoryboard.script_id || scriptId;
      await mark(onStage, 'storyboard', 'done', '已复用当前章节已有分镜');
    } else {
      const generated = await apiClient.generateSmartStoryboard({
        novel_id: novelId,
        chapter_id: chapterId,
        style: 'anime',
        use_ai_refine: true,
        model_config_id: params.textModelConfigId || undefined,
      });
      storyboardId = generated.id;
      scriptId = generated.script_id || scriptId;
      await mark(onStage, 'storyboard', 'done', `已生成 ${generated.shot_count || generated.shots?.length || 0} 个分镜镜头`);
    }
  } else {
    await mark(onStage, 'storyboard', 'done', '已绑定工作流分镜');
  }

  await apiClient.updateWorkflowStep(workflowId, {
    current_step: 6,
    completed_steps: [1, 2, 3, 4, 5, 6],
    novel_id: novelId,
    chapter_id: chapterId,
    script_id: scriptId || '',
    storyboard_id: storyboardId || '',
  });

  let selectedShotIds = params.shotIds?.map((shotId) => String(shotId || '').trim()).filter(Boolean);
  if (selectedShotIds?.length) {
    if (!storyboardId) {
      await mark(onStage, 'storyboard', 'failed', '所选镜头缺少当前分镜上下文');
      throw new Error('所选镜头缺少当前分镜上下文，请重新选择工作流和分镜');
    }
    const storyboardShots = normalizeList<any>(await apiClient.getShots(storyboardId));
    const validShotIds = new Set(storyboardShots.map((shot: any) => shot.id).filter(Boolean));
    const filteredShotIds = selectedShotIds.filter((shotId) => validShotIds.has(shotId));
    if (filteredShotIds.length === 0) {
      await mark(onStage, 'storyboard', 'failed', '所选镜头不属于当前分镜');
      throw new Error('所选镜头不属于当前分镜，请重新加载并选择当前分镜下的关键镜头');
    }
    if (filteredShotIds.length !== selectedShotIds.length) {
      await mark(onStage, 'storyboard', 'done', `已忽略 ${selectedShotIds.length - filteredShotIds.length} 个过期镜头选择`);
    }
    selectedShotIds = filteredShotIds;
  }

  await mark(onStage, 'assistant', 'running', '正在执行 AI 制片安全补齐');
  await apiClient.runProducerAssistant(workflowId, { auto_fix: true });
  await mark(onStage, 'assistant', 'done', '制片检查和安全补齐已完成');

  const productionStrategy = params.productionStrategy || DEFAULT_PRODUCTION_STRATEGY;
  const strategy = params.generationStrategy || getGenerationStrategyForProduction(productionStrategy);
  const audioMode = params.audioMode || 'model_audio';
  const strategyCopy = getProductionStrategyCopy(productionStrategy);
  const strategyContract = getStrategyContractFlags(productionStrategy);
  const requiresProviderMedia = shouldRequireProviderMedia(productionStrategy, params.videoModelConfigId);

  await mark(
    onStage,
    'contracts',
    'running',
    strategyContract.requiresFinalLocks
      ? '正在应用终稿资产锁、声线锁和镜头生产合约'
      : '正在应用资产锁和镜头生产合约，并保留草稿缺口提示'
  );
  await apiClient.applyWorkflowAssetLocks(workflowId, { create_missing_assets: true, persist: true });
  await apiClient.refreshWorkflowShortVideoContracts(workflowId);
  await mark(
    onStage,
    'contracts',
    'done',
    strategyContract.requiresFinalLocks
      ? '终稿所需人物、场景、道具、声线、字幕和模型路线已锁定'
      : '草稿生产合约已应用；未锁定资产/声线缺口会随结果保留'
  );
  await mark(
    onStage,
    'media',
    'running',
    audioMode === 'none'
      ? `正在按「${strategyCopy.label}」生成无配音视频和字幕；可稍后补配音`
      : strategy === 'separate_video_tts'
      ? requiresProviderMedia
        ? `正在按「${strategyCopy.label}」分别调用视频模型和声音模型；${strategyCopy.contractHint}`
        : `正在按「${strategyCopy.label}」生成本地可审阅草片；未选择真实视频配置时允许 DEV_MODE 占位，终稿仍需补齐模型配置。`
      : `正在按「${strategyCopy.label}」调用直生音视频模型；${strategyCopy.contractHint}`
  );
  const mediaBatch = await apiClient.generateWorkflowMediaBatch(workflowId, {
    production_strategy: productionStrategy,
    strategy,
    shot_ids: selectedShotIds && selectedShotIds.length > 0 ? selectedShotIds : undefined,
    resolution: '720p',
    subtitle_mode: 'shot_dialogue',
    audio_mode: audioMode,
    model_config_id: params.videoModelConfigId || undefined,
    audio_model_config_id: audioMode === 'none' ? undefined : params.audioModelConfigId || undefined,
    require_real_video: requiresProviderMedia,
    require_provider_reference_image: requiresProviderMedia,
  });
  const videoJobIds = mediaBatch.video_job_ids || [];
  const ttsJobIds = mediaBatch.tts_job_ids || [];
  const mediaJobIds = mediaBatch.media_job_ids || [];
  const subtitleTrackIds = mediaBatch.subtitle_track_ids || [];
  const pendingVideoJobIds = mediaBatch.pending_video_job_ids || [];
  const pendingTtsJobIds = mediaBatch.pending_tts_job_ids || [];
  if (mediaBatch.ready_for_concatenate === false) {
    const message = `已提交 ${videoJobIds.length} 个视频任务、${ttsJobIds.length} 个声音任务；正在等待云端生成完成`;
    await mark(onStage, 'media', 'done', message);
    const videoWait = await waitForCloudVideoJobs({ jobIds: pendingVideoJobIds, onStage });
    const ttsWait = await waitForTtsJobsIfNeeded({ jobIds: pendingTtsJobIds, onStage });
    if (!videoWait.completed || !ttsWait.completed) {
      const remainingVideoJobIds = videoWait.pendingJobIds;
      const remainingTtsJobIds = ttsWait.pendingJobIds;
      await mark(
        onStage,
        'concatenate',
        'waiting',
        videoWait.timedOut
          ? '云端视频仍未完成，已保留任务 ID，稍后可回到工作台继续合成'
          : '视频/声音仍在云端生成中；完成后可回到工作台继续合成'
      );
      return {
        workflowId,
        novelId,
        chapterId,
        productionStrategy,
        productionStrategyLabel: strategyCopy.label,
        productionStrategyContract: strategyCopy.contractHint,
        ...strategyContract,
        scriptId,
        storyboardId,
        videoJobIds,
        ttsJobIds,
        mediaJobIds,
        subtitleTrackIds,
        readyForConcatenate: false,
        pendingVideoJobIds: remainingVideoJobIds,
        pendingTtsJobIds: remainingTtsJobIds,
        cloudWaitTimedOut: videoWait.timedOut,
      };
    }

    await mark(onStage, 'media', 'done', '云端视频和配音任务已完成，可继续合成');
    const resumed = await resumeEpisodePreviewFromConcatenate({
      workflowId,
      videoJobIds,
      mediaJobIds,
      ttsJobIds,
      title: params.title || '本集预览草片',
      onStage,
    });

    return {
      workflowId,
      novelId,
      chapterId,
      productionStrategy,
      productionStrategyLabel: strategyCopy.label,
      productionStrategyContract: strategyCopy.contractHint,
      ...strategyContract,
      scriptId,
      storyboardId,
      videoJobIds,
      ttsJobIds,
      mediaJobIds,
      subtitleTrackIds,
      readyForConcatenate: true,
      pendingVideoJobIds: [],
      pendingTtsJobIds: [],
      synthesisJobId: resumed.synthesisJobId,
      outputUrl: resumed.outputUrl,
      manifestUrl: resumed.manifestUrl,
      previewUrl: resumed.previewUrl,
      srtUrl: resumed.srtUrl,
      timelineUrl: resumed.timelineUrl,
      renderManifestUrl: resumed.renderManifestUrl,
      preflight: resumed.preflight,
      render: resumed.render,
    };
  }
  await mark(
    onStage,
    'media',
    'done',
    audioMode === 'none'
      ? `已创建 ${videoJobIds.length || mediaJobIds.length} 个无配音视频任务和 ${subtitleTrackIds.length} 条字幕轨`
      : strategy === 'separate_video_tts'
      ? `已创建 ${videoJobIds.length} 个视频任务、${ttsJobIds.length} 个声音任务和 ${subtitleTrackIds.length} 条字幕轨`
      : `已创建 ${mediaJobIds.length} 个直生音视频任务和 ${subtitleTrackIds.length} 条字幕轨`
  );

  const resumed = await resumeEpisodePreviewFromConcatenate({
    workflowId,
    videoJobIds,
    mediaJobIds,
    ttsJobIds,
    title: params.title || '本集预览草片',
    onStage,
  });

  return {
    workflowId,
    novelId,
    chapterId,
    productionStrategy,
    productionStrategyLabel: strategyCopy.label,
    productionStrategyContract: strategyCopy.contractHint,
    ...strategyContract,
    scriptId,
    storyboardId,
    videoJobIds,
    ttsJobIds,
    mediaJobIds,
    subtitleTrackIds,
    readyForConcatenate: true,
    pendingVideoJobIds,
    pendingTtsJobIds,
    synthesisJobId: resumed.synthesisJobId,
    outputUrl: resumed.outputUrl,
    manifestUrl: resumed.manifestUrl,
    previewUrl: resumed.previewUrl,
    srtUrl: resumed.srtUrl,
    timelineUrl: resumed.timelineUrl,
    renderManifestUrl: resumed.renderManifestUrl,
    preflight: resumed.preflight,
    render: resumed.render,
  };
}
