'use client';

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { MainLayout } from '@/components/layout/main-layout';
import { ModelCapabilitySelector } from '@/components/model-capability-selector';
import { ProductionStatusRail } from '@/components/production/production-status-rail';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select } from '@/components/ui/select';
import { EmptyState } from '@/components/ui/empty-state';
import { useToast } from '@/components/ui/toast';
import { apiClient } from '@/lib/api-client';
import { getDefaultConfigForCapability, SavedModelConfig } from '@/lib/model-configs';
import {
  createInitialEpisodePreviewStages,
  EpisodePreviewProductionResult,
  EpisodePreviewStage,
  EpisodePreviewStageUpdate,
  runEpisodePreviewProduction,
} from '@/lib/episode-preview-production';
import {
  ArrowRight,
  AlertCircle,
  Bot,
  CheckCircle2,
  Database,
  Files,
  Layers3,
  Loader2,
  RefreshCw,
  Sparkles,
  ShieldCheck,
  Film,
  Wand2,
  ClipboardList,
  Workflow,
  ImageIcon,
  FileText,
  PlayCircle,
  Check,
  Book,
  ListTree,
  Zap,
  FileText as FileTextIcon,
  Clapperboard,
  Image as ImageIcon2,
  Volume2,
  Film as FilmIcon2,
  Pause,
  Play,
  RotateCw,
  X,
} from 'lucide-react';

type WorkflowItem = {
  workflow_id?: string;
  title?: string;
  status?: string;
  current_step?: number;
  completed_steps?: number[];
  novel_id?: string | null;
  chapter_id?: string | null;
  script_id?: string | null;
  storyboard_id?: string | null;
  video_job_ids?: string[];
  tts_job_ids?: string[];
  synthesis_job_ids?: string[];
  metadata?: Record<string, any>;
  error_message?: string | null;
  created_at?: string;
  updated_at?: string;
};

type StoryBibleItem = {
  id: string;
  title: string;
  novel_id?: string | null;
  style?: string;
  worldview?: string;
  extra_data?: Record<string, any>;
  updated_at?: string;
};

type NovelItem = {
  id: string;
  title?: string;
  genre?: string;
  description?: string;
};

type ChapterItem = {
  id: string;
  title?: string;
  chapter_number?: number;
  content?: string;
};

type ProductionPack = {
  version?: string;
  novel_id?: string;
  novel_title?: string;
  generated_at?: string;
  summary?: {
    entity_count?: number;
    asset_count?: number;
    lock_count?: number;
    created_asset_count?: number;
    missing_entity_count?: number;
  };
  locks?: Array<Record<string, any>>;
  missing_entities?: Array<Record<string, any>>;
  recommendations?: string[];
  created_asset_ids?: string[];
};

type ProducerResult = {
  summary?: Record<string, any>;
  actions?: Array<Record<string, any>>;
  executed?: Array<Record<string, any>>;
  media_audit?: Record<string, any>;
  quality?: Record<string, any>;
  production_pack?: ProductionPack;
  [key: string]: any;
};

type WorkflowRecordResult = {
  workflowId: string;
  reused: boolean;
};

const statusLabels: Record<string, string> = {
  draft: '草稿',
  active: '进行中',
  paused: '暂停',
  completed: '已完成',
  archived: '已归档',
};

const actionTone: Record<string, string> = {
  ready: 'text-emerald-300 border-emerald-500/25 bg-emerald-500/10',
  blocked: 'text-red-300 border-red-500/25 bg-red-500/10',
  manual: 'text-yellow-200 border-yellow-500/25 bg-yellow-500/10',
};

const formatDate = (value?: string) => {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
};

const stepLabel = (step?: number) => {
  if (!step || step <= 0) return '待启动';
  return `第 ${step} 步`;
};

const countLabel = (value?: number) => (typeof value === 'number' ? String(value) : '-');

const API_ORIGIN = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1').replace(/\/api\/v1\/?$/, '');

const toMediaUrl = (url?: string) => {
  if (!url) return '';
  return url.startsWith('/') ? `${API_ORIGIN}${url}` : url;
};

export default function ProducerCenterPage() {
  return (
    <Suspense fallback={
      <MainLayout>
        <div className="p-6 text-white/60">正在加载 AI 制片中心…</div>
      </MainLayout>
    }>
      <ProducerCenterContent />
    </Suspense>
  );
}

function ProducerCenterContent() {
  const { toast } = useToast();
  const searchParams = useSearchParams();
  const [workflowId, setWorkflowId] = useState<string>(searchParams.get('workflow_id') || '');
  const [novels, setNovels] = useState<NovelItem[]>([]);
  const [chapters, setChapters] = useState<ChapterItem[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [storyBibles, setStoryBibles] = useState<StoryBibleItem[]>([]);
  const [selectedStoryBibleId, setSelectedStoryBibleId] = useState('');
  const [selectedNovelId, setSelectedNovelId] = useState('');
  const [selectedChapterId, setSelectedChapterId] = useState('');
  const [workflowStatus, setWorkflowStatus] = useState<any>(null);
  const [storyStateMachine, setStoryStateMachine] = useState<any>(null);
  const [productionPack, setProductionPack] = useState<ProductionPack | null>(null);
  const [producerResult, setProducerResult] = useState<ProducerResult | null>(null);
  const [modelConfigs, setModelConfigs] = useState<SavedModelConfig[]>([]);
  const [textModelConfigId, setTextModelConfigId] = useState('');
  const [videoModelConfigId, setVideoModelConfigId] = useState('');
  const [audioModelConfigId, setAudioModelConfigId] = useState('');
  const [previewStages, setPreviewStages] = useState<EpisodePreviewStage[]>(() => createInitialEpisodePreviewStages());
  const [previewResult, setPreviewResult] = useState<EpisodePreviewProductionResult | null>(null);
  const [shortVideoReadiness, setShortVideoReadiness] = useState<any>(null);
  const [publicationResult, setPublicationResult] = useState<any>(null);
  const [loadingAction, setLoadingAction] = useState('');
  const [loadingNovels, setLoadingNovels] = useState(false);
  const [loadingChapters, setLoadingChapters] = useState(false);
  const [loadingWorkflows, setLoadingWorkflows] = useState(false);
  const [loadingStoryBibles, setLoadingStoryBibles] = useState(false);
  const [loadingReadiness, setLoadingReadiness] = useState(false);
  const [publishingPreview, setPublishingPreview] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [productionStatus, setProductionStatus] = useState<any>(null);
  const [generationMode, setGenerationMode] = useState<'script' | 'storyboard' | 'all' | null>(null);
  const [generationProgress, setGenerationProgress] = useState<string>('');

  // Batch operations state
  const [shots, setShots] = useState<any[]>([]);
  const [selectedShotIds, setSelectedShotIds] = useState<Set<string>>(new Set());
  const [batchJobs, setBatchJobs] = useState<any[]>([]);
  const [activeBatchJob, setActiveBatchJob] = useState<any>(null);
  const [batchJobItems, setBatchJobItems] = useState<any[]>([]);
  const [loadingShots, setLoadingShots] = useState(false);
  const [batchModalOpen, setBatchModalOpen] = useState(false);

  const selectedWorkflow = useMemo(
    () => workflows.find((item) => item.workflow_id === workflowId) || null,
    [workflows, workflowId]
  );
  const selectedStoryBible = useMemo(
    () => storyBibles.find((item) => item.id === selectedStoryBibleId) || null,
    [storyBibles, selectedStoryBibleId]
  );
  const selectedNovel = useMemo(
    () => novels.find((item) => item.id === selectedNovelId) || null,
    [novels, selectedNovelId]
  );
  const selectedChapter = useMemo(
    () => chapters.find((item) => item.id === selectedChapterId) || null,
    [chapters, selectedChapterId]
  );
  const filteredWorkflows = useMemo(
    () => workflows.filter((item) => {
      if (selectedNovelId && item.novel_id !== selectedNovelId) return false;
      if (selectedChapterId && item.chapter_id !== selectedChapterId) return false;
      return true;
    }),
    [workflows, selectedNovelId, selectedChapterId]
  );

  const refreshWorkflowStatus = useCallback(async (id: string) => {
    const data = await apiClient.getWorkflowStatus(id);
    setWorkflowStatus(data);
    return data;
  }, []);

  const loadShortVideoReadiness = useCallback(async (id: string) => {
    if (!id) {
      setShortVideoReadiness(null);
      return null;
    }
    setLoadingReadiness(true);
    try {
      const data = await apiClient.getWorkflowShortVideoReadiness(id, {
        target_duration_seconds: 60,
        aspect_ratio: '9:16',
      });
      setShortVideoReadiness(data);
      return data;
    } catch (err: any) {
      setShortVideoReadiness(null);
      setError(err.message || '加载短视频就绪度失败');
      return null;
    } finally {
      setLoadingReadiness(false);
    }
  }, []);

  const loadNovels = useCallback(async () => {
    setLoadingNovels(true);
    try {
      const data = await apiClient.getNovels();
      const list = Array.isArray(data) ? data : [];
      setNovels(list);
    } catch (err: any) {
      setError(err.message || '加载小说失败');
    } finally {
      setLoadingNovels(false);
    }
  }, []);

  const loadModelConfigs = useCallback(async () => {
    try {
      const data = await apiClient.getLLMConfigs();
      const list = Array.isArray(data) ? data : [];
      setModelConfigs(list);
      const textDefault = getDefaultConfigForCapability(list, 'text');
      const videoDefault = getDefaultConfigForCapability(list, 'video');
      const audioDefault = getDefaultConfigForCapability(list, 'audio');
      if (textDefault) setTextModelConfigId(textDefault.id);
      if (videoDefault) setVideoModelConfigId(videoDefault.id);
      if (audioDefault) setAudioModelConfigId(audioDefault.id);
    } catch (err: any) {
      setError(err.message || '加载模型配置失败');
    }
  }, []);

  const loadChapters = useCallback(async (novelId: string) => {
    if (!novelId) {
      setChapters([]);
      setSelectedChapterId('');
      return;
    }
    setLoadingChapters(true);
    try {
      const data = await apiClient.getChapters(novelId);
      const list = Array.isArray(data) ? data : [];
      setChapters(list);
      setSelectedChapterId((prev) => {
        if (!list.length) return '';
        return list.some((item) => item.id === prev) ? prev : list[0].id;
      });
    } catch (err: any) {
      setError(err.message || '加载章节失败');
      setChapters([]);
    } finally {
      setLoadingChapters(false);
    }
  }, []);

  const loadWorkflows = useCallback(async () => {
    setLoadingWorkflows(true);
    try {
      const data = await apiClient.getWorkflows({ limit: 50, offset: 0 });
      const list = Array.isArray(data) ? data : [];
      setWorkflows(list);
    } catch (err: any) {
      setError(err.message || '加载工作流失败');
    } finally {
      setLoadingWorkflows(false);
    }
  }, []);

  const loadStoryBibles = useCallback(async (novelId?: string) => {
    setLoadingStoryBibles(true);
    try {
      const data = await apiClient.getStoryBibles({ novel_id: novelId || undefined });
      const list = Array.isArray(data) ? data : [];
      setStoryBibles(list);
      setSelectedStoryBibleId((prev) => {
        if (!list.length) return '';
        return list.some((item) => item.id === prev) ? prev : list[0].id;
      });
    } catch (err: any) {
      setError(err.message || '加载 Story Bible 失败');
    } finally {
      setLoadingStoryBibles(false);
    }
  }, []);

  const loadChapterProductionStatus = useCallback(async (chapterId: string) => {
    if (!chapterId) {
      setProductionStatus(null);
      return;
    }
    try {
      const data = await apiClient.getChapterProductionStatus(chapterId);
      setProductionStatus(data);
    } catch (err: any) {
      console.error('加载章节生产状态失败:', err);
    }
  }, []);

  const createWorkflowRecord = async (links: { scriptId?: string; storyboardId?: string } = {}): Promise<WorkflowRecordResult> => {
    if (!selectedNovelId || !selectedChapterId) {
      toast({ title: '请先选择小说和章节', description: 'AI 制片工程必须绑定到具体小说章节。', type: 'info' });
      return { workflowId: '', reused: false };
    }
    const reusableWorkflow = workflows.find((item) =>
      item.workflow_id &&
      item.novel_id === selectedNovelId &&
      item.chapter_id === selectedChapterId &&
      item.status !== 'archived'
    );
    if (reusableWorkflow?.workflow_id) {
      const nextScriptId = links.scriptId || reusableWorkflow.script_id || '';
      const nextStoryboardId = links.storyboardId || reusableWorkflow.storyboard_id || '';
      if (links.scriptId || links.storyboardId) {
        await apiClient.updateWorkflowStep(reusableWorkflow.workflow_id, {
          current_step: nextStoryboardId ? Math.max(reusableWorkflow.current_step || 0, 6) : Math.max(reusableWorkflow.current_step || 0, 4),
          completed_steps: nextStoryboardId ? [1, 2, 3, 4, 5, 6] : [1, 2, 3, 4],
          novel_id: selectedNovelId,
          chapter_id: selectedChapterId,
          script_id: nextScriptId,
          storyboard_id: nextStoryboardId,
        });
      }
      setWorkflowId(reusableWorkflow.workflow_id);
      await loadWorkflows();
      await refreshWorkflowStatus(reusableWorkflow.workflow_id);
      await loadShortVideoReadiness(reusableWorkflow.workflow_id);
      return { workflowId: reusableWorkflow.workflow_id, reused: true };
    }
    const result = await apiClient.startWorkflow({
      title: `${selectedNovel?.title || '小说'} · ${selectedChapter?.title || '章节'} 制片工程`,
      novel_id: selectedNovelId,
      chapter_id: selectedChapterId,
      script_id: links.scriptId,
      storyboard_id: links.storyboardId,
    });
    setWorkflowId(result.workflow_id);
    await loadWorkflows();
    await refreshWorkflowStatus(result.workflow_id);
    await loadShortVideoReadiness(result.workflow_id);
    return { workflowId: result.workflow_id, reused: false };
  };

  const runOneClickProduction = async (mode: 'script' | 'storyboard' | 'all') => {
    if (!selectedChapterId) {
      toast({ title: '请先选择章节', description: '需要选择具体章节才能一键生成。', type: 'info' });
      return;
    }
    setGenerationMode(mode);
    setError(null);
    setGenerationProgress('正在准备生成...');
    try {
      let result: any;
      if (mode === 'script') {
        setGenerationProgress('正在生成剧本...');
        result = await apiClient.generateChapterScript(selectedChapterId, {
          style: 'anime',
          model_config_id: textModelConfigId || undefined,
        });
        setGenerationProgress('剧本生成完成');
        toast({ title: '剧本生成完成', description: result.message, type: 'success' });
      } else if (mode === 'storyboard') {
        setGenerationProgress('正在生成剧本和分镜...');
        result = await apiClient.generateChapterStoryboard(selectedChapterId, {
          style: 'anime',
          model_config_id: textModelConfigId || undefined,
          shot_count: 5,
        });
        setGenerationProgress('剧本和分镜生成完成');
        toast({ title: '剧本和分镜生成完成', description: result.message, type: 'success' });
      } else {
        setGenerationProgress('正在一键生成全部（剧本+分镜+镜头）...');
        result = await apiClient.generateChapterAll(selectedChapterId, {
          style: 'anime',
          model_config_id: textModelConfigId || undefined,
          shot_count: 5,
        });
        setGenerationProgress(`生成完成！共 ${result.shot_count} 个镜头`);
        toast({
          title: '一键生成完成',
          description: `已生成 ${result.shot_count} 个镜头，脚本：${result.script_title}`,
          type: 'success',
        });
      }
      // 更新生产状态
      await loadChapterProductionStatus(selectedChapterId);
      if (!workflowId && (result.script_id || result.storyboard_id)) {
        const workflowRecord = await createWorkflowRecord({
          scriptId: result.script_id,
          storyboardId: result.storyboard_id,
        });
        if (workflowRecord.workflowId) {
          setGenerationProgress(workflowRecord.reused ? '生成完成，已挂载到已有本集工程' : '生成完成，本集工程已自动创建');
        }
      } else if (workflowId) {
        if (result.script_id || result.storyboard_id) {
          await apiClient.updateWorkflowStep(workflowId, {
            current_step: result.storyboard_id ? 6 : 4,
            completed_steps: result.storyboard_id ? [1, 2, 3, 4, 5, 6] : [1, 2, 3, 4],
            novel_id: selectedNovelId,
            chapter_id: selectedChapterId,
            script_id: result.script_id || workflowStatus?.script_id || '',
            storyboard_id: result.storyboard_id || workflowStatus?.storyboard_id || '',
          });
        }
        await refreshWorkflowStatus(workflowId);
        await loadShortVideoReadiness(workflowId);
      }
    } catch (err: any) {
      const message = err.message || '生成失败';
      setError(message);
      setGenerationProgress('');
      toast({ title: '生成失败', description: message, type: 'error' });
    } finally {
      setGenerationMode(null);
    }
  };

  useEffect(() => {
    loadNovels();
    loadModelConfigs();
    loadWorkflows();
  }, [loadNovels, loadModelConfigs, loadWorkflows]);

  useEffect(() => {
    const nextWorkflowId = searchParams.get('workflow_id') || workflowId;
    if (nextWorkflowId && nextWorkflowId !== workflowId) {
      setWorkflowId(nextWorkflowId);
    }
  }, [searchParams, workflowId]);

  useEffect(() => {
    if (selectedNovelId) {
      loadChapters(selectedNovelId);
    }
  }, [selectedNovelId, loadChapters]);

  useEffect(() => {
    if (selectedChapterId) {
      loadChapterProductionStatus(selectedChapterId);
    }
  }, [selectedChapterId, loadChapterProductionStatus]);

  useEffect(() => {
    if (workflowId) {
      refreshWorkflowStatus(workflowId).catch((err) => setError(err.message || '加载工作流状态失败'));
      loadShortVideoReadiness(workflowId).catch((err) => setError(err.message || '加载短视频就绪度失败'));
    } else {
      setWorkflowStatus(null);
      setShortVideoReadiness(null);
    }
  }, [workflowId, refreshWorkflowStatus, loadShortVideoReadiness]);

  useEffect(() => {
    const novelId = workflowStatus?.novel_id || selectedWorkflow?.novel_id || selectedNovelId || '';
    const chapterId = workflowStatus?.chapter_id || selectedWorkflow?.chapter_id || selectedChapterId || '';
    if (novelId && novelId !== selectedNovelId) setSelectedNovelId(novelId);
    if (chapterId && chapterId !== selectedChapterId) setSelectedChapterId(chapterId);
    loadStoryBibles(novelId || undefined);
    setStoryStateMachine(null);
    setProductionPack(null);
    setProducerResult(null);
  }, [
    workflowStatus?.novel_id,
    workflowStatus?.chapter_id,
    selectedWorkflow?.novel_id,
    selectedWorkflow?.chapter_id,
    selectedNovelId,
    selectedChapterId,
    loadStoryBibles,
  ]);

  useEffect(() => {
    if (!selectedNovelId || !filteredWorkflows.length) {
      if (!searchParams.get('workflow_id')) setWorkflowId('');
      return;
    }
    if (!workflowId || !filteredWorkflows.some((item) => item.workflow_id === workflowId)) {
      setWorkflowId(filteredWorkflows[0].workflow_id || '');
    }
  }, [filteredWorkflows, searchParams, selectedNovelId, workflowId]);

  const workflowMetrics = useMemo(() => {
    const videoCount = workflowStatus?.video_jobs?.length || selectedWorkflow?.video_job_ids?.length || 0;
    const ttsCount = workflowStatus?.tts_jobs?.length || selectedWorkflow?.tts_job_ids?.length || 0;
    const mediaCount = workflowStatus?.media_jobs?.length || 0;
    const synthesisCount = workflowStatus?.synthesis_jobs?.length || selectedWorkflow?.synthesis_job_ids?.length || 0;
    return { videoCount, ttsCount, mediaCount, synthesisCount };
  }, [workflowStatus, selectedWorkflow]);

  const runAction = async (action: string, fn: () => Promise<any>, successMessage: string, options: { requiresWorkflow?: boolean } = {}) => {
    const requiresWorkflow = options.requiresWorkflow !== false;
    if (requiresWorkflow && !workflowId) {
      toast({ title: '请先选择工作流', description: '没有工作流就无法执行制片动作。', type: 'info' });
      return;
    }
    setLoadingAction(action);
    setError(null);
    try {
      const result = await fn();
      if (action === 'story-state') {
        setStoryStateMachine(result.state_machine || result);
      } else {
        setProducerResult(result);
      }
      if (action === 'pack') setProductionPack(result.production_pack || result);
      if (action === 'assistant') {
        setProducerResult(result);
      }
      toast({ title: successMessage, type: 'success' });
      if (workflowId) {
        await refreshWorkflowStatus(workflowId);
        await loadShortVideoReadiness(workflowId);
      }
    } catch (err: any) {
      const message = err.message || '执行失败';
      setError(message);
      toast({ title: '操作失败', description: message, type: 'error' });
    } finally {
      setLoadingAction('');
    }
  };

  const updatePreviewStage = (stage: EpisodePreviewStageUpdate) => {
    setPreviewStages((prev) =>
      prev.map((item) => item.key === stage.key ? { ...item, ...stage } : item)
    );
  };

  const createWorkflowForSelection = async () => {
    if (!selectedNovelId || !selectedChapterId) {
      toast({ title: '请先选择小说和章节', description: 'AI 制片工程必须绑定到具体小说章节。', type: 'info' });
      return;
    }
    setLoadingAction('create-workflow');
    setError(null);
    try {
      const result = await createWorkflowRecord();
      if (result.workflowId) {
        toast({ title: result.reused ? '已复用本集制片工程' : '本集制片工程已创建', type: 'success' });
      }
    } catch (err: any) {
      const message = err.message || '创建工作流失败';
      setError(message);
      toast({ title: '创建失败', description: message, type: 'error' });
    } finally {
      setLoadingAction('');
    }
  };

  const runPreviewProduction = async () => {
    setLoadingAction('preview-production');
    setPreviewResult(null);
    setPublicationResult(null);
    setPreviewStages(createInitialEpisodePreviewStages());
    setError(null);
    try {
      const activeWorkflow = workflowId
        ? { workflowId, reused: true }
        : await createWorkflowRecord({
        scriptId: productionStatus?.script_id,
        storyboardId: productionStatus?.storyboard_id,
      });
      const activeWorkflowId = activeWorkflow.workflowId;
      if (!activeWorkflowId) return;
      const result = await runEpisodePreviewProduction({
        workflowId: activeWorkflowId,
        novelId: selectedNovelId,
        chapterId: selectedChapterId,
        title: `${selectedNovel?.title || '本集'} · ${selectedChapter?.title || '预览草片'}`,
        textModelConfigId: textModelConfigId || undefined,
        videoModelConfigId: videoModelConfigId || undefined,
        audioModelConfigId: audioModelConfigId || undefined,
        generationStrategy: 'separate_video_tts',
        onStage: updatePreviewStage,
      });
      setPreviewResult(result);
      setProducerResult((prev) => ({
        ...(prev || {}),
        preview_production: result,
        summary: {
          ...(prev?.summary || {}),
          next_action: {
            label: result.readyForConcatenate === false ? '等待视频/声音任务完成' : '审阅本集草片',
            detail: result.readyForConcatenate === false
              ? '视频模型和声音模型任务已提交，完成后可回到工作流继续合成。'
              : '预览、字幕和时间线包已生成，可进入工作流继续细调。',
          },
        },
      }));
      await loadWorkflows();
      await refreshWorkflowStatus(activeWorkflowId);
      await loadShortVideoReadiness(activeWorkflowId);
      toast({
        title: result.readyForConcatenate === false ? '视频/声音任务已提交' : '本集草片已生成',
        description: result.readyForConcatenate === false ? '等待云端任务完成后再合成。' : '已输出预览、字幕和时间线包。',
        type: 'success',
      });
    } catch (err: any) {
      const message = err.message || '本集草片生成失败';
      setError(message);
      toast({ title: '生成失败', description: message, type: 'error' });
    } finally {
      setLoadingAction('');
    }
  };

  const publishPreviewResult = async () => {
    if (!previewResult?.synthesisJobId) {
      toast({ title: '请先生成本集草片', description: '发布需要可追踪的合成任务。', type: 'info' });
      return;
    }
    setPublishingPreview(true);
    setError(null);
    try {
      const publication = await apiClient.publishSynthesis(previewResult.synthesisJobId, {
        title: `${selectedNovel?.title || '本集'} · ${selectedChapter?.title || '草片'}`,
        visibility: 'private',
      });
      setPublicationResult(publication);
      toast({ title: '本集草片已生成发布记录', description: '可在合成/发布页继续下载、撤销或归档。', type: 'success' });
    } catch (err: any) {
      const message = err.message || '发布草片失败';
      setError(message);
      toast({ title: '发布失败', description: message, type: 'error' });
    } finally {
      setPublishingPreview(false);
    }
  };

  // ========== Batch Operations ==========

  const loadShotsForStoryboard = useCallback(async (storyboardId: string) => {
    if (!storyboardId) {
      setShots([]);
      return;
    }
    setLoadingShots(true);
    try {
      const data = await apiClient.getShots(storyboardId);
      setShots(Array.isArray(data) ? data : []);
    } catch (err: any) {
      console.error('加载镜头失败:', err);
      setShots([]);
    } finally {
      setLoadingShots(false);
    }
  }, []);

  // Load batch jobs on mount
  const loadBatchJobs = useCallback(async () => {
    try {
      const data = await apiClient.getBatchJobs({ limit: 10 });
      const list = data.jobs || [];
      setBatchJobs(list);
    } catch (err: any) {
      console.error('加载批量任务失败:', err);
    }
  }, []);

  useEffect(() => {
    loadBatchJobs();
  }, [loadBatchJobs]);

  const loadBatchJobProgress = useCallback(async (jobId: string) => {
    try {
      const progress = await apiClient.getBatchJobProgress(jobId);
      setActiveBatchJob(progress);
      return progress;
    } catch (err: any) {
      console.error('加载批量任务进度失败:', err);
      return null;
    }
  }, []);

  const createBatchJob = async (jobType: 'image' | 'tts' | 'video') => {
    if (selectedShotIds.size === 0) {
      toast({ title: '请先选择镜头', description: '需要至少选择一个镜头才能创建批量任务。', type: 'info' });
      return;
    }
    const storyboardId = workflowStatus?.storyboard_id || productionStatus?.storyboard_id;
    if (!storyboardId) {
      toast({ title: '请先选择有分镜的工作流', description: '需要关联分镜才能创建批量任务。', type: 'info' });
      return;
    }
    setLoadingAction(`batch-${jobType}`);
    setError(null);
    try {
      const result = await apiClient.createBatchJob({
        job_type: jobType,
        title: `批量生成${jobType === 'image' ? '参考图' : jobType === 'tts' ? '配音' : '视频'} (${selectedShotIds.size}个)`,
        shot_ids: Array.from(selectedShotIds),
        storyboard_id: storyboardId,
        workflow_id: workflowId || undefined,
      });
      setActiveBatchJob(result);
      await loadBatchJobs();
      toast({
        title: '批量任务已创建',
        description: `已创建 ${selectedShotIds.size} 个${jobType === 'image' ? '参考图' : jobType === 'tts' ? '配音' : '视频'}生成任务`,
        type: 'success',
      });
    } catch (err: any) {
      const message = err.message || '创建批量任务失败';
      setError(message);
      toast({ title: '创建失败', description: message, type: 'error' });
    } finally {
      setLoadingAction('');
    }
  };

  const pauseBatchJob = async () => {
    if (!activeBatchJob) return;
    setLoadingAction('pause-batch');
    try {
      await apiClient.pauseBatchJob(activeBatchJob.job_id);
      await loadBatchJobProgress(activeBatchJob.job_id);
      toast({ title: '已暂停批量任务', type: 'success' });
    } catch (err: any) {
      toast({ title: '暂停失败', description: err.message, type: 'error' });
    } finally {
      setLoadingAction('');
    }
  };

  const resumeBatchJob = async () => {
    if (!activeBatchJob) return;
    setLoadingAction('resume-batch');
    try {
      await apiClient.resumeBatchJob(activeBatchJob.job_id);
      await loadBatchJobProgress(activeBatchJob.job_id);
      toast({ title: '已恢复批量任务', type: 'success' });
    } catch (err: any) {
      toast({ title: '恢复失败', description: err.message, type: 'error' });
    } finally {
      setLoadingAction('');
    }
  };

  const retryFailedBatchJob = async () => {
    if (!activeBatchJob) return;
    setLoadingAction('retry-batch');
    try {
      await apiClient.retryFailedBatchJob(activeBatchJob.job_id);
      await loadBatchJobProgress(activeBatchJob.job_id);
      toast({ title: '已重试失败项', type: 'success' });
    } catch (err: any) {
      toast({ title: '重试失败', description: err.message, type: 'error' });
    } finally {
      setLoadingAction('');
    }
  };

  const toggleShotSelection = (shotId: string) => {
    setSelectedShotIds((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(shotId)) {
        newSet.delete(shotId);
      } else {
        newSet.add(shotId);
      }
      return newSet;
    });
  };

  const selectAllShots = () => {
    setSelectedShotIds(new Set(shots.map((s) => s.id)));
  };

  const deselectAllShots = () => {
    setSelectedShotIds(new Set());
  };

  const novelOptions = novels.map((item) => ({
    value: item.id,
    label: `${item.title || '未命名小说'}${item.genre ? ` · ${item.genre}` : ''}`,
  }));

  const chapterOptions = chapters.map((item) => ({
    value: item.id,
    label: `${item.chapter_number ? `第 ${item.chapter_number} 章 · ` : ''}${item.title || '未命名章节'}`,
  }));

  const workflowOptions = filteredWorkflows.map((item) => ({
    value: item.workflow_id || '',
    label: `${item.title || '未命名工作流'}${item.chapter_id ? ` · 章节 ${item.chapter_id.slice(0, 6)}` : ''}`,
  })).filter((item) => item.value);

  const storyBibleOptions = storyBibles.map((item) => ({
    value: item.id,
    label: `${item.title}${item.style ? ` · ${item.style}` : ''}`,
  }));

  const statusCards = [
    {
      label: '镜头视频',
      value: countLabel(workflowMetrics.videoCount),
      icon: Film,
    },
    {
      label: '配音任务',
      value: countLabel(workflowMetrics.ttsCount),
      icon: Sparkles,
    },
    {
      label: '媒体任务',
      value: countLabel(workflowMetrics.mediaCount),
      icon: Database,
    },
    {
      label: '合成任务',
      value: countLabel(workflowMetrics.synthesisCount),
      icon: Files,
    },
  ];

  const storySummary = storyStateMachine?.summary || selectedStoryBible?.extra_data?.state_machine?.summary || {};
  const packSummary = productionPack?.summary || producerResult?.production_pack?.summary || {};
  const qualitySummary = producerResult?.quality || workflowStatus?.metadata?.production_quality_report || {};
  const mediaSummary = producerResult?.media_audit || workflowStatus?.metadata?.media_persistence_audit || {};
  const nextAction = producerResult?.summary?.next_action;
  const actions = Array.isArray(producerResult?.actions) ? producerResult.actions : [];
  const executed = Array.isArray(producerResult?.executed) ? producerResult.executed : [];
  const readinessSummary = shortVideoReadiness?.summary || {};
  const readinessBlockers = Array.isArray(shortVideoReadiness?.blocking_issues) ? shortVideoReadiness.blocking_issues : [];
  const readinessWarnings = Array.isArray(shortVideoReadiness?.warnings) ? shortVideoReadiness.warnings : [];
  const readinessRecommendations = Array.isArray(shortVideoReadiness?.recommendations) ? shortVideoReadiness.recommendations : [];
  const producerStatusItems = [
    {
      label: '小说章节',
      ok: Boolean(selectedNovelId && selectedChapterId),
      detail: selectedNovelId && selectedChapterId ? '已选择当前制作章节' : '先选择小说和章节，避免后续生成失去上下文',
    },
    {
      label: '制片工程',
      ok: Boolean(workflowId),
      detail: workflowId ? '已有本集工程承接剧本、分镜、镜头和成片' : '需要创建或选择本集工程',
    },
    {
      label: '剧本分镜',
      ok: Boolean(productionStatus?.has_script && productionStatus?.has_storyboard),
      detail: productionStatus?.has_storyboard ? '剧本和分镜已准备' : '可用一键生成补齐剧本和分镜',
    },
    {
      label: '镜头资产',
      ok: Boolean((readinessSummary.shot_count || 0) > 0 && (packSummary.lock_count || 0) > 0),
      detail: (readinessSummary.shot_count || 0) > 0
        ? `镜头 ${readinessSummary.shot_count || 0}，资产锁 ${packSummary.lock_count || 0}`
        : '需要先生成镜头并锁定关键角色/场景/道具资产',
    },
    {
      label: '音视频草片',
      ok: Boolean(readinessSummary.ready || previewResult?.previewUrl),
      detail: previewResult?.previewUrl ? '已生成本集草片预览' : readinessSummary.ready ? '短视频链路可生成' : '仍有阻断项需要处理',
    },
    {
      label: '发布交付',
      ok: Boolean(publicationResult?.id || previewResult?.srtUrl),
      detail: publicationResult?.id ? '已有发布记录' : previewResult?.srtUrl ? '已有字幕和预览，可继续发布' : '生成草片后再发布',
    },
  ];
  const producerIssues = [
    ...readinessBlockers.map((message: any) => ({
      code: 'readiness_blocker',
      message: String(message),
      severity: 'blocking',
    })),
    ...readinessWarnings.map((message: any) => ({
      code: 'readiness_warning',
      message: String(message),
      severity: 'warning',
    })),
  ];

  return (
    <MainLayout>
      <div className="space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100">
              <Bot className="h-3.5 w-3.5" />
              AI 制片中心
            </div>
            <h1 className="text-2xl font-bold text-white">把生产控制能力放到台面上</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/60">
              这里集中暴露 Story Bible 状态机、资产定稿包、媒体巡检、质量检查和 AI 制片助手。不是隐藏在工作流侧栏里，而是给非专业人员一个明确的生产入口。
            </p>
          </div>
          <Button asChild variant="outline" className="border-white/20">
            <Link href="/workflow">
              打开工作流
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </div>

        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">
            <AlertCircle className="h-4 w-4" />
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setError(null)}
              className="ml-auto text-red-100/70 underline"
            >
              关闭
            </button>
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-5">
          {statusCards.map((item) => {
            const Icon = item.icon;
            return (
              <Card key={item.label} className="border-white/10 bg-white/5">
                <CardContent className="p-5">
                  <div className="flex items-center justify-between">
                    <Icon className="h-5 w-5 text-white/40" />
                    <div className="text-2xl font-bold text-white">{item.value}</div>
                  </div>
                  <div className="mt-3 text-sm text-white/60">{item.label}</div>
                </CardContent>
              </Card>
            );
          })}
          <Card className="border-white/10 bg-white/5">
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <ShieldCheck className="h-5 w-5 text-white/40" />
                <div className={readinessSummary.ready ? 'text-2xl font-bold text-emerald-300' : 'text-2xl font-bold text-amber-300'}>
                  {workflowId ? (readinessSummary.ready ? '可生成' : '待补齐') : '-'}
                </div>
              </div>
              <div className="mt-3 text-sm text-white/60">出片就绪度</div>
            </CardContent>
          </Card>
        </div>

        <ProductionStatusRail
          workflowId={workflowId || null}
          items={producerStatusItems}
          issues={producerIssues}
          title="本集生产状态"
          subtitle="按小说章节、工程、剧本分镜、资产、草片和发布六个节点检查，缺什么就从本页补什么。"
        />

        <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
          <Card className="border-white/10 bg-white/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <Workflow className="h-4 w-4 text-violet-300" />
                小说、章节与制片工程
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/10 p-3 text-sm leading-6 text-cyan-50">
                先确定小说和章节，再选择或创建本集制片工程。后续剧本、分镜、镜头、字幕、资产锁和视频都会沿用这条链路。
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                <div>
                  <div className="mb-2 flex items-center gap-1 text-xs text-white/50">
                    <Book className="h-3.5 w-3.5" />
                    小说
                  </div>
                  <Select
                    value={selectedNovelId}
                    onChange={(event) => {
                      setSelectedNovelId(event.target.value);
                      setSelectedChapterId('');
                      setWorkflowId('');
                    }}
                    options={novelOptions}
                    placeholder={loadingNovels ? '正在加载小说…' : '选择小说'}
                    disabled={loadingNovels || novelOptions.length === 0 || Boolean(loadingAction)}
                  />
                </div>
                <div>
                  <div className="mb-2 flex items-center gap-1 text-xs text-white/50">
                    <ListTree className="h-3.5 w-3.5" />
                    章节
                  </div>
                  <Select
                    value={selectedChapterId}
                    onChange={(event) => {
                      setSelectedChapterId(event.target.value);
                      setWorkflowId('');
                    }}
                    options={chapterOptions}
                    placeholder={loadingChapters ? '正在加载章节…' : '选择章节'}
                    disabled={!selectedNovelId || loadingChapters || chapterOptions.length === 0 || Boolean(loadingAction)}
                  />
                </div>
                <div>
                  <div className="mb-2 text-xs text-white/50">制片工程</div>
                  <Select
                    value={workflowId}
                    onChange={(event) => setWorkflowId(event.target.value)}
                    options={workflowOptions}
                    placeholder={loadingWorkflows ? '正在加载工程…' : '选择或创建工程'}
                    disabled={!selectedNovelId || !selectedChapterId || loadingWorkflows || workflowOptions.length === 0 || Boolean(loadingAction)}
                  />
                </div>
                <div>
                  <div className="mb-2 flex items-center gap-1 text-xs text-white/50">
                    <Zap className="h-3.5 w-3.5 text-amber-400" />
                    一键生产
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="border-amber-500/25 text-amber-300 hover:bg-amber-500/10"
                      onClick={() => runOneClickProduction('script')}
                      disabled={!selectedChapterId || generationMode !== null}
                    >
                      {generationMode === 'script' ? (
                        <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <FileTextIcon className="mr-1 h-3.5 w-3.5" />
                      )}
                      剧本
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="border-violet-500/25 text-violet-300 hover:bg-violet-500/10"
                      onClick={() => runOneClickProduction('storyboard')}
                      disabled={!selectedChapterId || generationMode !== null}
                    >
                      {generationMode === 'storyboard' ? (
                        <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Layers3 className="mr-1 h-3.5 w-3.5" />
                      )}
                      分镜
                    </Button>
                    <Button
                      size="sm"
                      className="bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500"
                      onClick={() => runOneClickProduction('all')}
                      disabled={!selectedChapterId || generationMode !== null}
                    >
                      {generationMode === 'all' ? (
                        <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Zap className="mr-1 h-3.5 w-3.5" />
                      )}
                      全部
                    </Button>
                  </div>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <div className="mb-2 text-xs text-white/50">Story Bible</div>
                  <Select
                    value={selectedStoryBibleId}
                    onChange={(event) => setSelectedStoryBibleId(event.target.value)}
                    options={storyBibleOptions}
                    placeholder={loadingStoryBibles ? '正在加载 Story Bible…' : '选择 Story Bible'}
                    disabled={loadingStoryBibles || storyBibleOptions.length === 0}
                  />
                </div>
                <div className="flex items-end gap-2">
                  <Button
                    variant="outline"
                    className="flex-1 border-white/20"
                    onClick={createWorkflowForSelection}
                    disabled={!selectedNovelId || !selectedChapterId || Boolean(loadingAction)}
                  >
                    {loadingAction === 'create-workflow' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Workflow className="mr-2 h-4 w-4" />}
                    创建/复用本集工程
                  </Button>
                  <Button
                    className="flex-1 bg-violet-600 hover:bg-violet-700"
                    onClick={runPreviewProduction}
                    disabled={(!workflowId && (!selectedNovelId || !selectedChapterId)) || Boolean(loadingAction)}
                  >
                    {loadingAction === 'preview-production' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
                    一键生成本集草片
                  </Button>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                <ModelCapabilitySelector
                  capability="text"
                  configs={modelConfigs}
                  value={textModelConfigId}
                  onChange={setTextModelConfigId}
                  disabled={Boolean(loadingAction)}
                  title="剧本/分镜文本模型"
                  description="未手动选择时使用当前用户已配置的文本默认模型。"
                  compact
                />
                <ModelCapabilitySelector
                  capability="video"
                  configs={modelConfigs}
                  value={videoModelConfigId}
                  onChange={setVideoModelConfigId}
                  disabled={Boolean(loadingAction)}
                  title="本集草片视频模型"
                  description="分步生成会用该模型创建视频任务，声音不会再混用视频模型。"
                  compact
                />
                <ModelCapabilitySelector
                  capability="audio"
                  configs={modelConfigs}
                  value={audioModelConfigId}
                  onChange={setAudioModelConfigId}
                  disabled={Boolean(loadingAction)}
                  title="本集草片声音模型"
                  description="分步生成会用该声音模型创建每个镜头的配音任务，并用于后续合成。"
                  compact
                />
              </div>

              <div className="grid gap-3 lg:grid-cols-3">
                <div className="rounded-lg border border-white/10 bg-black/20 p-4">
                  <div className="text-xs text-white/40">当前工程</div>
                  <div className="mt-1 text-base font-medium text-white">
                    {selectedWorkflow?.title || workflowStatus?.title || '未选择'}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-white/60">
                    <Badge variant="outline" className="border-white/10 text-white/70">
                      {statusLabels[selectedWorkflow?.status || workflowStatus?.status || ''] || '未知状态'}
                    </Badge>
                    <Badge variant="outline" className="border-white/10 text-white/70">
                      {stepLabel(selectedWorkflow?.current_step || workflowStatus?.current_step)}
                    </Badge>
                    <Badge variant="outline" className="border-white/10 text-white/70">
                      小说 {selectedWorkflow?.novel_id || workflowStatus?.novel_id || '未绑定'}
                    </Badge>
                    <Badge variant="outline" className="border-white/10 text-white/70">
                      章节 {selectedWorkflow?.chapter_id || workflowStatus?.chapter_id || '未绑定'}
                    </Badge>
                  </div>
                </div>
                <div className="rounded-lg border border-white/10 bg-black/20 p-4">
                  <div className="text-xs text-white/40">当前制作对象</div>
                  <div className="mt-1 text-base font-medium text-white">{selectedNovel?.title || '未选择小说'}</div>
                  <div className="mt-2 text-xs leading-5 text-white/60">
                    {selectedChapter?.title ? `章节：${selectedChapter.title}` : '请先选择章节。'}
                  </div>
                  {selectedStoryBible?.title && (
                    <div className="mt-2 text-xs leading-5 text-white/50 line-clamp-2">
                      Story Bible：{selectedStoryBible.title}{selectedStoryBible.style ? ` · ${selectedStoryBible.style}` : ''}
                    </div>
                  )}
                  {productionStatus && (
                    <div className="mt-3 flex flex-wrap gap-2 border-t border-white/10 pt-2">
                      <Badge variant="outline" className={productionStatus.has_script ? 'border-emerald-500/25 text-emerald-300' : 'border-white/10 text-white/50'}>
                        剧本 {productionStatus.has_script ? '✓' : '×'}
                      </Badge>
                      <Badge variant="outline" className={productionStatus.has_storyboard ? 'border-emerald-500/25 text-emerald-300' : 'border-white/10 text-white/50'}>
                        分镜 {productionStatus.has_storyboard ? '✓' : '×'}
                      </Badge>
                      {productionStatus.storyboard_shot_count > 0 && (
                        <Badge variant="outline" className="border-cyan-500/25 text-cyan-300">
                          镜头 {productionStatus.storyboard_shot_count}
                        </Badge>
                      )}
                      {productionStatus.storyboard_id && (
                        <Button asChild size="sm" variant="ghost" className="h-5 text-xs text-cyan-400 hover:text-cyan-300">
                          <Link href={`/storyboards?storyboard_id=${productionStatus.storyboard_id}`}>
                            <Clapperboard className="mr-1 h-3 w-3" />
                            查看分镜
                          </Link>
                        </Button>
                      )}
                    </div>
                  )}
                  {generationMode && (
                    <div className="mt-3 flex items-center gap-2 border-t border-amber-500/25 pt-2">
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-400" />
                      <span className="text-xs text-amber-300">{generationProgress}</span>
                    </div>
                  )}
                </div>
                <div className="rounded-lg border border-white/10 bg-black/20 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-xs text-white/40">短视频出片就绪度</div>
                    {loadingReadiness ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-white/50" />
                    ) : (
                      <Badge
                        variant="outline"
                        className={readinessSummary.ready ? 'border-emerald-500/25 text-emerald-300' : 'border-amber-500/25 text-amber-300'}
                      >
                        {workflowId ? (readinessSummary.ready ? '可生成' : '待补齐') : '未选择'}
                      </Badge>
                    )}
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
                    <div className="rounded bg-white/5 p-2">
                      <div className="text-base font-semibold text-white">{readinessSummary.shot_count ?? '-'}</div>
                      <div className="text-white/45">镜头</div>
                    </div>
                    <div className="rounded bg-white/5 p-2">
                      <div className="text-base font-semibold text-white">{readinessSummary.estimated_duration_seconds ?? '-'}</div>
                      <div className="text-white/45">秒</div>
                    </div>
                    <div className="rounded bg-white/5 p-2">
                      <div className="text-base font-semibold text-white">{readinessSummary.blocking_issue_count ?? '-'}</div>
                      <div className="text-white/45">阻断</div>
                    </div>
                  </div>
                  <div className="mt-3 space-y-2 text-xs leading-5 text-white/60">
                    {readinessRecommendations.slice(0, 2).map((item, index) => (
                      <div key={`${item}-${index}`} className="rounded border border-white/10 bg-white/5 px-2 py-1.5">
                        {item}
                      </div>
                    ))}
                    {!workflowId && <div>选择或创建本集工程后会自动检查。</div>}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="border-white/20"
                      disabled={!workflowId || loadingReadiness}
                      onClick={() => workflowId && loadShortVideoReadiness(workflowId)}
                    >
                      <RefreshCw className="mr-1 h-3.5 w-3.5" />
                      复查
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="border-white/20"
                      disabled={!workflowId || Boolean(loadingAction)}
                      onClick={() =>
                        runAction('contracts-refresh', () => apiClient.refreshWorkflowShortVideoContracts(workflowId), '生产合约已刷新')
                      }
                    >
                      <ShieldCheck className="mr-1 h-3.5 w-3.5" />
                      刷新合约
                    </Button>
                  </div>
                  {(readinessBlockers.length > 0 || readinessWarnings.length > 0) && (
                    <div className="mt-3 border-t border-white/10 pt-2 text-xs leading-5 text-white/55">
                      {readinessBlockers.slice(0, 2).map((issue: any) => (
                        <div key={`blocker-${issue.code || issue.message}`} className="text-red-200">
                          阻断：{issue.message || issue.code}
                        </div>
                      ))}
                      {readinessWarnings.slice(0, 2).map((issue: any) => (
                        <div key={`warning-${issue.code || issue.message}`} className="text-amber-200">
                          提醒：{issue.message || issue.code}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-lg border border-white/10 bg-black/20 p-4">
                <div className="mb-3 text-sm font-medium text-white">本集草片生成阶段</div>
                <div className="grid gap-2 md:grid-cols-3">
                  {previewStages.map((stage) => (
                    <div
                      key={stage.key}
                      className={`rounded-lg border p-3 text-xs leading-5 ${
                        stage.status === 'done'
                          ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-50'
                          : stage.status === 'failed'
                            ? 'border-red-500/25 bg-red-500/10 text-red-50'
                            : stage.status === 'running'
                              ? 'border-violet-500/25 bg-violet-500/10 text-violet-50'
                              : 'border-white/10 bg-white/5 text-white/55'
                      }`}
                    >
                      <div className="flex items-center gap-2 font-medium">
                        {stage.status === 'running' && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                        {stage.status === 'done' && <CheckCircle2 className="h-3.5 w-3.5" />}
                        {stage.status === 'failed' && <AlertCircle className="h-3.5 w-3.5" />}
                        {stage.label}
                      </div>
                      <div className="mt-1 opacity-75">{stage.message}</div>
                    </div>
                  ))}
                </div>
                {previewResult?.previewUrl && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button asChild size="sm" className="bg-emerald-600 hover:bg-emerald-700">
                      <a href={toMediaUrl(previewResult.previewUrl)} target="_blank" rel="noreferrer">
                        打开草片预览
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </a>
                    </Button>
                    {previewResult.srtUrl && (
                      <Button asChild size="sm" variant="outline" className="border-white/20">
                        <a href={toMediaUrl(previewResult.srtUrl)} target="_blank" rel="noreferrer">查看字幕</a>
                      </Button>
                    )}
                    {previewResult.synthesisJobId && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="border-white/20"
                        onClick={publishPreviewResult}
                        disabled={publishingPreview}
                      >
                        {publishingPreview ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
                        发布草片
                      </Button>
                    )}
                    {publicationResult?.export_url && (
                      <Button asChild size="sm" variant="outline" className="border-emerald-500/25 text-emerald-300">
                        <a href={toMediaUrl(publicationResult.export_url)} target="_blank" rel="noreferrer">打开发布文件</a>
                      </Button>
                    )}
                    {publicationResult && (
                      <Button asChild size="sm" variant="ghost" className="text-white/70 hover:text-white">
                        <Link href="/synthesis">发布记录</Link>
                      </Button>
                    )}
                  </div>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  className="border-white/20"
                  onClick={() => workflowId && refreshWorkflowStatus(workflowId)}
                  disabled={!workflowId}
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  刷新工作流
                </Button>
                <Button
                  variant="outline"
                  className="border-white/20"
                  onClick={async () => {
                    if (!selectedStoryBibleId) {
                      toast({ title: '请先选择 Story Bible', type: 'info' });
                      return;
                    }
                    await runAction('story-state', () => apiClient.checkStoryBibleStateMachine(selectedStoryBibleId, { novel_id: selectedNovelId, persist: false }), '状态机检查完成', { requiresWorkflow: false });
                  }}
                  disabled={!selectedStoryBibleId || Boolean(loadingAction)}
                >
                  <ClipboardList className="mr-2 h-4 w-4" />
                  检查状态机
                </Button>
                <Button
                  variant="outline"
                  className="border-white/20"
                  onClick={async () => {
                    if (!selectedStoryBibleId) {
                      toast({ title: '请先选择 Story Bible', type: 'info' });
                      return;
                    }
                    await runAction('story-state', () => apiClient.generateStoryBibleStateMachine(selectedStoryBibleId, { novel_id: selectedNovelId, persist: true }), '状态机已生成', { requiresWorkflow: false });
                  }}
                  disabled={!selectedStoryBibleId || Boolean(loadingAction)}
                >
                  <Layers3 className="mr-2 h-4 w-4" />
                  生成状态机
                </Button>
                <Button
                  asChild
                  variant="ghost"
                  className="text-white/70 hover:text-white"
                >
                  <Link href={workflowId ? `/workflow?workflow_id=${workflowId}` : '/workflow'}>
                    进入工作流页
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="border-white/10 bg-white/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <Database className="h-4 w-4 text-emerald-300" />
                生产检查提示
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-sm leading-6 text-white/70">
                这个面板是给生产操作员看的。先选工作流，再看 Story Bible 状态机和资产定稿包，再决定是否执行媒体巡检或质量检查。
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex items-start gap-2 rounded-lg border border-white/10 bg-white/5 p-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" />
                  <div>
                    <div className="text-white">资产锁</div>
                    <div className="text-white/50">锁定角色、场景、道具和关键参考图，避免多镜头漂移。</div>
                  </div>
                </div>
                <div className="flex items-start gap-2 rounded-lg border border-white/10 bg-white/5 p-3">
                  <ShieldCheck className="mt-0.5 h-4 w-4 text-cyan-300" />
                  <div>
                    <div className="text-white">媒体巡检</div>
                    <div className="text-white/50">检查视频、图片、音频、字幕和渲染产物是否能长期播放。</div>
                  </div>
                </div>
                <div className="flex items-start gap-2 rounded-lg border border-white/10 bg-white/5 p-3">
                  <Wand2 className="mt-0.5 h-4 w-4 text-violet-300" />
                  <div>
                    <div className="text-white">AI 制片助手</div>
                    <div className="text-white/50">先补齐安全缺口，再给出下一步，不替代人工做高风险决策。</div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="border-white/10 bg-white/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <ShieldCheck className="h-4 w-4 text-cyan-300" />
                Story Bible 状态机
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {storyStateMachine ? (
                <>
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                      <div className="text-xs text-white/40">人物</div>
                      <div className="mt-1 text-lg font-semibold text-white">{countLabel(storySummary.characters)}</div>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                      <div className="text-xs text-white/40">场景</div>
                      <div className="mt-1 text-lg font-semibold text-white">{countLabel(storySummary.scenes)}</div>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                      <div className="text-xs text-white/40">道具</div>
                      <div className="mt-1 text-lg font-semibold text-white">{countLabel(storySummary.props)}</div>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                      <div className="text-xs text-white/40">事件</div>
                      <div className="mt-1 text-lg font-semibold text-white">{countLabel(storySummary.events)}</div>
                    </div>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-xs leading-6 text-white/60">
                    当前状态会继承到后续章节、分镜、镜头和视频生成中，避免角色、服装、场景和道具前后不一致。
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      className="border-white/20"
                      onClick={async () => {
                        if (!selectedStoryBibleId) return;
                        await runAction('story-state', () => apiClient.checkStoryBibleStateMachine(selectedStoryBibleId, { novel_id: selectedNovelId, persist: false }), '状态机检查已完成', { requiresWorkflow: false });
                      }}
                      disabled={!selectedStoryBibleId || Boolean(loadingAction)}
                    >
                      <AlertCircle className="mr-2 h-4 w-4" />
                      复查
                    </Button>
                    <Button
                      variant="outline"
                      className="border-white/20"
                      onClick={async () => {
                        if (!selectedStoryBibleId) return;
                        await runAction('story-state', () => apiClient.generateStoryBibleStateMachine(selectedStoryBibleId, { novel_id: selectedNovelId, persist: true }), '状态机已重新生成', { requiresWorkflow: false });
                      }}
                      disabled={!selectedStoryBibleId || Boolean(loadingAction)}
                    >
                      <RefreshCw className="mr-2 h-4 w-4" />
                      重建状态机
                    </Button>
                  </div>
                </>
              ) : (
                <EmptyState
                  icon={Layers3}
                  title="还没有状态机"
                  description="先选一个 Story Bible，再生成或检查状态机。"
                />
              )}
            </CardContent>
          </Card>

          <Card className="border-white/10 bg-white/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <Sparkles className="h-4 w-4 text-violet-300" />
                AI 制片助手
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                  <div className="text-xs text-white/40">资产锁</div>
                  <div className="mt-1 text-lg font-semibold text-white">{countLabel(packSummary.lock_count)}</div>
                </div>
                <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                  <div className="text-xs text-white/40">缺失媒体</div>
                  <div className="mt-1 text-lg font-semibold text-white">{countLabel(mediaSummary.missing_count)}</div>
                </div>
                <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                  <div className="text-xs text-white/40">质量分</div>
                  <div className="mt-1 text-lg font-semibold text-white">{countLabel(qualitySummary.average_score)}</div>
                </div>
                <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                  <div className="text-xs text-white/40">建议数</div>
                  <div className="mt-1 text-lg font-semibold text-white">{actions.length}</div>
                </div>
              </div>

              {nextAction ? (
                <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/10 p-3 text-sm leading-6 text-cyan-50">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="font-medium">下一步：{nextAction.label}</div>
                      <div className="text-white/70">{nextAction.detail}</div>
                    </div>
                    <Button
                      size="sm"
                      className="bg-cyan-600 hover:bg-cyan-700"
                      disabled={!workflowId || Boolean(loadingAction)}
                      onClick={() =>
                        runAction(
                          'assistant-next',
                          () => apiClient.runProducerAssistant(workflowId, {
                            auto_fix: true,
                            ...(typeof nextAction.code === 'string' ? { action_code: nextAction.code } : {}),
                          }),
                          '下一步已执行'
                        )
                      }
                    >
                      {loadingAction === 'assistant-next' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Zap className="mr-2 h-4 w-4" />}
                      执行下一步
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-sm text-emerald-50">
                  当前工作流可直接进入生成、渲染或发布。
                </div>
              )}

              <div className="grid gap-2 md:grid-cols-2">
                <Button
                  className="bg-cyan-600 hover:bg-cyan-700"
                  disabled={!workflowId || Boolean(loadingAction)}
                  onClick={() =>
                    runAction('assistant', () => apiClient.runProducerAssistant(workflowId, { auto_fix: false }), 'AI 制片检查已完成')
                  }
                >
                  {loadingAction === 'assistant' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Bot className="mr-2 h-4 w-4" />}
                  制片检查
                </Button>
                <Button
                  variant="outline"
                  className="border-white/20"
                  disabled={!workflowId || Boolean(loadingAction)}
                  onClick={() =>
                    runAction('assistant-auto', () => apiClient.runProducerAssistant(workflowId, { auto_fix: true }), '安全补齐已执行')
                  }
                >
                  {loadingAction === 'assistant-auto' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
                  安全补齐
                </Button>
                <Button
                  variant="outline"
                  className="border-white/20"
                  disabled={!workflowId || !selectedNovelId || Boolean(loadingAction)}
                  onClick={() =>
                    runAction('pack', () => apiClient.applyWorkflowAssetLocks(workflowId, { create_missing_assets: true, persist: true }), '资产定稿已完成')
                  }
                >
                  {loadingAction === 'pack' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Layers3 className="mr-2 h-4 w-4" />}
                  资产定稿
                </Button>
                <Button
                  variant="outline"
                  className="border-white/20"
                  disabled={!workflowId || Boolean(loadingAction)}
                  onClick={() =>
                    runAction('media', () => apiClient.auditWorkflowMedia(workflowId, { persist_remote: true, dry_run: false }), '媒体巡检已完成')
                  }
                >
                  {loadingAction === 'media' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ImageIcon className="mr-2 h-4 w-4" />}
                  媒体巡检
                </Button>
                <Button
                  variant="outline"
                  className="border-white/20"
                  disabled={!workflowId || Boolean(loadingAction)}
                  onClick={() =>
                    runAction('quality', () => apiClient.checkWorkflowProductionQuality(workflowId, { persist: true }), '质量检查已完成')
                  }
                >
                  {loadingAction === 'quality' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileText className="mr-2 h-4 w-4" />}
                  生产质量检查
                </Button>
                <Button
                  variant="outline"
                  className="border-white/20"
                  disabled={!workflowId || Boolean(loadingAction)}
                  onClick={async () => {
                    if (!workflowId) return;
                    setLoadingAction('refresh');
                    try {
                      await refreshWorkflowStatus(workflowId);
                      toast({ title: '工作流已刷新', type: 'success' });
                    } catch (err: any) {
                      setError(err.message || '刷新失败');
                    } finally {
                      setLoadingAction('');
                    }
                  }}
                >
                  {loadingAction === 'refresh' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                  刷新状态
                </Button>
              </div>

              {executed.length > 0 && (
                <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-xs leading-6 text-emerald-50">
                  已自动执行 {executed.length} 项安全补齐。
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="border-white/10 bg-white/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <Database className="h-4 w-4 text-amber-300" />
                资产定稿包
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {productionPack ? (
                <>
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                      <div className="text-xs text-white/40">实体</div>
                      <div className="mt-1 text-lg font-semibold text-white">{countLabel(productionPack.summary?.entity_count)}</div>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                      <div className="text-xs text-white/40">资产</div>
                      <div className="mt-1 text-lg font-semibold text-white">{countLabel(productionPack.summary?.asset_count)}</div>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                      <div className="text-xs text-white/40">锁定数</div>
                      <div className="mt-1 text-lg font-semibold text-white">{countLabel(productionPack.summary?.lock_count)}</div>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                      <div className="text-xs text-white/40">补齐数</div>
                      <div className="mt-1 text-lg font-semibold text-white">{countLabel(productionPack.summary?.created_asset_count)}</div>
                    </div>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-black/20 p-3 text-xs leading-6 text-white/60">
                    这个包会把角色、场景、道具和事件锁定成生产参考，后续镜头和媒体任务直接复用。
                  </div>
                  <div className="space-y-2">
                    {(productionPack.recommendations || []).slice(0, 3).map((item, index) => (
                      <div key={`${item}-${index}`} className="rounded-lg border border-white/10 bg-white/5 p-3 text-sm leading-6 text-white/70">
                        {item}
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <EmptyState
                  icon={Database}
                  title="还没有定稿包"
                  description="先执行资产定稿，锁定当前小说的角色、场景和道具参考。"
                />
              )}
            </CardContent>
          </Card>

          <Card className="border-white/10 bg-white/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-white">
                <PlayCircle className="h-4 w-4 text-violet-300" />
                工作流摘要
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="rounded-lg border border-white/10 bg-black/20 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-xs text-white/40">标题</div>
                    <div className="text-base font-medium text-white">{selectedWorkflow?.title || workflowStatus?.title || '未选择'}</div>
                  </div>
                  <Badge variant="outline" className="border-white/10 text-white/70">
                    {statusLabels[selectedWorkflow?.status || workflowStatus?.status || ''] || '未知状态'}
                  </Badge>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3 text-sm text-white/60 md:grid-cols-4">
                  <div>
                    <div className="text-xs text-white/40">创建</div>
                    <div>{formatDate(selectedWorkflow?.created_at || workflowStatus?.updated_at)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-white/40">更新</div>
                    <div>{formatDate(selectedWorkflow?.updated_at || workflowStatus?.updated_at)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-white/40">小说</div>
                    <div>{selectedWorkflow?.novel_id || workflowStatus?.novel_id || '未绑定'}</div>
                  </div>
                  <div>
                    <div className="text-xs text-white/40">章节</div>
                    <div>{selectedWorkflow?.chapter_id || workflowStatus?.chapter_id || '未绑定'}</div>
                  </div>
                </div>
              </div>

              <div className="grid gap-2 md:grid-cols-2">
                <Button asChild variant="outline" className="border-white/20">
                  <Link href="/dashboard">
                    回到控制台
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
                <Button asChild variant="outline" className="border-white/20">
                  <Link href="/workflow">
                    打开工作流
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="border-white/10 bg-white/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-white">
              <ClipboardList className="h-4 w-4 text-emerald-300" />
              操作结果与说明
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {producerResult ? (
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-lg border border-white/10 bg-black/20 p-4">
                  <div className="text-sm font-medium text-white">执行反馈</div>
                  <div className="mt-2 space-y-2 text-sm text-white/60">
                    <div>已执行动作：{producerResult?.summary?.executed_count ?? executed.length ?? 0}</div>
                    <div>待处理动作：{producerResult?.summary?.action_count ?? actions.length ?? 0}</div>
                    <div>媒体缺失：{producerResult?.summary?.media_missing_count ?? mediaSummary?.missing_count ?? 0}</div>
                    <div>质量分：{producerResult?.summary?.quality_average_score ?? qualitySummary?.average_score ?? '-'}</div>
                  </div>
                </div>
                <div className="rounded-lg border border-white/10 bg-black/20 p-4">
                  <div className="text-sm font-medium text-white">近期动作</div>
                  <div className="mt-2 space-y-2">
                    {actions.slice(0, 4).map((action) => (
                      <div
                        key={action.code}
                        className={`rounded-lg border px-3 py-2 text-sm ${actionTone[action.status as string] || 'text-white/70 border-white/10 bg-white/5'}`}
                      >
                        <div className="font-medium">{action.label}</div>
                        <div className="text-xs opacity-80">{action.detail}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-lg border border-white/10 bg-black/20 p-4 text-sm text-white/60">
                这里会显示 AI 制片检查、资产定稿、媒体巡检和质量检查的执行结果。先选择工作流，再点击上面的动作按钮。
              </div>
            )}
          </CardContent>
        </Card>

        {/* Batch Operations Panel */}
        <Card className="border-white/10 bg-white/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-white">
              <Layers3 className="h-4 w-4 text-cyan-300" />
              批量操作
              {selectedShotIds.size > 0 && (
                <Badge variant="outline" className="border-cyan-500/25 text-cyan-300 ml-2">
                  已选 {selectedShotIds.size} 个镜头
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Shot Selection Section */}
            <div className="rounded-lg border border-white/10 bg-black/20 p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="text-sm font-medium text-white">选择镜头</div>
                <div className="flex gap-2">
                  <Button size="sm" variant="ghost" className="text-cyan-400" onClick={selectAllShots} disabled={shots.length === 0}>
                    全选
                  </Button>
                  <Button size="sm" variant="ghost" className="text-white/60" onClick={deselectAllShots} disabled={selectedShotIds.size === 0}>
                    取消
                  </Button>
                  {(workflowStatus?.storyboard_id || productionStatus?.storyboard_id) && (
                    <Button size="sm" variant="outline" className="border-white/20" onClick={() => loadShotsForStoryboard(workflowStatus?.storyboard_id || productionStatus?.storyboard_id)} disabled={loadingShots}>
                      {loadingShots ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                      加载镜头
                    </Button>
                  )}
                </div>
              </div>
              {shots.length > 0 ? (
                <div className="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2 max-h-48 overflow-y-auto">
                  {shots.map((shot) => (
                    <div
                      key={shot.id}
                      className={`relative rounded-lg border p-2 cursor-pointer transition-all ${
                        selectedShotIds.has(shot.id)
                          ? 'border-cyan-500 bg-cyan-500/10'
                          : 'border-white/10 bg-white/5 hover:border-white/30'
                      }`}
                      onClick={() => toggleShotSelection(shot.id)}
                    >
                      {shot.image_url && (
                        <img src={toMediaUrl(shot.image_url)} alt={`镜头 ${shot.shot_number}`} className="w-full h-16 object-cover rounded mb-1" />
                      )}
                      {!shot.image_url && (
                        <div className="w-full h-16 bg-white/10 rounded mb-1 flex items-center justify-center">
                          <Film className="h-6 w-6 text-white/30" />
                        </div>
                      )}
                      <div className="text-xs text-center text-white/70">镜头 {shot.shot_number}</div>
                      {selectedShotIds.has(shot.id) && (
                        <div className="absolute top-1 right-1 w-5 h-5 bg-cyan-500 rounded-full flex items-center justify-center">
                          <Check className="h-3 w-3 text-white" />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-white/50 py-4 text-center">
                  {loadingShots ? '加载中...' : '点击"加载镜头"获取分镜下的镜头列表'}
                </div>
              )}
            </div>

            {/* Batch Action Buttons */}
            <div className="flex flex-wrap gap-3">
              <Button
                variant="outline"
                className="border-cyan-500/25 text-cyan-300 hover:bg-cyan-500/10"
                onClick={() => createBatchJob('image')}
                disabled={selectedShotIds.size === 0 || loadingAction?.startsWith('batch-')}
              >
                {loadingAction === 'batch-image' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ImageIcon2 className="mr-2 h-4 w-4" />}
                批量生成参考图
              </Button>
              <Button
                variant="outline"
                className="border-violet-500/25 text-violet-300 hover:bg-violet-500/10"
                onClick={() => createBatchJob('tts')}
                disabled={selectedShotIds.size === 0 || loadingAction?.startsWith('batch-')}
              >
                {loadingAction === 'batch-tts' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Volume2 className="mr-2 h-4 w-4" />}
                批量生成配音
              </Button>
              <Button
                className="bg-gradient-to-r from-cyan-600 to-violet-600 hover:from-cyan-500 hover:to-violet-500"
                onClick={() => createBatchJob('video')}
                disabled={selectedShotIds.size === 0 || loadingAction?.startsWith('batch-')}
              >
                {loadingAction === 'batch-video' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FilmIcon2 className="mr-2 h-4 w-4" />}
                批量生成视频
              </Button>
            </div>

            {/* Batch Job Progress */}
            {activeBatchJob && (
              <div className="rounded-lg border border-cyan-500/25 bg-cyan-500/5 p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-medium text-white">批量任务进度</div>
                  <div className="flex gap-2">
                    {activeBatchJob.status === 'running' && (
                      <Button size="sm" variant="outline" className="border-amber-500/25 text-amber-300" onClick={pauseBatchJob} disabled={loadingAction === 'pause-batch'}>
                        {loadingAction === 'pause-batch' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Pause className="h-3.5 w-3.5" />}
                        暂停
                      </Button>
                    )}
                    {activeBatchJob.status === 'paused' && (
                      <Button size="sm" variant="outline" className="border-emerald-500/25 text-emerald-300" onClick={resumeBatchJob} disabled={loadingAction === 'resume-batch'}>
                        {loadingAction === 'resume-batch' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                        恢复
                      </Button>
                    )}
                    {activeBatchJob.failed_count > 0 && (
                      <Button size="sm" variant="outline" className="border-red-500/25 text-red-300" onClick={retryFailedBatchJob} disabled={loadingAction === 'retry-batch'}>
                        {loadingAction === 'retry-batch' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCw className="h-3.5 w-3.5" />}
                        重试失败
                      </Button>
                    )}
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-white/70">状态</span>
                    <Badge variant="outline" className={
                      activeBatchJob.status === 'completed' ? 'border-emerald-500/25 text-emerald-300' :
                      activeBatchJob.status === 'failed' ? 'border-red-500/25 text-red-300' :
                      activeBatchJob.status === 'paused' ? 'border-amber-500/25 text-amber-300' :
                      'border-cyan-500/25 text-cyan-300'
                    }>
                      {activeBatchJob.status === 'completed' ? '已完成' :
                       activeBatchJob.status === 'failed' ? '失败' :
                       activeBatchJob.status === 'paused' ? '已暂停' :
                       activeBatchJob.status === 'running' ? '进行中' : '待处理'}
                    </Badge>
                  </div>
                  <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-cyan-500 to-violet-500 transition-all duration-300"
                      style={{ width: `${activeBatchJob.progress_percent || 0}%` }}
                    />
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-center text-xs">
                    <div className="rounded bg-black/20 p-2">
                      <div className="text-lg font-bold text-white">{activeBatchJob.succeeded_count || 0}</div>
                      <div className="text-white/50">成功</div>
                    </div>
                    <div className="rounded bg-black/20 p-2">
                      <div className="text-lg font-bold text-amber-300">{activeBatchJob.pending_count || 0}</div>
                      <div className="text-white/50">待处理</div>
                    </div>
                    <div className="rounded bg-black/20 p-2">
                      <div className="text-lg font-bold text-red-300">{activeBatchJob.failed_count || 0}</div>
                      <div className="text-white/50">失败</div>
                    </div>
                    <div className="rounded bg-black/20 p-2">
                      <div className="text-lg font-bold text-white/50">{activeBatchJob.skipped_count || 0}</div>
                      <div className="text-white/50">跳过</div>
                    </div>
                  </div>
                  <div className="text-xs text-white/50 text-center">
                    {activeBatchJob.message}
                  </div>
                </div>
              </div>
            )}

            {/* Recent Batch Jobs */}
            {batchJobs.length > 0 && (
              <div className="rounded-lg border border-white/10 bg-black/20 p-4">
                <div className="text-sm font-medium text-white mb-3">最近批量任务</div>
                <div className="space-y-2">
                  {batchJobs.slice(0, 5).map((job) => (
                    <div
                      key={job.id}
                      className="flex items-center justify-between rounded border border-white/10 bg-white/5 p-3 cursor-pointer hover:bg-white/10"
                      onClick={() => loadBatchJobProgress(job.id)}
                    >
                      <div>
                        <div className="text-sm text-white">{job.title || `批量${job.job_type}`}</div>
                        <div className="text-xs text-white/50">{job.total_count} 项</div>
                      </div>
                      <Badge variant="outline" className={
                        job.status === 'completed' ? 'border-emerald-500/25 text-emerald-300' :
                        job.status === 'failed' ? 'border-red-500/25 text-red-300' :
                        job.status === 'paused' ? 'border-amber-500/25 text-amber-300' :
                        job.status === 'running' ? 'border-cyan-500/25 text-cyan-300' :
                        'border-white/10 text-white/50'
                      }>
                        {job.status === 'completed' ? '完成' :
                         job.status === 'failed' ? '失败' :
                         job.status === 'paused' ? '暂停' :
                         job.status === 'running' ? '进行' :
                         job.status === 'pending' ? '待处理' : job.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
