'use client';

import { Suspense, useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Select } from '@/components/ui/select';
import { MainLayout } from '@/components/layout/main-layout';
import { ModelCapabilitySelector } from '@/components/model-capability-selector';
import { ProductionStatusRail } from '@/components/production/production-status-rail';
import { PreflightIssueList } from '@/components/production/preflight-issue-list';
import { useToast } from '@/components/ui/toast';
import { apiClient } from '@/lib/api-client';
import {
  getDefaultConfigForCapability,
  SavedModelConfig,
} from '@/lib/model-configs';
import {
  createInitialEpisodePreviewStages,
  EpisodePreviewProductionResult,
  EpisodePreviewStage,
  EpisodePreviewStageUpdate,
  runEpisodePreviewProduction,
} from '@/lib/episode-preview-production';
import {
  Workflow as WorkflowIcon,
  Book,
  Users,
  FileText,
  Layers,
  Camera,
  Video,
  Mic,
  Merge,
  Download,
  ChevronRight,
  ChevronLeft,
  Check,
  Loader2,
  AlertCircle,
  Sparkles,
  Play,
  Pause,
  RotateCcw
} from 'lucide-react';

// 工作流步骤定义
const WORKFLOW_STEPS = [
  { id: 'novel', name: '小说', icon: Book, description: '创建或选择小说' },
  { id: 'chapter', name: '章节', icon: Book, description: '创建章节' },
  { id: 'character', name: '角色', icon: Users, description: '创建角色' },
  { id: 'script', name: '剧本', icon: FileText, description: '生成剧本' },
  { id: 'storyboard', name: '分镜', icon: Layers, description: '生成分镜' },
  { id: 'shot', name: '镜头', icon: Camera, description: '编辑镜头' },
  { id: 'video', name: '视频', icon: Video, description: '生成视频' },
  { id: 'tts', name: '语音', icon: Mic, description: '生成TTS' },
  { id: 'synthesis', name: '合成', icon: Merge, description: '音视频合成' },
  { id: 'export', name: '导出', icon: Download, description: '导出最终视频' },
];

const SHORT_VIDEO_ASPECT_RATIO_OPTIONS = [
  { value: '9:16', label: '9:16 竖屏短剧' },
  { value: '16:9', label: '16:9 横屏预告' },
  { value: '1:1', label: '1:1 方形参考' },
  { value: '21:9', label: '21:9 影院宽屏' },
  { value: '4:3', label: '4:3 经典横幅' },
  { value: '3:4', label: '3:4 竖版设定' },
];

const API_ORIGIN = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1').replace(/\/api\/v1\/?$/, '');

const toMediaUrl = (url?: string) => {
  if (!url) return '';
  return url.startsWith('/') ? `${API_ORIGIN}${url}` : url;
};

const buildReadinessItems = (workflowData: WorkflowData): ReadinessItem[] => {
  const mediaCount = workflowData.videoJobIds.length + workflowData.mediaJobIds.length;
  return [
    {
      label: '上游链路',
      ok: Boolean(workflowData.novelId && workflowData.chapterId && workflowData.storyboardId),
      detail: workflowData.novelId && workflowData.chapterId && workflowData.storyboardId
        ? '已绑定小说、章节和分镜'
        : '需要绑定小说、章节和分镜，才能保持人物、场景和事件一致',
    },
    {
      label: '镜头草稿',
      ok: mediaCount > 0,
      detail: mediaCount > 0
        ? `已有 ${workflowData.videoJobIds.length} 个静音视频、${workflowData.mediaJobIds.length} 个直生音视频`
        : '需要生成镜头视频，或一键生成直生音视频草稿',
    },
    {
      label: '音频/配音',
      ok: workflowData.ttsJobIds.length > 0 || workflowData.mediaJobIds.length > 0,
      detail: workflowData.mediaJobIds.length > 0
        ? '直生音视频已包含音频轨'
        : workflowData.ttsJobIds.length > 0
          ? `已有 ${workflowData.ttsJobIds.length} 个配音任务`
          : '分步生成链路需要补齐 TTS 配音',
    },
    {
      label: '字幕轨',
      ok: workflowData.subtitleTrackIds.length > 0 || Boolean(workflowData.renderSrtUrl),
      detail: workflowData.subtitleTrackIds.length > 0
        ? `已有 ${workflowData.subtitleTrackIds.length} 条可导出字幕轨`
        : workflowData.renderSrtUrl
          ? '渲染包已产出 SRT 字幕'
          : '需要从镜头对白、TTS 或直生音视频生成字幕轨',
    },
    {
      label: '连续成片',
      ok: Boolean(workflowData.synthesisManifestUrl),
      detail: workflowData.synthesisManifestUrl
        ? '已生成可审阅的多镜头成片清单'
        : '需要进入合成步骤生成时间线清单',
    },
    {
      label: '渲染包',
      ok: Boolean(workflowData.renderPreviewUrl && workflowData.renderSrtUrl && workflowData.renderTimelineUrl),
      detail: workflowData.renderPreviewUrl
        ? '已生成 HTML 预览、SRT 和时间线 artifact'
        : '生产交付前需要通过预检并生成渲染包',
    },
  ];
};

const getMaxAccessibleStep = (workflowData: WorkflowData, currentStep: number) => {
  let maxStep = Math.max(0, currentStep);
  if (workflowData.novelId) maxStep = Math.max(maxStep, 1);
  if (workflowData.chapterId) maxStep = Math.max(maxStep, 3);
  if (workflowData.scriptId) maxStep = Math.max(maxStep, 4);
  if (workflowData.storyboardId) maxStep = Math.max(maxStep, 6);
  if (workflowData.videoJobIds.length > 0 || workflowData.mediaJobIds.length > 0) maxStep = Math.max(maxStep, 8);
  if (workflowData.synthesisManifestUrl || workflowData.renderPreviewUrl) maxStep = Math.max(maxStep, 9);
  return Math.min(WORKFLOW_STEPS.length - 1, maxStep);
};

// 工作流数据
interface WorkflowData {
  novelId?: string;
  chapterId?: string;
  scriptId?: string;
  storyboardId?: string;
  shotIds: string[];
  videoJobIds: string[];
  ttsJobIds: string[];
  ttsJobs?: any[];
  mediaJobIds: string[];
  subtitleTrackIds: string[];
  synthesisJobIds: string[];
  synthesisJobId?: string;
  synthesisManifestUrl?: string;
  synthesisOutputUrl?: string;
  synthesisSegmentCount?: number;
  synthesisDurationSeconds?: number;
  renderStatus?: string;
  renderPreviewUrl?: string;
  renderSrtUrl?: string;
  renderTimelineUrl?: string;
  renderManifestUrl?: string;
  editableTimelineId?: string;
  editableTimelineClipCount?: number;
  renderIssues?: any[];
  metadata?: any;
}

type ReadinessItem = {
  label: string;
  ok: boolean;
  detail: string;
};

type WorkflowPatchHandler = (patch: Partial<WorkflowData>, stepIndex?: number) => Promise<void>;

export default function WorkflowPage() {
  return (
    <Suspense fallback={
      <MainLayout>
        <div className="p-6 text-white/60">正在加载工作流...</div>
      </MainLayout>
    }>
      <WorkflowPageContent />
    </Suspense>
  );
}

function WorkflowPageContent() {
  const { toast } = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [currentStep, setCurrentStep] = useState(0);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [workflowData, setWorkflowData] = useState<WorkflowData>({
    shotIds: [],
    videoJobIds: [],
    ttsJobIds: [],
    ttsJobs: [],
    mediaJobIds: [],
    subtitleTrackIds: [],
    synthesisJobIds: [],
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modelConfigs, setModelConfigs] = useState<SavedModelConfig[]>([]);
  const [textModelConfigId, setTextModelConfigId] = useState('');
  const [videoModelConfigId, setVideoModelConfigId] = useState('');
  const [audioModelConfigId, setAudioModelConfigId] = useState('');
  const [imageModelConfigId, setImageModelConfigId] = useState('');
  const [productionRefreshToken, setProductionRefreshToken] = useState(0);
  const [previewStages, setPreviewStages] = useState<EpisodePreviewStage[]>(() => createInitialEpisodePreviewStages());
  const [previewResult, setPreviewResult] = useState<EpisodePreviewProductionResult | null>(null);
  const [isPreviewProducing, setIsPreviewProducing] = useState(false);
  const maxAccessibleStep = getMaxAccessibleStep(workflowData, currentStep);
  const workflowDataRef = useRef(workflowData);
  const currentStepRef = useRef(currentStep);

  useEffect(() => {
    workflowDataRef.current = workflowData;
  }, [workflowData]);

  useEffect(() => {
    currentStepRef.current = currentStep;
  }, [currentStep]);

  useEffect(() => {
    loadModelConfigs();
  }, []);

  const loadModelConfigs = async () => {
    try {
      const configs = await apiClient.getLLMConfigs();
      const list = Array.isArray(configs) ? configs : [];
      setModelConfigs(list);
      const textDefault = getDefaultConfigForCapability(list, 'text');
      const imageDefault = getDefaultConfigForCapability(list, 'image');
      const videoDefault = getDefaultConfigForCapability(list, 'video');
      const audioDefault = getDefaultConfigForCapability(list, 'audio');
      if (textDefault) setTextModelConfigId(textDefault.id);
      if (imageDefault) setImageModelConfigId(imageDefault.id);
      if (videoDefault) setVideoModelConfigId(videoDefault.id);
      if (audioDefault) setAudioModelConfigId(audioDefault.id);
    } catch (err) {
      console.error('加载模型配置失败:', err);
    }
  };

  const persistWorkflowPatch = useCallback(async (patch: Partial<WorkflowData>, stepIndex?: number) => {
    setWorkflowData(prev => ({ ...prev, ...patch }));
    if (typeof stepIndex === 'number') {
      setCurrentStep(stepIndex);
    }
    if (!workflowId) return;

    const nextData = { ...workflowDataRef.current, ...patch };
    const nextStep = typeof stepIndex === 'number' ? stepIndex : currentStepRef.current;
    try {
      await apiClient.updateWorkflowStep(workflowId, {
        current_step: nextStep + 1,
        completed_steps: Array.from(new Set(
          Array.from({ length: nextStep + 1 }, (_, index) => index + 1)
        )),
        novel_id: nextData.novelId || '',
        chapter_id: nextData.chapterId || '',
        script_id: nextData.scriptId || '',
        storyboard_id: nextData.storyboardId || '',
      });
    } catch (err) {
      console.error('保存工作流链路失败:', err);
    }
  }, [workflowId]);

  // 创建新工作流
  const createWorkflow = async (title: string) => {
    try {
      setIsLoading(true);
      const result = await apiClient.startWorkflow({
        title: title || `工作流 ${new Date().toLocaleString()}`
      });
      setWorkflowId(result.workflow_id);
      return result.workflow_id;
    } catch (err: any) {
      console.error('创建工作流失败:', err);
      setError(err.message || '创建工作流失败');
      return null;
    } finally {
      setIsLoading(false);
    }
  };

  // 获取工作流状态
  const refreshWorkflowStatus = useCallback(async () => {
    if (!workflowId) return;

    try {
      const status = await apiClient.getWorkflowStatus(workflowId, {
        novel_id: workflowData.novelId,
        chapter_id: workflowData.chapterId,
        script_id: workflowData.scriptId,
        storyboard_id: workflowData.storyboardId,
      });
      const activeNovelId = workflowData.novelId || status.novel_id;
      const activeChapterId = workflowData.chapterId || status.chapter_id;
      const activeScriptId = workflowData.scriptId || status.script_id;
      const activeStoryboardId = workflowData.storyboardId || status.storyboard_id;
      if (typeof status.current_step === 'number') {
        setCurrentStep(prev => Math.max(prev, Math.min(WORKFLOW_STEPS.length - 1, status.current_step - 1)));
      }
      setWorkflowData(prev => ({
        ...prev,
        novelId: prev.novelId || status.novel_id,
        chapterId: prev.chapterId || status.chapter_id,
        scriptId: prev.scriptId || status.script_id,
        storyboardId: prev.storyboardId || status.storyboard_id,
        metadata: status.metadata || prev.metadata,
      }));
      // 更新工作流数据（客户端按 novel_id/script_id 过滤）
      if (status.video_jobs) {
        const filtered = status.video_jobs.filter((v: any) =>
          (!activeScriptId || v.script_id === activeScriptId) &&
          (!activeNovelId || v.novel_id === activeNovelId) &&
          (!activeChapterId || v.chapter_id === activeChapterId) &&
          (!activeStoryboardId || v.storyboard_id === activeStoryboardId)
        );
        setWorkflowData(prev => ({
          ...prev,
          videoJobIds: filtered.map((v: any) => v.id),
        }));
      }
      if (status.tts_jobs) {
        const filtered = status.tts_jobs.filter((t: any) =>
          (!activeScriptId || t.script_id === activeScriptId) &&
          (!activeChapterId || t.chapter_id === activeChapterId) &&
          (!activeStoryboardId || t.storyboard_id === activeStoryboardId)
        );
        setWorkflowData(prev => ({
          ...prev,
          ttsJobIds: filtered.map((t: any) => t.id),
          ttsJobs: filtered,
        }));
      }
      if (status.media_jobs) {
        const filtered = status.media_jobs.filter((job: any) =>
          (!activeNovelId || job.novel_id === activeNovelId) &&
          (!activeChapterId || job.chapter_id === activeChapterId) &&
          (!activeScriptId || job.script_id === activeScriptId) &&
          (!activeStoryboardId || job.storyboard_id === activeStoryboardId)
        );
        setWorkflowData(prev => ({
          ...prev,
          mediaJobIds: filtered.map((job: any) => job.id),
        }));
      }
      if (status.subtitle_tracks) {
        const filtered = status.subtitle_tracks.filter((track: any) =>
          (!activeNovelId || track.novel_id === activeNovelId) &&
          (!activeChapterId || track.chapter_id === activeChapterId) &&
          (!activeScriptId || track.script_id === activeScriptId) &&
          (!activeStoryboardId || track.storyboard_id === activeStoryboardId)
        );
        setWorkflowData(prev => ({
          ...prev,
          subtitleTrackIds: filtered.map((track: any) => track.id),
        }));
      }
      if (status.synthesis_jobs) {
        const latest = status.synthesis_jobs[0];
        setWorkflowData(prev => ({
          ...prev,
          synthesisJobIds: status.synthesis_jobs.map((job: any) => job.id),
          synthesisJobId: latest?.id || prev.synthesisJobId,
          synthesisManifestUrl: latest?.manifest_url || latest?.extra_data?.manifest_url || prev.synthesisManifestUrl,
          synthesisOutputUrl: latest?.output_url || latest?.extra_data?.output_url || prev.synthesisOutputUrl,
          synthesisSegmentCount: latest?.segment_count || latest?.extra_data?.segment_count || prev.synthesisSegmentCount,
          synthesisDurationSeconds: latest?.duration_seconds || latest?.extra_data?.duration_seconds || prev.synthesisDurationSeconds,
          renderStatus: latest?.extra_data?.render_status || prev.renderStatus,
          renderPreviewUrl: latest?.extra_data?.render_artifacts?.preview_url || prev.renderPreviewUrl,
          renderSrtUrl: latest?.extra_data?.render_artifacts?.srt_url || prev.renderSrtUrl,
          renderTimelineUrl: latest?.extra_data?.render_artifacts?.timeline_url || prev.renderTimelineUrl,
          renderManifestUrl: latest?.extra_data?.render_artifacts?.render_manifest_url || prev.renderManifestUrl,
          editableTimelineId: latest?.extra_data?.timeline_id || status.metadata?.latest_timeline_id || prev.editableTimelineId,
          editableTimelineClipCount: latest?.extra_data?.timeline_clip_count || prev.editableTimelineClipCount,
          renderIssues: latest?.extra_data?.render_issues || prev.renderIssues,
        }));
      }
    } catch (err) {
      console.error('刷新工作流状态失败:', err);
    }
  }, [workflowId, workflowData.novelId, workflowData.chapterId, workflowData.scriptId, workflowData.storyboardId]);

  // 初始化工作流
  useEffect(() => {
    const urlWorkflowId = searchParams.get('workflow_id');
    if (urlWorkflowId && workflowId !== urlWorkflowId) {
      setWorkflowId(urlWorkflowId);
    }
  }, [searchParams, workflowId]);

  // 定期刷新状态
  useEffect(() => {
    if (workflowId) {
      refreshWorkflowStatus();
      const interval = setInterval(refreshWorkflowStatus, 10000);
      return () => clearInterval(interval);
    }
  }, [workflowId, refreshWorkflowStatus]);

  // 下一步
  const handleNext = () => {
    if (currentStep < WORKFLOW_STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  // 上一步
  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  // 跳转到指定步骤
  const handleGoToStep = (step: number) => {
    if (step >= 0 && step < WORKFLOW_STEPS.length) {
      setCurrentStep(step);
    }
  };

  // 完成最终视频拼接
  const handleConcatenate = async () => {
    if (workflowData.videoJobIds.length === 0 && workflowData.mediaJobIds.length === 0) {
      setError('请先生成静音视频或直生音视频草稿');
      return;
    }

    try {
      setIsLoading(true);
      const result = await apiClient.concatenateVideos(workflowId!, {
        video_job_ids: workflowData.videoJobIds,
        media_job_ids: workflowData.mediaJobIds,
        tts_job_ids: workflowData.ttsJobIds,
        title: '最终视频',
        transition_style: 'fade',
        include_subtitles: true,
        subtitle_mode: 'dialogue',
        audio_mix_strategy: 'match_by_shot',
        quality_profile: 'review',
      });
      setCurrentStep(8);
      setWorkflowData(prev => ({
        ...prev,
        synthesisJobId: result.job_id,
        synthesisManifestUrl: result.manifest_url,
        synthesisOutputUrl: result.output_url,
        synthesisSegmentCount: result.segment_count,
        synthesisDurationSeconds: result.duration_seconds,
      }));
      toast({ title: '连续成片编排已完成', description: '请在合成步骤生成渲染包。', type: 'success' });
    } catch (err: any) {
      console.error('拼接失败:', err);
      setError(err.message || '视频拼接失败');
    } finally {
      setIsLoading(false);
    }
  };

  const updatePreviewStage = (stage: EpisodePreviewStageUpdate) => {
    setPreviewStages((prev) =>
      prev.map((item) => item.key === stage.key ? { ...item, ...stage } : item)
    );
  };

  const handlePreviewProduction = async () => {
    if (!workflowId) {
      toast({ title: '工作流未初始化', description: '请稍后刷新后再试。', type: 'info' });
      return;
    }
    if (!workflowData.novelId || !workflowData.chapterId) {
      toast({ title: '请先选择小说和章节', description: '本集草片必须绑定具体小说章节，才能保持剧情、人物和场景一致。', type: 'info' });
      setCurrentStep(!workflowData.novelId ? 0 : 1);
      return;
    }
    setIsPreviewProducing(true);
    setPreviewResult(null);
    setPreviewStages(createInitialEpisodePreviewStages());
    setError(null);
    try {
      const result = await runEpisodePreviewProduction({
        workflowId,
        novelId: workflowData.novelId,
        chapterId: workflowData.chapterId,
        scriptId: workflowData.scriptId,
        storyboardId: workflowData.storyboardId,
        textModelConfigId: textModelConfigId || undefined,
        videoModelConfigId: videoModelConfigId || undefined,
        audioModelConfigId: audioModelConfigId || undefined,
        generationStrategy: 'separate_video_tts',
        onStage: updatePreviewStage,
      });
      setPreviewResult(result);
      setWorkflowData(prev => ({
        ...prev,
        scriptId: result.scriptId || prev.scriptId,
        storyboardId: result.storyboardId || prev.storyboardId,
        videoJobIds: Array.from(new Set<string>([...(prev.videoJobIds || []), ...result.videoJobIds])),
        ttsJobIds: Array.from(new Set<string>([...(prev.ttsJobIds || []), ...result.ttsJobIds])),
        mediaJobIds: Array.from(new Set<string>([...(prev.mediaJobIds || []), ...result.mediaJobIds])),
        subtitleTrackIds: Array.from(new Set<string>([...(prev.subtitleTrackIds || []), ...result.subtitleTrackIds])),
        synthesisJobId: result.synthesisJobId,
        synthesisManifestUrl: result.manifestUrl,
        synthesisOutputUrl: result.outputUrl,
        renderPreviewUrl: result.previewUrl,
        renderSrtUrl: result.srtUrl,
        renderTimelineUrl: result.timelineUrl,
        renderManifestUrl: result.renderManifestUrl,
      }));
      setCurrentStep(result.readyForConcatenate === false ? 6 : 8);
      setProductionRefreshToken((value) => value + 1);
      await refreshWorkflowStatus();
      toast({
        title: result.readyForConcatenate === false ? '视频/声音任务已提交' : '本集草片已生成',
        description: result.readyForConcatenate === false ? '等待云端生成完成后再合成。' : '已生成预览、字幕和时间线包。',
        type: 'success',
      });
    } catch (err: any) {
      const message = err.message || '本集草片生成失败';
      setError(message);
      toast({ title: '生成失败', description: message, type: 'error' });
    } finally {
      setIsPreviewProducing(false);
    }
  };

  const step = WORKFLOW_STEPS[currentStep];
  const Icon = step.icon;
  const readinessItems = buildReadinessItems(workflowData);
  const productionIssues = [
    ...(workflowData.renderIssues || []),
    ...readinessItems
      .filter((item) => !item.ok)
      .map((item) => ({
        code: `workflow_${item.label}`,
        message: item.detail,
        severity: item.label === '渲染包' || item.label === '连续成片' ? 'warning' : 'blocking',
      })),
  ];

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <WorkflowIcon className="w-6 h-6" />
              AI 视频创作工作流
            </h1>
            <p className="text-white/60 mt-1">
              从小说到视频的完整创作流程
              {workflowId && <span className="ml-2 text-white/40">ID: {workflowId.slice(0, 8)}...</span>}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => router.push('/dashboard')}
              className="border-white/20"
            >
              返回首页
            </Button>
            <Button
              variant="outline"
              onClick={refreshWorkflowStatus}
              className="border-white/20"
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              刷新
            </Button>
            <Button
              asChild
              variant="outline"
              className="border-white/20"
            >
              <Link href="/producer">
                AI制片中心
                <Sparkles className="w-4 h-4 ml-2" />
              </Link>
            </Button>
          </div>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="p-4 bg-red-500/20 border border-red-500/30 rounded-lg text-red-300 flex items-center gap-2">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setError(null)}
              className="ml-auto underline"
            >
              关闭
            </button>
          </div>
        )}

        {!workflowId && (
          <Card className="border-cyan-500/20 bg-cyan-500/10">
            <CardContent className="p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-base font-semibold text-cyan-50">
                    <WorkflowIcon className="h-5 w-5" />
                    选择或创建本集工程
                  </div>
                  <p className="mt-2 max-w-3xl text-sm leading-6 text-white/65">
                    工作流需要绑定小说、章节、剧本和分镜后再继续生成。系统不会再自动创建空工程，避免流程回到起点或产生无关联任务。
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <Badge variant="outline" className="border-white/10 text-white/70">推荐：从 AI 制片中心选择小说章节</Badge>
                    <Badge variant="outline" className="border-white/10 text-white/70">可选：创建空白工程后手动绑定</Badge>
                  </div>
                </div>
                <div className="flex flex-col gap-2 sm:flex-row lg:flex-col">
                  <Button asChild className="bg-cyan-600 hover:bg-cyan-700">
                    <Link href="/producer">
                      <Sparkles className="mr-2 h-4 w-4" />
                      去 AI 制片中心
                    </Link>
                  </Button>
                  <Button
                    variant="outline"
                    className="border-white/20"
                    disabled={isLoading}
                    onClick={() => createWorkflow('空白制片工程')}
                  >
                    {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <WorkflowIcon className="mr-2 h-4 w-4" />}
                    创建空白工程
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {workflowId && (
          <ProductionStatusRail
            workflowId={workflowId}
            items={readinessItems}
            issues={productionIssues}
            title="本集生产状态"
            subtitle="生成前先确认小说链路、镜头、音频、字幕、连续成片和渲染包；缺项可回到 AI 制片中心补齐。"
          />
        )}

        <Card className="border-violet-500/20 bg-violet-500/10">
          <CardContent className="p-4">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-sm font-medium text-violet-100">
                  <Sparkles className="h-4 w-4" />
                  本集草片一键生成
                </div>
                <p className="mt-1 text-sm leading-6 text-white/65">
                  按当前小说、章节、剧本、分镜、镜头、对白、字幕和资产锁生成短视频草片；默认使用“视频模型 + 声音模型”分步生成，缺剧本或分镜时会先自动补齐。
                </p>
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  <Badge variant="outline" className="border-white/10 text-white/70">
                    小说 {workflowData.novelId ? '已绑定' : '未选择'}
                  </Badge>
                  <Badge variant="outline" className="border-white/10 text-white/70">
                    章节 {workflowData.chapterId ? '已绑定' : '未选择'}
                  </Badge>
                  <Badge variant="outline" className="border-white/10 text-white/70">
                    分镜 {workflowData.storyboardId ? '已绑定' : '可自动生成'}
                  </Badge>
                  <Badge variant="outline" className="border-white/10 text-white/70">
                    字幕 {workflowData.subtitleTrackIds.length || 0} 条
                  </Badge>
                </div>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row xl:flex-col">
                <Button
                  onClick={handlePreviewProduction}
                  disabled={isPreviewProducing || !workflowId}
                  className="bg-violet-600 hover:bg-violet-700"
                >
                  {isPreviewProducing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
                  一键生成本集草片
                </Button>
                <Button
                  asChild
                  variant="outline"
                  className="border-white/20"
                >
                  <Link href={workflowId ? `/producer?workflow_id=${workflowId}` : '/producer'}>
                    打开 AI 制片中心
                  </Link>
                </Button>
              </div>
            </div>
            <div className="mt-4 grid gap-2 md:grid-cols-3 xl:grid-cols-9">
              {previewStages.map((stage) => (
                <div
                  key={stage.key}
                  className={`rounded-lg border p-2 text-xs leading-5 ${
                    stage.status === 'done'
                      ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-50'
                      : stage.status === 'failed'
                        ? 'border-red-500/25 bg-red-500/10 text-red-50'
                        : stage.status === 'running'
                          ? 'border-violet-400/30 bg-violet-500/15 text-violet-50'
                          : 'border-white/10 bg-black/20 text-white/50'
                  }`}
                >
                  <div className="flex items-center gap-1.5 font-medium">
                    {stage.status === 'running' && <Loader2 className="h-3 w-3 animate-spin" />}
                    {stage.status === 'done' && <Check className="h-3 w-3" />}
                    {stage.status === 'failed' && <AlertCircle className="h-3 w-3" />}
                    {stage.label}
                  </div>
                  <div className="mt-1 line-clamp-2 opacity-75">{stage.message}</div>
                </div>
              ))}
            </div>
            {previewResult?.previewUrl && (
              <div className="mt-3 flex flex-wrap gap-2">
                <Button asChild size="sm" className="bg-emerald-600 hover:bg-emerald-700">
                  <a href={toMediaUrl(previewResult.previewUrl)} target="_blank" rel="noreferrer">
                    打开草片预览
                  </a>
                </Button>
                {previewResult.srtUrl && (
                  <Button asChild size="sm" variant="outline" className="border-white/20">
                    <a href={toMediaUrl(previewResult.srtUrl)} target="_blank" rel="noreferrer">查看字幕</a>
                  </Button>
                )}
                {previewResult.timelineUrl && (
                  <Button asChild size="sm" variant="outline" className="border-white/20">
                    <a href={toMediaUrl(previewResult.timelineUrl)} target="_blank" rel="noreferrer">查看时间线</a>
                  </Button>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* 左侧：步骤进度 */}
          <div className="lg:col-span-1">
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white text-lg">创作步骤</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-1">
                  {WORKFLOW_STEPS.map((s, idx) => {
                    const StepIcon = s.icon;
                    const isCompleted = idx < currentStep;
                    const isCurrent = idx === currentStep;
                    const isLocked = idx > maxAccessibleStep;

                    return (
                      <button
                        type="button"
                        key={s.id}
                        onClick={() => !isLocked && handleGoToStep(idx)}
                        disabled={isLocked}
                        className={`w-full flex items-center gap-3 p-3 rounded-lg transition-colors text-left ${
                          isCurrent
                            ? 'bg-violet-500/20 border border-violet-500/50'
                            : isCompleted
                            ? 'bg-green-500/10 border border-green-500/30 hover:bg-green-500/20'
                            : 'hover:bg-white/5 border border-transparent'
                        } ${isLocked ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                      >
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                          isCurrent
                            ? 'bg-violet-500 text-white'
                            : isCompleted
                            ? 'bg-green-500 text-white'
                            : 'bg-white/10 text-white/40'
                        }`}>
                          {isCompleted ? (
                            <Check className="w-4 h-4" />
                          ) : (
                            <StepIcon className="w-4 h-4" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className={`font-medium truncate ${
                            isCurrent ? 'text-white' : isCompleted ? 'text-green-300' : 'text-white/60'
                          }`}>
                            {idx + 1}. {s.name}
                          </div>
                          <div className="text-xs text-white/40 truncate">
                            {s.description}
                          </div>
                        </div>
                        {isCurrent && <ChevronRight className="w-4 h-4 text-violet-400" />}
                      </button>
                    );
                  })}
                </div>

                {/* 进度统计 */}
                <div className="mt-4 pt-4 border-t border-white/10">
                  <div className="text-sm text-white/60 mb-2">完成进度</div>
                  <div className="w-full h-2 bg-white/10 rounded-full">
                    <div
                      className="h-full bg-violet-500 rounded-full transition-[width]"
                      style={{ width: `${(currentStep / WORKFLOW_STEPS.length) * 100}%` }}
                    />
                  </div>
                  <div className="text-xs text-white/40 mt-1">
                    {currentStep} / {WORKFLOW_STEPS.length} 步骤完成
                  </div>
                </div>
              </CardContent>
            </Card>

            <ProductionControlPanel
              workflowId={workflowId}
              workflowData={workflowData}
              currentStep={currentStep}
              refreshToken={productionRefreshToken}
              onRefreshWorkflow={async () => {
                setProductionRefreshToken((value) => value + 1);
                await refreshWorkflowStatus();
              }}
            />
            <ShortVideoProductionPanel workflowId={workflowId} workflowData={workflowData} />

            {/* 快捷链接 */}
            <Card className="bg-white/5 border-white/10 mt-4">
              <CardHeader>
                <CardTitle className="text-white text-sm">快捷入口</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Button
                  variant="ghost"
                  className="w-full justify-start text-white/70 hover:text-white"
                  onClick={() => router.push('/novels')}
                >
                  <Book className="w-4 h-4 mr-2" />
                  小说管理
                </Button>
                <Button
                  variant="ghost"
                  className="w-full justify-start text-white/70 hover:text-white"
                  onClick={() => router.push('/characters')}
                >
                  <Users className="w-4 h-4 mr-2" />
                  角色管理
                </Button>
                <Button
                  variant="ghost"
                  className="w-full justify-start text-white/70 hover:text-white"
                  onClick={() => router.push('/video-generation')}
                >
                  <Video className="w-4 h-4 mr-2" />
                  视频生成
                </Button>
                <Button
                  variant="ghost"
                  className="w-full justify-start text-white/70 hover:text-white"
                  onClick={() => router.push('/tts')}
                >
                  <Mic className="w-4 h-4 mr-2" />
                  TTS 语音
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* 右侧：步骤内容 */}
          <div className="lg:col-span-3">
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Icon className="w-5 h-5" />
                  {step.name}
                  <span className="text-white/40 text-sm font-normal ml-2">
                    第 {currentStep + 1} 步，共 {WORKFLOW_STEPS.length} 步
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* 步骤内容区域 */}
                <div className="min-h-[400px]">
                  {currentStep === 0 && (
                    <NovelStep
                      workflowData={workflowData}
                      onPatchWorkflow={persistWorkflowPatch}
                    />
                  )}
                  {currentStep === 1 && (
                    <ChapterStep
                      workflowData={workflowData}
                      onPatchWorkflow={persistWorkflowPatch}
                    />
                  )}
                  {currentStep === 2 && (
                    <CharacterStep
                      workflowData={workflowData}
                      onPatchWorkflow={persistWorkflowPatch}
                      modelConfigs={modelConfigs}
                      textModelConfigId={textModelConfigId}
                      imageModelConfigId={imageModelConfigId}
                      onTextModelConfigChange={setTextModelConfigId}
                      onImageModelConfigChange={setImageModelConfigId}
                    />
                  )}
                  {currentStep === 3 && (
                    <ScriptStep
                      workflowData={workflowData}
                      onPatchWorkflow={persistWorkflowPatch}
                      modelConfigs={modelConfigs}
                      textModelConfigId={textModelConfigId}
                      onTextModelConfigChange={setTextModelConfigId}
                    />
                  )}
                  {currentStep === 4 && (
                    <StoryboardStep
                      workflowData={workflowData}
                      onPatchWorkflow={persistWorkflowPatch}
                      modelConfigs={modelConfigs}
                      textModelConfigId={textModelConfigId}
                      onTextModelConfigChange={setTextModelConfigId}
                    />
                  )}
                  {currentStep === 5 && (
                    <ShotStep
                      workflowData={workflowData}
                      onPatchWorkflow={persistWorkflowPatch}
                    />
                  )}
                  {currentStep === 6 && (
                    <VideoStep
                      workflowId={workflowId}
                      workflowData={workflowData}
                      setWorkflowData={setWorkflowData}
                      onVideoGenerated={refreshWorkflowStatus}
                      modelConfigs={modelConfigs}
                      videoModelConfigId={videoModelConfigId}
                      onVideoModelConfigChange={setVideoModelConfigId}
                      audioModelConfigId={audioModelConfigId}
                      onAudioModelConfigChange={setAudioModelConfigId}
                    />
                  )}
                  {currentStep === 7 && (
                    <TTSStep
                      workflowData={workflowData}
                      setWorkflowData={setWorkflowData}
                      onTTSGenerated={refreshWorkflowStatus}
                      modelConfigs={modelConfigs}
                      audioModelConfigId={audioModelConfigId}
                      onAudioModelConfigChange={setAudioModelConfigId}
                    />
                  )}
                  {currentStep === 8 && (
                    <SynthesisStep
                      workflowId={workflowId}
                      workflowData={workflowData}
                      onSynthesisComplete={refreshWorkflowStatus}
                    />
                  )}
                  {currentStep === 9 && (
                    <ExportStep
                      workflowData={workflowData}
                    />
                  )}
                </div>

                {/* 步骤导航 */}
                <div className="flex items-center justify-between pt-4 border-t border-white/10">
                  <Button
                    variant="outline"
                    onClick={handlePrevious}
                    disabled={currentStep === 0}
                    className="border-white/20"
                  >
                    <ChevronLeft className="w-4 h-4 mr-2" />
                    上一步
                  </Button>

                  <div className="flex gap-2">
                    {currentStep === 8 && (workflowData.videoJobIds.length > 0 || workflowData.mediaJobIds.length > 0) && (
                      <Button
                        onClick={handleConcatenate}
                        disabled={isLoading}
                        className="bg-green-600 hover:bg-green-700"
                      >
                        <Merge className="w-4 h-4 mr-2" />
                        {isLoading ? '处理中…' : '合成最终视频'}
                      </Button>
                    )}

                    <Button
                      onClick={handleNext}
                      disabled={currentStep === WORKFLOW_STEPS.length - 1}
                      className="bg-violet-600 hover:bg-violet-700"
                    >
                      下一步
                      <ChevronRight className="w-4 h-4 ml-2" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}

// ========== 步骤组件 ==========

function ProductionReadinessPanel({ workflowData, currentStep }: { workflowData: WorkflowData; currentStep: number }) {
  const items = buildReadinessItems(workflowData);
  const readyCount = items.filter((item) => item.ok).length;

  return (
    <Card className="bg-white/5 border-white/10 mt-4">
      <CardHeader>
        <CardTitle className="text-white text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-violet-300" />
          生产就绪检查
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="text-xs text-white/50">
          {readyCount} / {items.length} 项就绪，当前第 {currentStep + 1} 步
        </div>
        <div className="space-y-2">
          {items.map((item) => (
            <div key={item.label} className="rounded border border-white/10 bg-white/5 p-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-white/80">{item.label}</span>
                <span className={`text-xs ${item.ok ? 'text-green-300' : 'text-yellow-300'}`}>
                  {item.ok ? '就绪' : '待处理'}
                </span>
              </div>
              <div className="mt-1 text-xs text-white/40 leading-5">{item.detail}</div>
            </div>
          ))}
        </div>
        <div className="rounded border border-yellow-500/20 bg-yellow-500/10 p-2 text-xs text-yellow-100 leading-5">
          当前本地 DEV_MODE 可验证完整流程；真实供应商直生音视频、FFmpeg/云剪辑转码和字幕烧录仍需生产环境适配。
        </div>
      </CardContent>
    </Card>
  );
}

function ProductionControlPanel({
  workflowId,
  workflowData,
  currentStep,
  refreshToken,
  onRefreshWorkflow,
}: {
  workflowId: string | null;
  workflowData: WorkflowData;
  currentStep: number;
  refreshToken: number;
  onRefreshWorkflow?: () => Promise<void> | void;
}) {
  const { toast } = useToast();
  const items = buildReadinessItems(workflowData);
  const readyCount = items.filter((item) => item.ok).length;
  const [loadingAction, setLoadingAction] = useState('');
  const [assistant, setAssistant] = useState<any>(null);
  const [pack, setPack] = useState<any>(null);
  const [mediaAudit, setMediaAudit] = useState<any>(null);
  const [quality, setQuality] = useState<any>(null);
  const canUseWorkflow = Boolean(workflowId);

  const runAction = async (action: string, fn: () => Promise<any>, successTitle: string) => {
    if (!workflowId) {
      toast({ title: '工作流未初始化', description: '请先创建或打开一个工作流。', type: 'info' });
      return;
    }
    setLoadingAction(action);
    try {
      const result = await fn();
      if (action === 'assistant' || action === 'assistant-auto') setAssistant(result);
      if (action === 'pack') setPack(result.production_pack || result);
      if (action === 'media') setMediaAudit(result);
      if (action === 'quality') setQuality(result);
      toast({ title: successTitle, type: 'success' });
      await onRefreshWorkflow?.();
    } catch (err: any) {
      toast({ title: successTitle.replace('已', '失败：'), description: err.message || '请稍后重试。', type: 'error' });
    } finally {
      setLoadingAction('');
    }
  };

  const loadAssistant = useCallback(async () => {
    if (!workflowId) return;
    try {
      const data = await apiClient.runProducerAssistant(workflowId, { auto_fix: false });
      setAssistant(data);
    } catch (err) {
      console.error('加载 AI 制片助手失败:', err);
    }
  }, [workflowId]);

  useEffect(() => {
    loadAssistant();
  }, [loadAssistant, refreshToken]);

  const nextAction = assistant?.summary?.next_action;
  const qualitySummary = quality?.summary || assistant?.quality;
  const mediaSummary = mediaAudit?.summary || assistant?.media_audit;
  const packSummary = pack?.summary;

  return (
    <Card className="bg-white/5 border-white/10 mt-4">
      <CardHeader>
        <CardTitle className="text-white text-sm flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-cyan-300" />
          AI 制片控制台
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="rounded border border-white/10 bg-white/5 p-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-white/70">基础流程</span>
            <span className={readyCount >= items.length ? 'text-green-300' : 'text-yellow-300'}>
              {readyCount} / {items.length}
            </span>
          </div>
          <div className="mt-2 space-y-1">
            {items.slice(0, 4).map((item) => (
              <div key={item.label} className="flex items-start justify-between gap-2 text-xs">
                <span className="text-white/60">{item.label}</span>
                <span className={item.ok ? 'text-green-300' : 'text-yellow-300'}>{item.ok ? '就绪' : '待补'}</span>
              </div>
            ))}
          </div>
          <div className="mt-2 text-xs text-white/35">当前第 {currentStep + 1} 步</div>
        </div>

        {nextAction && (
          <div className="rounded border border-cyan-500/25 bg-cyan-500/10 p-2 text-xs leading-5">
            <div className="text-cyan-100 font-medium">下一步：{nextAction.label}</div>
            <div className="text-white/60">{nextAction.detail}</div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={!canUseWorkflow || Boolean(loadingAction)}
            onClick={() => runAction('assistant', () => apiClient.runProducerAssistant(workflowId as string, { auto_fix: false }), 'AI 制片检查已完成')}
            className="border-white/20 text-xs"
          >
            {loadingAction === 'assistant' ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <AlertCircle className="w-3 h-3 mr-1" />}
            制片检查
          </Button>
          <Button
            size="sm"
            disabled={!canUseWorkflow || Boolean(loadingAction)}
            onClick={() => runAction('assistant-auto', () => apiClient.runProducerAssistant(workflowId as string, { auto_fix: true }), '安全补齐已执行')}
            className="bg-cyan-600 hover:bg-cyan-700 text-xs"
          >
            {loadingAction === 'assistant-auto' ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Sparkles className="w-3 h-3 mr-1" />}
            AI 补齐
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!canUseWorkflow || !workflowData.novelId || Boolean(loadingAction)}
            onClick={() => runAction('pack', () => apiClient.applyWorkflowAssetLocks(workflowId as string, { create_missing_assets: true, persist: true }), '资产锁已应用')}
            className="border-white/20 text-xs"
          >
            {loadingAction === 'pack' ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Layers className="w-3 h-3 mr-1" />}
            资产定稿
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!canUseWorkflow || Boolean(loadingAction)}
            onClick={() => runAction('media', () => apiClient.auditWorkflowMedia(workflowId as string, { persist_remote: true, dry_run: false }), '媒体巡检已完成')}
            className="border-white/20 text-xs"
          >
            {loadingAction === 'media' ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Video className="w-3 h-3 mr-1" />}
            媒体巡检
          </Button>
        </div>

        <Button
          size="sm"
          variant="outline"
          disabled={!canUseWorkflow || Boolean(loadingAction)}
          onClick={() => runAction('quality', () => apiClient.checkWorkflowProductionQuality(workflowId as string, { persist: true }), '质量检查已完成')}
          className="w-full border-white/20 text-xs"
        >
          {loadingAction === 'quality' ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Check className="w-3 h-3 mr-1" />}
          生产质量检查
        </Button>

        <div className="grid grid-cols-3 gap-2 text-xs">
          <div className="rounded border border-white/10 bg-white/5 p-2">
            <div className="text-white/40">资产锁</div>
            <div className="mt-1 text-white">{packSummary?.lock_count ?? workflowData.metadata?.production_pack?.lock_count ?? '-'}</div>
          </div>
          <div className="rounded border border-white/10 bg-white/5 p-2">
            <div className="text-white/40">媒体缺失</div>
            <div className="mt-1 text-white">{mediaSummary?.missing_count ?? '-'}</div>
          </div>
          <div className="rounded border border-white/10 bg-white/5 p-2">
            <div className="text-white/40">质量分</div>
            <div className="mt-1 text-white">{qualitySummary?.average_score ?? '-'}</div>
          </div>
        </div>

        {Array.isArray(assistant?.actions) && assistant.actions.length > 0 && (
          <div className="space-y-1">
            {assistant.actions.slice(0, 3).map((action: any) => (
              <div key={action.code} className="rounded border border-yellow-500/20 bg-yellow-500/10 p-2 text-xs text-yellow-100 leading-5">
                {action.label}：{action.detail}
              </div>
            ))}
          </div>
        )}

        {Array.isArray(assistant?.executed) && assistant.executed.length > 0 && (
          <div className="rounded border border-green-500/20 bg-green-500/10 p-2 text-xs text-green-100">
            已自动执行 {assistant.executed.length} 项安全补齐。
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ShortVideoProductionPanel({
  workflowId,
  workflowData,
}: {
  workflowId: string | null;
  workflowData: WorkflowData;
}) {
  const [targetDuration, setTargetDuration] = useState(60);
  const [aspectRatio, setAspectRatio] = useState('9:16');
  const [selectedStyleAssetId, setSelectedStyleAssetId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [readiness, setReadiness] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const canCheck = Boolean(workflowId && workflowData.novelId);
  const presets = readiness?.production_presets || {};
  const styleReferences = Array.isArray(presets.style_references) ? presets.style_references : [];
  const aspectPresetOptions = Array.isArray(presets.aspect_ratios) && presets.aspect_ratios.length > 0
    ? presets.aspect_ratios.map((item: any) => ({
        value: item.ratio,
        label: `${item.ratio} ${item.label || ''}`.trim(),
      }))
    : SHORT_VIDEO_ASPECT_RATIO_OPTIONS;
  const styleOptions = [
    { value: '', label: styleReferences.length ? '默认风格' : '检查后加载风格图' },
    ...styleReferences.map((item: any) => ({
      value: item.id,
      label: item.name,
    })),
  ];
  const selectedAspectPreset = Array.isArray(presets.aspect_ratios)
    ? presets.aspect_ratios.find((item: any) => item.ratio === aspectRatio || item.selected)
    : null;
  const selectedStyle = styleReferences.find((item: any) => item.id === selectedStyleAssetId)
    || styleReferences.find((item: any) => item.selected);
  const consistencyTemplates = presets.consistency_templates || {};
  const characterTemplate = consistencyTemplates.character_three_view;
  const sceneTemplate = consistencyTemplates.scene_multi_view;
  const propTemplate = consistencyTemplates.prop_multi_view;

  const loadReadiness = useCallback(async () => {
    if (!workflowId) {
      setError('工作流还未创建完成');
      return;
    }
    if (!workflowData.novelId) {
      setError('请先选择小说，再生成短视频出片规划');
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.getWorkflowShortVideoReadiness(workflowId, {
        target_duration_seconds: targetDuration,
        aspect_ratio: aspectRatio,
        style_asset_id: selectedStyleAssetId || undefined,
      });
      setReadiness(data);
    } catch (err: any) {
      setError(err.message || '短视频一致性检查失败');
    } finally {
      setIsLoading(false);
    }
  }, [workflowId, workflowData.novelId, targetDuration, aspectRatio, selectedStyleAssetId]);

  const refreshContracts = async () => {
    if (!workflowId) {
      setError('工作流还未创建完成');
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      await apiClient.refreshWorkflowShortVideoContracts(workflowId);
      const data = await apiClient.getWorkflowShortVideoReadiness(workflowId, {
        target_duration_seconds: targetDuration,
        aspect_ratio: aspectRatio,
        style_asset_id: selectedStyleAssetId || undefined,
      });
      setReadiness(data);
    } catch (err: any) {
      setError(err.message || '刷新镜头生产合约失败');
    } finally {
      setIsLoading(false);
    }
  };

  const summary = readiness?.summary;
  const plan = readiness?.episode_plan;
  const narrative = plan?.narrative_control || {};
  const contracts = Array.isArray(readiness?.contracts) ? readiness.contracts : [];
  const mainRoute = readiness?.model_route?.shot_audio_video || readiness?.model_route?.shot_video;

  return (
    <Card className="bg-white/5 border-white/10 mt-4">
      <CardHeader>
        <CardTitle className="text-white text-sm flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-violet-300" />
          短视频出片模式
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-[1fr_170px] gap-2">
          <div className="flex items-center gap-2">
            <Input
              type="number"
              min={30}
              max={90}
              value={targetDuration}
              onChange={(event) => setTargetDuration(Number(event.target.value) || 60)}
              className="h-8 bg-white/10 border-white/10 text-white"
              aria-label="目标时长"
            />
            <span className="text-xs text-white/50 whitespace-nowrap">秒</span>
          </div>
          <Select
            value={aspectRatio}
            onChange={(event) => setAspectRatio(event.target.value)}
            options={aspectPresetOptions}
            aria-label="画面比例"
            className="h-8 bg-white/10 border-white/10 text-white"
          />
        </div>
        <Select
          value={selectedStyleAssetId}
          onChange={(event) => setSelectedStyleAssetId(event.target.value)}
          options={styleOptions}
          disabled={!readiness || styleReferences.length === 0}
          aria-label="整集画面风格"
          className="h-8 bg-white/10 border-white/10 text-white"
        />
        <div className="grid grid-cols-2 gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={!canCheck || isLoading}
            onClick={loadReadiness}
            className="border-white/20 text-xs"
          >
            {isLoading ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <AlertCircle className="w-3 h-3 mr-1" />}
            检查
          </Button>
          <Button
            size="sm"
            disabled={!workflowId || isLoading}
            onClick={refreshContracts}
            className="bg-violet-600 hover:bg-violet-700 text-xs"
          >
            {isLoading ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <RotateCcw className="w-3 h-3 mr-1" />}
            刷新合约
          </Button>
        </div>

        {error && (
          <div className="rounded border border-red-500/20 bg-red-500/10 p-2 text-xs text-red-200 leading-5">
            {error}
          </div>
        )}

        {!readiness && !error && (
          <div className="rounded border border-white/10 bg-white/5 p-2 text-xs text-white/45 leading-5">
            选择小说、章节和分镜后，可检查开场钩子、镜头节奏、角色三视图、场景/道具参考、字幕和模型路线。
          </div>
        )}

        {readiness && (
          <div className="rounded border border-cyan-500/20 bg-cyan-500/10 p-2 text-xs leading-5">
            <div className="flex items-center justify-between gap-2">
              <span className="text-cyan-100 font-medium">制作规格</span>
              <span className="text-cyan-100/70">{aspectRatio}</span>
            </div>
            <div className="mt-1 text-white/60">
              {selectedAspectPreset?.label || '当前画幅'}：{selectedAspectPreset?.use_case || '按当前发布渠道构图'}
            </div>
            <div className="mt-1 text-white/45 line-clamp-2">
              风格：{selectedStyle?.name || '默认跟随小说/分镜风格'}
              {selectedStyle?.prompt_summary ? ` · ${selectedStyle.prompt_summary}` : ''}
            </div>
            <div className="mt-2 grid grid-cols-1 sm:grid-cols-3 gap-1 text-white/50">
              <div>角色：{characterTemplate?.name || '待加载三视图模板'}</div>
              <div>场景：{sceneTemplate?.name || '待加载多视图模板'}</div>
              <div>道具：{propTemplate?.name || '待加载视觉 DNA 模板'}</div>
            </div>
          </div>
        )}

        {summary && (
          <div className="rounded border border-white/10 bg-white/5 p-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-white/70">出片状态</span>
              <span className={summary.ready ? 'text-green-300' : summary.blocking_issue_count ? 'text-red-300' : 'text-yellow-300'}>
                {summary.ready ? '可生成' : summary.blocking_issue_count ? '有阻断' : '需补齐'}
              </span>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-white/45">
              <div>{summary.shot_count || 0} 镜头</div>
              <div>{summary.estimated_duration_seconds || 0}s</div>
              <div>{summary.blocking_issue_count || 0} 阻断</div>
              <div>{summary.warning_count || 0} 提醒</div>
            </div>
          </div>
        )}

        {plan && (
          <div className="rounded border border-violet-500/20 bg-violet-500/10 p-2 text-xs leading-5">
            <div className="text-violet-100 font-medium">钩子与承接</div>
            <div className="mt-1 text-white/65 line-clamp-2">{narrative.hook}</div>
            <div className="mt-1 text-white/45 line-clamp-2">{narrative.cliffhanger}</div>
          </div>
        )}

        {contracts.length > 0 && (
          <div className="space-y-2">
            {contracts.slice(0, 4).map((contract: any) => (
              <div key={contract.shot_id} className="rounded border border-white/10 bg-white/5 p-2">
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="text-white/75 truncate">
                    镜头 {contract.shot_number} · {contract.role?.label || '节奏节点'}
                  </span>
                  <span className={contract.status === 'ready' ? 'text-green-300' : contract.blocking_issue_count ? 'text-red-300' : 'text-yellow-300'}>
                    {contract.status === 'ready' ? 'ready' : contract.blocking_issue_count ? 'blocked' : 'warning'}
                  </span>
                </div>
                <div className="mt-1 text-xs text-white/40 line-clamp-2">
                  人物 {(contract.characters || []).join('、') || '未绑定'} · 场景 {(contract.scenes || []).join('、') || '未绑定'}
                </div>
                <div className="mt-1 text-xs text-white/35 line-clamp-1">
                  字幕 {contract.subtitle_text || '缺失'} · 资产锁 {contract.asset_lock_count || 0}
                </div>
              </div>
            ))}
          </div>
        )}

        {mainRoute && (
          <div className="rounded border border-white/10 bg-white/5 p-2 text-xs text-white/45 leading-5">
            默认模型：{mainRoute.model?.display_name || mainRoute.default_model_id || '未配置'}
            <br />
            {mainRoute.reason}
          </div>
        )}

        {Array.isArray(readiness?.recommendations) && readiness.recommendations.length > 0 && (
          <div className="rounded border border-yellow-500/20 bg-yellow-500/10 p-2 text-xs text-yellow-100 leading-5">
            {readiness.recommendations[0]}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function NovelStep({
  workflowData,
  onPatchWorkflow,
}: {
  workflowData: WorkflowData;
  onPatchWorkflow: WorkflowPatchHandler;
}) {
  const { toast } = useToast();
  const router = useRouter();
  const [novels, setNovels] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedNovel, setSelectedNovel] = useState<any>(null);

  useEffect(() => {
    loadNovels();
  }, []);

  const loadNovels = async () => {
    try {
      const data = await apiClient.getNovels();
      setNovels(data || []);
      // 如果有已选小说，选中它
      if (workflowData.novelId) {
        const novel = data?.find((n: any) => n.id === workflowData.novelId);
        if (novel) setSelectedNovel(novel);
      }
    } catch (err) {
      console.error('加载小说失败:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectNovel = (novel: any) => {
    setSelectedNovel(novel);
    onPatchWorkflow({
      novelId: novel.id,
      chapterId: undefined,
      scriptId: undefined,
      storyboardId: undefined,
      shotIds: [],
      videoJobIds: [],
      ttsJobIds: [],
      mediaJobIds: [],
      subtitleTrackIds: [],
      synthesisJobIds: [],
      synthesisJobId: undefined,
      synthesisManifestUrl: undefined,
      synthesisOutputUrl: undefined,
      renderPreviewUrl: undefined,
      renderSrtUrl: undefined,
      renderTimelineUrl: undefined,
      renderManifestUrl: undefined,
    }, 1);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-white/60">选择或创建小说作为创作起点</p>
        <Button
          size="sm"
          onClick={() => router.push('/novels?create=true')}
          className="bg-violet-600 hover:bg-violet-700"
        >
          <Sparkles className="w-4 h-4 mr-2" />
          创建新小说
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-violet-500 animate-spin" />
        </div>
      ) : novels.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {novels.map((novel) => (
            <div
              key={novel.id}
              onClick={() => handleSelectNovel(novel)}
              className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                selectedNovel?.id === novel.id
                  ? 'border-violet-500 bg-violet-500/10'
                  : 'border-white/10 hover:border-white/20 bg-white/5'
              }`}
            >
              <div className="font-medium text-white">{novel.title}</div>
              <div className="text-sm text-white/60 mt-1 line-clamp-2">
                {novel.description || novel.content?.slice(0, 100) || '暂无描述'}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-white/40">
          <Book className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>暂无小说</p>
          <p className="text-sm mt-2">点击上方按钮创建您的第一部小说</p>
        </div>
      )}
    </div>
  );
}

function ChapterStep({
  workflowData,
  onPatchWorkflow,
}: {
  workflowData: WorkflowData;
  onPatchWorkflow: WorkflowPatchHandler;
}) {
  const router = useRouter();
  const [chapters, setChapters] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (workflowData.novelId) {
      loadChapters();
    } else {
      setIsLoading(false);
    }
  }, [workflowData.novelId]);

  const loadChapters = async () => {
    try {
      const data = await apiClient.getChapters(workflowData.novelId);
      setChapters(data || []);
    } catch (err) {
      console.error('加载章节失败:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectChapter = (chapter: any) => {
    onPatchWorkflow({
      chapterId: chapter.id,
      scriptId: undefined,
      storyboardId: undefined,
      shotIds: [],
      videoJobIds: [],
      ttsJobIds: [],
      mediaJobIds: [],
      subtitleTrackIds: [],
      synthesisJobIds: [],
      synthesisJobId: undefined,
      synthesisManifestUrl: undefined,
      synthesisOutputUrl: undefined,
      renderPreviewUrl: undefined,
      renderSrtUrl: undefined,
      renderTimelineUrl: undefined,
      renderManifestUrl: undefined,
    }, 2);
  };

  if (!workflowData.novelId) {
    return (
      <div className="text-center py-12 text-yellow-400">
        <AlertCircle className="w-12 h-12 mx-auto mb-4" />
        <p>请先在"小说"步骤选择一部小说</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-white/60">管理小说的章节内容</p>
        <Button
          size="sm"
          onClick={() => router.push(`/novels/${workflowData.novelId}/chapters`)}
          className="bg-violet-600 hover:bg-violet-700"
        >
          <Sparkles className="w-4 h-4 mr-2" />
          AI 生成章节
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-violet-500 animate-spin" />
        </div>
      ) : chapters.length > 0 ? (
        <div className="space-y-2">
          {chapters.map((chapter, idx) => (
            <div
              key={chapter.id}
              onClick={() => handleSelectChapter(chapter)}
              className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                workflowData.chapterId === chapter.id
                  ? 'border-violet-500 bg-violet-500/10'
                  : 'border-white/10 bg-white/5 hover:border-white/30'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-violet-500/20 flex items-center justify-center text-violet-300 text-sm">
                  {idx + 1}
                </div>
                <div className="flex-1">
                  <div className="font-medium text-white flex items-center gap-2">
                    {chapter.title}
                    {workflowData.chapterId === chapter.id && (
                      <span className="text-xs text-violet-200">已选择</span>
                    )}
                  </div>
                  <div className="text-sm text-white/60 line-clamp-1">
                    {chapter.content?.slice(0, 100) || '暂无内容'}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-white/40">
          <Book className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>暂无章节</p>
          <p className="text-sm mt-2">点击上方按钮使用 AI 生成章节</p>
        </div>
      )}
    </div>
  );
}

function CharacterStep({
  workflowData,
  onPatchWorkflow,
  modelConfigs,
  textModelConfigId,
  imageModelConfigId,
  onTextModelConfigChange,
  onImageModelConfigChange,
}: {
  workflowData: WorkflowData;
  onPatchWorkflow: WorkflowPatchHandler;
  modelConfigs: SavedModelConfig[];
  textModelConfigId: string;
  imageModelConfigId: string;
  onTextModelConfigChange: (configId: string) => void;
  onImageModelConfigChange: (configId: string) => void;
}) {
  const { toast } = useToast();
  const router = useRouter();
  const [characters, setCharacters] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);

  const loadCharacters = useCallback(async () => {
    if (!workflowData.novelId) {
      setCharacters([]);
      return;
    }
    setIsLoading(true);
    try {
      const data = await apiClient.getCharacters({
        novel_id: workflowData.novelId,
        chapter_id: workflowData.chapterId,
        include_global: true,
      });
      setCharacters(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('加载角色失败:', err);
      setCharacters([]);
    } finally {
      setIsLoading(false);
    }
  }, [workflowData.novelId, workflowData.chapterId]);

  useEffect(() => {
    loadCharacters();
  }, [loadCharacters]);

  const handleExtractCharacters = async () => {
    if (!workflowData.novelId && !workflowData.chapterId) {
      toast({ title: '请先选择小说和章节', description: '完成上游选择后再提取角色。', type: 'info' });
      return;
    }
    setIsExtracting(true);
    try {
      await apiClient.extractCharacters({
        novel_id: workflowData.novelId,
        chapter_id: workflowData.chapterId,
        character_count: 12,
        auto_generate_avatar: true,
        model_config_id: textModelConfigId || undefined,
        image_model_config_id: imageModelConfigId || undefined,
      });
      await loadCharacters();
      toast({ title: '角色提取完成', type: 'success' });
    } catch (err: any) {
      toast({ title: 'AI 提取角色失败', description: err.message || '请稍后重试。', type: 'error' });
    } finally {
      setIsExtracting(false);
    }
  };

  if (!workflowData.novelId) {
    return (
      <div className="text-center py-12 text-yellow-400">
        <AlertCircle className="w-12 h-12 mx-auto mb-4" />
        <p>请先在"小说"步骤选择一部小说</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-white/80">当前小说/章节角色设定</p>
          <p className="text-white/50 text-sm mt-1">
            角色会按小说和章节作用域加载，生成分镜和视频时用于保持人物一致性。
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={isExtracting}
            onClick={handleExtractCharacters}
            className="border-violet-500/50 text-violet-300"
          >
            {isExtracting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
            AI 提取角色
          </Button>
          <Button
            size="sm"
            onClick={() => router.push(`/characters?novel_id=${workflowData.novelId}`)}
            className="bg-violet-600 hover:bg-violet-700"
          >
            <Users className="w-4 h-4 mr-2" />
            管理角色
          </Button>
        </div>
      </div>
      <ModelCapabilitySelector
        capability="text"
        configs={modelConfigs}
        value={textModelConfigId}
        onChange={onTextModelConfigChange}
        disabled={isExtracting}
        title="角色提取模型"
        description="工作流会用该文本模型从当前小说和章节提取角色，并保持角色归属不串到其他小说。"
        compact
      />
      <ModelCapabilitySelector
        capability="image"
        configs={modelConfigs}
        value={imageModelConfigId}
        onChange={onImageModelConfigChange}
        disabled={isExtracting}
        title="角色头像模型"
        description="开启自动头像时，角色外观图会使用该图像模型生成。"
        compact
      />

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-violet-500 animate-spin" />
        </div>
      ) : characters.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {characters.slice(0, 12).map((character) => (
            <div key={character.id} className="rounded-lg border border-white/10 bg-white/5 p-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-violet-500/20 overflow-hidden flex items-center justify-center">
                  {character.avatar ? (
                    <img src={toMediaUrl(character.avatar)} alt="" width={40} height={40} loading="lazy" className="w-full h-full object-cover" />
                  ) : (
                    <Users className="w-5 h-5 text-violet-200" />
                  )}
                </div>
                <div className="min-w-0">
                  <div className="text-white font-medium truncate">{character.name}</div>
                  <div className="text-white/50 text-xs truncate">
                    {character.appearance || character.description || '未补充外貌设定'}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-white/40">
          <Users className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>当前小说/章节暂无角色</p>
          <p className="text-sm mt-2">可直接 AI 提取角色，或进入角色管理手动创建</p>
        </div>
      )}

      <div className="flex justify-end">
        <Button
          onClick={() => onPatchWorkflow({}, 3)}
          disabled={characters.length === 0}
          className="bg-violet-600 hover:bg-violet-700"
        >
          进入剧本
          <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}

function ScriptStep({
  workflowData,
  onPatchWorkflow,
  modelConfigs,
  textModelConfigId,
  onTextModelConfigChange,
}: {
  workflowData: WorkflowData;
  onPatchWorkflow: WorkflowPatchHandler;
  modelConfigs: SavedModelConfig[];
  textModelConfigId: string;
  onTextModelConfigChange: (configId: string) => void;
}) {
  const { toast } = useToast();
  const router = useRouter();
  const [scripts, setScripts] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  const loadScripts = useCallback(async () => {
    if (!workflowData.novelId && !workflowData.chapterId) {
      setScripts([]);
      return;
    }
    setIsLoading(true);
    try {
      const data = await apiClient.getScripts({
        novel_id: workflowData.novelId,
        chapter_id: workflowData.chapterId,
      });
      setScripts(Array.isArray(data) ? data : []);
      if (!workflowData.scriptId && Array.isArray(data) && data.length === 1) {
        await onPatchWorkflow({ scriptId: data[0].id }, 3);
      }
    } catch (err) {
      console.error('加载剧本失败:', err);
      setScripts([]);
    } finally {
      setIsLoading(false);
    }
  }, [workflowData.novelId, workflowData.chapterId, workflowData.scriptId, onPatchWorkflow]);

  useEffect(() => {
    loadScripts();
  }, [loadScripts]);

  const handleGenerateScript = async () => {
    if (!workflowData.chapterId) {
      toast({ title: '请先选择章节', description: '章节确定后才能生成剧本。', type: 'info' });
      return;
    }
    setIsGenerating(true);
    try {
      const script = await apiClient.generateScript({
        chapter_id: workflowData.chapterId,
        style: 'anime',
        model_config_id: textModelConfigId || undefined,
      });
      setScripts(prev => [script, ...prev.filter(item => item.id !== script.id)]);
      await onPatchWorkflow({ scriptId: script.id, storyboardId: undefined, shotIds: [] }, 4);
      toast({ title: '剧本已生成', type: 'success' });
    } catch (err: any) {
      toast({ title: 'AI 生成剧本失败', description: err.message || '请稍后重试。', type: 'error' });
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSelectScript = async (script: any) => {
    await onPatchWorkflow({ scriptId: script.id, storyboardId: undefined, shotIds: [] }, 4);
  };

  if (!workflowData.novelId || !workflowData.chapterId) {
    return (
      <div className="text-center py-12 text-yellow-400">
        <AlertCircle className="w-12 h-12 mx-auto mb-4" />
        <p>请先完成"小说"和"章节"步骤</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-white/80">从当前章节生成或选择剧本</p>
          <p className="text-white/50 text-sm mt-1">剧本会绑定当前小说和章节，供分镜、镜头和视频生成继承上下文。</p>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => router.push(`/scripts?novel_id=${workflowData.novelId}&chapter_id=${workflowData.chapterId}`)}
            className="border-white/20"
          >
            <FileText className="w-4 h-4 mr-2" />
            剧本管理
          </Button>
          <Button
            size="sm"
            disabled={isGenerating}
            onClick={handleGenerateScript}
            className="bg-violet-600 hover:bg-violet-700"
          >
            {isGenerating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
            AI 生成剧本
          </Button>
        </div>
      </div>
      <ModelCapabilitySelector
        capability="text"
        configs={modelConfigs}
        value={textModelConfigId}
        onChange={onTextModelConfigChange}
        disabled={isGenerating}
        title="剧本生成模型"
        description="剧本生成会把章节正文、小说设定、角色、事件和环境上下文写进提示词。"
        compact
      />

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-violet-500 animate-spin" />
        </div>
      ) : scripts.length > 0 ? (
        <div className="space-y-2">
          {scripts.map((script) => (
            <div
              key={script.id}
              onClick={() => handleSelectScript(script)}
              className={`rounded-lg border p-4 cursor-pointer transition-colors ${
                workflowData.scriptId === script.id
                  ? 'border-violet-500 bg-violet-500/10'
                  : 'border-white/10 bg-white/5 hover:border-white/30'
              }`}
            >
              <div className="text-white font-medium flex items-center gap-2">
                {script.title}
                {workflowData.scriptId === script.id && <span className="text-xs text-violet-200">已选择</span>}
              </div>
              <div className="mt-1 text-sm text-white/50 line-clamp-2">
                {script.description || script.content || '暂无剧本内容摘要'}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-white/40">
          <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>当前章节暂无剧本</p>
          <p className="text-sm mt-2">点击 AI 生成剧本，系统会带入小说、章节、角色、事件和环境上下文</p>
        </div>
      )}
    </div>
  );
}

function StoryboardStep({
  workflowData,
  onPatchWorkflow,
  modelConfigs,
  textModelConfigId,
  onTextModelConfigChange,
}: {
  workflowData: WorkflowData;
  onPatchWorkflow: WorkflowPatchHandler;
  modelConfigs: SavedModelConfig[];
  textModelConfigId: string;
  onTextModelConfigChange: (configId: string) => void;
}) {
  const { toast } = useToast();
  const router = useRouter();
  const [storyboards, setStoryboards] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  const loadStoryboards = useCallback(async () => {
    if (!workflowData.scriptId) {
      setStoryboards([]);
      return;
    }
    setIsLoading(true);
    try {
      const data = await apiClient.getStoryboards(workflowData.scriptId);
      const list = (Array.isArray(data) ? data : []).filter((storyboard: any) => {
        const chapterId = storyboard.chapter_id || storyboard.content?.chapter_id;
        return !workflowData.chapterId || !chapterId || chapterId === workflowData.chapterId;
      });
      setStoryboards(list);
      if (!workflowData.storyboardId && list.length === 1) {
        await onPatchWorkflow({ storyboardId: list[0].id }, 5);
      }
    } catch (err) {
      console.error('加载分镜失败:', err);
      setStoryboards([]);
    } finally {
      setIsLoading(false);
    }
  }, [workflowData.scriptId, workflowData.chapterId, workflowData.storyboardId, onPatchWorkflow]);

  useEffect(() => {
    loadStoryboards();
  }, [loadStoryboards]);

  const handleGenerateStoryboard = async () => {
    if (!workflowData.novelId) {
      toast({ title: '请先选择小说', description: '小说确定后才能生成分镜。', type: 'info' });
      return;
    }
    setIsGenerating(true);
    try {
      const storyboard = await apiClient.generateSmartStoryboard({
        novel_id: workflowData.novelId,
        chapter_id: workflowData.chapterId,
        script_id: workflowData.scriptId || undefined,
        shot_count: 8,
        style: 'anime',
        use_ai_refine: true,
        model_config_id: textModelConfigId || undefined,
      });
      setStoryboards(prev => [storyboard, ...prev.filter(item => item.id !== storyboard.id)]);
      await onPatchWorkflow({
        scriptId: storyboard.script_id || workflowData.scriptId,
        storyboardId: storyboard.id,
        shotIds: (storyboard.shots || []).map((shot: any) => shot.id),
      }, 5);
      toast({ title: '分镜已生成', type: 'success' });
    } catch (err: any) {
      toast({ title: 'AI 生成分镜失败', description: err.message || '请稍后重试。', type: 'error' });
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSelectStoryboard = async (storyboard: any) => {
    await onPatchWorkflow({ storyboardId: storyboard.id, shotIds: [] }, 5);
  };

  if (!workflowData.scriptId && !workflowData.novelId) {
    return (
      <div className="text-center py-12 text-yellow-400">
        <AlertCircle className="w-12 h-12 mx-auto mb-4" />
        <p>请先完成小说、章节和剧本步骤</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-white/80">将剧本转换为分镜和镜头</p>
          <p className="text-white/50 text-sm mt-1">智能分镜会绑定小说、章节、人物、场景、道具、事件和字幕对白。</p>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              const params = new URLSearchParams();
              if (workflowData.novelId) params.set('novel_id', workflowData.novelId);
              if (workflowData.chapterId) params.set('chapter_id', workflowData.chapterId);
              if (workflowData.storyboardId) params.set('storyboard_id', workflowData.storyboardId);
              router.push(`/storyboards${params.toString() ? `?${params}` : ''}`);
            }}
            className="border-white/20"
          >
            <Layers className="w-4 h-4 mr-2" />
            分镜管理
          </Button>
          <Button
            size="sm"
            disabled={isGenerating}
            onClick={handleGenerateStoryboard}
            className="bg-violet-600 hover:bg-violet-700"
          >
            {isGenerating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
            AI 生成分镜
          </Button>
        </div>
      </div>
      <ModelCapabilitySelector
        capability="text"
        configs={modelConfigs}
        value={textModelConfigId}
        onChange={onTextModelConfigChange}
        disabled={isGenerating}
        title="分镜细化模型"
        description="智能分镜会先匹配模板，再用该文本模型细化画面、对白、镜头运动和字幕信息。"
        compact
      />

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-violet-500 animate-spin" />
        </div>
      ) : storyboards.length > 0 ? (
        <div className="space-y-2">
          {storyboards.map((storyboard) => (
            <div
              key={storyboard.id}
              onClick={() => handleSelectStoryboard(storyboard)}
              className={`rounded-lg border p-4 cursor-pointer transition-colors ${
                workflowData.storyboardId === storyboard.id
                  ? 'border-violet-500 bg-violet-500/10'
                  : 'border-white/10 bg-white/5 hover:border-white/30'
              }`}
            >
              <div className="text-white font-medium flex items-center gap-2">
                {storyboard.title}
                {workflowData.storyboardId === storyboard.id && <span className="text-xs text-violet-200">已选择</span>}
              </div>
              <div className="mt-1 text-sm text-white/50">
                {storyboard.shot_count || 0} 个镜头 · {storyboard.total_duration || 0} 秒 · {storyboard.status || 'draft'}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-white/40">
          <Layers className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>当前剧本暂无分镜</p>
          <p className="text-sm mt-2">可直接用当前小说/章节智能生成分镜和镜头</p>
        </div>
      )}
    </div>
  );
}

function ShotStep({
  workflowData,
  onPatchWorkflow,
}: {
  workflowData: WorkflowData;
  onPatchWorkflow: WorkflowPatchHandler;
}) {
  const router = useRouter();
  const [shots, setShots] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const loadShots = useCallback(async () => {
    if (!workflowData.storyboardId) {
      setShots([]);
      return;
    }
    setIsLoading(true);
    try {
      const data = await apiClient.getShots(workflowData.storyboardId);
      const list = Array.isArray(data) ? data : [];
      setShots(list);
      if (list.length > 0) {
        await onPatchWorkflow({ shotIds: list.map((shot: any) => shot.id) }, 5);
      }
    } catch (err) {
      console.error('加载镜头失败:', err);
      setShots([]);
    } finally {
      setIsLoading(false);
    }
  }, [workflowData.storyboardId, onPatchWorkflow]);

  useEffect(() => {
    loadShots();
  }, [loadShots]);

  if (!workflowData.storyboardId) {
    return (
      <div className="text-center py-12 text-yellow-400">
        <AlertCircle className="w-12 h-12 mx-auto mb-4" />
        <p>请先选择或生成分镜</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-white/80">审核和调整镜头</p>
          <p className="text-white/50 text-sm mt-1">镜头会继承当前分镜的小说、章节、剧本、人物、场景和对白上下文。</p>
        </div>
        <Button
          size="sm"
          onClick={() => {
            const params = new URLSearchParams();
            if (workflowData.novelId) params.set('novel_id', workflowData.novelId);
            if (workflowData.chapterId) params.set('chapter_id', workflowData.chapterId);
            if (workflowData.scriptId) params.set('script_id', workflowData.scriptId);
            if (workflowData.storyboardId) params.set('storyboard_id', workflowData.storyboardId);
            router.push(`/shots?${params.toString()}`);
          }}
          className="bg-violet-600 hover:bg-violet-700"
        >
          <Camera className="w-4 h-4 mr-2" />
          管理镜头
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-violet-500 animate-spin" />
        </div>
      ) : shots.length > 0 ? (
        <div className="space-y-2">
          {shots.map((shot) => (
            <div key={shot.id} className="rounded-lg border border-white/10 bg-white/5 p-4">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded bg-violet-500/20 text-violet-200 flex items-center justify-center text-sm">
                  {shot.shot_number}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-white font-medium line-clamp-1">{shot.prompt || shot.visual_description || '未设置镜头描述'}</div>
                  <div className="mt-1 text-sm text-white/50 line-clamp-2">{shot.dialogue || shot.extra_data?.subtitle_text || '无对白'}</div>
                  <div className="mt-1 text-xs text-white/35">{shot.duration || 4}s · 视频 {shot.video_status || 'pending'} · 语音 {shot.audio_status || 'pending'}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-white/40">
          <Camera className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>当前分镜暂无镜头</p>
          <p className="text-sm mt-2">返回分镜步骤重新生成，或进入镜头管理手动创建</p>
        </div>
      )}

      <div className="flex justify-end">
        <Button
          onClick={() => onPatchWorkflow({ shotIds: shots.map((shot) => shot.id) }, 6)}
          disabled={shots.length === 0}
          className="bg-violet-600 hover:bg-violet-700"
        >
          进入视频生成
          <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}

function VideoStep({
  workflowId,
  workflowData,
  setWorkflowData,
  onVideoGenerated,
  modelConfigs,
  videoModelConfigId,
  onVideoModelConfigChange,
  audioModelConfigId,
  onAudioModelConfigChange,
}: any) {
  const { toast } = useToast();
  const router = useRouter();
  const [isGeneratingBatch, setIsGeneratingBatch] = useState(false);
  const [batchResult, setBatchResult] = useState<any>(null);
  const [batchPreflightFailure, setBatchPreflightFailure] = useState<any>(null);
  const [storyBibles, setStoryBibles] = useState<any[]>([]);
  const [selectedStoryBibleId, setSelectedStoryBibleId] = useState('');
  const [useStoryBibleVoice, setUseStoryBibleVoice] = useState(true);

  useEffect(() => {
    if (!workflowData.novelId) {
      setStoryBibles([]);
      setSelectedStoryBibleId('');
      return;
    }

    let isMounted = true;
    apiClient.getStoryBibles({ novel_id: workflowData.novelId })
      .then((list) => {
        if (!isMounted) return;
        const items = Array.isArray(list) ? list : [];
        setStoryBibles(items);
        setSelectedStoryBibleId((current) => (
          current && items.some((item) => item.id === current)
            ? current
            : items[0]?.id || ''
        ));
      })
      .catch(() => {
        if (!isMounted) return;
        setStoryBibles([]);
        setSelectedStoryBibleId('');
      });

    return () => {
      isMounted = false;
    };
  }, [workflowData.novelId]);

  const selectedStoryBible = storyBibles.find((item) => item.id === selectedStoryBibleId);
  const storyBibleOptions = storyBibles.map((item) => ({
    value: item.id,
    label: `${item.title || '未命名 Story Bible'}${item.character_rules?.length ? ` · ${item.character_rules.length} 角色` : ''}`,
  }));
  const ttsVoiceLockCount = (workflowData.ttsJobs || []).filter(
    (job: any) => job.extra_data?.voice_source === 'story_bible'
  ).length;

  const handleGenerateMediaBatch = async () => {
    if (!workflowData.storyboardId) {
      toast({ title: '工作流缺少分镜', description: '请先从极速向导或分镜页创建分镜，再批量生成镜头音视频。', type: 'info' });
      return;
    }
    if (!workflowId) {
      toast({ title: '工作流状态未加载完成', description: '请稍后刷新后再试。', type: 'info' });
      return;
    }
    setIsGeneratingBatch(true);
    setBatchPreflightFailure(null);
    try {
      const result = await apiClient.generateWorkflowMediaBatch(workflowId, {
        strategy: 'separate_video_tts',
        resolution: '720p',
        subtitle_mode: 'shot_dialogue',
        audio_mode: 'model_audio',
        model_config_id: videoModelConfigId || undefined,
        audio_model_config_id: audioModelConfigId || undefined,
        story_bible_id: selectedStoryBibleId || undefined,
        use_story_bible_voice: useStoryBibleVoice,
      });
      setBatchResult(result);
      setBatchPreflightFailure(null);
      setWorkflowData((prev: WorkflowData) => ({
        ...prev,
        mediaJobIds: Array.from(new Set<string>([...(prev.mediaJobIds || []), ...(result.media_job_ids || [])])),
        videoJobIds: Array.from(new Set<string>([...(prev.videoJobIds || []), ...(result.video_job_ids || [])])),
        ttsJobIds: Array.from(new Set<string>([...(prev.ttsJobIds || []), ...(result.tts_job_ids || [])])),
        subtitleTrackIds: Array.from(new Set<string>([...(prev.subtitleTrackIds || []), ...(result.subtitle_track_ids || [])])),
      }));
      onVideoGenerated?.(result);
      toast({
        title: result.ready_for_concatenate === false ? '视频/声音任务已提交' : '批量视频和配音已生成',
        description: result.ready_for_concatenate === false
          ? `已创建 ${result.video_job_ids?.length || 0} 个视频任务、${result.tts_job_ids?.length || 0} 个声音任务，等待云端完成后再合成。`
          : `已创建 ${result.video_job_ids?.length || 0} 个视频任务、${result.tts_job_ids?.length || 0} 个声音任务。`,
        type: 'success',
      });
    } catch (err: any) {
      const detail = err?.detail;
      if (detail?.code === 'generation_preflight_failed') {
        setBatchPreflightFailure(detail);
        setBatchResult(null);
      }
      toast({ title: '批量直生音视频失败', description: detail?.message || err.message || '请稍后重试。', type: 'error' });
    } finally {
      setIsGeneratingBatch(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-white/80">为每个镜头生成视频和配音草稿</p>
          <p className="text-white/50 text-sm mt-1">
            默认按当前小说、章节、分镜、镜头、角色和字幕上下文，分别调用视频模型与声音模型，并生成字幕轨。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            onClick={handleGenerateMediaBatch}
            disabled={isGeneratingBatch}
            className="bg-blue-600 hover:bg-blue-700"
          >
            {isGeneratingBatch ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
            批量生成视频和配音
          </Button>
          <Button
            size="sm"
            onClick={() => {
              const params = new URLSearchParams();
              if (workflowId) params.set('workflow_id', workflowId);
              if (workflowData.novelId) params.set('novel_id', workflowData.novelId);
              if (workflowData.chapterId) params.set('chapter_id', workflowData.chapterId);
              if (workflowData.scriptId) params.set('script_id', workflowData.scriptId);
              if (workflowData.storyboardId) params.set('storyboard_id', workflowData.storyboardId);
              router.push(`/video-generation${params.toString() ? `?${params.toString()}` : ''}`);
            }}
            className="bg-violet-600 hover:bg-violet-700"
          >
            <Video className="w-4 h-4 mr-2" />
            单镜头生成
          </Button>
        </div>
      </div>

      {batchPreflightFailure && (
        <div
          data-testid="workflow-media-preflight"
          className="rounded border border-red-500/30 bg-red-500/10 p-3"
        >
          <div className="flex items-center gap-2 text-sm font-medium text-red-100">
            <AlertCircle className="h-4 w-4" />
            生成前预检未通过
          </div>
          <p className="mt-1 text-xs leading-5 text-red-100/70">
            {batchPreflightFailure.message || `发现 ${batchPreflightFailure.blocking_issue_count || 0} 个阻断项，请处理后再批量生成。`}
          </p>
          <div className="mt-3">
            <PreflightIssueList
              issues={batchPreflightFailure.issues || []}
              emptyText="未返回具体阻断项，请检查模型配置和镜头资产。"
            />
          </div>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <ModelCapabilitySelector
          capability="video"
          configs={modelConfigs || []}
          value={videoModelConfigId}
          onChange={onVideoModelConfigChange}
          disabled={isGeneratingBatch}
          title="批量视频模型"
          description="为每个镜头创建视频生成任务，输入包含小说、章节、分镜、镜头、人物、环境和道具上下文。"
          compact
        />
        <ModelCapabilitySelector
          capability="audio"
          configs={modelConfigs || []}
          value={audioModelConfigId}
          onChange={onAudioModelConfigChange}
          disabled={isGeneratingBatch}
          title="批量声音模型"
          description="为每个镜头创建配音任务；无对白镜头会自动生成旁白草稿，避免成片缺声音。"
          compact
        />
      </div>

      <div className="rounded border border-white/10 bg-white/5 p-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-white">角色音色锁</span>
              <Badge className={useStoryBibleVoice ? 'bg-green-500/20 text-green-200 border-green-500/30' : 'bg-white/10 text-white/60 border-white/10'}>
                {useStoryBibleVoice ? '启用' : '关闭'}
              </Badge>
              {selectedStoryBible && (
                <Badge className="bg-violet-500/20 text-violet-100 border-violet-500/30">
                  {selectedStoryBible.character_rules?.length || 0} 个角色设定
                </Badge>
              )}
              {(batchResult?.tts_voice_lock_count || ttsVoiceLockCount) > 0 && (
                <Badge className="bg-cyan-500/20 text-cyan-100 border-cyan-500/30">
                  已命中 {batchResult?.tts_voice_lock_count || ttsVoiceLockCount} 个配音
                </Badge>
              )}
            </div>
            <p className="mt-1 text-xs text-white/50">
              批量配音优先读取 Story Bible 中的角色 voice/voice_speed，再回退到默认音色。
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm text-white/70">
            <Checkbox
              checked={useStoryBibleVoice}
              onCheckedChange={(checked) => setUseStoryBibleVoice(Boolean(checked))}
              disabled={isGeneratingBatch}
            />
            使用角色音色
          </label>
        </div>
        <div className="mt-3">
          <Select
            value={selectedStoryBibleId}
            onValueChange={setSelectedStoryBibleId}
            disabled={isGeneratingBatch || storyBibles.length === 0}
            placeholder={storyBibles.length ? '选择 Story Bible' : '当前小说暂无 Story Bible'}
            options={storyBibleOptions}
          />
        </div>
      </div>

      {batchResult && (
        <div className="rounded border border-green-500/30 bg-green-500/10 p-3 text-sm text-green-100">
          已创建 {batchResult.video_job_ids?.length || 0} 个视频任务、{batchResult.tts_job_ids?.length || 0} 个声音任务，并生成 {batchResult.subtitle_track_ids?.length || 0} 条字幕轨。
          <div className="mt-1 text-xs text-green-100/70">
            已消费当前 workflow 的小说/章节/分镜/镜头链路；本次 {batchResult.tts_voice_lock_count || 0} 个配音命中角色音色锁。
            {batchResult.ready_for_concatenate === false ? ' 当前仍有云端任务未完成，完成后再合成。' : ''}
          </div>
        </div>
      )}

      {workflowData.videoJobIds.length > 0 || workflowData.mediaJobIds.length > 0 ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="rounded border border-white/10 bg-white/5 p-4">
            <div className="text-white/50 text-xs">静音视频</div>
            <div className="mt-1 text-2xl font-semibold text-white">{workflowData.videoJobIds.length}</div>
          </div>
          <div className="rounded border border-white/10 bg-white/5 p-4">
            <div className="text-white/50 text-xs">直生音视频</div>
            <div className="mt-1 text-2xl font-semibold text-white">{workflowData.mediaJobIds.length}</div>
          </div>
          <div className="rounded border border-white/10 bg-white/5 p-4">
            <div className="text-white/50 text-xs">字幕轨</div>
            <div className="mt-1 text-2xl font-semibold text-white">{workflowData.subtitleTrackIds.length}</div>
          </div>
        </div>
      ) : (
        <div className="text-center py-12 text-white/40">
          <Video className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>暂无镜头视频草稿</p>
          <p className="text-sm mt-2">可批量直生音视频，也可进入单镜头页面精细生成</p>
        </div>
      )}
    </div>
  );
}

function TTSStep({
  workflowData,
  modelConfigs,
  audioModelConfigId,
  onAudioModelConfigChange,
}: any) {
  const router = useRouter();
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-white/60">为对话生成语音</p>
        <Button
          size="sm"
          onClick={() => router.push('/tts')}
          className="bg-violet-600 hover:bg-violet-700"
        >
          <Mic className="w-4 h-4 mr-2" />
          前往生成
        </Button>
      </div>
      <ModelCapabilitySelector
        capability="audio"
        configs={modelConfigs || []}
        value={audioModelConfigId}
        onChange={onAudioModelConfigChange}
        title="TTS/声音模型"
        description="TTS 页面会默认选择该语音配置，可再切换其他已验证声音模型。"
        compact
      />

      {workflowData.ttsJobIds.length > 0 ? (
        <div className="text-center py-4 text-green-400">
          <Check className="w-8 h-8 mx-auto mb-2" />
          <p>已生成 {workflowData.ttsJobIds.length} 个语音</p>
        </div>
      ) : (
        <div className="text-center py-12 text-white/40">
          <Mic className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>暂无生成的语音</p>
          <p className="text-sm mt-2">点击上方按钮前往 TTS 页面</p>
        </div>
      )}
    </div>
  );
}

function SynthesisStep({ workflowId, workflowData, onSynthesisComplete }: {
  workflowId: string | null;
  workflowData: WorkflowData;
  onSynthesisComplete?: (result?: any) => void;
}) {
  const { toast } = useToast();
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [isPreflighting, setIsPreflighting] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [lastResult, setLastResult] = useState<any>(null);
  const [preflight, setPreflight] = useState<any>(null);
  const [renderResult, setRenderResult] = useState<any>(null);
  const [renderBackend, setRenderBackend] = useState('local_artifact_package');
  const [externalConfigId, setExternalConfigId] = useState('');
  const [burnSubtitles, setBurnSubtitles] = useState(false);
  const [useEditableTimeline, setUseEditableTimeline] = useState(true);
  const [renderConfigs, setRenderConfigs] = useState<any[]>([]);
  const [isSyncingTimeline, setIsSyncingTimeline] = useState(false);
  const [timelineResult, setTimelineResult] = useState<any>(null);
  const [timelineTracks, setTimelineTracks] = useState<any[]>([]);
  const [timelineClips, setTimelineClips] = useState<any[]>([]);

  useEffect(() => {
    apiClient.getExternalConfigs()
      .then((configs) => {
        const renderOnly = configs.filter((config: any) =>
          config.api_type === 'render' && config.provider_key === 'ffmpeg_cloud'
        );
        setRenderConfigs(renderOnly);
        const defaultConfig = renderOnly.find((config: any) => config.is_default) || renderOnly[0];
        if (defaultConfig && !externalConfigId) {
          setExternalConfigId(defaultConfig.id);
        }
      })
      .catch(() => setRenderConfigs([]));
  }, [externalConfigId]);

  const handleSynthesis = async () => {
    if (workflowData.videoJobIds.length === 0 && workflowData.mediaJobIds.length === 0) {
      toast({ title: '请先生成视频草稿', description: '需要至少一个静音视频或直生音视频草稿。', type: 'info' });
      return;
    }

    if (!workflowId) {
      toast({ title: '工作流未初始化', description: '请刷新后再试。', type: 'info' });
      return;
    }

    setIsSynthesizing(true);
    try {
      const result = await apiClient.concatenateVideos(workflowId, {
        video_job_ids: workflowData.videoJobIds,
        media_job_ids: workflowData.mediaJobIds,
        tts_job_ids: workflowData.ttsJobIds,
        title: '最终视频',
        transition_style: 'fade',
        include_subtitles: true,
        subtitle_mode: 'dialogue',
        audio_mix_strategy: 'match_by_shot',
        quality_profile: 'review',
      });
      setLastResult(result);
      toast({ title: '连续成片编排已完成', type: 'success' });
      onSynthesisComplete?.(result);
    } catch (err: any) {
      toast({ title: '视频拼接失败', description: err.message || '请稍后重试。', type: 'error' });
    } finally {
      setIsSynthesizing(false);
    }
  };

  const handlePreflight = async () => {
    if (!workflowId) {
      toast({ title: '工作流未初始化', description: '请刷新后再试。', type: 'info' });
      return;
    }
    setIsPreflighting(true);
    try {
      const result = await apiClient.preflightWorkflowRender(workflowId, workflowData.synthesisJobId || lastResult?.job_id, {
        use_editable_timeline: useEditableTimeline,
        timeline_id: useEditableTimeline ? editableTimelineId : undefined,
      });
      setPreflight(result);
    } catch (err: any) {
      toast({ title: '渲染预检失败', description: err.message || '请稍后重试。', type: 'error' });
    } finally {
      setIsPreflighting(false);
    }
  };

  const handleRender = async (force = false) => {
    if (!workflowId) {
      toast({ title: '工作流未初始化', description: '请刷新后再试。', type: 'info' });
      return;
    }
    setIsRendering(true);
    try {
      const result = await apiClient.renderWorkflowPackage(workflowId, {
        synthesis_job_id: workflowData.synthesisJobId || lastResult?.job_id,
        quality_profile: 'review',
        render_backend: renderBackend,
        external_config_id: renderBackend === 'ffmpeg_cloud' ? externalConfigId || undefined : undefined,
        burn_subtitles: burnSubtitles,
        use_editable_timeline: useEditableTimeline,
        timeline_id: useEditableTimeline ? editableTimelineId : undefined,
        force,
      });
      setRenderResult(result);
      if (result.status === 'preflight_failed') {
        setPreflight({ ready: false, issues: result.issues || [], blocking_issue_count: result.issues?.length || 0 });
      } else {
        setPreflight({ ready: true, issues: [], blocking_issue_count: 0 });
      }
      onSynthesisComplete?.(result);
      toast({ title: result.status === 'preflight_failed' ? '渲染预检未通过' : '渲染包已生成', type: result.status === 'preflight_failed' ? 'info' : 'success' });
    } catch (err: any) {
      toast({ title: '本地渲染包生成失败', description: err.message || '请稍后重试。', type: 'error' });
    } finally {
      setIsRendering(false);
    }
  };

  const loadEditableTimeline = async (timelineId: string) => {
    try {
      const [tracks, clips] = await Promise.all([
        apiClient.getTimelineTracks(timelineId),
        apiClient.getTimelineClips(timelineId),
      ]);
      setTimelineTracks(tracks || []);
      setTimelineClips(clips || []);
    } catch (err) {
      console.error('加载时间线失败:', err);
    }
  };

  useEffect(() => {
    if (workflowData.editableTimelineId) {
      loadEditableTimeline(workflowData.editableTimelineId);
    }
  }, [workflowData.editableTimelineId]);

  const handleSyncTimeline = async (force = false) => {
    if (!workflowId) {
      toast({ title: '工作流未初始化', description: '请刷新后再试。', type: 'info' });
      return;
    }
    const synthesisJobId = workflowData.synthesisJobId || lastResult?.job_id;
    if (!synthesisJobId) {
      toast({ title: '请先生成连续成片清单', description: '完成合成编排后才能同步时间线。', type: 'info' });
      return;
    }
    setIsSyncingTimeline(true);
    try {
      const result = await apiClient.syncWorkflowTimeline(workflowId, {
        synthesis_job_id: synthesisJobId,
        name: '首集可编辑时间线',
        force,
      });
      setTimelineResult(result);
      await loadEditableTimeline(result.timeline_id);
      onSynthesisComplete?.({ timeline_id: result.timeline_id, timeline_clip_count: result.clip_count });
      toast({ title: '时间线已同步', description: `已生成 ${result.clip_count || 0} 个可编辑片段。`, type: 'success' });
    } catch (err: any) {
      toast({ title: '同步时间线失败', description: err.message || '请稍后重试。', type: 'error' });
    } finally {
      setIsSyncingTimeline(false);
    }
  };

  const manifestUrl = workflowData.synthesisManifestUrl || lastResult?.manifest_url;
  const outputUrl = renderResult?.output_url || workflowData.renderPreviewUrl || workflowData.synthesisOutputUrl || lastResult?.output_url;
  const segmentCount = workflowData.synthesisSegmentCount || lastResult?.segment_count || workflowData.videoJobIds.length + workflowData.mediaJobIds.length;
  const durationSeconds = workflowData.synthesisDurationSeconds || lastResult?.duration_seconds;
  const renderArtifacts = {
    preview_url: renderResult?.preview_url || workflowData.renderPreviewUrl,
    srt_url: renderResult?.srt_url || workflowData.renderSrtUrl,
    timeline_url: renderResult?.timeline_url || workflowData.renderTimelineUrl,
    render_manifest_url: renderResult?.render_manifest_url || workflowData.renderManifestUrl,
  };
  const renderStatus = renderResult?.status || workflowData.renderStatus;
  const renderIssues = preflight?.issues || workflowData.renderIssues || [];
  const editableTimelineId = timelineResult?.timeline_id || workflowData.editableTimelineId;
  const currentRenderSource = renderResult?.render_source || preflight?.render_source;
  const clipsByTrack = timelineTracks.map((track) => ({
    track,
    clips: timelineClips.filter((clip) => clip.track_id === track.id),
  }));

  return (
    <div className="space-y-4">
      <div className="p-4 bg-violet-500/10 border border-violet-500/30 rounded-lg">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-white font-medium">多镜头连续成片</div>
            <div className="text-white/60 text-sm">
              按镜头顺序生成时间线、配音轨、字幕轨、转场和成片清单
            </div>
          </div>
          <Button
            size="sm"
            disabled={(workflowData.videoJobIds.length === 0 && workflowData.mediaJobIds.length === 0) || isSynthesizing}
            onClick={handleSynthesis}
            className="bg-green-600 hover:bg-green-700"
          >
            <Merge className="w-4 h-4 mr-2" />
            {isSynthesizing ? '处理中…' : '生成连续成片'}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="p-4 bg-white/5 border border-white/10 rounded-lg">
          <div className="text-white/50 text-xs">视频镜头</div>
          <div className="text-2xl font-semibold text-white mt-1">{workflowData.videoJobIds.length + workflowData.mediaJobIds.length}</div>
        </div>
        <div className="p-4 bg-white/5 border border-white/10 rounded-lg">
          <div className="text-white/50 text-xs">配音轨</div>
          <div className="text-2xl font-semibold text-white mt-1">{workflowData.ttsJobIds.length || workflowData.mediaJobIds.length}</div>
        </div>
        <div className="p-4 bg-white/5 border border-white/10 rounded-lg">
          <div className="text-white/50 text-xs">成片段落</div>
          <div className="text-2xl font-semibold text-white mt-1">{segmentCount || 0}</div>
        </div>
        <div className="p-4 bg-white/5 border border-white/10 rounded-lg">
          <div className="text-white/50 text-xs">预计时长</div>
          <div className="text-2xl font-semibold text-white mt-1">
            {durationSeconds ? `${Math.round(durationSeconds)}s` : '--'}
          </div>
        </div>
      </div>

      {manifestUrl ? (
        <div className="space-y-3">
          <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
            <div className="flex items-start gap-3">
              <Check className="w-5 h-5 text-green-400 mt-0.5" />
              <div className="space-y-2">
                <div className="text-green-200 font-medium">连续成片清单已生成</div>
                <div className="text-green-100/70 text-sm">
                  清单包含镜头顺序、视频源、配音源、字幕、转场、时长和小说/章节/分镜/镜头血缘信息。
                </div>
                <div className="flex flex-wrap gap-2">
                  <a
                    href={toMediaUrl(manifestUrl)}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-green-200 underline"
                  >
                    查看成片清单
                  </a>
                  {outputUrl && (
                    <a
                      href={toMediaUrl(outputUrl)}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm text-green-200 underline"
                    >
                      查看当前输出
                    </a>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="p-4 bg-white/5 border border-white/10 rounded-lg">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="text-white font-medium">可编辑 Timeline</div>
                <div className="text-white/60 text-sm">
                  将连续成片清单落库为视频轨、对白轨和字幕轨，后续可调整片段位置、时长和字幕。
                </div>
                {editableTimelineId && (
                  <div className="mt-1 text-xs text-white/45">
                    时间线 ID：{editableTimelineId.slice(0, 8)} · 片段 {timelineResult?.clip_count || workflowData.editableTimelineClipCount || timelineClips.length || 0}
                  </div>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleSyncTimeline(Boolean(editableTimelineId))}
                  disabled={isSyncingTimeline}
                  className="border-white/20"
                >
                  {isSyncingTimeline ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Layers className="w-4 h-4 mr-2" />}
                  {editableTimelineId ? '重建时间线' : '生成可编辑时间线'}
                </Button>
              </div>
            </div>

            {timelineTracks.length > 0 && (
              <div className="mt-4 space-y-2">
                {clipsByTrack.map(({ track, clips }) => (
                  <div key={track.id} className="grid grid-cols-1 gap-2 rounded border border-white/10 bg-black/20 p-2 md:grid-cols-[140px_1fr]">
                    <div className="text-sm text-white/70">
                      <div className="font-medium">{track.name || track.track_type}</div>
                      <div className="text-xs text-white/35">{track.track_type}</div>
                    </div>
                    <div className="flex min-h-12 flex-wrap gap-2">
                      {clips.length > 0 ? clips.map((clip: any) => (
                        <div
                          key={clip.id}
                          className="min-w-[120px] rounded border border-violet-500/25 bg-violet-500/10 px-2 py-1"
                          title={`${clip.position}s / ${clip.duration}s`}
                        >
                          <div className="truncate text-xs font-medium text-white">{clip.name || clip.source_type}</div>
                          <div className="text-[11px] text-white/45">
                            {Math.round((clip.position || 0) * 10) / 10}s · {Math.round((clip.duration || 0) * 10) / 10}s
                          </div>
                          {clip.text_content && (
                            <div className="mt-1 line-clamp-1 text-[11px] text-cyan-100/70">{clip.text_content}</div>
                          )}
                        </div>
                      )) : (
                        <div className="text-xs text-white/35">暂无片段</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="p-4 bg-white/5 border border-white/10 rounded-lg">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="text-white font-medium">渲染预检与执行</div>
                <div className="text-white/60 text-sm">
                  检查视频、音频、字幕和时间线，输出本地包或提交云渲染
                </div>
                {renderStatus && (
                  <div className="mt-1 text-xs text-white/50">状态：{renderStatus}</div>
                )}
                <div className="mt-1 text-xs text-white/45">
                  默认优先消费最新可编辑 Timeline；关闭后按原始连续成片 manifest 生成。FFmpeg 云渲染会额外提交生产适配配置和字幕烧录参数。
                </div>
                {currentRenderSource && (
                  <div className="mt-1 text-xs text-cyan-100/70">
                    当前渲染源：{currentRenderSource === 'editable_timeline' ? '可编辑 Timeline' : '原始成片清单'}
                  </div>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={renderBackend}
                  onChange={(event) => setRenderBackend(event.target.value)}
                  className="h-9 rounded-md border border-white/10 bg-white/5 px-3 text-sm text-white"
                  title="渲染执行器"
                >
                  <option className="bg-gray-900" value="local_artifact_package">本地渲染包</option>
                  <option className="bg-gray-900" value="ffmpeg_cloud">FFmpeg 云渲染</option>
                </select>
                {renderBackend === 'ffmpeg_cloud' && (
                  <select
                    value={externalConfigId}
                    onChange={(event) => setExternalConfigId(event.target.value)}
                    className="h-9 rounded-md border border-white/10 bg-white/5 px-3 text-sm text-white"
                    title="FFmpeg 云渲染配置"
                  >
                    <option className="bg-gray-900" value="">默认/待配置</option>
                    {renderConfigs.map((config: any) => (
                      <option className="bg-gray-900" key={config.id} value={config.id}>
                        {config.name}
                      </option>
                    ))}
                  </select>
                )}
                <label className="flex h-9 items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 text-sm text-white/70">
                  <input
                    type="checkbox"
                    checked={useEditableTimeline}
                    disabled={!editableTimelineId}
                    onChange={(event) => setUseEditableTimeline(event.target.checked)}
                    className="accent-violet-500"
                  />
                  使用可编辑 Timeline
                </label>
                <label className="flex h-9 items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 text-sm text-white/70">
                  <input
                    type="checkbox"
                    checked={burnSubtitles}
                    onChange={(event) => setBurnSubtitles(event.target.checked)}
                    className="accent-violet-500"
                  />
                  烧录字幕
                </label>
                <Button variant="outline" size="sm" className="border-white/20" onClick={handlePreflight} disabled={isPreflighting}>
                  {isPreflighting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <AlertCircle className="w-4 h-4 mr-2" />}
                  渲染预检
                </Button>
                <Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={() => handleRender(Boolean(renderArtifacts.preview_url))} disabled={isRendering}>
                  {isRendering ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
                  {renderBackend === 'ffmpeg_cloud' ? '提交云渲染' : (renderArtifacts.preview_url ? '重新渲染' : '生成渲染包')}
                </Button>
              </div>
            </div>

            {preflight && (
              <div className={`mt-3 rounded border p-3 text-sm ${preflight.ready ? 'border-green-500/30 bg-green-500/10 text-green-100' : 'border-yellow-500/30 bg-yellow-500/10 text-yellow-100'}`}>
                {preflight.ready ? '预检通过，可以生成本地渲染包。' : `预检发现 ${preflight.issue_count || renderIssues.length} 个问题。`}
              </div>
            )}

            {renderIssues.length > 0 && (
              <div className="mt-3 space-y-2">
                {renderIssues.map((issue: any, index: number) => (
                  <div key={`${issue.code || 'issue'}-${index}`} className="rounded border border-yellow-500/30 bg-yellow-500/10 p-2 text-sm text-yellow-100">
                    {issue.message || issue.code}
                  </div>
                ))}
              </div>
            )}

            {(renderArtifacts.preview_url || renderArtifacts.srt_url || renderArtifacts.timeline_url || renderArtifacts.render_manifest_url) && (
              <div className="mt-3 flex flex-wrap gap-2 text-sm">
                {renderArtifacts.preview_url && <a className="text-blue-200 underline" href={toMediaUrl(renderArtifacts.preview_url)} target="_blank" rel="noreferrer">HTML 预览</a>}
                {renderArtifacts.srt_url && <a className="text-blue-200 underline" href={toMediaUrl(renderArtifacts.srt_url)} target="_blank" rel="noreferrer">SRT 字幕</a>}
                {renderArtifacts.timeline_url && <a className="text-blue-200 underline" href={toMediaUrl(renderArtifacts.timeline_url)} target="_blank" rel="noreferrer">时间线 EDL</a>}
                {renderArtifacts.render_manifest_url && <a className="text-blue-200 underline" href={toMediaUrl(renderArtifacts.render_manifest_url)} target="_blank" rel="noreferrer">渲染清单</a>}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="text-center py-12 text-white/40">
          <Merge className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>等待连续成片编排</p>
          <p className="text-sm mt-2">
            {workflowData.videoJobIds.length > 0 || workflowData.mediaJobIds.length > 0
              ? `${workflowData.videoJobIds.length} 个静音视频、${workflowData.mediaJobIds.length} 个直生音视频、${workflowData.ttsJobIds.length} 个 TTS，可生成时间线清单`
              : '请先生成视频或直生音视频'}
          </p>
        </div>
      )}
    </div>
  );
}

function ExportStep({ workflowData }: any) {
  const router = useRouter();
  const manifestUrl = workflowData.synthesisManifestUrl;
  const outputUrl = workflowData.renderPreviewUrl || workflowData.synthesisOutputUrl;
  const renderManifestUrl = workflowData.renderManifestUrl;
  const srtUrl = workflowData.renderSrtUrl;
  const timelineUrl = workflowData.renderTimelineUrl;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-white/60">导出最终视频作品</p>
      </div>

      <div className="text-center py-12">
        <Download className="w-16 h-16 mx-auto mb-4 text-violet-400 opacity-50" />
        <p className="text-xl text-white mb-2">恭喜！</p>
        <p className="text-white/60">
          您已完成从小说到连续成片的全部创作流程
        </p>

        <div className="mt-8 p-4 bg-white/5 rounded-lg inline-block">
          <div className="text-sm text-white/60 mb-2">创作统计</div>
          <div className="flex gap-8">
            <div className="text-center">
              <div className="text-2xl font-bold text-violet-400">
                {workflowData.videoJobIds.length + workflowData.mediaJobIds.length}
              </div>
              <div className="text-xs text-white/40">镜头视频</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-400">
                {workflowData.ttsJobIds.length || workflowData.mediaJobIds.length}
              </div>
              <div className="text-xs text-white/40">音频轨</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-400">
                {workflowData.synthesisSegmentCount || 0}
              </div>
              <div className="text-xs text-white/40">成片段落</div>
            </div>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {manifestUrl && (
            <Button
              variant="outline"
              onClick={() => window.open(toMediaUrl(manifestUrl), '_blank')}
              className="border-white/20"
            >
              <FileText className="w-4 h-4 mr-2" />
              成片清单
            </Button>
          )}
          {outputUrl && (
            <Button
              variant="outline"
              onClick={() => window.open(toMediaUrl(outputUrl), '_blank')}
              className="border-white/20"
            >
              <Play className="w-4 h-4 mr-2" />
              HTML 预览
            </Button>
          )}
          {srtUrl && (
            <Button
              variant="outline"
              onClick={() => window.open(toMediaUrl(srtUrl), '_blank')}
              className="border-white/20"
            >
              <FileText className="w-4 h-4 mr-2" />
              SRT 字幕
            </Button>
          )}
          {timelineUrl && (
            <Button
              variant="outline"
              onClick={() => window.open(toMediaUrl(timelineUrl), '_blank')}
              className="border-white/20"
            >
              <Layers className="w-4 h-4 mr-2" />
              时间线 EDL
            </Button>
          )}
          {renderManifestUrl && (
            <Button
              variant="outline"
              onClick={() => window.open(toMediaUrl(renderManifestUrl), '_blank')}
              className="border-white/20"
            >
              <FileText className="w-4 h-4 mr-2" />
              渲染清单
            </Button>
          )}
          <Button
            onClick={() => router.push('/dashboard')}
            className="bg-violet-600 hover:bg-violet-700"
          >
            <Download className="w-4 h-4 mr-2" />
            查看作品
          </Button>
        </div>
      </div>
    </div>
  );
}
