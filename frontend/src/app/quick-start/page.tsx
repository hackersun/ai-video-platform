'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
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

const sampleStory = {
  title: '星灯邮差',
  premise:
    '十二岁的林澈在山城旧邮局发现一盏会说话的星灯。星灯告诉他，夜空中有一列只在雨后出现的云上列车，列车会把遗失的愿望送回主人身边。林澈决定成为临时邮差，帮沉默的转学生安禾找回她写给妈妈却从未寄出的信。',
  chapterTitle: '第一章 雨后的旧邮局',
  chapterContent:
    '暴雨停下时，山城的石阶像被星光洗过一样发亮。林澈抱着被雨打湿的书包，躲进街角那间早已停业的旧邮局。柜台后面忽然亮起一盏蓝色小灯，灯芯里传来细小的声音：“第七百二十一任邮差，你终于来了。”林澈吓得后退一步，却看见灯光照出一封没有地址的银色信封。信封上写着安禾的名字。窗外，一声悠长的汽笛从云层深处传来。',
};

const QUICK_START_DRAFT_KEY = 'ai-video-platform:quick-start-draft';
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
  const [productionStrategy, setProductionStrategy] = useState<ProductionStrategy>(DEFAULT_PRODUCTION_STRATEGY);
  const [progressSteps, setProgressSteps] = useState<QuickStartProgressStep[]>([]);
  const [advancedOpen, setAdvancedOpen] = useState(false);

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
          title: `${title} 动漫设定本`,
          style: form.style,
          model_config_id: textModelConfigId || undefined,
        });
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
          productionStrategy,
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
