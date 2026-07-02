'use client';

import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { NextStepGuide } from '@/components/production/next-step-guide';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { MainLayout } from '@/components/layout/main-layout';
import { ModelCapabilitySelector } from '@/components/model-capability-selector';
import apiClient from '@/lib/api-client';
import { runEpisodePreviewProduction } from '@/lib/episode-preview-production';
import {
  getDefaultConfigForCapability,
  SavedModelConfig,
} from '@/lib/model-configs';
import {
  DEFAULT_PRODUCTION_STRATEGY,
  getProductionStrategyCopy,
  ProductionStrategy,
  PRODUCTION_STRATEGY_OPTIONS,
} from '@/lib/production-strategy';
import {
  BookOpen,
  Captions,
  ChevronDown,
  CheckCircle,
  Clapperboard,
  Download,
  FileText,
  Film,
  Loader2,
  PlayCircle,
  Route,
  Save,
  Sparkles,
  Wand2,
} from 'lucide-react';

type QuickStartResult = {
  novelId: string;
  chapterId: string;
  storyBibleId?: string;
  scriptId: string;
  storyboardId: string;
  workflowId: string;
  shotCount: number;
  videoJobIds?: string[];
  ttsJobIds?: string[];
  mediaJobIds?: string[];
  subtitleTrackIds?: string[];
  readyForConcatenate?: boolean;
  pendingVideoJobIds?: string[];
  pendingTtsJobIds?: string[];
  synthesisJobId?: string;
  outputUrl?: string;
  manifestUrl?: string;
  previewUrl?: string;
  srtUrl?: string;
  timelineUrl?: string;
  renderManifestUrl?: string;
  autoProduced?: boolean;
};

type ProgressStatus = 'pending' | 'running' | 'done' | 'failed' | 'stopped' | 'waiting';

type QuickStartProgressStep = {
  id: string;
  label: string;
  status: ProgressStatus;
  detail?: string;
  updatedAt?: string;
};

type QuickStartIssue = {
  stepId: string;
  stepLabel: string;
  summary: string;
  rawMessage: string;
  cause: string;
  advice: string[];
  canSkipAudio: boolean;
  canRetryProduction: boolean;
};

const genreOptions = [
  { value: 'fantasy', label: '奇幻冒险' },
  { value: 'suspense', label: '悬疑揭示' },
  { value: 'urban', label: '都市异能' },
  { value: 'romance', label: '恋爱日常' },
  { value: 'xianxia', label: '国风仙侠' },
  { value: 'sci-fi', label: '机甲科幻' },
];

const styleOptions = [
  { value: 'anime', label: '动画电影' },
  { value: 'comic', label: '漫画分格' },
  { value: 'ink', label: '国风水墨' },
  { value: 'cyberpunk', label: '赛博霓虹' },
];

const sampleStory = {
  title: '星灯邮差',
  premise:
    '十二岁的林澈在山城旧邮局发现一盏会说话的星灯。星灯告诉他，夜空中有一列只在雨后出现的云上列车，列车会把遗失的愿望送回主人身边。林澈决定成为临时邮差，帮沉默的转学生安禾找回她写给妈妈却从未寄出的信。',
  chapterTitle: '第一章 雨后的旧邮局',
  chapterContent:
    '暴雨停下时，山城的石阶像被星光洗过一样发亮。林澈抱着被雨打湿的书包，躲进街角那间早已停业的旧邮局。柜台后面忽然亮起一盏蓝色小灯，灯芯里传来细小的声音：“第七百二十一任邮差，你终于来了。”林澈吓得后退一步，却看见灯光照出一封没有地址的银色信封。信封上写着安禾的名字。窗外，一声悠长的汽笛从云层深处传来。',
};

const QUICK_START_DRAFT_KEY = 'ai-video-platform:quick-start-draft';
const QUICK_START_RUN_KEY = 'ai-video-platform:quick-start-last-run';
const API_ORIGIN = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1').replace(/\/api\/v1\/?$/, '');

const toMediaUrl = (url?: string) => {
  if (!url) return '';
  return url.startsWith('/') ? `${API_ORIGIN}${url}` : url;
};

const buildProgressSteps = (createStoryBible: boolean, autoProducePreview: boolean): QuickStartProgressStep[] => [
  { id: 'novel', label: '创建作品', status: 'pending' },
  { id: 'chapter', label: '创建首章', status: 'pending' },
  ...(createStoryBible ? [{ id: 'story_bible', label: '生成动漫设定本', status: 'pending' as ProgressStatus }] : []),
  { id: 'storyboard', label: '智能生成剧本与分镜', status: 'pending' },
  { id: 'workflow', label: '创建首集工作流', status: 'pending' },
  ...(autoProducePreview
    ? [
        { id: 'contracts', label: '刷新镜头生产合约', status: 'pending' as ProgressStatus },
        { id: 'media', label: '批量生成音视频草稿', status: 'pending' as ProgressStatus },
        { id: 'concatenate', label: '编排连续成片', status: 'pending' as ProgressStatus },
        { id: 'preflight', label: '渲染预检', status: 'pending' as ProgressStatus },
        { id: 'render', label: '生成本地预览包与字幕', status: 'pending' as ProgressStatus },
      ]
    : []),
];

const progressBadgeVariant = (status: ProgressStatus) => {
  if (status === 'done') return 'success';
  if (status === 'failed') return 'danger';
  if (status === 'running') return 'warning';
  if (status === 'waiting') return 'warning';
  if (status === 'stopped') return 'outline';
  return 'outline';
};

const progressStatusText = (status: ProgressStatus) => {
  if (status === 'done') return '完成';
  if (status === 'failed') return '失败';
  if (status === 'running') return '执行中';
  if (status === 'waiting') return '等待云端';
  if (status === 'stopped') return '已停止';
  return '等待';
};

const stageToStep: Record<string, string> = {
  workflow: 'workflow',
  script: 'storyboard',
  storyboard: 'storyboard',
  assistant: 'contracts',
  contracts: 'contracts',
  media: 'media',
  concatenate: 'concatenate',
  preflight: 'preflight',
  render: 'render',
};

const stringifyDetail = (detail: any): string => {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (typeof detail?.message === 'string') return detail.message;
  try {
    return JSON.stringify(detail, null, 2);
  } catch {
    return String(detail);
  }
};

const buildIssue = (
  err: any,
  stepId: string,
  stepLabel: string,
  canSkipAudio: boolean,
  canRetryProduction = canSkipAudio
): QuickStartIssue => {
  const detail = stringifyDetail(err?.detail);
  const rawMessage = [err?.message, detail].filter(Boolean).join('\n\n') || '极速向导执行失败';
  const normalized = rawMessage.toLowerCase();
  const isVoiceMissing = normalized.includes('voice id not exist') || rawMessage.includes('[2054]');

  if (isVoiceMissing) {
    return {
      stepId,
      stepLabel,
      summary: '配音音色不可用，已暂停在音视频草稿阶段',
      rawMessage,
      cause: '当前角色声线或默认 TTS 音色在 MiniMax 账号下不存在，可能是 voice_id 写错、音色未开通，或使用了其他服务商的音色 ID。',
      advice: [
        '去模型与密钥中检查当前 TTS 配置，确认 MiniMax API Key、模型和音色 ID 已开通。',
        '去 TTS 工作台试听同一个音色；如果试听失败，先换成已验证音色。',
        '也可以先跳过配音继续生成无声视频和字幕，后续再补角色声音。',
      ],
      canSkipAudio,
      canRetryProduction,
    };
  }

  return {
    stepId,
    stepLabel,
    summary: `${stepLabel}失败，已保留已创建内容`,
    rawMessage,
    cause: '当前步骤调用外部模型或后端生产接口失败；作品、章节、分镜和工作流会继续保留。',
    advice: [
      '先进入连续动漫工作台查看已创建的镜头和生产状态。',
      '如果是模型配置或密钥问题，去模型与密钥页面重新验证后再继续。',
      '如果只是配音失败，可以跳过配音先生成无声视频和字幕。',
    ],
    canSkipAudio,
    canRetryProduction,
  };
};

const compactIds = (ids?: string[]) => {
  if (!ids?.length) return '';
  return ids.slice(0, 3).join('、') + (ids.length > 3 ? ` 等 ${ids.length} 个` : '');
};

export default function QuickStartPage() {
  const [form, setForm] = useState({
    title: '',
    premise: '',
    genre: 'fantasy',
    style: 'anime',
    chapterTitle: '第一章',
    chapterContent: '',
    shotCount: 4,
    createStoryBible: true,
    autoProducePreview: true,
  });
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issue, setIssue] = useState<QuickStartIssue | null>(null);
  const [result, setResult] = useState<QuickStartResult | null>(null);
  const [draftReady, setDraftReady] = useState(false);
  const [draftSavedAt, setDraftSavedAt] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [restoredRunAt, setRestoredRunAt] = useState<string | null>(null);
  const [modelConfigs, setModelConfigs] = useState<SavedModelConfig[]>([]);
  const [textModelConfigId, setTextModelConfigId] = useState('');
  const [videoModelConfigId, setVideoModelConfigId] = useState('');
  const [audioModelConfigId, setAudioModelConfigId] = useState('');
  const [productionStrategy, setProductionStrategy] = useState<ProductionStrategy>(DEFAULT_PRODUCTION_STRATEGY);
  const [progressSteps, setProgressSteps] = useState<QuickStartProgressStep[]>([]);
  const [expandedStepIds, setExpandedStepIds] = useState<string[]>([]);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const activeRunIdRef = useRef(0);
  const runStateReadyRef = useRef(false);

  const checks = useMemo(() => {
    const content = form.chapterContent.trim() || form.premise.trim();
    return [
      { label: '作品名', ok: form.title.trim().length > 0 },
      { label: '故事梗概', ok: form.premise.trim().length >= 8 },
      { label: '章节内容', ok: content.length >= 8 },
      { label: '镜头数', ok: form.shotCount >= 1 && form.shotCount <= 12 },
    ];
  }, [form]);

  const isReady = checks.every((item) => item.ok);
  const productionStrategyCopy = useMemo(() => getProductionStrategyCopy(productionStrategy), [productionStrategy]);

  const toggleStepDetails = (stepId: string) => {
    setExpandedStepIds((current) => (
      current.includes(stepId) ? current.filter((id) => id !== stepId) : [...current, stepId]
    ));
  };

  const stepDetails = (step: QuickStartProgressStep) => {
    const details = [
      { label: '环节状态', value: progressStatusText(step.status) },
      { label: '最近更新', value: step.updatedAt ? new Date(step.updatedAt).toLocaleString() : '尚未开始' },
      { label: '当前说明', value: step.detail || '等待上游环节完成' },
    ];
    if (!result) return details;

    const idMap: Record<string, Array<{ label: string; value?: string | number }>> = {
      novel: [{ label: '作品 ID', value: result.novelId }],
      chapter: [{ label: '章节 ID', value: result.chapterId }],
      story_bible: [{ label: '设定本 ID', value: result.storyBibleId || '未生成或未启用' }],
      storyboard: [
        { label: '脚本 ID', value: result.scriptId },
        { label: '分镜 ID', value: result.storyboardId },
        { label: '镜头数', value: result.shotCount },
      ],
      workflow: [{ label: '工作流 ID', value: result.workflowId }],
      contracts: [
        { label: '生产策略', value: productionStrategyCopy.label },
        { label: '策略说明', value: productionStrategyCopy.contractHint },
      ],
      media: [
        { label: '视频任务', value: result.videoJobIds?.length || 0 },
        { label: 'TTS 任务', value: result.ttsJobIds?.length || 0 },
        { label: '直生音视频任务', value: result.mediaJobIds?.length || 0 },
        { label: '字幕轨', value: result.subtitleTrackIds?.length || 0 },
        { label: '视频任务 ID', value: compactIds(result.videoJobIds) || compactIds(result.mediaJobIds) || '暂无' },
        { label: 'TTS 任务 ID', value: compactIds(result.ttsJobIds) || '暂无' },
        { label: '待完成视频', value: result.pendingVideoJobIds?.length || 0 },
        { label: '待完成 TTS', value: result.pendingTtsJobIds?.length || 0 },
        { label: '待完成视频 ID', value: compactIds(result.pendingVideoJobIds) || '暂无' },
        { label: '待完成 TTS ID', value: compactIds(result.pendingTtsJobIds) || '暂无' },
      ],
      concatenate: [
        { label: '合成任务 ID', value: result.synthesisJobId || '暂无' },
        { label: '是否可合成', value: result.readyForConcatenate === false ? '等待视频/声音任务完成' : '可继续合成' },
      ],
      preflight: [
        { label: '预览包', value: result.previewUrl || '暂无' },
        { label: '字幕文件', value: result.srtUrl || '暂无' },
      ],
      render: [
        { label: '预览包', value: result.previewUrl || '暂无' },
        { label: '时间线', value: result.timelineUrl || '暂无' },
        { label: '渲染清单', value: result.renderManifestUrl || '暂无' },
      ],
    };
    return [...details, ...(idMap[step.id] || [])].filter((item) => item.value !== undefined && item.value !== '');
  };

  useEffect(() => {
    loadModelConfigs();
    try {
      const saved = localStorage.getItem(QUICK_START_DRAFT_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed?.form) {
          setForm((current) => ({ ...current, ...parsed.form }));
          setDraftSavedAt(parsed.savedAt || null);
        }
      }
    } catch {
      localStorage.removeItem(QUICK_START_DRAFT_KEY);
    }
    try {
      const savedRun = localStorage.getItem(QUICK_START_RUN_KEY);
      if (savedRun) {
        const parsed = JSON.parse(savedRun);
        if (Array.isArray(parsed?.progressSteps)) {
          setProgressSteps(parsed.progressSteps.map((step: QuickStartProgressStep) => (
            step.status === 'running'
              ? { ...step, status: 'stopped', detail: step.detail || '页面刷新后已停止等待，可从这里继续处理。' }
              : step
          )));
        }
        if (parsed?.result) setResult(parsed.result);
        if (parsed?.issue) setIssue(parsed.issue);
        if (parsed?.error) setError(parsed.error);
        if (parsed?.productionStrategy) setProductionStrategy(parsed.productionStrategy);
        if (parsed?.savedAt) setRestoredRunAt(parsed.savedAt);
      }
    } catch {
      localStorage.removeItem(QUICK_START_RUN_KEY);
    } finally {
      setDraftReady(true);
      runStateReadyRef.current = true;
    }
  }, []);

  useEffect(() => {
    if (!runStateReadyRef.current) return;
    const hasRunState = progressSteps.length > 0 || result || issue || error;
    if (!hasRunState) {
      localStorage.removeItem(QUICK_START_RUN_KEY);
      return;
    }
    localStorage.setItem(QUICK_START_RUN_KEY, JSON.stringify({
      progressSteps,
      result,
      issue,
      error,
      productionStrategy,
      savedAt: new Date().toISOString(),
    }));
  }, [progressSteps, result, issue, error, productionStrategy]);

  const loadModelConfigs = async () => {
    try {
      const configs = await apiClient.getLLMConfigs();
      const list = Array.isArray(configs) ? configs : [];
      setModelConfigs(list);
      const textDefault = getDefaultConfigForCapability(list, 'text');
      const videoDefault = getDefaultConfigForCapability(list, 'video');
      const audioDefault = getDefaultConfigForCapability(list, 'audio');
      if (textDefault) setTextModelConfigId(textDefault.id);
      if (videoDefault) setVideoModelConfigId(videoDefault.id);
      if (audioDefault) setAudioModelConfigId(audioDefault.id);
    } catch {
      setModelConfigs([]);
    }
  };

  useEffect(() => {
    if (!draftReady) return;
    const timer = window.setTimeout(() => {
      saveDraft(false);
    }, 400);
    return () => window.clearTimeout(timer);
  }, [form, draftReady]);

  const saveDraft = (showMessage = true) => {
    const savedAt = new Date().toISOString();
    localStorage.setItem(QUICK_START_DRAFT_KEY, JSON.stringify({ form, savedAt }));
    setDraftSavedAt(savedAt);
    if (showMessage) {
      setError(null);
      setSaveMessage(`草稿已保存：${new Date(savedAt).toLocaleString()}`);
      window.setTimeout(() => setSaveMessage(null), 3000);
    }
  };

  const fillSampleStory = () => {
    setForm((current) => ({
      ...current,
      ...sampleStory,
      genre: 'fantasy',
      style: 'anime',
      shotCount: 4,
      createStoryBible: true,
      autoProducePreview: true,
    }));
    setError(null);
    setIssue(null);
  };

  const updateProgressStep = (id: string, status: ProgressStatus, detail?: string) => {
    setProgressSteps((current) => current.map((step) => (
      step.id === id ? { ...step, status, detail, updatedAt: new Date().toISOString() } : step
    )));
  };

  const applyPreviewResult = (base: QuickStartResult, preview: Awaited<ReturnType<typeof runEpisodePreviewProduction>>): QuickStartResult => ({
    ...base,
    scriptId: preview.scriptId || base.scriptId,
    storyboardId: preview.storyboardId || base.storyboardId,
    videoJobIds: preview.videoJobIds || [],
    ttsJobIds: preview.ttsJobIds || [],
    mediaJobIds: preview.mediaJobIds || [],
    subtitleTrackIds: preview.subtitleTrackIds || [],
    readyForConcatenate: preview.readyForConcatenate,
    pendingVideoJobIds: preview.pendingVideoJobIds || [],
    pendingTtsJobIds: preview.pendingTtsJobIds || [],
    synthesisJobId: preview.synthesisJobId,
    outputUrl: preview.outputUrl,
    manifestUrl: preview.manifestUrl,
    previewUrl: preview.previewUrl,
    srtUrl: preview.srtUrl,
    timelineUrl: preview.timelineUrl,
    renderManifestUrl: preview.renderManifestUrl,
    autoProduced: preview.readyForConcatenate !== false && Boolean(preview.previewUrl || preview.renderManifestUrl),
  });

  const runPreviewProductionFromResult = async (audioMode: 'model_audio' | 'none') => {
    if (!result?.workflowId) return;
    const runId = activeRunIdRef.current + 1;
    activeRunIdRef.current = runId;
    setIsRunning(true);
    setError(null);
    setIssue(null);
    setRestoredRunAt(null);
    updateProgressStep(
      'media',
      'running',
      audioMode === 'none' ? '正在跳过配音，继续生成无声视频和字幕' : '正在重新执行首集生产阶段'
    );
    updateProgressStep('concatenate', 'pending');
    updateProgressStep('preflight', 'pending');
    updateProgressStep('render', 'pending');

    try {
      const preview = await runEpisodePreviewProduction({
        workflowId: result.workflowId,
        novelId: result.novelId,
        chapterId: result.chapterId,
        scriptId: result.scriptId,
        storyboardId: result.storyboardId,
        title: `${form.title.trim() || '首集'} 无配音预览`,
        textModelConfigId: textModelConfigId || undefined,
        videoModelConfigId: videoModelConfigId || undefined,
        audioModelConfigId: audioMode === 'none' ? undefined : audioModelConfigId || undefined,
        productionStrategy,
        audioMode,
        onStage: (stage) => {
          if (activeRunIdRef.current !== runId) return;
          const stepId = stageToStep[stage.key];
          if (stepId && stage.status) {
            updateProgressStep(stepId, stage.status, stage.message);
          }
        },
      });
      if (activeRunIdRef.current !== runId) return;
      setResult(applyPreviewResult(result, preview));
    } catch (err: any) {
      if (activeRunIdRef.current !== runId) return;
      const message = err?.message || '跳过配音继续生成失败';
      updateProgressStep('media', 'failed', message);
      setError(message);
      setIssue(buildIssue(err, 'media', '批量生成音视频草稿', audioMode !== 'none'));
    } finally {
      if (activeRunIdRef.current === runId) {
        setIsRunning(false);
      }
    }
  };

  const continueWithoutAudio = () => runPreviewProductionFromResult('none');

  const retryProductionStage = () => {
    if (result?.workflowId) {
      runPreviewProductionFromResult('model_audio');
      return;
    }
    runQuickStart();
  };

  const stopCurrentRun = () => {
    activeRunIdRef.current += 1;
    setIsRunning(false);
    setRestoredRunAt(null);
    setProgressSteps((current) => current.map((step) => (
      step.status === 'running'
        ? { ...step, status: 'stopped', detail: '已停止等待；已创建内容会保留，可稍后进入工作台或重试。', updatedAt: new Date().toISOString() }
        : step
    )));
    setIssue((current) => current || {
      stepId: 'workflow',
      stepLabel: '已停止等待',
      summary: '已停止当前等待，保留已创建内容',
      rawMessage: '前端已停止继续等待当前向导流程。已经发出的后端或云端任务不会被强制取消，可在工作台继续查看状态。',
      cause: '用户主动停止等待。',
      advice: ['进入工作台查看已创建内容和任务状态。', '确认模型配置后，可重新执行生产阶段。'],
      canSkipAudio: Boolean(result?.workflowId),
      canRetryProduction: Boolean(result?.workflowId),
    });
  };

  const runQuickStart = async () => {
    if (!isReady) {
      const missing = checks.filter((item) => !item.ok).map((item) => item.label).join('、');
      setError(`请先补齐：${missing}`);
      return;
    }

    setIsRunning(true);
    const runId = activeRunIdRef.current + 1;
    activeRunIdRef.current = runId;
    setError(null);
    setIssue(null);
    setResult(null);
    setRestoredRunAt(null);
    setExpandedStepIds([]);
    const initialSteps = buildProgressSteps(form.createStoryBible, form.autoProducePreview);
    setProgressSteps(initialSteps);
    let activeStepId = '';
    let partialResult: QuickStartResult | null = null;

    const markStep = (id: string, status: ProgressStatus, detail?: string) => {
      if (activeRunIdRef.current !== runId) return;
      activeStepId = status === 'running' ? id : activeStepId;
      setProgressSteps((current) => {
        const source = current.length > 0 ? current : initialSteps;
        return source.map((step) => (
          step.id === id ? { ...step, status, detail, updatedAt: new Date().toISOString() } : step
        ));
      });
    };
    const ensureActive = () => {
      if (activeRunIdRef.current !== runId) {
        throw new Error('当前向导已停止等待');
      }
    };

    try {
      const title = form.title.trim();
      const premise = form.premise.trim();
      const chapterContent = form.chapterContent.trim() || premise;

      markStep('novel', 'running', '正在保存作品基础信息');
      const novel = await apiClient.createNovel({
        title,
        description: premise,
        genre: form.genre,
        style: form.style,
        status: 'writing',
      });
      ensureActive();
      markStep('novel', 'done', '作品已保存');

      markStep('chapter', 'running', '正在保存首章正文');
      const chapter = await apiClient.createChapter({
        novel_id: novel.id,
        title: form.chapterTitle.trim() || '第一章',
        chapter_number: 1,
        content: chapterContent,
      });
      ensureActive();
      markStep('chapter', 'done', '首章已保存');

      let storyBibleId: string | undefined;
      if (form.createStoryBible) {
        markStep('story_bible', 'running', '正在提取故事设定、人物和世界观');
        const storyBible = await apiClient.generateStoryBible({
          novel_id: novel.id,
          title: `${title} 动漫设定本`,
          style: form.style,
          model_config_id: textModelConfigId || undefined,
        });
        ensureActive();
        storyBibleId = storyBible.id;
        markStep('story_bible', 'done', '动漫设定本已生成');
      }

      markStep('storyboard', 'running', '正在把章节改编为剧本、分镜和镜头');
      const storyboard = await apiClient.generateSmartStoryboard({
        novel_id: novel.id,
        chapter_id: chapter.id,
        shot_count: form.shotCount,
        style: form.style,
        title: `${title} 首集分镜`,
        story_bible_id: storyBibleId,
        use_ai_refine: false,
        model_config_id: textModelConfigId || undefined,
      });
      ensureActive();
      const shotCount = storyboard.shot_count || storyboard.shots?.length || form.shotCount;
      markStep('storyboard', 'done', `已生成 ${shotCount} 个镜头`);

      markStep('workflow', 'running', '正在创建首集制作工作流');
      const workflow = await apiClient.startWorkflow({
        title: `${title} 制作工作流`,
        novel_id: novel.id,
        chapter_id: chapter.id,
        script_id: storyboard.script_id,
        storyboard_id: storyboard.id,
      });
      ensureActive();
      markStep('workflow', 'done', '工作流已创建');

      let nextResult: QuickStartResult = {
        novelId: novel.id,
        chapterId: chapter.id,
        storyBibleId,
        scriptId: storyboard.script_id,
        storyboardId: storyboard.id,
        workflowId: workflow.workflow_id,
        shotCount,
      };
      partialResult = nextResult;
      if (activeRunIdRef.current === runId) {
        setResult(nextResult);
      }

      if (form.autoProducePreview) {
        const preview = await runEpisodePreviewProduction({
          workflowId: workflow.workflow_id,
          novelId: novel.id,
          chapterId: chapter.id,
          scriptId: storyboard.script_id,
          storyboardId: storyboard.id,
          title: `${title} 首集预览`,
          textModelConfigId: textModelConfigId || undefined,
          videoModelConfigId: videoModelConfigId || undefined,
          audioModelConfigId: audioModelConfigId || undefined,
          productionStrategy,
          onStage: (stage) => {
            if (activeRunIdRef.current !== runId) return;
            const stepId = stageToStep[stage.key];
            if (stepId && stage.status) {
              markStep(stepId, stage.status, stage.message);
            }
          },
        });
        ensureActive();
        nextResult = applyPreviewResult(nextResult, preview);
        partialResult = nextResult;
        setResult(nextResult);
      }
    } catch (err: any) {
      if (activeRunIdRef.current !== runId) return;
      const message = err?.message || '极速向导执行失败';
      if (activeStepId) {
        markStep(activeStepId, 'failed', message);
      }
      setError(message);
      const failedStep = initialSteps.find((step) => step.id === activeStepId);
      const canRecoverFromWorkflow = Boolean(partialResult?.workflowId || result?.workflowId);
      const canSkipAudio = canRecoverFromWorkflow && (activeStepId === 'media' || activeStepId === 'concatenate');
      setIssue(buildIssue(
        err,
        activeStepId || 'media',
        failedStep?.label || '当前步骤',
        canSkipAudio,
        canRecoverFromWorkflow
      ));
    } finally {
      if (activeRunIdRef.current === runId) {
        setIsRunning(false);
      }
    }
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white flex items-center gap-2">
              <Wand2 className="h-7 w-7 text-violet-400" />
              连续动漫向导
            </h1>
            <p className="mt-1 text-white/60">粘贴故事，AI 自动生成动漫设定本、首集剧本分镜和可预览草片</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Button onClick={() => saveDraft(true)} variant="outline" className="border-white/20 text-white">
              <Save className="mr-2 h-4 w-4" />
              保存草稿
            </Button>
            <Button onClick={runQuickStart} disabled={isRunning} className="bg-violet-600 hover:bg-violet-700">
              {isRunning ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
              生成第一集
            </Button>
            {isRunning && (
              <Button type="button" onClick={stopCurrentRun} variant="outline" className="border-yellow-400/30 text-yellow-100">
                停止等待
              </Button>
            )}
          </div>
        </div>

        <NextStepGuide
          title="这一步 AI 会帮你做什么"
          current="你只需要提供作品名、故事梗概和首章内容"
          next="AI 会整理统一设定，再生成第一集的剧本、分镜、配音、字幕和草片"
          reason="先把角色、场景、道具、事件和声音锁进设定本，后续多集才不容易跑偏。"
          href="#quick-start-form"
          actionLabel="填写故事信息"
          checklist={['自动抽取角色与世界观', '自动拆成镜头和对白', '高级模型配置可先不管']}
        />

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <Card id="quick-start-form" className="bg-white/5 border-white/10">
            <CardHeader>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <CardTitle className="text-white flex items-center gap-2">
                    <BookOpen className="h-5 w-5 text-violet-400" />
                    故事输入
                  </CardTitle>
                  <p className="mt-1 text-sm text-white/50">只填故事信息即可；类型、风格和镜头数都有默认值。</p>
                </div>
                <Button type="button" variant="outline" className="border-white/20 text-white" onClick={fillSampleStory}>
                  <Sparkles className="mr-2 h-4 w-4" />
                  填入示例故事
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="space-y-1.5">
                  <div className="text-xs text-white/50">作品名</div>
                  <Input
                    value={form.title}
                    onChange={(event) => setForm({ ...form, title: event.target.value })}
                    placeholder="例如：星灯邮差"
                    className="bg-white/5 border-white/10 text-white"
                  />
                </div>
                <div className="space-y-1.5">
                  <div className="text-xs text-white/50">首集章节名</div>
                  <Input
                    value={form.chapterTitle}
                    onChange={(event) => setForm({ ...form, chapterTitle: event.target.value })}
                    placeholder="例如：第一章 雨后的旧邮局"
                    className="bg-white/5 border-white/10 text-white"
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-[1fr_1fr_160px]">
                <div className="space-y-1.5">
                  <div className="text-xs text-white/50">故事类型</div>
                  <Select value={form.genre} onChange={(event) => setForm({ ...form, genre: event.target.value })} options={genreOptions} />
                </div>
                <div className="space-y-1.5">
                  <div className="text-xs text-white/50">画面风格</div>
                  <Select value={form.style} onChange={(event) => setForm({ ...form, style: event.target.value })} options={styleOptions} />
                </div>
                <div className="space-y-1.5">
                  <div className="text-xs text-white/50">首集镜头数</div>
                  <Input
                    type="number"
                    min={1}
                    max={12}
                    value={form.shotCount}
                    onChange={(event) => setForm({ ...form, shotCount: Number(event.target.value) })}
                    aria-label="首集镜头数"
                    className="bg-white/5 border-white/10 text-white"
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <div className="text-xs text-white/50">故事梗概：告诉 AI 主角、目标、冲突和世界观</div>
                <Textarea
                  value={form.premise}
                  onChange={(event) => setForm({ ...form, premise: event.target.value })}
                  placeholder="写 2-5 句话即可，例如：主角是谁、遇到什么事件、这一季要完成什么目标。"
                  className="min-h-[100px]"
                />
              </div>
              <div className="space-y-1.5">
                <div className="text-xs text-white/50">首章正文：可粘贴完整第一章，也可先写一段用于几秒草片验证</div>
                <Textarea
                  value={form.chapterContent}
                  onChange={(event) => setForm({ ...form, chapterContent: event.target.value })}
                  placeholder="粘贴首章正文。没有完整章节时，也可以先粘贴 1-3 段关键剧情。"
                  className="min-h-[180px]"
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-white/70">
                <input
                  type="checkbox"
                  checked={form.createStoryBible}
                  onChange={(event) => setForm({ ...form, createStoryBible: event.target.checked })}
                />
                自动生成动漫设定本，统一人物、场景、道具和风格
              </label>
              <label className="flex items-center gap-2 text-sm text-white/70">
                <input
                  type="checkbox"
                  checked={form.autoProducePreview}
                  onChange={(event) => setForm({ ...form, autoProducePreview: event.target.checked })}
                />
                自动生成首集可预览草片、字幕和本地渲染包
              </label>
              <div className="rounded-lg border border-white/10 bg-white/5">
                <button
                  type="button"
                  onClick={() => setAdvancedOpen((value) => !value)}
                  className="flex w-full items-center justify-between gap-3 p-3 text-left text-sm text-white"
                  aria-expanded={advancedOpen}
                >
                  <span>
                    高级设置
                    <span className="ml-2 text-white/45">模型、效果模式和角色配音；默认可直接运行</span>
                  </span>
                  <ChevronDown className={`h-4 w-4 text-white/50 transition-transform ${advancedOpen ? 'rotate-180' : ''}`} />
                </button>
                {advancedOpen && (
                  <div className="space-y-3 border-t border-white/10 p-3">
                    <ModelCapabilitySelector
                      capability="text"
                      configs={modelConfigs}
                      value={textModelConfigId}
                      onChange={setTextModelConfigId}
                      disabled={isRunning}
                      title="AI编剧模型（高级）"
                      description="用于生成动漫设定本和分镜一致性上下文；不懂模型时保持默认即可。"
                      compact
                    />
                    {form.autoProducePreview && (
                      <>
                        <div className="rounded-lg border border-cyan-400/20 bg-cyan-500/10 p-3">
                          <div className="mb-2 text-xs text-cyan-100/70">效果模式</div>
                          <Select
                            value={productionStrategy}
                            onChange={(event) => setProductionStrategy(event.target.value as ProductionStrategy)}
                            options={PRODUCTION_STRATEGY_OPTIONS}
                            disabled={isRunning}
                          />
                          <div className="mt-2 text-sm text-cyan-50/80">
                            <span className="font-medium text-white">{productionStrategyCopy.label}</span>
                            <span className="ml-2">{productionStrategyCopy.description}</span>
                          </div>
                          <div className="mt-1 text-xs text-cyan-100/70">{productionStrategyCopy.modelHint}</div>
                        </div>
                        <ModelCapabilitySelector
                          capability="video"
                          configs={modelConfigs}
                          value={videoModelConfigId}
                          onChange={setVideoModelConfigId}
                          disabled={isRunning}
                          title="视频质量配置（高级）"
                          description="默认按效果模式路由；需要指定 Seedance 等视频模型时再调整。"
                          compact
                        />
                        <ModelCapabilitySelector
                          capability="audio"
                          configs={modelConfigs}
                          value={audioModelConfigId}
                          onChange={setAudioModelConfigId}
                          disabled={isRunning}
                          title="角色配音配置（高级）"
                          description="用于生成角色对白；后续会结合声线锁保持多集声音一致。"
                          compact
                        />
                      </>
                    )}
                  </div>
                )}
              </div>
              <div className="text-xs text-white/40">
                草稿会自动保存在本机{draftSavedAt ? `，上次保存：${new Date(draftSavedAt).toLocaleString()}` : ''}。
              </div>
              {saveMessage && (
                <div className="rounded border border-emerald-400/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
                  {saveMessage}
                </div>
              )}
              {restoredRunAt && (
                <div className="rounded border border-cyan-400/30 bg-cyan-500/10 p-3 text-sm text-cyan-100">
                  已恢复上次执行记录：{new Date(restoredRunAt).toLocaleString()}。你可以查看进度明细、进入工作台，或从失败环节继续处理。
                </div>
              )}
              {error && !issue && <div className="rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</div>}
              {issue && (
                <div className="space-y-3 rounded-xl border border-red-400/30 bg-red-500/10 p-4">
                  <div>
                    <div className="text-sm font-semibold text-red-100">{issue.summary}</div>
                    <div className="mt-1 text-xs text-red-100/70">
                      已完成的作品、章节、设定本、分镜和工作流不会丢失；你可以修复配置后继续，也可以先跳过配音生成无声草片。
                    </div>
                    <div className="mt-2 rounded border border-red-300/20 bg-black/20 px-2 py-1 text-xs text-red-100/80">
                      错误摘要：{issue.rawMessage.split('\n')[0]}
                    </div>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                    <div className="text-xs font-medium text-white/70">可能原因</div>
                    <div className="mt-1 text-sm text-white/80">{issue.cause}</div>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                    <div className="text-xs font-medium text-white/70">处理办法</div>
                    <ul className="mt-2 space-y-1 text-sm text-white/75">
                      {issue.advice.map((item) => (
                        <li key={item}>- {item}</li>
                      ))}
                    </ul>
                  </div>
                  <details className="rounded-lg border border-white/10 bg-black/20 p-3">
                    <summary className="cursor-pointer text-xs font-medium text-white/70">查看完整错误信息</summary>
                    <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-red-100/80">{issue.rawMessage}</pre>
                  </details>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {issue.canRetryProduction && (
                      <Button type="button" onClick={retryProductionStage} disabled={isRunning} className="justify-start bg-emerald-600 hover:bg-emerald-700">
                        {isRunning ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                        重试生产阶段
                      </Button>
                    )}
                    {issue.canSkipAudio && result?.workflowId && (
                      <Button type="button" onClick={continueWithoutAudio} disabled={isRunning} className="justify-start bg-cyan-600 hover:bg-cyan-700">
                        {isRunning ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Film className="mr-2 h-4 w-4" />}
                        跳过配音继续生成
                      </Button>
                    )}
                    <Button type="button" onClick={stopCurrentRun} variant="outline" className="justify-start border-yellow-400/30 text-yellow-100">
                      停止处理并保留成果
                    </Button>
                    <Button asChild variant="outline" className="justify-start border-white/20 text-white">
                      <Link href="/llm-config">
                        <CheckCircle className="mr-2 h-4 w-4" />
                        去模型与密钥检查
                      </Link>
                    </Button>
                    <Button asChild variant="outline" className="justify-start border-white/20 text-white">
                      <Link href="/tts">
                        <PlayCircle className="mr-2 h-4 w-4" />
                        去 TTS 试听音色
                      </Link>
                    </Button>
                    {result?.workflowId && (
                      <Button asChild variant="outline" className="justify-start border-white/20 text-white">
                        <Link href={`/studio?workflow_id=${result.workflowId}`}>
                          <Route className="mr-2 h-4 w-4" />
                          进入工作台处理
                        </Link>
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <div className="space-y-4">
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-violet-400" />
                  检查
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {checks.map((item) => (
                  <div key={item.label} className="flex items-center justify-between gap-3">
                    <span className="text-sm text-white/70">{item.label}</span>
                    <Badge variant={item.ok ? 'success' : 'warning'}>{item.ok ? '就绪' : '待补齐'}</Badge>
                  </div>
                ))}
                {!isReady && (
                  <div className="rounded border border-yellow-500/20 bg-yellow-500/10 p-3 text-xs text-yellow-100">
                    作品名必填，故事梗概和章节内容至少 8 个字，镜头数需在 1-12 之间。点击“生成第一集”会提示还缺哪些内容。
                  </div>
                )}
              </CardContent>
            </Card>

            {progressSteps.length > 0 && (
              <Card className="bg-white/5 border-white/10">
                <CardHeader>
                  <CardTitle className="text-white flex items-center gap-2">
                    <Film className="h-5 w-5 text-violet-400" />
                    生成进度
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {progressSteps.map((step) => {
                    const expanded = expandedStepIds.includes(step.id);
                    const details = stepDetails(step);
                    return (
                      <div key={step.id} className="rounded border border-white/10 bg-white/5 p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <span className="text-sm text-white">{step.label}</span>
                            {step.detail && <div className="mt-1 text-xs text-white/50">{step.detail}</div>}
                          </div>
                          <Badge variant={progressBadgeVariant(step.status)}>
                            {step.status === 'running' && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
                            {progressStatusText(step.status)}
                          </Badge>
                        </div>
                        <button
                          type="button"
                          onClick={() => toggleStepDetails(step.id)}
                          className="mt-2 text-xs text-cyan-200 hover:text-cyan-100"
                          aria-expanded={expanded}
                        >
                          {expanded ? '隐藏任务明细' : '查看任务明细'}
                        </button>
                        {expanded && (
                          <div className="mt-3 space-y-2 rounded-lg border border-white/10 bg-black/20 p-3">
                            {details.map((item) => (
                              <div key={`${step.id}-${item.label}`} className="grid grid-cols-[80px_minmax(0,1fr)] gap-3 text-xs">
                                <div className="text-white/45">{item.label}</div>
                                <div className="break-all text-white/75">{String(item.value)}</div>
                              </div>
                            ))}
                            {step.status === 'failed' && issue?.rawMessage && (
                              <div className="border-t border-white/10 pt-2 text-xs text-red-100/80">
                                错误：{issue.rawMessage.split('\n')[0]}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </CardContent>
              </Card>
            )}

            {result && (
              <Card className="bg-white/5 border-white/10">
                <CardHeader>
                  <CardTitle className="text-white flex items-center gap-2">
                    <Route className="h-5 w-5 text-violet-400" />
                    已创建
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded border border-white/10 bg-white/5 p-3">
                      <div className="text-white/50">分镜</div>
                      <div className="text-lg font-semibold text-white">{result.shotCount}</div>
                    </div>
                    <div className="rounded border border-white/10 bg-white/5 p-3">
                      <div className="text-white/50">工作流</div>
                      <div className="text-lg font-semibold text-white">1</div>
                    </div>
                    <div className="rounded border border-white/10 bg-white/5 p-3">
                      <div className="text-white/50">音视频草稿</div>
                      <div className="text-lg font-semibold text-white">
                        {(result.mediaJobIds?.length || 0) + (result.videoJobIds?.length || 0) + (result.ttsJobIds?.length || 0)}
                      </div>
                    </div>
                    <div className="rounded border border-white/10 bg-white/5 p-3">
                      <div className="text-white/50">字幕轨</div>
                      <div className="text-lg font-semibold text-white">{result.subtitleTrackIds?.length || 0}</div>
                    </div>
                  </div>
                  {result.autoProduced && (
                    <div className="rounded border border-emerald-400/20 bg-emerald-500/10 p-3 text-sm text-emerald-100">
                      首集预览草片、字幕和渲染包已生成，可直接审阅或进入工作流继续调整。
                    </div>
                  )}
                  <div className="rounded-xl border border-cyan-400/20 bg-cyan-500/10 p-3">
                    <div className="text-sm font-semibold text-white">下一步制作路径</div>
                    <div className="mt-1 text-xs text-cyan-100/70">建议按顺序完成审核、整书规划和一致性资产检查，降低后续多集制作返工。</div>
                    <div className="mt-3 grid grid-cols-1 gap-2">
                      <Link
                        href={`/studio?workflow_id=${result.workflowId}`}
                        className="rounded-lg border border-white/10 bg-white/5 p-3 transition hover:border-cyan-300/50 hover:bg-white/10"
                      >
                        <div className="flex items-center gap-2 text-sm font-medium text-white">
                          <Route className="h-4 w-4 text-cyan-200" />
                          1. 进入连续动漫工作台继续审核
                        </div>
                        <div className="mt-1 text-xs text-white/55">审阅首集工作流、分镜、镜头生产状态和预览结果。</div>
                      </Link>
                      <Link
                        href={`/novels/${result.novelId}?tab=series-plan`}
                        className="rounded-lg border border-white/10 bg-white/5 p-3 transition hover:border-cyan-300/50 hover:bg-white/10"
                      >
                        <div className="flex items-center gap-2 text-sm font-medium text-white">
                          <BookOpen className="h-4 w-4 text-cyan-200" />
                          2. 进入整书/下一集计划
                        </div>
                        <div className="mt-1 text-xs text-white/55">规划后续集数、章节覆盖、关键角色和下一集制作节奏。</div>
                      </Link>
                      <Link
                        href={`/novels/${result.novelId}?tab=story-bible`}
                        className="rounded-lg border border-white/10 bg-white/5 p-3 transition hover:border-cyan-300/50 hover:bg-white/10"
                      >
                        <div className="flex items-center gap-2 text-sm font-medium text-white">
                          <CheckCircle className="h-4 w-4 text-cyan-200" />
                          3. 进入一致性资产检查/角色设定
                        </div>
                        <div className="mt-1 text-xs text-white/55">检查 Story Bible、角色规则、场景道具和状态机一致性。</div>
                      </Link>
                    </div>
                  </div>
                  {(result.previewUrl || result.outputUrl || result.srtUrl || result.timelineUrl) && (
                    <div className="grid grid-cols-1 gap-2">
                      {result.previewUrl && (
                        <Button asChild variant="outline" className="justify-start border-white/20 text-white">
                          <a href={toMediaUrl(result.previewUrl)} target="_blank" rel="noreferrer">
                            <PlayCircle className="mr-2 h-4 w-4" />
                            播放预览包
                          </a>
                        </Button>
                      )}
                      {result.outputUrl && (
                        <Button asChild variant="outline" className="justify-start border-white/20 text-white">
                          <a href={toMediaUrl(result.outputUrl)} target="_blank" rel="noreferrer">
                            <Film className="mr-2 h-4 w-4" />
                            打开草片视频
                          </a>
                        </Button>
                      )}
                      {result.srtUrl && (
                        <Button asChild variant="outline" className="justify-start border-white/20 text-white">
                          <a href={toMediaUrl(result.srtUrl)} target="_blank" rel="noreferrer">
                            <Captions className="mr-2 h-4 w-4" />
                            查看 SRT 字幕
                          </a>
                        </Button>
                      )}
                      {result.timelineUrl && (
                        <Button asChild variant="outline" className="justify-start border-white/20 text-white">
                          <a href={toMediaUrl(result.timelineUrl)} target="_blank" rel="noreferrer">
                            <Download className="mr-2 h-4 w-4" />
                            查看时间线
                          </a>
                        </Button>
                      )}
                    </div>
                  )}
                  <div className="grid grid-cols-1 gap-2">
                    <Button asChild className="justify-start bg-cyan-600 hover:bg-cyan-700">
                      <Link href={`/studio?workflow_id=${result.workflowId}`}>
                        <Route className="mr-2 h-4 w-4" />
                        进入创作工作台
                      </Link>
                    </Button>
                    <Button asChild variant="outline" className="justify-start border-white/20 text-white">
                      <Link href={`/novels/${result.novelId}`}>
                        <BookOpen className="mr-2 h-4 w-4" />
                        打开作品
                      </Link>
                    </Button>
                    <Button asChild variant="outline" className="justify-start border-white/20 text-white">
                      <Link href={`/novels/${result.novelId}?tab=series-plan`}>
                        <BookOpen className="mr-2 h-4 w-4" />
                        进入整书计划
                      </Link>
                    </Button>
                    <Button asChild variant="outline" className="justify-start border-white/20 text-white">
                      <Link href={`/storyboards?storyboard_id=${result.storyboardId}`}>
                        <Clapperboard className="mr-2 h-4 w-4" />
                        审核分镜
                      </Link>
                    </Button>
                    <Button asChild variant="outline" className="justify-start border-white/20 text-white">
                      <Link href={`/scripts/${result.scriptId}`}>
                        <FileText className="mr-2 h-4 w-4" />
                        查看脚本
                      </Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
