'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
  BookOpen,
  Captions,
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
  synthesisJobId?: string;
  outputUrl?: string;
  manifestUrl?: string;
  previewUrl?: string;
  srtUrl?: string;
  timelineUrl?: string;
  renderManifestUrl?: string;
  autoProduced?: boolean;
};

type ProgressStatus = 'pending' | 'running' | 'done' | 'failed';

type QuickStartProgressStep = {
  id: string;
  label: string;
  status: ProgressStatus;
  detail?: string;
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

const QUICK_START_DRAFT_KEY = 'ai-video-platform:quick-start-draft';
const API_ORIGIN = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1').replace(/\/api\/v1\/?$/, '');

const toMediaUrl = (url?: string) => {
  if (!url) return '';
  return url.startsWith('/') ? `${API_ORIGIN}${url}` : url;
};

const buildProgressSteps = (createStoryBible: boolean, autoProducePreview: boolean): QuickStartProgressStep[] => [
  { id: 'novel', label: '创建作品', status: 'pending' },
  { id: 'chapter', label: '创建首章', status: 'pending' },
  ...(createStoryBible ? [{ id: 'story_bible', label: '生成 Story Bible', status: 'pending' as ProgressStatus }] : []),
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
  return 'outline';
};

const progressStatusText = (status: ProgressStatus) => {
  if (status === 'done') return '完成';
  if (status === 'failed') return '失败';
  if (status === 'running') return '执行中';
  return '等待';
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
  const [result, setResult] = useState<QuickStartResult | null>(null);
  const [draftReady, setDraftReady] = useState(false);
  const [draftSavedAt, setDraftSavedAt] = useState<string | null>(null);
  const [modelConfigs, setModelConfigs] = useState<SavedModelConfig[]>([]);
  const [textModelConfigId, setTextModelConfigId] = useState('');
  const [videoModelConfigId, setVideoModelConfigId] = useState('');
  const [audioModelConfigId, setAudioModelConfigId] = useState('');
  const [progressSteps, setProgressSteps] = useState<QuickStartProgressStep[]>([]);

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
    } finally {
      setDraftReady(true);
    }
  }, []);

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
    }
  };

  const runQuickStart = async () => {
    if (!isReady) {
      const missing = checks.filter((item) => !item.ok).map((item) => item.label).join('、');
      setError(`请先补齐：${missing}`);
      return;
    }

    setIsRunning(true);
    setError(null);
    setResult(null);
    const initialSteps = buildProgressSteps(form.createStoryBible, form.autoProducePreview);
    setProgressSteps(initialSteps);
    let activeStepId = '';

    const markStep = (id: string, status: ProgressStatus, detail?: string) => {
      activeStepId = status === 'running' ? id : activeStepId;
      setProgressSteps((current) => {
        const source = current.length > 0 ? current : initialSteps;
        return source.map((step) => (step.id === id ? { ...step, status, detail } : step));
      });
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
      markStep('novel', 'done', '作品已保存');

      markStep('chapter', 'running', '正在保存首章正文');
      const chapter = await apiClient.createChapter({
        novel_id: novel.id,
        title: form.chapterTitle.trim() || '第一章',
        chapter_number: 1,
        content: chapterContent,
      });
      markStep('chapter', 'done', '首章已保存');

      let storyBibleId: string | undefined;
      if (form.createStoryBible) {
        markStep('story_bible', 'running', '正在提取故事设定、人物和世界观');
        const storyBible = await apiClient.generateStoryBible({
          novel_id: novel.id,
          title: `${title} Story Bible`,
          style: form.style,
          model_config_id: textModelConfigId || undefined,
        });
        storyBibleId = storyBible.id;
        markStep('story_bible', 'done', 'Story Bible 已生成');
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
      setResult(nextResult);

      if (form.autoProducePreview) {
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
          generationStrategy: 'separate_video_tts',
          onStage: (stage) => {
            const stepId = stageToStep[stage.key];
            if (stepId && stage.status) {
              markStep(stepId, stage.status, stage.message);
            }
          },
        });
        nextResult = {
          ...nextResult,
          scriptId: preview.scriptId || nextResult.scriptId,
          storyboardId: preview.storyboardId || nextResult.storyboardId,
          videoJobIds: preview.videoJobIds || [],
          ttsJobIds: preview.ttsJobIds || [],
          mediaJobIds: preview.mediaJobIds || [],
          subtitleTrackIds: preview.subtitleTrackIds || [],
          synthesisJobId: preview.synthesisJobId,
          outputUrl: preview.outputUrl,
          manifestUrl: preview.manifestUrl,
          previewUrl: preview.previewUrl,
          srtUrl: preview.srtUrl,
          timelineUrl: preview.timelineUrl,
          renderManifestUrl: preview.renderManifestUrl,
          autoProduced: preview.readyForConcatenate !== false && Boolean(preview.previewUrl || preview.renderManifestUrl),
        };
        setResult(nextResult);
      }
    } catch (err: any) {
      const message = err?.message || '极速向导执行失败';
      if (activeStepId) {
        markStep(activeStepId, 'failed', message);
      }
      setError(message);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white flex items-center gap-2">
              <Wand2 className="h-7 w-7 text-violet-400" />
              极速向导
            </h1>
            <p className="mt-1 text-white/60">一次创建小说、章节、Story Bible、智能分镜和工作流</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Button onClick={() => saveDraft(true)} variant="outline" className="border-white/20 text-white">
              <Save className="mr-2 h-4 w-4" />
              保存草稿
            </Button>
            <Button onClick={runQuickStart} disabled={isRunning} className="bg-violet-600 hover:bg-violet-700">
              {isRunning ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
              生成首集工程
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <Card className="bg-white/5 border-white/10">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-violet-400" />
                故事输入
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Input
                  value={form.title}
                  onChange={(event) => setForm({ ...form, title: event.target.value })}
                  placeholder="作品名"
                  className="bg-white/5 border-white/10 text-white"
                />
                <Input
                  value={form.chapterTitle}
                  onChange={(event) => setForm({ ...form, chapterTitle: event.target.value })}
                  placeholder="章节名"
                  className="bg-white/5 border-white/10 text-white"
                />
              </div>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-[1fr_1fr_160px]">
                <Select value={form.genre} onChange={(event) => setForm({ ...form, genre: event.target.value })} options={genreOptions} />
                <Select value={form.style} onChange={(event) => setForm({ ...form, style: event.target.value })} options={styleOptions} />
                <Input
                  type="number"
                  min={1}
                  max={12}
                  value={form.shotCount}
                  onChange={(event) => setForm({ ...form, shotCount: Number(event.target.value) })}
                  className="bg-white/5 border-white/10 text-white"
                />
              </div>
              <Textarea
                value={form.premise}
                onChange={(event) => setForm({ ...form, premise: event.target.value })}
                placeholder="故事梗概"
                className="min-h-[100px]"
              />
              <Textarea
                value={form.chapterContent}
                onChange={(event) => setForm({ ...form, chapterContent: event.target.value })}
                placeholder="首章正文"
                className="min-h-[180px]"
              />
              <label className="flex items-center gap-2 text-sm text-white/70">
                <input
                  type="checkbox"
                  checked={form.createStoryBible}
                  onChange={(event) => setForm({ ...form, createStoryBible: event.target.checked })}
                />
                同步生成 Story Bible 和实体上下文
              </label>
              <label className="flex items-center gap-2 text-sm text-white/70">
                <input
                  type="checkbox"
                  checked={form.autoProducePreview}
                  onChange={(event) => setForm({ ...form, autoProducePreview: event.target.checked })}
                />
                自动生成首集可预览草片、字幕和本地渲染包
              </label>
              <ModelCapabilitySelector
                capability="text"
                configs={modelConfigs}
                value={textModelConfigId}
                onChange={setTextModelConfigId}
                disabled={isRunning}
                title="首集工程文本模型"
                description="极速向导会用该文本模型生成 Story Bible，并为智能分镜准备一致性上下文。"
                compact
              />
              {form.autoProducePreview && (
                <>
                  <ModelCapabilitySelector
                    capability="video"
                    configs={modelConfigs}
                    value={videoModelConfigId}
                    onChange={setVideoModelConfigId}
                    disabled={isRunning}
                    title="首集草片视频模型"
                    description="自动出片会优先使用该视频能力配置；未配置时 DEV_MODE 会生成本地可播放草片。"
                    compact
                  />
                  <ModelCapabilitySelector
                    capability="audio"
                    configs={modelConfigs}
                    value={audioModelConfigId}
                    onChange={setAudioModelConfigId}
                    disabled={isRunning}
                    title="首集草片声音模型"
                    description="自动出片会用该声音模型生成角色对白，并在合成前执行字幕与时间线预检。"
                    compact
                  />
                </>
              )}
              <div className="text-xs text-white/40">
                草稿会自动保存在本机{draftSavedAt ? `，上次保存：${new Date(draftSavedAt).toLocaleString()}` : ''}。
              </div>
              {error && <div className="rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</div>}
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
                    作品名必填，故事梗概和章节内容至少 8 个字，镜头数需在 1-12 之间。点击“生成首集工程”会提示还缺哪些内容。
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
                  {progressSteps.map((step) => (
                    <div key={step.id} className="rounded border border-white/10 bg-white/5 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm text-white">{step.label}</span>
                        <Badge variant={progressBadgeVariant(step.status)}>
                          {step.status === 'running' && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
                          {progressStatusText(step.status)}
                        </Badge>
                      </div>
                      {step.detail && <div className="mt-1 text-xs text-white/50">{step.detail}</div>}
                    </div>
                  ))}
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
