'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { MainLayout } from '@/components/layout/main-layout';
import { ModelCapabilitySelector } from '@/components/model-capability-selector';
import { useToast } from '@/components/ui/toast';
import { 
  BookOpen, 
  Plus, 
  Trash2,
  Search,
  FileText,
  Users,
  Clock,
  Copy,
  Eye,
  Loader2,
  AlertCircle,
  ArrowLeft,
  Sparkles,
  Film,
  Volume2,
  Image,
  Play,
  Settings,
  ImageIcon,
  RefreshCw,
  ShieldCheck,
  ListChecks
} from 'lucide-react';
import Link from 'next/link';
import { fetchWithAuth } from '@/lib/fetch-with-auth';
import { apiClient } from '@/lib/api-client';
import {
  getDefaultConfigForCapability,
  SavedModelConfig,
} from '@/lib/model-configs';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, '');

const toMediaUrl = (url?: string | null) => {
  if (!url) return '';
  return url.startsWith('/') ? `${API_ORIGIN}${url}` : url;
};

interface Novel {
  id: string;
  title: string;
  description?: string;
  genre?: string;
  status: string;
  cover_url?: string;
  created_at: string;
  updated_at: string;
}

interface Chapter {
  id: string;
  title: string;
  chapter_number: number;
  word_count?: number;
  status: string;
  created_at: string;
}

interface Character {
  id: string;
  name: string;
  description?: string;
  avatar_url?: string;
}

interface Script {
  id: string;
  title: string;
  genre?: string;
  status: string;
  chapter_id?: string;
  created_at: string;
}

interface StoryboardSummary {
  id: string;
  script_id?: string;
  chapter_id?: string;
  title: string;
  shot_count?: number;
}

interface VideoJobSummary {
  id: string;
  chapter_id?: string;
  script_id?: string;
  storyboard_id?: string;
  shot_id?: string;
  status: string;
}

interface StoryBible {
  id: string;
  title: string;
  style?: string;
  worldview?: string;
  character_rules?: any[];
  scene_rules?: any[];
  prop_rules?: any[];
  event_timeline?: any[];
  negative_prompt?: string;
  extra_data?: Record<string, any>;
}

interface StoryStateMachine {
  summary?: {
    characters?: number;
    scenes?: number;
    props?: number;
    events?: number;
    issues?: number;
  };
  current_state?: {
    characters?: Record<string, any>;
    scenes?: Record<string, any>;
    props?: Record<string, any>;
  };
  prop_flows?: Record<string, any[]>;
  event_timeline?: any[];
  episode_states?: any[];
  issues?: any[];
  updated_at?: string;
}

interface SeriesEpisode {
  episode_number: number;
  title: string;
  status: string;
  next_action?: {
    label?: string;
    code?: string;
    description?: string;
  };
  chapter_ids?: string[];
  chapters?: Array<{
    id: string;
    chapter_number?: number;
    title: string;
    word_count?: number;
  }>;
  chapter_range?: {
    label?: string;
  };
  narrative?: {
    hook?: string;
    conflict?: string;
    turning_point?: string;
    cliffhanger?: string;
    next_episode_bridge?: string;
    summary?: string;
  };
  key_characters?: string[];
  key_scenes?: string[];
  key_props?: string[];
  key_events?: string[];
  production_counts?: {
    chapters?: number;
    scripts?: number;
    storyboards?: number;
    shots?: number;
    video_jobs?: number;
    media_jobs?: number;
    completed_media?: number;
  };
  primary_chapter_id?: string;
  workflow_id?: string | null;
}

interface SeriesPlan {
  version?: number;
  novel_id?: string;
  novel_title?: string;
  target_episode_count?: number;
  target_duration_seconds?: number;
  aspect_ratio?: string;
  style?: string;
  chapter_count?: number;
  updated_at?: string;
  episodes?: SeriesEpisode[];
  rules?: string[];
}

const statusLabels: Record<string, string> = {
  blocked: '缺章节',
  planned: '已规划',
  script_ready: '剧本完成',
  storyboard_ready: '分镜完成',
  shots_ready: '镜头就绪',
  media_generating: '生成中',
  media_ready: '可合成',
};

const entriesOf = (value?: Record<string, any> | null) => Object.entries(value || {});

export default function NovelDetailPage() {
  const { toast } = useToast();
  const params = useParams();
  const router = useRouter();
  const novelId = params.id as string;
  
  const [novel, setNovel] = useState<Novel | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [scripts, setScripts] = useState<Script[]>([]);
  const [storyboardSummaries, setStoryboardSummaries] = useState<StoryboardSummary[]>([]);
  const [videoSummaries, setVideoSummaries] = useState<VideoJobSummary[]>([]);
  const [storyBibles, setStoryBibles] = useState<StoryBible[]>([]);
  const [seriesPlan, setSeriesPlan] = useState<SeriesPlan | null>(null);
  const [storyStateMachine, setStoryStateMachine] = useState<StoryStateMachine | null>(null);
  const [stateMachineIssues, setStateMachineIssues] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // 新章节表单
  const [showChapterForm, setShowChapterForm] = useState(false);
  const [newChapterTitle, setNewChapterTitle] = useState('');
  const [newChapterContent, setNewChapterContent] = useState('');
  const [creatingChapter, setCreatingChapter] = useState(false);
  
  // 新角色表单
  const [showCharacterForm, setShowCharacterForm] = useState(false);
  const [newCharacterName, setNewCharacterName] = useState('');
  const [newCharacterDesc, setNewCharacterDesc] = useState('');
  const [creatingCharacter, setCreatingCharacter] = useState(false);
  const [settingsTitle, setSettingsTitle] = useState('');
  const [settingsDescription, setSettingsDescription] = useState('');
  const [settingsGenre, setSettingsGenre] = useState('');
  const [savingNovelSettings, setSavingNovelSettings] = useState(false);
  
  // 封面生成
  const [generatingCover, setGeneratingCover] = useState(false);
  const [coverPreview, setCoverPreview] = useState<string | null>(novel?.cover_url || null);
  const [extractingEntities, setExtractingEntities] = useState(false);
  const [entityMessage, setEntityMessage] = useState<string | null>(null);
  const [generatingBible, setGeneratingBible] = useState(false);
  const [checkingBible, setCheckingBible] = useState(false);
  const [generatingStateMachine, setGeneratingStateMachine] = useState(false);
  const [checkingStateMachine, setCheckingStateMachine] = useState(false);
  const [generatingSeriesPlan, setGeneratingSeriesPlan] = useState(false);
  const [startingEpisodeNumber, setStartingEpisodeNumber] = useState<number | null>(null);
  const [generatingScriptChapterId, setGeneratingScriptChapterId] = useState<string | null>(null);
  const [bibleMessage, setBibleMessage] = useState<string | null>(null);
  const [stateMachineMessage, setStateMachineMessage] = useState<string | null>(null);
  const [seriesPlanMessage, setSeriesPlanMessage] = useState<string | null>(null);
  const [bibleIssues, setBibleIssues] = useState<any[]>([]);
  const [modelConfigs, setModelConfigs] = useState<SavedModelConfig[]>([]);
  const [textModelConfigId, setTextModelConfigId] = useState('');
  const [imageModelConfigId, setImageModelConfigId] = useState('');

  useEffect(() => {
    if (novelId) {
      loadNovelData();
      loadModelConfigs();
    }
  }, [novelId]);

  const loadModelConfigs = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/llm/configs`);
      if (!res.ok) return;
      const configs = await res.json();
      const list = Array.isArray(configs) ? configs : [];
      setModelConfigs(list);
      const textDefault = getDefaultConfigForCapability(list, 'text');
      const imageDefault = getDefaultConfigForCapability(list, 'image');
      if (textDefault) setTextModelConfigId(textDefault.id);
      if (imageDefault) setImageModelConfigId(imageDefault.id);
    } catch (err) {
      console.error('加载模型配置失败:', err);
    }
  };

  const loadNovelData = async () => {
    setLoading(true);
    try {
      // 并行加载小说、章节、角色、剧本
      const [novelRes, chaptersRes, charactersRes, scriptsRes, storyBibleRes, seriesPlanRes] = await Promise.all([
        fetchWithAuth(`${API_BASE}/novels/${novelId}`),
        fetchWithAuth(`${API_BASE}/chapters/novel/${novelId}`),
        fetchWithAuth(`${API_BASE}/characters?novel_id=${novelId}`),
        fetchWithAuth(`${API_BASE}/scripts?novel_id=${novelId}`),
        fetchWithAuth(`${API_BASE}/story-bibles?novel_id=${novelId}`),
        fetchWithAuth(`${API_BASE}/novels/${novelId}/series-plan`)
      ]);
      
      if (novelRes.ok) {
        const novelData = await novelRes.json();
        setNovel(novelData);
        setSettingsTitle(novelData.title || '');
        setSettingsDescription(novelData.description || '');
        setSettingsGenre(novelData.genre || '');
      }
      
      if (chaptersRes.ok) {
        const chaptersData = await chaptersRes.json();
        setChapters(Array.isArray(chaptersData) ? chaptersData : []);
      }
      
      if (charactersRes.ok) {
        const charsData = await charactersRes.json();
        setCharacters(Array.isArray(charsData) ? charsData : []);
      }
      
      if (scriptsRes.ok) {
        const scriptsData = await scriptsRes.json();
        const scriptList = Array.isArray(scriptsData) ? scriptsData : [];
        setScripts(scriptList);
        const storyboardLists = await Promise.all(
          scriptList.map((script: Script) => apiClient.getStoryboards(script.id).catch(() => []))
        );
        setStoryboardSummaries(
          storyboardLists.flat().map((storyboard: any) => ({
            id: storyboard.id,
            script_id: storyboard.script_id,
            chapter_id: storyboard.chapter_id,
            title: storyboard.title,
            shot_count: storyboard.shot_count,
          }))
        );
        const videoJobs = await apiClient.getVideoJobs({ novel_id: novelId }).catch(() => []);
        setVideoSummaries(Array.isArray(videoJobs) ? videoJobs : []);
      }

      if (storyBibleRes.ok) {
        const bibleData = await storyBibleRes.json();
        const bibleList = Array.isArray(bibleData) ? bibleData : [];
        setStoryBibles(bibleList);
        const primaryBible = bibleList[0];
        const savedStateMachine = primaryBible?.extra_data?.state_machine;
        setStoryStateMachine(savedStateMachine || null);
        setStateMachineIssues(savedStateMachine?.issues || []);
      }

      if (seriesPlanRes.ok) {
        const planData = await seriesPlanRes.json();
        setSeriesPlan(planData && Object.keys(planData).length > 0 ? planData : null);
      } else {
        setSeriesPlan(null);
      }
    } catch (err) {
      setError('加载失败');
    } finally {
      setLoading(false);
    }
  };

  const generateScriptForChapter = async (chapterId: string) => {
    setGeneratingScriptChapterId(chapterId);
    try {
      const script = await apiClient.generateScript({
        chapter_id: chapterId,
        style: 'anime',
        model_config_id: textModelConfigId || undefined,
      });
      await loadNovelData();
      router.push(`/scripts/${script.id}`);
    } catch (err: any) {
      toast({ title: '剧本生成失败', description: err?.message || '请稍后重试。', type: 'error' });
    } finally {
      setGeneratingScriptChapterId(null);
    }
  };

  const createChapter = async () => {
    if (!newChapterTitle.trim()) return;
    
    setCreatingChapter(true);
    try {
      const res = await fetchWithAuth(`${API_BASE}/chapters`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          novel_id: novelId,
          title: newChapterTitle,
          content: newChapterContent || ' '
        })
      });
      
      if (res.ok) {
        setNewChapterTitle('');
        setNewChapterContent('');
        setShowChapterForm(false);
        loadNovelData();
      }
    } finally {
      setCreatingChapter(false);
    }
  };

  const createCharacter = async () => {
    if (!newCharacterName.trim()) return;
    
    setCreatingCharacter(true);
    try {
      const res = await fetchWithAuth(`${API_BASE}/characters`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          novel_id: novelId,
          name: newCharacterName,
          description: newCharacterDesc
        })
      });
      
      if (res.ok) {
        setNewCharacterName('');
        setNewCharacterDesc('');
        setShowCharacterForm(false);
        loadNovelData();
      }
    } finally {
      setCreatingCharacter(false);
    }
  };

  // 生成封面
  const handleGenerateCover = async () => {
    if (!novel) return;
    
    setGeneratingCover(true);
    try {
      const res = await fetchWithAuth(`${API_BASE}/novels/${novelId}/generate-cover`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: novel.title,
          genre: novel.genre || '通用',
          description: novel.description || '',
          prompt: '优先呈现主要人物、核心场景、关键道具和故事冲突',
          model_config_id: imageModelConfigId || undefined,
        })
      });
      
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || data.message || '生成失败');
      }
      if (data.cover_url) {
        setCoverPreview(data.cover_url);
        setNovel({ ...novel, cover_url: data.cover_url });
      }
      toast({ title: '封面生成成功', description: data.message || '已根据小说简介和故事上下文生成。', type: 'success' });
    } catch (err: any) {
      console.error('生成封面失败:', err);
      toast({ title: '封面生成失败', description: err?.message || '请检查图像模型配置。', type: 'error' });
    } finally {
      setGeneratingCover(false);
    }
  };

  const handleExtractEntities = async () => {
    setExtractingEntities(true);
    setEntityMessage(null);
    try {
      const extracted = await apiClient.extractNovelEntities({
        novel_id: novelId,
        entity_types: ['character', 'scene', 'prop', 'event'],
        persist: true,
        model_config_id: textModelConfigId || undefined,
      });
      setEntityMessage(`已提取 ${Array.isArray(extracted?.entities) ? extracted.entities.length : 0} 个实体`);
      await loadNovelData();
    } catch (err: any) {
      setEntityMessage(err?.message || '实体提取失败');
    } finally {
      setExtractingEntities(false);
    }
  };

  const handleGenerateStoryBible = async () => {
    if (!novel) return;

    setGeneratingBible(true);
    setBibleMessage(null);
    try {
      const bible = await apiClient.generateStoryBible({
        novel_id: novelId,
        title: `${novel.title} Story Bible`,
        style: novel.genre || 'anime',
        model_config_id: textModelConfigId || undefined,
      });
      setStoryBibles((prev) => [bible, ...prev.filter((item) => item.id !== bible.id)]);
      setStoryStateMachine(bible?.extra_data?.state_machine || null);
      setStateMachineIssues([]);
      setBibleMessage('Story Bible 已生成');
    } catch (err: any) {
      setBibleMessage(err?.message || 'Story Bible 生成失败');
    } finally {
      setGeneratingBible(false);
    }
  };

  const handleCheckStoryBible = async () => {
    const storyBible = storyBibles[0];
    if (!storyBible) {
      setBibleMessage('请先生成 Story Bible');
      return;
    }

    setCheckingBible(true);
    setBibleMessage(null);
    try {
      const result = await apiClient.checkStoryBible({
        story_bible_id: storyBible.id,
        novel_id: novelId,
      });
      setBibleIssues(result.issues || []);
      setBibleMessage(`检查完成：${result.issue_count || 0} 个提示`);
    } catch (err: any) {
      setBibleMessage(err?.message || 'Story Bible 检查失败');
    } finally {
      setCheckingBible(false);
    }
  };

  const handleGenerateStateMachine = async () => {
    const storyBible = storyBibles[0];
    if (!storyBible) {
      setStateMachineMessage('请先生成 Story Bible');
      return;
    }
    setGeneratingStateMachine(true);
    setStateMachineMessage(null);
    try {
      const result = await apiClient.generateStoryBibleStateMachine(storyBible.id, {
        novel_id: novelId,
        persist: true,
      });
      const machine = result.state_machine || {};
      setStoryStateMachine(machine);
      setStateMachineIssues(machine.issues || []);
      setStoryBibles((prev) =>
        prev.map((item) =>
          item.id === storyBible.id
            ? { ...item, extra_data: { ...(item.extra_data || {}), state_machine: machine } }
            : item
        )
      );
      setStateMachineMessage(`状态机已生成：人物 ${machine.summary?.characters || 0}、场景 ${machine.summary?.scenes || 0}、道具 ${machine.summary?.props || 0}、事件 ${machine.summary?.events || 0}`);
      toast({ title: 'Story Bible 状态机已生成', type: 'success' });
    } catch (err: any) {
      const message = err?.message || '状态机生成失败';
      setStateMachineMessage(message);
      toast({ title: '状态机生成失败', description: message, type: 'error' });
    } finally {
      setGeneratingStateMachine(false);
    }
  };

  const handleCheckStateMachine = async () => {
    const storyBible = storyBibles[0];
    if (!storyBible) {
      setStateMachineMessage('请先生成 Story Bible');
      return;
    }
    setCheckingStateMachine(true);
    setStateMachineMessage(null);
    try {
      const result = await apiClient.checkStoryBibleStateMachine(storyBible.id, {
        novel_id: novelId,
      });
      setStateMachineIssues(result.issues || []);
      setStateMachineMessage(`状态机检查完成：${result.issue_count || 0} 个提示`);
    } catch (err: any) {
      setStateMachineMessage(err?.message || '状态机检查失败');
    } finally {
      setCheckingStateMachine(false);
    }
  };

  const handleGenerateSeriesPlan = async () => {
    setGeneratingSeriesPlan(true);
    setSeriesPlanMessage(null);
    try {
      const plan = await apiClient.generateNovelSeriesPlan(novelId, {
        target_episode_count: chapters.length > 0 ? Math.min(12, Math.max(1, Math.ceil(chapters.length / 2))) : undefined,
        target_duration_seconds: 60,
        aspect_ratio: '9:16',
        style: novel?.genre || 'anime',
        persist: true,
      });
      setSeriesPlan(plan);
      setSeriesPlanMessage(`已生成 ${plan?.episodes?.length || 0} 集整书生产计划`);
      toast({ title: '整书生产计划已生成', type: 'success' });
    } catch (err: any) {
      const message = err?.message || '整书生产计划生成失败';
      setSeriesPlanMessage(message);
      toast({ title: '整书生产计划生成失败', description: message, type: 'error' });
    } finally {
      setGeneratingSeriesPlan(false);
    }
  };

  const handleContinueEpisode = async (episode: SeriesEpisode) => {
    const chapterId = episode.primary_chapter_id || episode.chapter_ids?.[0];
    if (!chapterId) {
      toast({ title: '无法继续本集', description: '该集没有关联章节。', type: 'error' });
      return;
    }
    setStartingEpisodeNumber(episode.episode_number);
    try {
      if (episode.workflow_id) {
        router.push(`/workflow?workflow_id=${episode.workflow_id}&novel_id=${novelId}&chapter_id=${chapterId}`);
        return;
      }
      const workflow = await apiClient.startWorkflow({
        title: `${novel?.title || '漫剧'} ${episode.title}`,
        novel_id: novelId,
        chapter_id: chapterId,
      });
      const workflowId = workflow?.workflow_id || workflow?.id;
      await loadNovelData();
      router.push(`/workflow?workflow_id=${workflowId}&novel_id=${novelId}&chapter_id=${chapterId}`);
    } catch (err: any) {
      toast({ title: '本集工程创建失败', description: err?.message || '请稍后重试。', type: 'error' });
    } finally {
      setStartingEpisodeNumber(null);
    }
  };

  const handleSaveNovelSettings = async () => {
    if (!settingsTitle.trim()) {
      toast({ title: '请填写小说标题', type: 'error' });
      return;
    }
    setSavingNovelSettings(true);
    try {
      const updated = await apiClient.updateNovel(novelId, {
        title: settingsTitle.trim(),
        description: settingsDescription,
        genre: settingsGenre,
      });
      setNovel(updated);
      setSettingsTitle(updated.title || '');
      setSettingsDescription(updated.description || '');
      setSettingsGenre(updated.genre || '');
      toast({ title: '小说设置已保存', type: 'success' });
    } catch (err: any) {
      toast({ title: '保存失败', description: err?.message || '请稍后重试。', type: 'error' });
    } finally {
      setSavingNovelSettings(false);
    }
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="space-y-6 px-4 max-w-6xl mx-auto">
          {/* 顶部导航 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Skeleton className="w-20 h-10" />
              <Skeleton className="w-48 h-8" />
            </div>
            <Skeleton className="w-32 h-10" />
          </div>

          {/* 封面区域 */}
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-6">
              <div className="flex gap-6">
                <Skeleton className="w-32 h-44 rounded-lg" />
                <div className="flex-1 space-y-3">
                  <Skeleton className="w-3/4 h-8" />
                  <Skeleton className="w-1/2 h-4" />
                  <Skeleton className="w-full h-20" />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 标签页 */}
          <Skeleton className="w-full h-12" />

          {/* 内容区域 */}
          <Skeleton className="w-full h-64" />
        </div>
      </MainLayout>
    );
  }

  if (!novel) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 text-red-500" />
          <h2 className="text-xl font-bold text-white mb-2">小说不存在</h2>
          <Button onClick={() => router.push('/novels')}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            返回列表
          </Button>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 顶部导航 */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex min-w-0 items-start gap-3 sm:gap-4">
            <Button variant="ghost" onClick={() => router.push('/novels')}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              返回
            </Button>
            <div className="min-w-0">
              <h1 className="flex items-center gap-2 break-words text-2xl font-bold text-white">
                <BookOpen className="h-6 w-6 shrink-0" />
                {novel.title}
              </h1>
              <p className="text-white/60 text-sm mt-1">
                {novel.genre} · {novel.status === 'draft' ? '草稿' : novel.status === 'writing' ? '创作中' : '已完成'}
              </p>
            </div>
          </div>
          
          {/* 快捷操作 */}
          <div className="flex flex-wrap gap-2 sm:justify-end">
            <Button 
              variant="outline" 
              className="border-violet-500/50"
              onClick={handleGenerateCover}
              disabled={generatingCover}
            >
              {generatingCover ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <ImageIcon className="w-4 h-4 mr-2" />
              )}
              生成封面
            </Button>
            <Button asChild className="bg-violet-600 hover:bg-violet-700">
              <Link href={`/video-generation?novel_id=${novelId}`}>
                <Film className="w-4 h-4 mr-2" />
                开始视频
              </Link>
            </Button>
            <Button
              variant="outline"
              className="border-blue-500/50"
              onClick={handleGenerateSeriesPlan}
              disabled={generatingSeriesPlan || chapters.length === 0}
            >
              {generatingSeriesPlan ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <ListChecks className="w-4 h-4 mr-2" />
              )}
              整书计划
            </Button>
          </div>
        </div>

        {/* 封面图预览 */}
        {(novel.cover_url || coverPreview) && (
          <Card className="bg-white/5 border-white/10 overflow-hidden">
            <CardContent className="p-4">
              <div className="relative aspect-video max-w-md mx-auto rounded-lg overflow-hidden bg-black/20">
                <img 
                  src={toMediaUrl(coverPreview || novel.cover_url)}
                  alt={novel.title}
                  width={640}
                  height={360}
                  loading="lazy"
                  className="w-full h-full object-contain"
                />
              </div>
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <ModelCapabilitySelector
            capability="text"
            configs={modelConfigs}
            value={textModelConfigId}
            onChange={setTextModelConfigId}
            disabled={extractingEntities || generatingBible}
            title="文本生成默认"
            description="实体提取和 Story Bible 生成会读取小说、章节、角色、场景、道具和事件上下文。"
          />
          <ModelCapabilitySelector
            capability="image"
            configs={modelConfigs}
            value={imageModelConfigId}
            onChange={setImageModelConfigId}
            disabled={generatingCover}
            title="图像生成默认"
            description="小说封面会优先使用该图像模型，并绑定当前小说的题材和核心内容。"
          />
        </div>

        {/* 标签页 */}
        <Tabs defaultValue="chapters" className="space-y-4">
          <TabsList className="h-auto max-w-full flex-wrap justify-start bg-white/5">
            <TabsTrigger value="chapters" className="data-[state=active]:bg-violet-600">
              <FileText className="w-4 h-4 mr-2" />
              章节 ({chapters.length})
            </TabsTrigger>
            <TabsTrigger value="series-plan" className="data-[state=active]:bg-violet-600">
              <ListChecks className="w-4 h-4 mr-2" />
              整书计划 ({seriesPlan?.episodes?.length || 0})
            </TabsTrigger>
            <TabsTrigger value="characters" className="data-[state=active]:bg-violet-600">
              <Users className="w-4 h-4 mr-2" />
              角色 ({characters.length})
            </TabsTrigger>
            <TabsTrigger value="scripts" className="data-[state=active]:bg-violet-600">
              <FileText className="w-4 h-4 mr-2" />
              剧本 ({scripts.length})
            </TabsTrigger>
            <TabsTrigger value="story-bible" className="data-[state=active]:bg-violet-600">
              <ShieldCheck className="w-4 h-4 mr-2" />
              Story Bible ({storyBibles.length})
            </TabsTrigger>
            <TabsTrigger value="settings" className="data-[state=active]:bg-violet-600">
              <Settings className="w-4 h-4 mr-2" />
              设置
            </TabsTrigger>
          </TabsList>

          {/* 章节列表 */}
          <TabsContent value="chapters">
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <CardTitle className="text-white">章节管理</CardTitle>
                <Button size="sm" onClick={() => setShowChapterForm(!showChapterForm)}>
                  <Plus className="w-4 h-4 mr-2" />
                  新建章节
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* 新建章节表单 */}
                {showChapterForm && (
                  <div className="p-4 bg-white/5 rounded-lg space-y-3">
                    <Input
                      placeholder="章节标题"
                      value={newChapterTitle}
                      onChange={(e) => setNewChapterTitle(e.target.value)}
                      className="bg-white/10 border-white/20 text-white"
                    />
                    <Textarea
                      placeholder="章节内容（可选，后续可编辑）"
                      value={newChapterContent}
                      onChange={(e) => setNewChapterContent(e.target.value)}
                      className="bg-white/10 border-white/20 text-white min-h-[100px]"
                    />
                    <div className="flex gap-2">
                      <Button 
                        size="sm" 
                        onClick={createChapter}
                        disabled={creatingChapter || !newChapterTitle.trim()}
                        className="bg-violet-600 hover:bg-violet-700"
                      >
                        {creatingChapter && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                        创建
                      </Button>
                      <Button 
                        size="sm" 
                        variant="ghost"
                        onClick={() => setShowChapterForm(false)}
                      >
                        取消
                      </Button>
                    </div>
                  </div>
                )}
                
                {/* 章节列表 */}
                {chapters.length === 0 ? (
                  <div className="text-center py-8 text-white/40">
                    <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>暂无章节</p>
                    <p className="text-sm">点击"新建章节"开始创作</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {chapters.map((chapter, index) => (
                      <div key={chapter.id} className="rounded-lg bg-white/5 p-3 transition-colors hover:bg-white/10">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                          <Link href={`/novels/${novelId}/chapters/${chapter.id}`} className="flex min-w-0 flex-1 items-center gap-3">
                            <span className="text-white/40 text-sm w-8">
                              {chapter.chapter_number || index + 1}
                            </span>
                            <div className="min-w-0">
                              <div className="break-words text-white font-medium">{chapter.title}</div>
                              <div className="text-white/40 text-sm">
                                {chapter.word_count || 0} 字 · {chapter.status || '草稿'}
                              </div>
                            </div>
                          </Link>
                          <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                            {(() => {
                              const chapterScripts = scripts.filter((script) => script.chapter_id === chapter.id);
                              const chapterStoryboards = storyboardSummaries.filter((storyboard) =>
                                chapterScripts.some((script) => script.id === storyboard.script_id) || storyboard.chapter_id === chapter.id
                              );
                              const chapterVideos = videoSummaries.filter((job) => job.chapter_id === chapter.id);
                              return (
                                <>
                                  <Badge variant="outline" className="border-blue-400/40 text-blue-200">剧本 {chapterScripts.length}</Badge>
                                  <Badge variant="outline" className="border-violet-400/40 text-violet-200">分镜 {chapterStoryboards.length}</Badge>
                                  <Badge variant="outline" className="border-green-400/40 text-green-200">视频 {chapterVideos.length}</Badge>
                                </>
                              );
                            })()}
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => generateScriptForChapter(chapter.id)}
                              disabled={generatingScriptChapterId === chapter.id}
                              className="border-violet-500/50"
                            >
                              {generatingScriptChapterId === chapter.id ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1" />}
                              生成剧本
                            </Button>
                            <Button asChild size="sm" variant="ghost">
                              <Link href={`/scripts?novel_id=${novelId}&chapter_id=${chapter.id}`}>
                                <FileText className="w-4 h-4 mr-1" />
                                查看
                              </Link>
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="series-plan">
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2 text-white">
                    <ListChecks className="h-5 w-5 text-blue-300" />
                    整部漫剧生产计划
                  </CardTitle>
                  <p className="mt-1 text-sm text-white/50">
                    按章节顺序拆成多集，统一管理每集剧情钩子、人物场景道具事件和生产状态。
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 sm:justify-end">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={loadNovelData}
                    className="border-white/20"
                  >
                    <RefreshCw className="w-4 h-4 mr-2" />
                    刷新
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleGenerateSeriesPlan}
                    disabled={generatingSeriesPlan || chapters.length === 0}
                    className="bg-violet-600 hover:bg-violet-700"
                  >
                    {generatingSeriesPlan ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
                    生成多集计划
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {seriesPlanMessage && (
                  <div className="rounded-md bg-white/5 px-3 py-2 text-sm text-white/60">{seriesPlanMessage}</div>
                )}

                {chapters.length === 0 ? (
                  <div className="text-center py-8 text-white/40">
                    <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>暂无章节</p>
                    <p className="text-sm">先导入或创建章节后，再生成整书生产计划</p>
                  </div>
                ) : !seriesPlan?.episodes?.length ? (
                  <div className="rounded-lg border border-dashed border-white/15 bg-white/5 p-6 text-center">
                    <ListChecks className="mx-auto mb-3 h-10 w-10 text-blue-300" />
                    <div className="text-white font-medium">还没有整书生产计划</div>
                    <p className="mx-auto mt-2 max-w-2xl text-sm text-white/50">
                      生成后会得到每集覆盖章节、剧情钩子、冲突/反转/悬念、关键角色场景道具事件，以及剧本、分镜、镜头和音视频生产状态。
                    </p>
                    <Button
                      className="mt-4 bg-violet-600 hover:bg-violet-700"
                      onClick={handleGenerateSeriesPlan}
                      disabled={generatingSeriesPlan}
                    >
                      {generatingSeriesPlan ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
                      AI 生成多集计划
                    </Button>
                  </div>
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                      <div className="rounded-lg bg-white/5 p-3">
                        <div className="text-xs text-white/40">计划集数</div>
                        <div className="mt-1 text-xl font-semibold text-white">{seriesPlan.target_episode_count || seriesPlan.episodes.length}</div>
                      </div>
                      <div className="rounded-lg bg-white/5 p-3">
                        <div className="text-xs text-white/40">覆盖章节</div>
                        <div className="mt-1 text-xl font-semibold text-white">{seriesPlan.chapter_count || chapters.length}</div>
                      </div>
                      <div className="rounded-lg bg-white/5 p-3">
                        <div className="text-xs text-white/40">单集时长</div>
                        <div className="mt-1 text-xl font-semibold text-white">{seriesPlan.target_duration_seconds || 60}s</div>
                      </div>
                      <div className="rounded-lg bg-white/5 p-3">
                        <div className="text-xs text-white/40">风格画幅</div>
                        <div className="mt-1 truncate text-sm font-medium text-white">{seriesPlan.style || novel.genre || 'anime'} · {seriesPlan.aspect_ratio || '9:16'}</div>
                      </div>
                    </div>

                    <div className="space-y-3">
                      {seriesPlan.episodes.map((episode) => {
                        const counts = episode.production_counts || {};
                        return (
                          <div key={episode.episode_number} className="rounded-lg bg-white/5 p-4">
                            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                              <div className="min-w-0 flex-1">
                                <div className="flex flex-wrap items-center gap-2">
                                  <h3 className="break-words text-base font-semibold text-white">{episode.title}</h3>
                                  <Badge variant="outline" className="border-blue-400/40 text-blue-200">
                                    {statusLabels[episode.status] || episode.status}
                                  </Badge>
                                  <Badge variant="outline" className="border-white/20 text-white/60">
                                    {episode.chapter_range?.label || `${episode.chapters?.length || 0} 章`}
                                  </Badge>
                                </div>
                                <p className="mt-2 text-sm text-white/55 line-clamp-2">{episode.narrative?.summary || episode.narrative?.hook}</p>
                              </div>
                              <Button
                                size="sm"
                                onClick={() => handleContinueEpisode(episode)}
                                disabled={startingEpisodeNumber === episode.episode_number}
                                className="shrink-0 bg-violet-600 hover:bg-violet-700"
                              >
                                {startingEpisodeNumber === episode.episode_number ? (
                                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                ) : (
                                  <Play className="w-4 h-4 mr-2" />
                                )}
                                {episode.workflow_id ? '继续本集工程' : episode.next_action?.label || '创建本集工程'}
                              </Button>
                            </div>

                            <div className="mt-3 grid gap-2 text-sm text-white/60 md:grid-cols-2">
                              <div className="rounded-md bg-black/10 p-3">
                                <div className="mb-1 text-white/80">剧情控制</div>
                                <div>钩子：{episode.narrative?.hook || '待生成'}</div>
                                <div>冲突：{episode.narrative?.conflict || '待生成'}</div>
                                <div>悬念：{episode.narrative?.cliffhanger || '待生成'}</div>
                              </div>
                              <div className="rounded-md bg-black/10 p-3">
                                <div className="mb-1 text-white/80">一致性资产</div>
                                <div>人物：{episode.key_characters?.join('、') || '待提取'}</div>
                                <div>场景：{episode.key_scenes?.join('、') || '待提取'}</div>
                                <div>道具：{episode.key_props?.join('、') || '待提取'}</div>
                              </div>
                            </div>

                            <div className="mt-3 flex flex-wrap gap-2">
                              <Badge variant="outline" className="border-white/20 text-white/60">剧本 {counts.scripts || 0}</Badge>
                              <Badge variant="outline" className="border-white/20 text-white/60">分镜 {counts.storyboards || 0}</Badge>
                              <Badge variant="outline" className="border-white/20 text-white/60">镜头 {counts.shots || 0}</Badge>
                              <Badge variant="outline" className="border-white/20 text-white/60">视频任务 {counts.video_jobs || 0}</Badge>
                              <Badge variant="outline" className="border-white/20 text-white/60">直生任务 {counts.media_jobs || 0}</Badge>
                              <Badge variant="outline" className="border-green-400/40 text-green-200">完成媒体 {counts.completed_media || 0}</Badge>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* 角色列表 */}
          <TabsContent value="characters">
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <CardTitle className="text-white">角色管理</CardTitle>
                <div className="flex flex-wrap gap-2 sm:justify-end">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleExtractEntities}
                    disabled={extractingEntities}
                    className="border-violet-500/50"
                  >
                    {extractingEntities ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
                    提取实体
                  </Button>
                  <Button size="sm" onClick={() => setShowCharacterForm(!showCharacterForm)}>
                    <Plus className="w-4 h-4 mr-2" />
                    新建角色
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {entityMessage && (
                  <div className="rounded-md bg-white/5 px-3 py-2 text-sm text-white/60">{entityMessage}</div>
                )}
                {/* 新建角色表单 */}
                {showCharacterForm && (
                  <div className="p-4 bg-white/5 rounded-lg space-y-3">
                    <Input
                      placeholder="角色名称"
                      value={newCharacterName}
                      onChange={(e) => setNewCharacterName(e.target.value)}
                      className="bg-white/10 border-white/20 text-white"
                    />
                    <Textarea
                      placeholder="角色描述"
                      value={newCharacterDesc}
                      onChange={(e) => setNewCharacterDesc(e.target.value)}
                      className="bg-white/10 border-white/20 text-white min-h-[80px]"
                    />
                    <div className="flex gap-2">
                      <Button 
                        size="sm" 
                        onClick={createCharacter}
                        disabled={creatingCharacter || !newCharacterName.trim()}
                        className="bg-violet-600 hover:bg-violet-700"
                      >
                        {creatingCharacter && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                        创建
                      </Button>
                      <Button 
                        size="sm" 
                        variant="ghost"
                        onClick={() => setShowCharacterForm(false)}
                      >
                        取消
                      </Button>
                    </div>
                  </div>
                )}
                
                {/* 角色列表 */}
                {characters.length === 0 ? (
                  <div className="text-center py-8 text-white/40">
                    <Users className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>暂无角色</p>
                    <p className="text-sm">点击"新建角色"添加</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {characters.map((char) => (
                      <div
                        key={char.id}
                        className="p-4 bg-white/5 rounded-lg hover:bg-white/10 transition-colors"
                      >
                        <div className="w-16 h-16 rounded-full bg-violet-500/20 flex items-center justify-center mx-auto mb-3">
                          <Users className="w-8 h-8 text-violet-400" />
                        </div>
                        <div className="text-center">
                          <div className="text-white font-medium">{char.name}</div>
                          <div className="text-white/40 text-sm truncate">
                            {char.description || '暂无描述'}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="story-bible">
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <CardTitle className="text-white flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-violet-400" />
                  Story Bible
                </CardTitle>
                <div className="flex flex-wrap gap-2 sm:justify-end">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={loadNovelData}
                    className="border-white/20"
                  >
                    <RefreshCw className="w-4 h-4 mr-2" />
                    刷新
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleGenerateStoryBible}
                    disabled={generatingBible}
                    className="bg-violet-600 hover:bg-violet-700"
                  >
                    {generatingBible ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
                    生成
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleCheckStoryBible}
                    disabled={checkingBible || storyBibles.length === 0}
                    className="border-violet-500/50"
                  >
                    {checkingBible ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ShieldCheck className="w-4 h-4 mr-2" />}
                    检查
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleGenerateStateMachine}
                    disabled={generatingStateMachine || storyBibles.length === 0}
                    className="border-blue-500/50"
                  >
                    {generatingStateMachine ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ListChecks className="w-4 h-4 mr-2" />}
                    状态机
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleCheckStateMachine}
                    disabled={checkingStateMachine || storyBibles.length === 0}
                    className="border-yellow-500/50"
                  >
                    {checkingStateMachine ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <AlertCircle className="w-4 h-4 mr-2" />}
                    状态检查
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {bibleMessage && (
                  <div className="rounded-md bg-white/5 px-3 py-2 text-sm text-white/60">{bibleMessage}</div>
                )}
                {stateMachineMessage && (
                  <div className="rounded-md bg-blue-500/10 px-3 py-2 text-sm text-blue-100">{stateMachineMessage}</div>
                )}

                {storyBibles.length === 0 ? (
                  <div className="text-center py-8 text-white/40">
                    <ShieldCheck className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>暂无 Story Bible</p>
                    <p className="text-sm">可基于章节和角色生成一致性设定</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {storyBibles.map((bible) => (
                      <div key={bible.id} className="rounded-lg bg-white/5 p-4">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <div className="text-white font-medium">{bible.title}</div>
                            <div className="text-white/50 text-sm mt-1">
                              风格：{bible.style || '未设置'} · 角色规则 {bible.character_rules?.length || 0} · 场景规则 {bible.scene_rules?.length || 0}
                            </div>
                          </div>
                          <Badge variant="outline" className="text-violet-300 border-violet-400/50">
                            {bible.negative_prompt ? '含负面提示' : '基础版'}
                          </Badge>
                        </div>
                        {bible.worldview && (
                          <p className="text-white/60 text-sm mt-3 line-clamp-3">{bible.worldview}</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {storyStateMachine ? (
                  <div className="rounded-lg border border-blue-500/20 bg-blue-500/10 p-4">
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div>
                        <div className="flex items-center gap-2 text-white font-medium">
                          <ListChecks className="h-4 w-4 text-blue-200" />
                          跨章节状态机
                        </div>
                        <p className="mt-1 text-sm text-white/55">
                          人物、场景、道具和事件状态会进入后续章节、分镜、镜头和视频生成约束。
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="outline" className="border-blue-300/40 text-blue-100">人物 {storyStateMachine.summary?.characters || 0}</Badge>
                        <Badge variant="outline" className="border-blue-300/40 text-blue-100">场景 {storyStateMachine.summary?.scenes || 0}</Badge>
                        <Badge variant="outline" className="border-blue-300/40 text-blue-100">道具 {storyStateMachine.summary?.props || 0}</Badge>
                        <Badge variant="outline" className="border-blue-300/40 text-blue-100">事件 {storyStateMachine.summary?.events || 0}</Badge>
                        <Badge variant="outline" className="border-yellow-300/40 text-yellow-100">提示 {stateMachineIssues.length}</Badge>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-3 md:grid-cols-3">
                      <div className="rounded-md bg-black/15 p-3">
                        <div className="mb-2 text-sm text-white/80">人物状态</div>
                        <div className="space-y-1 text-sm text-white/60">
                          {entriesOf(storyStateMachine.current_state?.characters).slice(0, 6).map(([name, state]) => (
                            <div key={name}>{name}：{state.state || '已登场'} · {state.costume || '服装待锁定'}</div>
                          ))}
                          {entriesOf(storyStateMachine.current_state?.characters).length === 0 && <div>暂无人物状态</div>}
                        </div>
                      </div>
                      <div className="rounded-md bg-black/15 p-3">
                        <div className="mb-2 text-sm text-white/80">道具流转</div>
                        <div className="space-y-1 text-sm text-white/60">
                          {entriesOf(storyStateMachine.current_state?.props).slice(0, 6).map(([name, state]) => (
                            <div key={name}>{name}：{state.state || '已出现'}{state.owner ? ` · ${state.owner}` : ''}</div>
                          ))}
                          {entriesOf(storyStateMachine.current_state?.props).length === 0 && <div>暂无道具状态</div>}
                        </div>
                      </div>
                      <div className="rounded-md bg-black/15 p-3">
                        <div className="mb-2 text-sm text-white/80">环境事件</div>
                        <div className="space-y-1 text-sm text-white/60">
                          {entriesOf(storyStateMachine.current_state?.scenes).slice(0, 3).map(([name, state]) => (
                            <div key={name}>{name}：{state.weather || state.lighting || '环境待细化'}</div>
                          ))}
                          {(storyStateMachine.event_timeline || []).slice(-3).map((event, index) => (
                            <div key={`${event.name}-${index}`}>第{event.chapter_number}章：{event.name}</div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : storyBibles.length > 0 ? (
                  <div className="rounded-lg border border-dashed border-white/15 bg-white/5 p-4">
                    <div className="text-white font-medium">尚未生成跨章节状态机</div>
                    <p className="mt-1 text-sm text-white/50">
                      状态机会把人物服装/关系、场景环境、道具流转和事件因果变成可检查规则，减少多集生成漂移。
                    </p>
                    <Button
                      size="sm"
                      className="mt-3 bg-violet-600 hover:bg-violet-700"
                      onClick={handleGenerateStateMachine}
                      disabled={generatingStateMachine}
                    >
                      {generatingStateMachine ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
                      生成状态机
                    </Button>
                  </div>
                ) : null}

                {bibleIssues.length > 0 && (
                  <div>
                    <div className="text-white/80 text-sm mb-2">一致性检查结果</div>
                    <div className="space-y-2">
                      {bibleIssues.slice(0, 12).map((issue, index) => (
                        <div key={`${issue.entity_type}-${issue.name}-${index}`} className="rounded-md bg-yellow-500/10 border border-yellow-500/20 px-3 py-2 text-sm text-yellow-100">
                          {issue.message}：{issue.name}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {stateMachineIssues.length > 0 && (
                  <div>
                    <div className="text-white/80 text-sm mb-2">状态机提示</div>
                    <div className="space-y-2">
                      {stateMachineIssues.slice(0, 12).map((issue, index) => (
                        <div key={`${issue.code}-${issue.name || issue.chapter_id || index}`} className="rounded-md bg-yellow-500/10 border border-yellow-500/20 px-3 py-2 text-sm text-yellow-100">
                          {issue.message || issue.code}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* 剧本列表 */}
          <TabsContent value="scripts">
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <CardTitle className="text-white">剧本管理</CardTitle>
                <Button asChild size="sm">
                  <Link href={`/scripts/new?novel_id=${novelId}`}>
                    <Plus className="w-4 h-4 mr-2" />
                    新建剧本
                  </Link>
                </Button>
              </CardHeader>
              <CardContent>
                {scripts.length === 0 ? (
                  <div className="text-center py-8 text-white/40">
                    <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>暂无剧本</p>
                    <p className="text-sm">从章节内容生成剧本</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {scripts.map((script) => (
                      <div
                        key={script.id}
                        className="flex items-center justify-between p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors"
                      >
                        <div>
                          <div className="text-white font-medium">{script.title}</div>
                          <div className="text-white/40 text-sm">
                            {script.genre} · {script.status || '草稿'}
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button asChild size="sm" variant="ghost" aria-label={`查看剧本 ${script.title}`} title="查看剧本">
                            <Link href={`/scripts/${script.id}`}>
                              <Eye className="w-4 h-4" />
                            </Link>
                          </Button>
                          <Button size="sm" variant="ghost">
                            <Sparkles className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* 设置 */}
          <TabsContent value="settings">
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white">小说设置</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-white/80 mb-2 block">小说标题</label>
                  <Input 
                    value={settingsTitle}
                    onChange={(event) => setSettingsTitle(event.target.value)}
                    className="bg-white/10 border-white/20 text-white"
                  />
                </div>
                <div>
                  <label className="text-white/80 mb-2 block">简介</label>
                  <Textarea 
                    value={settingsDescription}
                    onChange={(event) => setSettingsDescription(event.target.value)}
                    className="bg-white/10 border-white/20 text-white"
                  />
                </div>
                <div>
                  <label className="text-white/80 mb-2 block">类型</label>
                  <Input 
                    value={settingsGenre}
                    onChange={(event) => setSettingsGenre(event.target.value)}
                    className="bg-white/10 border-white/20 text-white"
                  />
                </div>
                <Button
                  className="bg-violet-600 hover:bg-violet-700"
                  onClick={handleSaveNovelSettings}
                  disabled={savingNovelSettings || !settingsTitle.trim()}
                >
                  {savingNovelSettings && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  保存修改
                </Button>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* 底部快捷入口 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="bg-gradient-to-br from-violet-600/20 to-purple-600/20 border-violet-500/30">
            <CardContent className="p-4 text-center">
              <Film className="w-8 h-8 mx-auto mb-2 text-violet-400" />
              <div className="text-white font-medium">视频生成</div>
              <div className="text-white/60 text-sm">基于剧本生成视频</div>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-blue-600/20 to-cyan-600/20 border-blue-500/30">
            <CardContent className="p-4 text-center">
              <Volume2 className="w-8 h-8 mx-auto mb-2 text-blue-400" />
              <div className="text-white font-medium">语音合成</div>
              <div className="text-white/60 text-sm">TTS语音生成</div>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-green-600/20 to-emerald-600/20 border-green-500/30">
            <CardContent className="p-4 text-center">
              <Play className="w-8 h-8 mx-auto mb-2 text-green-400" />
              <div className="text-white font-medium">音视频合成</div>
              <div className="text-white/60 text-sm">视频+音频合并</div>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-orange-600/20 to-amber-600/20 border-orange-500/30">
            <CardContent className="p-4 text-center">
              <Image className="w-8 h-8 mx-auto mb-2 text-orange-400" />
              <div className="text-white font-medium">封面生成</div>
              <div className="text-white/60 text-sm">AI生成小说封面</div>
            </CardContent>
          </Card>
        </div>
      </div>
    </MainLayout>
  );
}
