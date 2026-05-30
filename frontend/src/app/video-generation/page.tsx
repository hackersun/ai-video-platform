'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import {
  Video,
  Play,
  Settings,
  Clock,
  Film,
  Sparkles,
  Wand2,
  Loader2,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Download,
  Copy,
  User,
  Image as ImageIcon,
  ChevronLeft,
  ChevronRight,
  BookOpen,
  FileText,
  LayoutGrid,
  Filter,
  PlugZap,
  ShieldCheck
} from 'lucide-react';
import Link from 'next/link';
import { fetchWithAuth } from '@/lib/fetch-with-auth';
import apiClient from '@/lib/api-client';
import { CAMERA_ANGLE_LABELS, getShotAttributeLabel } from '@/lib/shot-labels';
import { isInternalTestModelConfig, modelStatusClass, modelStatusLabel } from '@/lib/model-configs';
import { useToast } from '@/components/ui/toast';

// 视频生成状态
type GenerationStatus = 'idle' | 'submitting' | 'generating' | 'completed' | 'error';

// 视频模型配置（从后端动态加载）
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const SCRIPT_PAGE_SIZE = 8;

const getApiOrigin = () => {
  try {
    return new URL(API_BASE).origin;
  } catch {
    return typeof window !== 'undefined' ? window.location.origin : '';
  }
};

const resolveMediaUrl = (url?: string | null) => {
  if (!url) return '';
  try {
    return new URL(url).toString();
  } catch {
    try {
      return new URL(url, getApiOrigin()).toString();
    } catch {
      return url;
    }
  }
};

const safeDownloadName = (name?: string | null) => {
  const clean = (name || 'video').trim().replace(/[\\/:*?"<>|]/g, '_');
  const filename = clean || 'video';
  return filename.toLowerCase().endsWith('.mp4') ? filename : `${filename}.mp4`;
};

// 视频模型类型（从后端加载后填充）
interface VideoModelOption {
  id: string;
  name: string;
  name_cn: string;
  desc: string;
  duration: string;
  model_id: string; // API调用用的model_id
  config_model_id?: string;
  api_model_id?: string;
  provider_id?: string;
  model_type?: string;
  model_capabilities?: string[];
  is_default?: boolean;
  is_configured?: boolean;
  config_id?: string;
  test_status?: string | null;
  test_message?: string | null;
}

// 角色类型
interface Character {
  id: string;
  novel_id?: string;
  chapter_id?: string;
  name: string;
  avatar?: string;
  appearance?: string;
}

// 镜头类型
interface Shot {
  id: string;
  storyboard_id: string;
  shot_number: number;
  duration: number;
  prompt: string;
  dialogue?: string;
  visual_description?: string;
  camera_angle?: string;
  video_status: string;
  image_url?: string;
  character_id?: string;
  character_refs?: any[];
  keyframes?: any[];
  extra_data?: any;
}

// 小说类型
interface Novel {
  id: string;
  title: string;
}

// 章节类型
interface Chapter {
  id: string;
  novel_id: string;
  title: string;
  chapter_number: number;
}

// 剧本类型
interface Script {
  id: string;
  title: string;
  novel_id?: string;
  chapter_id?: string;
}

// 分镜类型
interface Storyboard {
  id: string;
  title: string;
  script_id: string;
  novel_id?: string;
  chapter_id?: string;
  shot_count: number;
}

// 视频任务类型
interface VideoJob {
  id: string;
  task_id?: string;
  title?: string;
  prompt?: string;
  model_name?: string;
  status: string;
  progress: number;
  video_url?: string;
  cover_url?: string;
  error_message?: string;
  duration?: number;
  resolution?: string;
  created_at: string;
  updated_at: string;
  novel_id?: string;
  novel_title?: string;
  provider_id?: string;
  config_model_id?: string;
  api_model_id?: string;
  model_endpoint_id?: string;
  model_test_status?: string;
  prompt_parameters?: Record<string, any>;
  chapter_id?: string;
  chapter_title?: string;
  chapter_number?: number;
  script_id?: string;
  script_title?: string;
  storyboard_id?: string;
  shot_id?: string;
  shot_number?: number;
  extra_data?: any;
  subtitle_text?: string;
  character_refs?: any[];
  scene_refs?: any[];
  prop_refs?: any[];
  event_refs?: any[];
  environment_context?: string;
  consistency?: any;
  seed?: number;
  source_prompt?: string;
}

interface MediaJob {
  id: string;
  task_id?: string;
  task_type: string;
  media_type: string;
  title?: string;
  prompt?: string;
  provider_id?: string;
  model_id?: string;
  model_name?: string;
  status: string;
  progress: number;
  output_video_url?: string;
  output_audio_url?: string;
  subtitle_track_id?: string;
  duration_seconds?: number;
  resolution?: string;
  created_at: string;
  updated_at: string;
  shot_id?: string;
  novel_id?: string;
  chapter_id?: string;
  script_id?: string;
  storyboard_id?: string;
  extra_data?: any;
}

// 视频生成参数
interface VideoGenerateParams {
  shot_id?: string;
  storyboard_id?: string;
  script_id?: string;
  chapter_id?: string;
  novel_id?: string;
  workflow_id?: string;
  prompt: string;
  duration: number;
  resolution: string;
  image_url?: string;
  model: string;
  character_ids?: string[];
}

const refNames = (refs?: any[]) =>
  (refs || [])
    .map((ref) => ref?.name || ref?.character_name || ref?.title)
    .filter(Boolean)
    .join('、');

const statusLabel = modelStatusLabel;

const entityRefsFromShot = (shot?: Shot | null) => {
  const extra = shot?.extra_data || {};
  const entityRefs = extra.entity_refs || {};
  return {
    characters: shot?.character_refs?.length ? shot.character_refs : (entityRefs.characters || []),
    scenes: extra.scene_refs || entityRefs.scenes || [],
    props: extra.prop_refs || entityRefs.props || [],
    events: extra.event_refs || entityRefs.events || [],
    environment: extra.environment_context,
    subtitle: extra.subtitle_text || shot?.dialogue,
  };
};

function VideoGenerationPageInner() {
  const { toast } = useToast();
  const searchParams = useSearchParams();

  // ====== URL 参数 ======
  const urlScriptId = searchParams.get('script_id');
  const urlStoryboardId = searchParams.get('storyboard_id');
  const urlShotId = searchParams.get('shot_id');
  const urlNovelId = searchParams.get('novel_id');
  const urlChapterId = searchParams.get('chapter_id');
  const urlWorkflowId = searchParams.get('workflow_id');

  // ====== 状态 ======
  const [status, setStatus] = useState<GenerationStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apiConfigured, setApiConfigured] = useState(false);
  const [devModeEnabled, setDevModeEnabled] = useState(false);
  const [apiConfigLoading, setApiConfigLoading] = useState(true);
  const [videoModels, setVideoModels] = useState<VideoModelOption[]>([]);
  const [videoModelsLoading, setVideoModelsLoading] = useState(true);
  const [generationMode, setGenerationMode] = useState<'video_only' | 'audio_video'>('video_only');
  const [mediaJob, setMediaJob] = useState<MediaJob | null>(null);
  const [mediaHistory, setMediaHistory] = useState<MediaJob[]>([]);
  const [subtitleTrack, setSubtitleTrack] = useState<any | null>(null);
  const [subtitleExportUrl, setSubtitleExportUrl] = useState<string | null>(null);
  const [externalConfigs, setExternalConfigs] = useState<any[]>([]);
  const [selectedExternalConfigId, setSelectedExternalConfigId] = useState('');
  const [shotProductionContext, setShotProductionContext] = useState<any>({});
  const [lipSyncMode, setLipSyncMode] = useState('off');
  const [reviewRequired, setReviewRequired] = useState(false);

  // 关联数据
  const [novels, setNovels] = useState<Novel[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedNovel, setSelectedNovel] = useState<string>(urlNovelId || '');
  const [selectedChapter, setSelectedChapter] = useState<string>(urlChapterId || '');
  const [shot, setShot] = useState<Shot | null>(null);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [selectedCharacterId, setSelectedCharacterId] = useState<string>('');
  const [scripts, setScripts] = useState<Script[]>([]);
  const [scriptPage, setScriptPage] = useState(1);
  const [storyboards, setStoryboards] = useState<Storyboard[]>([]);
  const [shots, setShots] = useState<Shot[]>([]);

  // 生成参数
  const [prompt, setPrompt] = useState('');
  const [duration, setDuration] = useState(5);
  const [resolution, setResolution] = useState('720p');
  const [imageUrl, setImageUrl] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [selectedShotId, setSelectedShotId] = useState<string>('');

  // 关联ID
  const [scriptId, setScriptId] = useState<string>(urlScriptId || '');
  const [storyboardId, setStoryboardId] = useState<string>(urlStoryboardId || '');
  const [currentShotId, setCurrentShotId] = useState<string>(urlShotId || '');
  const [workflowId, setWorkflowId] = useState<string>(urlWorkflowId || '');

  // 历史记录
  const [history, setHistory] = useState<VideoJob[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // 检查火山视频 API Key 是否已配置，密钥只保存在后端
  const loadApiConfigStatus = async () => {
    setApiConfigLoading(true);
    try {
      const [volcanoRes, agentPlanRes] = await Promise.all([
        fetchWithAuth(`${API_BASE}/llm/api-key/volcano`),
        fetchWithAuth(`${API_BASE}/llm/api-key/volcano_agent_plan`),
      ]);
      const volcanoData = volcanoRes.ok ? await volcanoRes.json() : {};
      const agentPlanData = agentPlanRes.ok ? await agentPlanRes.json() : {};
      setApiConfigured(Boolean(volcanoData.configured || agentPlanData.configured || volcanoData.dev_mode || agentPlanData.dev_mode));
      setDevModeEnabled(Boolean(volcanoData.dev_mode || agentPlanData.dev_mode));
    } catch (err) {
      console.error('加载API Key失败:', err);
    } finally {
      setApiConfigLoading(false);
    }
  };

  // 加载视频模型列表和默认模型
  const loadVideoModels = async () => {
    setVideoModelsLoading(true);
    try {
      // 并行加载：火山普通模型 + Agent Plan 模型 + 用户默认配置
      const [modelsRes, agentPlanModelsRes, defaultRes] = await Promise.all([
        fetchWithAuth(`${API_BASE}/llm/models?provider=volcano`),
        fetchWithAuth(`${API_BASE}/llm/models?provider=volcano_agent_plan`),
        fetchWithAuth(`${API_BASE}/llm/configs`),
      ]);

      let mapped: VideoModelOption[] = [];
      let configs: any[] = [];

      if (defaultRes.ok) {
        const configPayload = await defaultRes.json();
        configs = Array.isArray(configPayload)
          ? configPayload.filter((config: any) => !isInternalTestModelConfig(config))
          : [];
      }

      const providerModelPayloads: Array<{ providerId: string; response: Response }> = [
        { providerId: 'volcano', response: modelsRes },
        { providerId: 'volcano_agent_plan', response: agentPlanModelsRes },
      ];

      // 解析视频模型列表
      for (const payload of providerModelPayloads) {
        if (!payload.response.ok) continue;
        const allModels = await payload.response.json();
        const videoOnly = (allModels as any[]).filter(
          (m: any) => ['video-generation', 'video'].includes(m.model_type) && !isInternalTestModelConfig(m)
        );
        mapped = [
          ...mapped,
          ...videoOnly.map((m: any) => {
            const savedConfig = configs.find(
              (c: any) => c.provider_id === payload.providerId && ['video-generation', 'video'].includes(c.model_type) && (c.config_model_id === m.id || c.api_model_id === m.model_id || c.model_id === m.model_id)
            );
            return {
              id: m.id,                 // 前端选择用配置模型ID，避免不同 provider 的 API model_id 冲突
              name: m.model_name || m.model_id,
              name_cn: m.model_name_cn || m.model_name || m.model_id,
              desc: m.description || m.capabilities?.join('/') || '',
              duration: '4/5/8/10秒',
              model_id: m.model_id,
              config_model_id: m.id,
              api_model_id: m.model_id,
              provider_id: payload.providerId,
              model_type: m.model_type,
              model_capabilities: m.capabilities || [],
              is_configured: Boolean(savedConfig),
              config_id: savedConfig?.id,
              is_default: Boolean(savedConfig?.is_default),
              test_status: savedConfig?.test_status,
              test_message: savedConfig?.test_message,
            };
          }),
        ];
      }
      setVideoModels(mapped);

      // 解析用户默认视频模型
      if (configs.length > 0 || mapped.length > 0) {
        const defaultConfig = configs.find(
          (c: any) => c.is_default && ['volcano', 'volcano_agent_plan'].includes(c.provider_id) && ['video-generation', 'video'].includes(c.model_type)
        );
        if (defaultConfig) {
          setSelectedModel(defaultConfig.config_model_id || defaultConfig.api_model_id || defaultConfig.model_id);
        } else {
          const firstVerified = mapped.find(item => item.is_configured && item.test_status === 'success');
          if (firstVerified) {
            setSelectedModel(firstVerified.id);
          } else if (mapped.length > 0 && !selectedModel) {
            setSelectedModel(mapped[0].id);
          }
        }
      }
    } catch (err) {
      console.error('加载视频模型失败:', err);
    } finally {
      setVideoModelsLoading(false);
    }
  };
  const loadScripts = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/scripts`);
      if (res.ok) {
        const data = await res.json();
        const scriptList = Array.isArray(data) ? data : [];
        setScripts(scriptList);
        if (urlNovelId || urlChapterId) {
          loadStoryboardsForScripts(
            scriptList.filter((script: Script) =>
              (!urlNovelId || script.novel_id === urlNovelId) &&
              (!urlChapterId || !script.chapter_id || script.chapter_id === urlChapterId)
            )
          );
        }
        if (urlScriptId) {
          const current = scriptList.find((s: Script) => s.id === urlScriptId);
          if (current?.novel_id) {
            setSelectedNovel(current.novel_id);
            loadCharacters(current.novel_id);
            loadChaptersByNovel(current.novel_id);
          }
          if (current?.chapter_id) {
            setSelectedChapter(current.chapter_id);
          }
        }
      }
    } catch (err) {
      console.error('加载剧本失败:', err);
    }
  };

  // 加载小说列表
  const loadNovels = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/novels`);
      if (res.ok) {
        const data = await res.json();
        setNovels(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      console.error('加载小说失败:', err);
    }
  };

  // 加载指定小说的章节列表
  const loadChaptersByNovel = async (novelId: string) => {
    if (!novelId) {
      setChapters([]);
      return;
    }
    try {
      const res = await fetchWithAuth(`${API_BASE}/chapters/novel/${novelId}`);
      if (res.ok) {
        const data = await res.json();
        setChapters(Array.isArray(data) ? data : []);
      } else {
        setChapters([]);
      }
    } catch (err) {
      console.error('加载章节失败:', err);
      setChapters([]);
    }
  };

  // 加载角色的函数
  const loadCharacters = async (novelId = selectedNovel) => {
    try {
      const params = new URLSearchParams();
      if (novelId) params.set('novel_id', novelId);
      const res = await fetchWithAuth(`${API_BASE}/characters${params.toString() ? `?${params}` : ''}`);
      if (res.ok) {
        const data = await res.json();
        setCharacters(Array.isArray(data) ? data : []);
      } else {
        setCharacters([]);
      }
    } catch (err) {
      console.error('加载角色失败:', err);
      setCharacters([]);
    }
  };

  // 加载指定剧本的分镜列表
  const loadStoryboardsByScript = async (sid: string) => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/storyboards/script/${sid}`);
      if (res.ok) {
        const data = await res.json();
        setStoryboards(Array.isArray(data) ? data : []);
      } else {
        setStoryboards([]);
      }
    } catch (err) {
      console.error('加载分镜失败:', err);
      setStoryboards([]);
    }
  };

  const loadStoryboardsForScripts = async (scriptList: Script[]) => {
    const collected: Storyboard[] = [];
    for (const script of scriptList) {
      try {
        const res = await fetchWithAuth(`${API_BASE}/storyboards/script/${script.id}`);
        if (res.ok) {
          const data = await res.json();
          collected.push(...(Array.isArray(data) ? data : []));
        }
      } catch (err) {
        console.error('加载分镜失败:', err);
      }
    }
    setStoryboards(collected);
    return collected;
  };

  // 加载指定分镜的镜头列表
  const loadShotsByStoryboard = async (sid: string) => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/shots/storyboard/${sid}`);
      if (res.ok) {
        const data = await res.json();
        setShots(Array.isArray(data) ? data : []);
      } else {
        setShots([]);
      }
    } catch (err) {
      console.error('加载镜头失败:', err);
      setShots([]);
    }
  };

  // 加载单个镜头详情
  const loadShotDetail = async (shotId: string) => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/shots/${shotId}`);
      if (res.ok) {
        const data = await res.json();
        setShot(data);
        if (data.storyboard_id) {
          setStoryboardId(data.storyboard_id);
          loadShotsByStoryboard(data.storyboard_id);
          const storyboardRes = await fetchWithAuth(`${API_BASE}/storyboards/${data.storyboard_id}`);
          if (storyboardRes.ok) {
            const storyboardData = await storyboardRes.json();
            setScriptId(storyboardData.script_id || '');
            setStoryboardId(storyboardData.id || data.storyboard_id);
            if (storyboardData.novel_id) {
              setSelectedNovel(storyboardData.novel_id);
              loadCharacters(storyboardData.novel_id);
              loadChaptersByNovel(storyboardData.novel_id);
            }
            if (storyboardData.chapter_id) {
              setSelectedChapter(storyboardData.chapter_id);
            }
            if (storyboardData.script_id) {
              loadStoryboardsByScript(storyboardData.script_id);
            }
          }
        }
        // 自动填充prompt
        if (data.prompt) {
          setPrompt(data.prompt);
        }
        // 如果镜头有参考图片，自动填入
        if (data.image_url) {
          setImageUrl(data.image_url);
        }
        const firstCharacterRef = (data.character_refs || data.extra_data?.entity_refs?.characters || [])[0];
        if (firstCharacterRef?.character_id) {
          setSelectedCharacterId(firstCharacterRef.character_id);
          if (firstCharacterRef.avatar && !data.image_url) {
            setImageUrl(firstCharacterRef.avatar);
          }
        }
        try {
          const context = await apiClient.getShotProductionContext(shotId);
          setShotProductionContext(context.production_context || {});
        } catch {
          setShotProductionContext(data.extra_data?.production_context || {});
        }
      }
    } catch (err) {
      console.error('加载镜头详情失败:', err);
    }
  };

  const chooseChapter = (chapterId: string) => {
    setSelectedChapter(chapterId);
    setScriptId('');
    setStoryboardId('');
    setCurrentShotId('');
    setSelectedShotId('');
    setShot(null);
    const nextScripts = scripts.filter((script) =>
      selectedNovel ? script.novel_id === selectedNovel && (!chapterId || !script.chapter_id || script.chapter_id === chapterId) : true
    );
    loadStoryboardsForScripts(nextScripts);
  };

  // 加载历史记录
  const loadHistory = async () => {
    setIsLoadingHistory(true);
    try {
      const params = new URLSearchParams();
      if (workflowId) params.set('workflow_id', workflowId);
      if (selectedNovel) params.set('novel_id', selectedNovel);
      if (selectedChapter) params.set('chapter_id', selectedChapter);
      if (scriptId) params.set('script_id', scriptId);
      if (storyboardId) params.set('storyboard_id', storyboardId);
      if (currentShotId) params.set('shot_id', currentShotId);
      const response = await fetchWithAuth(`${API_BASE}/video/jobs${params.toString() ? `?${params}` : ''}`);
      if (response.ok) {
        const data = await response.json();
        setHistory(data || []);
      }
      const mediaJobs = await apiClient.getMediaJobs({
        task_type: 'shot_audio_video',
        media_type: 'audio_video',
        workflow_id: workflowId || undefined,
        novel_id: selectedNovel || undefined,
        chapter_id: selectedChapter || undefined,
        script_id: scriptId || undefined,
        storyboard_id: storyboardId || undefined,
        shot_id: currentShotId || undefined,
      });
      setMediaHistory(Array.isArray(mediaJobs) ? mediaJobs : []);
    } catch (err) {
      console.error('加载历史失败:', err);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  // 根据选择的小说过滤剧本列表，并分页展示剧本选项
  const filteredScripts = selectedNovel
    ? scripts.filter((s) => s.novel_id === selectedNovel && (!selectedChapter || !s.chapter_id || s.chapter_id === selectedChapter))
    : scripts;
  const scriptPageCount = Math.max(1, Math.ceil(filteredScripts.length / SCRIPT_PAGE_SIZE));
  const normalizedScriptPage = Math.min(scriptPage, scriptPageCount);
  const pagedScripts = filteredScripts.slice((normalizedScriptPage - 1) * SCRIPT_PAGE_SIZE, normalizedScriptPage * SCRIPT_PAGE_SIZE);
  const selectedScriptForOptions = scriptId ? filteredScripts.find((script) => script.id === scriptId) : undefined;
  const scriptOptionsForPage = selectedScriptForOptions && !pagedScripts.some((script) => script.id === selectedScriptForOptions.id)
    ? [selectedScriptForOptions, ...pagedScripts]
    : pagedScripts;

  // 初始化
  useEffect(() => {
    loadVideoModels();
    loadApiConfigStatus();
    loadScripts();
    loadCharacters(urlNovelId || '');
    loadNovels();
    apiClient.getExternalConfigs()
      .then((configs) => setExternalConfigs(Array.isArray(configs) ? configs : []))
      .catch(() => setExternalConfigs([]));
    if (urlNovelId) {
      loadChaptersByNovel(urlNovelId);
    }
  }, []);

  // 根据URL参数自动加载关联数据
  useEffect(() => {
    if (urlWorkflowId) {
      setWorkflowId(urlWorkflowId);
    }
    if (urlNovelId) {
      setSelectedNovel(urlNovelId);
      loadChaptersByNovel(urlNovelId);
    }
    if (urlChapterId) {
      setSelectedChapter(urlChapterId);
    }
    if (urlScriptId) {
      setScriptId(urlScriptId);
      loadStoryboardsByScript(urlScriptId);
    }
    if (urlStoryboardId) {
      setStoryboardId(urlStoryboardId);
      loadShotsByStoryboard(urlStoryboardId);
    }
    if (urlShotId) {
      setCurrentShotId(urlShotId);
      setSelectedShotId(urlShotId);
      loadShotDetail(urlShotId);
    }
  }, [urlNovelId, urlChapterId, urlScriptId, urlStoryboardId, urlShotId, urlWorkflowId]);

  useEffect(() => {
    loadHistory();
  }, [workflowId, selectedNovel, selectedChapter, scriptId, storyboardId, currentShotId]);

  useEffect(() => {
    setScriptPage(1);
  }, [selectedNovel, selectedChapter]);

  useEffect(() => {
    if (!scriptId) return;
    const scriptIndex = filteredScripts.findIndex((script) => script.id === scriptId);
    if (scriptIndex >= 0) {
      const nextPage = Math.max(1, Math.ceil((scriptIndex + 1) / SCRIPT_PAGE_SIZE));
      if (nextPage !== scriptPage) {
        setScriptPage(nextPage);
      }
    }
  }, [scriptId, selectedNovel, selectedChapter, scripts.length, scriptPage]);

  useEffect(() => {
    if (scriptPage > scriptPageCount) {
      setScriptPage(scriptPageCount);
    }
  }, [scriptPage, scriptPageCount]);

  useEffect(() => {
    loadCharacters(selectedNovel);
    setSelectedCharacterId('');
    setImageUrl((current) => (shot?.image_url ? current : ''));
  }, [selectedNovel]);

  // 角色选择变化 → 自动设置角色图像
  const handleCharacterChange = (charId: string) => {
    setSelectedCharacterId(charId);
    const char = characters.find(c => c.id === charId);
    if (char?.avatar) {
      setImageUrl(char.avatar);
    }
  };

  // 镜头选择变化 → 自动填充prompt和参考图
  const handleShotChange = (shotId: string) => {
    setSelectedShotId(shotId);
    setCurrentShotId(shotId);
    if (shotId) {
      loadShotDetail(shotId);
    } else {
      setShot(null);
      setShotProductionContext({});
    }
  };

  // 轮询任务状态
  const pollTaskStatus = async (tid: string, jid: string) => {
    try {
      const response = await fetchWithAuth(`${API_BASE}/video/status/${tid}`);
      if (!response.ok) {
        throw new Error('查询失败');
      }
      const data = await response.json();

      setProgress(data.progress || 0);

      if (data.status === 'succeeded') {
        setStatus('completed');
        setVideoUrl(resolveMediaUrl(data.video_url));
        setProgress(100);
        loadHistory();
      } else if (data.status === 'failed') {
        setStatus('error');
        setError(data.message || '生成失败');
        loadHistory();
      } else {
        setTimeout(() => pollTaskStatus(tid, jid), 3000);
      }
    } catch (err) {
      console.error('轮询状态失败:', err);
      setTimeout(() => pollTaskStatus(tid, jid), 5000);
    }
  };

  // 检查图片 URL 是否为本地/私有地址
  const isPrivateImageUrl = (url: string): boolean => {
    if (!url) return false;
    const patterns = [
      /^http:\/\/localhost/, /^http:\/\/127\./, /^http:\/\/192\.168\./,
      /^http:\/\/10\./, /^http:\/\/172\.(1[6-9]|2[0-9]|3[01])\./,
      /^http:\/\/0\.0\.0\.0/, /^file:\/\//, /^data:/,
      /^blob:/, /^file:\//i,
    ];
    return patterns.some(p => p.test(url));
  };

  // 检查公网图片 URL 是否可访问（返回 2xx/3xx 才认为有效）
  const checkImageAccessible = async (url: string): Promise<boolean> => {
    if (!url || isPrivateImageUrl(url)) return false;
    try {
      // 只验证公网 HTTPS/HTTP 图片地址
      const res = await fetch(url, { method: 'HEAD', mode: 'cors', signal: AbortSignal.timeout(5000) });
      if (res.ok || res.status === 301 || res.status === 302) return true;
      // 可能是跨域问题导致无法获取状态码，检查 content-type
      const ct = res.headers.get('content-type') || '';
      if (ct.startsWith('image/')) return true;
    } catch {
      // fetch 失败不阻止，可能是跨域，不做预判
    }
    return false;
  };

  // 生成视频
  const handleGenerate = async () => {
    if (!prompt.trim()) {
      toast({ title: '请输入视频描述', description: '补充描述后再开始生成。', type: 'error' });
      return;
    }
    if (!apiConfigured && !devModeEnabled) {
      toast({ title: '请先配置 API Key', description: '前往「LLM 配置」页面配置火山引擎 API Key。', type: 'error' });
      return;
    }

    // 私有/本地图片地址无法被火山引擎访问，直接跳过
    if (isPrivateImageUrl(imageUrl)) {
      toast({ title: '已改为纯文生视频', description: '参考图片是本地或私有地址，火山引擎无法访问。', type: 'info' });
    }

    setStatus('submitting');
    setProgress(0);
    setError(null);
    setVideoUrl(null);

    try {
      const params: VideoGenerateParams = {
        prompt: prompt,
        duration: duration,
        resolution: resolution,
        model: selectedModel,
      };

      if (workflowId) {
        params.workflow_id = workflowId;
      }
      if (selectedNovel) {
        params.novel_id = selectedNovel;
      }
      if (selectedChapter) {
        params.chapter_id = selectedChapter;
      }
      if (scriptId) {
        params.script_id = scriptId;
      }
      if (storyboardId) {
        params.storyboard_id = storyboardId;
      }
      if (currentShotId) {
        params.shot_id = currentShotId;
      }
      const shotEntityRefs = entityRefsFromShot(shot);
      const shotCharacterIds = shotEntityRefs.characters
        .map((ref: any) => ref.character_id)
        .filter(Boolean);
      const selectedCharacterIds = selectedCharacterId ? [selectedCharacterId] : [];
      params.character_ids = Array.from(new Set([...shotCharacterIds, ...selectedCharacterIds]));

      // 发送前验证图片 URL（跳过私有地址，公网地址预检可访问性）
      if (imageUrl && !isPrivateImageUrl(imageUrl)) {
        const accessible = await checkImageAccessible(imageUrl);
        if (accessible) {
          params.image_url = imageUrl.trim();
        } else {
          // 公网地址预检失败（跨域/超时/非图片），仍尝试发送给火山引擎
          // 火山引擎返回的 error 会更准确
          params.image_url = imageUrl.trim();
          console.warn('参考图片预检未通过，仍将发送请求，预期可能报错:', imageUrl);
        }
      }

      const response = await fetchWithAuth(`${API_BASE}/video/generate`, {
        method: 'POST',
        body: JSON.stringify(params)
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || '提交失败');
      }

      const data = await response.json();
      setTaskId(data.task_id);
      setJobId(data.job_id);
      setStatus('generating');

      pollTaskStatus(data.task_id, data.job_id);
      loadHistory();
    } catch (err: any) {
      setStatus('error');
      setError(err.message || '提交失败');
    }
  };

  const handleGenerateAudioVideo = async () => {
    if (!prompt.trim()) {
      toast({ title: '请输入音视频描述', description: '补充描述后再开始生成。', type: 'error' });
      return;
    }
    if (!currentShotId) {
      toast({ title: '请选择具体镜头', description: '直生音视频需要绑定镜头、角色、场景和字幕上下文。', type: 'error' });
      return;
    }

    setStatus('submitting');
    setProgress(0);
    setError(null);
    setVideoUrl(null);
    setMediaJob(null);
    setSubtitleTrack(null);
    setSubtitleExportUrl(null);

    try {
      const data = await apiClient.generateMedia({
        task_type: 'shot_audio_video',
        media_type: 'audio_video',
        prompt,
        title: shot ? `镜头${shot.shot_number} 音视频直生` : '音视频直生',
        duration,
        resolution,
        workflow_id: workflowId || undefined,
        novel_id: selectedNovel || undefined,
        chapter_id: selectedChapter || undefined,
        script_id: scriptId || undefined,
        storyboard_id: storyboardId || undefined,
        shot_id: currentShotId,
        subtitle_mode: 'shot_dialogue',
        audio_mode: 'model_audio',
        reference_asset_ids: selectedCharacterId ? [selectedCharacterId] : [],
        external_config_id: selectedExternalConfigId || undefined,
        asset_version_locks: shotProductionContext.asset_version_locks || [],
        keyframes: shotProductionContext.keyframes || shot?.keyframes || [],
        character_multiview_refs: shotProductionContext.character_multiview_refs || [],
        lip_sync_mode: lipSyncMode,
        review_required: reviewRequired,
      });
      setMediaJob(data);
      setJobId(data.id);
      setTaskId(data.task_id || data.id);
      setProgress(data.progress || 100);
      setStatus(data.status === 'failed' ? 'error' : 'completed');
      setVideoUrl(resolveMediaUrl(data.output_video_url));
      if (data.subtitle_track_id) {
        const track = await apiClient.getSubtitleTrack(data.subtitle_track_id);
        setSubtitleTrack(track);
      }
      loadHistory();
    } catch (err: any) {
      setStatus('error');
      setError(err.message || '音视频直生失败');
    }
  };

  const handleExportSubtitle = async (trackId?: string | null) => {
    if (!trackId) return;
    try {
      const result = await apiClient.exportSubtitleTrack(trackId, 'srt');
      setSubtitleExportUrl(resolveMediaUrl(result.url));
      if (result.url) {
        window.open(resolveMediaUrl(result.url), '_blank');
      }
    } catch (err: any) {
      toast({ title: '字幕导出失败', description: err.message || '请重试。', type: 'error' });
    }
  };

  // 刷新单个任务状态
  const handleRefreshStatus = async (job: VideoJob) => {
    if (!job.id) return;
    try {
      const response = await fetchWithAuth(`${API_BASE}/video/jobs/${job.id}/refresh`, {
        method: 'POST',
      });
      if (response.ok) {
        loadHistory();
      }
    } catch (err) {
      console.error('刷新状态失败:', err);
    }
  };

  // 复制视频链接
  const handleCopyUrl = () => {
    if (videoUrl) {
      navigator.clipboard.writeText(resolveMediaUrl(videoUrl));
      toast({ title: '链接已复制', type: 'success' });
    }
  };

  // 下载视频
  const handleDownload = async (sourceUrl?: string, filename?: string) => {
    const targetUrl = resolveMediaUrl(sourceUrl || videoUrl);
    if (!targetUrl) return;
    try {
      const response = await fetchWithAuth(`${API_BASE}/video/download`, {
        method: 'POST',
        body: JSON.stringify({
          video_url: targetUrl,
          filename: safeDownloadName(filename || 'video'),
        }),
      });
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || '下载失败');
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = safeDownloadName(filename || 'video');
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (err: any) {
      toast({ title: '下载失败', description: err.message || '请重试。', type: 'error' });
    }
  };

  const handlePlayVideo = (sourceUrl?: string | null) => {
    const resolvedUrl = resolveMediaUrl(sourceUrl);
    if (!resolvedUrl) return;
    setVideoUrl(resolvedUrl);
    setStatus('completed');
  };

  // 格式化时间
  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  // 判断是否有上游数据
  const hasUpstream = !!(urlNovelId || urlChapterId || urlScriptId || urlStoryboardId || urlShotId || urlWorkflowId);

  const filteredStoryboards = storyboards.filter((sb) => {
    if (scriptId) return sb.script_id === scriptId;
    if (!selectedNovel && !selectedChapter) return true;
    const script = scripts.find((item) => item.id === sb.script_id);
    const storyboardChapterId = sb.chapter_id || (sb as any).content?.chapter_id || script?.chapter_id;
    const storyboardNovelId = sb.novel_id || (sb as any).content?.novel_id || script?.novel_id;
    if (selectedNovel && storyboardNovelId !== selectedNovel) return false;
    if (selectedChapter && storyboardChapterId !== selectedChapter) return false;
    return true;
  });
  const shotEntityRefs = entityRefsFromShot(shot);
  const selectedVideoModel = videoModels.find(m => m.id === selectedModel || m.api_model_id === selectedModel || m.model_id === selectedModel);
  const videoModelReady = generationMode === 'audio_video'
    ? true
    : Boolean(selectedVideoModel && (devModeEnabled || (selectedVideoModel.is_configured && selectedVideoModel.test_status === 'success')));
  const selectedExternalConfig = externalConfigs.find(config => config.id === selectedExternalConfigId);
  const renderScriptPager = () => {
    if (filteredScripts.length <= SCRIPT_PAGE_SIZE) return null;
    return (
      <div className="mt-2 flex items-center justify-between rounded-lg border border-white/10 bg-black/20 px-2 py-1 text-xs text-white/50">
        <span>
          剧本 {((normalizedScriptPage - 1) * SCRIPT_PAGE_SIZE) + 1}-{Math.min(normalizedScriptPage * SCRIPT_PAGE_SIZE, filteredScripts.length)}
          / {filteredScripts.length}
        </span>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setScriptPage(Math.max(1, normalizedScriptPage - 1))}
            disabled={normalizedScriptPage <= 1}
            className="h-7 px-2 text-white/60"
            title="上一页剧本"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="px-1">{normalizedScriptPage}/{scriptPageCount}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setScriptPage(Math.min(scriptPageCount, normalizedScriptPage + 1))}
            disabled={normalizedScriptPage >= scriptPageCount}
            className="h-7 px-2 text-white/60"
            title="下一页剧本"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    );
  };
  const mediaLineageText = (job: MediaJob) => {
    const lineage = job.extra_data?.lineage || {};
    const novelTitle = lineage.novel_title || novels.find((item) => item.id === job.novel_id)?.title;
    const chapter = chapters.find((item) => item.id === job.chapter_id);
    const chapterTitle = lineage.chapter_title || chapter?.title;
    const chapterNumber = lineage.chapter_number || chapter?.chapter_number;
    const scriptTitle = lineage.script_title || scripts.find((item) => item.id === job.script_id)?.title;
    const storyboardTitle = lineage.storyboard_title || storyboards.find((item) => item.id === job.storyboard_id)?.title;
    const shotNumber = lineage.shot_number || shots.find((item) => item.id === job.shot_id)?.shot_number;
    const parts = [
      novelTitle,
      chapterTitle ? `第${chapterNumber || ''}章 ${chapterTitle}` : null,
      scriptTitle,
      storyboardTitle,
      shotNumber ? `镜头${shotNumber}` : null,
    ].filter(Boolean);
    return parts.join(' / ');
  };
  const productionContextUsage = [
    { label: '资产锁', value: shotProductionContext.asset_version_locks?.length || 0 },
    { label: '关键帧', value: shotProductionContext.keyframes?.length || shot?.keyframes?.length || 0 },
    { label: '多视图', value: shotProductionContext.character_multiview_refs?.length || 0 },
    { label: '审核', value: reviewRequired ? '进入审核' : (shotProductionContext.review_state || '未启用') },
  ];

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Video className="w-6 h-6" />
              视频生成
              {hasUpstream && (
                <span className="text-sm font-normal text-violet-400 bg-violet-500/10 px-2 py-1 rounded">
                  关联模式
                </span>
              )}
            </h1>
            <p className="text-white/60 mt-1">
              {hasUpstream ? '基于小说、章节、剧本、分镜和镜头生成连续视频' : '选择小说制作链路或直接输入描述生成视频'}
            </p>
          </div>
          <div className="flex gap-2">
            <Button asChild variant="outline" size="sm" className="border-white/20 text-white">
              <Link href="/scripts">
                <FileText className="w-4 h-4 mr-1" />剧本
              </Link>
            </Button>
            <Button asChild variant="outline" size="sm" className="border-white/20 text-white">
              <Link href="/storyboards">
                <LayoutGrid className="w-4 h-4 mr-1" />分镜
              </Link>
            </Button>
          </div>
        </div>

        {/* API Key 配置提示 */}
        {apiConfigLoading ? (
          <div className="flex items-center gap-2 text-white/40 text-sm">
            <Loader2 className="w-4 h-4 animate-spin" />
            加载 API 配置…
          </div>
        ) : !apiConfigured ? (
          <Card className="bg-yellow-500/10 border-yellow-500/30">
            <CardContent className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-yellow-400" />
                <div>
                  <p className="text-yellow-300 font-medium">未配置 API Key</p>
                  <p className="text-yellow-400/60 text-sm">请先配置火山引擎 API Key 才能生成视频</p>
                </div>
              </div>
              <Button asChild variant="outline" size="sm" className="border-yellow-500/50 text-yellow-400 hover:bg-yellow-500/10">
                <Link href="/llm-config">
                  前往配置
                </Link>
              </Button>
            </CardContent>
          </Card>
        ) : devModeEnabled ? (
          <Card className="bg-blue-500/10 border-blue-500/30">
            <CardContent className="p-3 text-sm text-blue-200">
              当前为 DEV_MODE，本地可生成可验证的视频任务；生产环境会按默认视频模型配置调用真实服务。
            </CardContent>
          </Card>
        ) : null}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧：关联选择 + 参数配置 */}
          <div className="lg:col-span-1 space-y-4">
            {/* 关联数据选择 */}
            <Card className="bg-white/5 border-white/10">
                <CardHeader>
                  <CardTitle className="text-white flex items-center gap-2">
                    <BookOpen className="w-5 h-5 text-violet-400" />
                    制作链路
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {workflowId && (
                    <div className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-xs text-white/50">
                      工作流：{workflowId.slice(0, 8)}...
                    </div>
                  )}
                  {(selectedNovel || selectedChapter || scriptId || storyboardId || currentShotId) && (
                    <div className="bg-violet-500/10 border border-violet-500/20 rounded-lg px-3 py-2 text-xs text-violet-100 space-y-1">
                      <div className="font-medium">当前链路</div>
                      <div className="text-white/60">
                        {selectedNovel ? novels.find((n) => n.id === selectedNovel)?.title || `小说 ${selectedNovel.slice(0, 8)}...` : '未选小说'}
                        {selectedChapter && ` / ${chapters.find((c) => c.id === selectedChapter)?.title || `章节 ${selectedChapter.slice(0, 8)}...`}`}
                        {scriptId && ` / ${scripts.find((s) => s.id === scriptId)?.title || `剧本 ${scriptId.slice(0, 8)}...`}`}
                        {storyboardId && ` / ${storyboards.find((sb) => sb.id === storyboardId)?.title || `分镜 ${storyboardId.slice(0, 8)}...`}`}
                        {currentShotId && ` / 镜头${shot?.shot_number || currentShotId.slice(0, 8)}`}
                      </div>
                    </div>
                  )}
                  {/* 小说选择 */}
                  <div>
                    <label className="text-white/60 text-sm mb-1 block">小说</label>
                    <select
                      value={selectedNovel}
                      onChange={(e) => {
                        const nextNovelId = e.target.value;
                        setSelectedNovel(nextNovelId);
                        setSelectedChapter('');
                        setScriptId('');
                        setStoryboardId('');
                        setCurrentShotId('');
                        setSelectedShotId('');
                        setShot(null);
                        setSelectedCharacterId('');
                        setImageUrl('');
                        loadChaptersByNovel(nextNovelId);
                        loadCharacters(nextNovelId);
                        const nextScripts = nextNovelId ? scripts.filter((script) => script.novel_id === nextNovelId) : scripts;
                        loadStoryboardsForScripts(nextScripts);
                      }}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                    >
                      <option value="">-- 选择小说 --</option>
                      {novels.map((n) => (
                        <option key={n.id} value={n.id}>{n.title}</option>
                      ))}
                    </select>
                  </div>

                  {/* 章节选择 */}
                  {selectedNovel && (
                    <div>
                      <label className="text-white/60 text-sm mb-1 block">章节</label>
                      <select
                        value={selectedChapter}
                        onChange={(e) => chooseChapter(e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                      >
                        <option value="">全部章节</option>
                        {chapters.map((chapter) => (
                          <option key={chapter.id} value={chapter.id}>
                            第{chapter.chapter_number}章 {chapter.title}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* 剧本选择 */}
                  <div>
                    <label className="text-white/60 text-sm mb-1 block">剧本</label>
                    <select
                      value={scriptId}
                      onChange={(e) => {
                        const nextScriptId = e.target.value;
                        setScriptId(nextScriptId);
                        setStoryboardId('');
                        setCurrentShotId('');
                        setSelectedShotId('');
                        setShot(null);
                        const selectedScript = scripts.find((s) => s.id === nextScriptId);
                        if (selectedScript?.novel_id) {
                          setSelectedNovel(selectedScript.novel_id);
                          loadCharacters(selectedScript.novel_id);
                          loadChaptersByNovel(selectedScript.novel_id);
                        }
                        if (selectedScript?.chapter_id) {
                          setSelectedChapter(selectedScript.chapter_id);
                        }
                        if (nextScriptId) {
                          loadStoryboardsByScript(nextScriptId);
                        } else {
                          const nextScripts = selectedNovel
                            ? scripts.filter((script) => script.novel_id === selectedNovel && (!selectedChapter || !script.chapter_id || script.chapter_id === selectedChapter))
                            : scripts;
                          loadStoryboardsForScripts(nextScripts);
                        }
                      }}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                    >
                      <option value="">手动输入描述</option>
                      {scriptOptionsForPage.map(s => (
                        <option key={s.id} value={s.id}>{s.title}</option>
                      ))}
                    </select>
                    {renderScriptPager()}
                  </div>

                  {/* 分镜选择 */}
                  {(scriptId || selectedNovel || selectedChapter) && (
                    <div>
                      <label className="text-white/60 text-sm mb-1 block">分镜</label>
                      <select
                      value={storyboardId}
                      onChange={(e) => {
                          const nextStoryboardId = e.target.value;
                          setStoryboardId(nextStoryboardId);
                          setCurrentShotId('');
                          setSelectedShotId('');
                          setShot(null);
                          const selectedStoryboard = storyboards.find((sb) => sb.id === nextStoryboardId);
                          if (selectedStoryboard?.chapter_id) {
                            setSelectedChapter(selectedStoryboard.chapter_id);
                          }
                          if (selectedStoryboard?.novel_id) {
                            setSelectedNovel(selectedStoryboard.novel_id);
                            loadCharacters(selectedStoryboard.novel_id);
                            loadChaptersByNovel(selectedStoryboard.novel_id);
                          }
                          if (nextStoryboardId) {
                            loadShotsByStoryboard(nextStoryboardId);
                          } else {
                            setShots([]);
                          }
                        }}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                      >
                        <option value="">全部镜头</option>
                        {filteredStoryboards.map(sb => (
                          <option key={sb.id} value={sb.id}>
                            {sb.title} ({sb.shot_count}个镜头)
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* 镜头选择 */}
                  {storyboardId && shots.length > 0 && (
                    <div>
                      <label className="text-white/60 text-sm mb-1 block">镜头</label>
                      <select
                        value={selectedShotId}
                        onChange={(e) => handleShotChange(e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                      >
                        <option value="">全部镜头（批量）</option>
                        {shots.map(s => (
                          <option key={s.id} value={s.id}>
                            镜头{s.shot_number} - {s.prompt?.slice(0, 30) || '(无描述)'}...
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* 当前镜头信息 */}
                  {shot && (
                    <div className="bg-violet-500/10 border border-violet-500/20 rounded-lg p-3 text-sm">
                      <div className="text-violet-300 font-medium mb-1">
                        镜头{shot.shot_number} | {shot.duration}秒 | {getShotAttributeLabel(CAMERA_ANGLE_LABELS, shot.camera_angle, '无角度')}
                      </div>
                      {shot.visual_description && (
                        <div className="text-white/50 text-xs mt-1 line-clamp-2">
                          {shot.visual_description}
                        </div>
                      )}
                      {(refNames(shotEntityRefs.characters) || refNames(shotEntityRefs.scenes) || refNames(shotEntityRefs.props) || refNames(shotEntityRefs.events) || shotEntityRefs.subtitle) && (
                        <div className="mt-3 space-y-1 border-t border-violet-400/20 pt-2 text-xs">
                          {refNames(shotEntityRefs.characters) && (
                            <div className="text-white/70">人物：{refNames(shotEntityRefs.characters)}</div>
                          )}
                          {refNames(shotEntityRefs.scenes) && (
                            <div className="text-white/70">场景：{refNames(shotEntityRefs.scenes)}</div>
                          )}
                          {refNames(shotEntityRefs.props) && (
                            <div className="text-white/70">道具：{refNames(shotEntityRefs.props)}</div>
                          )}
                          {refNames(shotEntityRefs.events) && (
                            <div className="text-white/70">事件：{refNames(shotEntityRefs.events)}</div>
                          )}
                          {shotEntityRefs.environment && (
                            <div className="text-white/50">环境：{shotEntityRefs.environment}</div>
                          )}
                          {shotEntityRefs.subtitle && (
                            <div className="text-green-200">字幕：{shotEntityRefs.subtitle}</div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

            {/* 视频模型选择 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Settings className="w-5 h-5" />
                  视频模型
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {videoModelsLoading ? (
                  <div className="text-white/50 text-sm py-2">加载中…</div>
                ) : videoModels.length === 0 ? (
                  <div className="text-white/50 text-sm py-2">暂无可用视频模型</div>
                ) : (
                  videoModels.map(model => (
                    <div
                      key={model.id}
                      onClick={() => setSelectedModel(model.id)}
                      className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                        selectedModel === model.id
                          ? 'border-violet-500 bg-violet-500/10'
                          : 'border-white/10 hover:border-white/20'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-white font-medium text-sm">
                            {model.name_cn || model.name}
                            {selectedModel === model.id && (
                              <span className="ml-2 text-xs text-violet-400">(已选)</span>
                            )}
                          </div>
                          <div className="text-white/40 text-xs mt-0.5">{model.desc}</div>
                          <div className="text-white/30 text-xs mt-0.5">ID: {model.id}</div>
                          <div className="mt-1 flex flex-wrap gap-1.5 text-xs">
                            <span className="rounded bg-white/10 px-2 py-0.5 text-white/55">
                              {model.is_default ? '默认视频配置' : model.is_configured ? '已保存配置' : '模型目录'}
                            </span>
                            <span className={`rounded border px-2 py-0.5 ${modelStatusClass(model.test_status)}`}>
                              {statusLabel(model.test_status)}
                            </span>
                          </div>
                        </div>
                        {selectedModel === model.id && (
                          <CheckCircle className="w-4 h-4 text-violet-400 flex-shrink-0" />
                        )}
                      </div>
                    </div>
                  ))
                )}
                {selectedVideoModel && (
                  <div className="rounded border border-white/10 bg-black/20 p-3 text-xs text-white/55">
                    <div className="text-white/75">当前静音视频会调用：{selectedVideoModel.provider_id || 'volcano'} / {selectedVideoModel.api_model_id || selectedVideoModel.id}</div>
                    <div className="mt-1">配置状态：{selectedVideoModel.is_configured ? '已保存配置' : '模型目录候选'}；验证状态：{statusLabel(selectedVideoModel.test_status)}。</div>
                    {!selectedVideoModel.is_configured && (
                      <div className="mt-1 text-yellow-100/70">
                        该模型尚未保存 API Key 配置。生产环境请先到大模型配置页保存并测试通过。
                      </div>
                    )}
                    {selectedVideoModel.is_configured && selectedVideoModel.test_status !== 'success' && !devModeEnabled && (
                      <div className="mt-1 text-yellow-100/70">
                        该配置尚未验证通过，正式生成前请先在大模型配置页测试连接。
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Sparkles className="w-5 h-5" />
                  生成模式
                </CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-2">
                <Button
                  variant={generationMode === 'video_only' ? 'default' : 'outline'}
                  onClick={() => setGenerationMode('video_only')}
                  className={generationMode === 'video_only' ? 'bg-violet-600' : 'border-white/10'}
                >
                  静音视频
                </Button>
                <Button
                  variant={generationMode === 'audio_video' ? 'default' : 'outline'}
                  onClick={() => setGenerationMode('audio_video')}
                  className={generationMode === 'audio_video' ? 'bg-violet-600' : 'border-white/10'}
                >
                  直生音视频
                </Button>
                <div className="col-span-2 text-xs text-white/45">
                  静音视频只消费火山视频模型和镜头一致性提示词；生产适配配置只在直生音视频或 workflow 云渲染中生效，并会生成字幕轨。
                </div>
              </CardContent>
            </Card>

            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <PlugZap className="w-5 h-5" />
                  生产适配上下文
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <label className="text-white/70 mb-2 block text-sm">外部适配配置</label>
                  <select
                    value={selectedExternalConfigId}
                    onChange={(event) => setSelectedExternalConfigId(event.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="">DEV_MODE / 默认配置</option>
                    {externalConfigs
                      .filter((config) => ['audio_video', 'workflow', 'lip_sync'].includes(config.api_type))
                      .map((config) => (
                        <option key={config.id} value={config.id}>
                          {config.provider_name} · {config.name}
                        </option>
                      ))}
                  </select>
                </div>
                <div className={`rounded border p-3 text-xs ${
                  generationMode === 'audio_video'
                    ? 'border-cyan-500/25 bg-cyan-500/10 text-cyan-50/80'
                    : 'border-yellow-500/25 bg-yellow-500/10 text-yellow-50/75'
                }`}>
                  {generationMode === 'audio_video'
                    ? `本次直生音视频会提交：${selectedExternalConfig ? `${selectedExternalConfig.provider_name} · ${selectedExternalConfig.name}` : 'DEV_MODE / 默认直生模型'}，并带入镜头、字幕、资产锁、关键帧、多视图和审核参数。`
                    : '当前是静音视频模式，不会调用这里的 Sora/Veo/ComfyUI/口型配置；切换到直生音视频，或在 workflow 合成步骤选择 FFmpeg 云渲染时才会消费这些配置。'}
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {productionContextUsage.map((item) => (
                    <div key={item.label} className="rounded bg-white/5 border border-white/10 p-2">
                      <div className="text-white/40">{item.label}</div>
                      <div className="text-white mt-1">{item.value}</div>
                    </div>
                  ))}
                </div>
                <div>
                  <label className="text-white/70 mb-2 block text-sm">口型模式</label>
                  <select
                    value={lipSyncMode}
                    onChange={(event) => setLipSyncMode(event.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="off">关闭</option>
                    <option value="model_audio">模型内置音画同步</option>
                    <option value="provider">外部口型服务</option>
                  </select>
                </div>
                <label className="flex items-center gap-2 text-sm text-white/70">
                  <input
                    type="checkbox"
                    checked={reviewRequired}
                    onChange={(event) => setReviewRequired(event.target.checked)}
                    className="accent-violet-500"
                  />
                  生成后进入审核
                </label>
                <div className="flex flex-wrap gap-2">
                  <Link href="/production-adapters" className="text-xs text-cyan-200 underline">
                    配置生产适配
                  </Link>
                  {currentShotId && (
                    <Link href="/shots" className="text-xs text-cyan-200 underline">
                      编辑镜头生产上下文
                    </Link>
                  )}
                </div>
                {currentShotId ? (
                  <div className="text-xs text-white/45">
                    当前镜头的资产锁、关键帧、多视图和审核状态会随直生音视频任务提交。
                  </div>
                ) : (
                  <div className="text-xs text-yellow-100/70">
                    请选择具体镜头后使用生产上下文。
                  </div>
                )}
              </CardContent>
            </Card>

            {/* 参数配置 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Wand2 className="w-5 h-5" />
                  参数配置
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* 视频描述 */}
                <div>
                  <label className="text-white/80 mb-2 block">视频描述</label>
                  <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="描述你想要生成的视频内容…"
                    disabled={status === 'generating'}
                    rows={5}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder:text-white/40 resize-none"
                  />
                  {shot?.prompt && prompt !== shot.prompt && (
                    <button
                      onClick={() => setPrompt(shot.prompt || '')}
                      className="text-xs text-violet-400 hover:text-violet-300 mt-1"
                    >
                      使用镜头prompt
                    </button>
                  )}
                </div>

                {/* 角色图像参考 */}
                <div>
                  <label className="text-white/80 mb-2 block">角色图像参考（可选）</label>
                  {characters.length > 0 ? (
                    <select
                      value={selectedCharacterId}
                      onChange={(e) => handleCharacterChange(e.target.value)}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white mb-2"
                    >
                      <option value="">不使用角色参考</option>
                      {characters.map(c => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                  ) : (
                    <p className="text-white/40 text-sm mb-2">
                      {selectedNovel ? '当前小说暂无角色' : '暂无角色'}
                    </p>
                  )}
                  {imageUrl && (
                    <div className="flex items-center gap-2">
                      <img src={resolveMediaUrl(imageUrl)} alt="参考" width={64} height={64} loading="lazy" className="w-16 h-16 rounded object-cover border border-white/10" />
                      <button
                        onClick={() => { setImageUrl(''); setSelectedCharacterId(''); }}
                        className="text-xs text-red-400 hover:text-red-300"
                      >
                        清除参考图
                      </button>
                    </div>
                  )}
                  {refNames(shotEntityRefs.characters) && (
                    <p className="mt-2 text-xs text-white/50">
                      镜头已绑定人物：{refNames(shotEntityRefs.characters)}
                    </p>
                  )}
                </div>

                {/* 时长 */}
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-white/80">时长</label>
                    <span className="text-white">{duration}秒</span>
                  </div>
                  <Slider
                    value={[duration]}
                    onValueChange={(v) => setDuration(v[0])}
                    min={4}
                    max={10}
                    step={1}
                    className="w-full"
                  />
                  <div className="flex justify-between text-white/40 text-xs mt-1">
                    <span>4s</span>
                    <span>10s</span>
                  </div>
                </div>

                {/* 分辨率 */}
                <div>
                  <label className="text-white/80 mb-2 block">分辨率</label>
                  <div className="flex gap-2">
                    {['480p', '720p', '1080p'].map(res => (
                      <Button
                        key={res}
                        variant={resolution === res ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setResolution(res)}
                        disabled={status === 'generating'}
                        className={resolution === res ? 'bg-violet-600' : 'border-white/10'}
                      >
                        {res}
                      </Button>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* 生成按钮 */}
            <Button
              onClick={generationMode === 'audio_video' ? handleGenerateAudioVideo : handleGenerate}
              disabled={status === 'submitting' || status === 'generating' || (!apiConfigured && !devModeEnabled) || apiConfigLoading || !videoModelReady}
              className="w-full bg-violet-600 hover:bg-violet-700 h-12"
            >
              {status === 'submitting' && <><Loader2 className="w-5 h-5 mr-2 animate-spin" />提交中…</>}
              {status === 'generating' && <><Loader2 className="w-5 h-5 mr-2 animate-spin" />生成中 {progress}%</>}
              {status === 'completed' && <><CheckCircle className="w-5 h-5 mr-2" />生成完成</>}
              {status === 'error' && <><AlertCircle className="w-5 h-5 mr-2" />重试</>}
              {status === 'idle' && <><Sparkles className="w-5 h-5 mr-2" />{generationMode === 'audio_video' ? '生成音视频' : '开始生成'}</>}
            </Button>

            {/* 错误信息 */}
            {error && (
              <Card className="bg-red-500/10 border-red-500/30">
                <CardContent className="p-3">
                  <p className="text-red-400 text-sm">{error}</p>
                </CardContent>
              </Card>
            )}
          </div>

          {/* 右侧：预览和历史 */}
          <div className="lg:col-span-2 space-y-4">
            {/* 预览区域 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Film className="w-5 h-5" />
                  视频预览
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="aspect-video bg-black/50 rounded-lg flex items-center justify-center relative overflow-hidden">
                  {status === 'idle' && (
                    <div className="text-center text-white/40">
                      <Video className="w-16 h-16 mx-auto mb-4 opacity-50" />
                      <p>输入描述并点击"开始生成"</p>
                    </div>
                  )}

                  {status === 'submitting' && (
                    <div className="text-center">
                      <Loader2 className="w-16 h-16 mx-auto mb-4 text-violet-400 animate-spin" />
                      <p className="text-white">正在提交任务…</p>
                    </div>
                  )}

                  {status === 'generating' && (
                    <div className="text-center w-full px-4">
                      <Loader2 className="w-16 h-16 mx-auto mb-4 text-violet-400 animate-spin" />
                      <p className="text-white">正在生成视频…</p>
                      <p className="text-white/60 text-sm mt-2">{progress}%</p>
                      {taskId && <p className="text-white/40 text-xs mt-1">任务ID: {taskId}</p>}
                      <div className="w-64 h-2 bg-white/10 rounded-full mt-4 mx-auto">
                        <div className="h-full bg-violet-500 rounded-full transition-[width]" style={{ width: `${progress}%` }} />
                      </div>
                    </div>
                  )}

                  {status === 'completed' && videoUrl && (
                    <div className="text-center w-full px-4">
                      <video src={videoUrl} controls autoPlay className="w-full h-full rounded-lg max-h-[400px]" />
                      {mediaJob?.subtitle_track_id && (
                        <div className="mt-3 rounded-lg border border-green-500/20 bg-green-500/10 p-3 text-left text-sm text-green-100">
                          <div className="font-medium">字幕轨已生成</div>
                          {subtitleTrack?.segments?.[0]?.text && (
                            <div className="mt-1 text-green-100/80">首段：{subtitleTrack.segments[0].text}</div>
                          )}
                          {subtitleExportUrl && (
                            <a className="mt-1 inline-block text-green-200 underline" href={subtitleExportUrl} target="_blank" rel="noreferrer">
                              打开 SRT 字幕
                            </a>
                          )}
                        </div>
                      )}
                      <div className="flex gap-2 mt-4 justify-center">
                        <Button onClick={() => handleDownload(undefined, 'video')} className="bg-violet-600 hover:bg-violet-700">
                          <Download className="w-4 h-4 mr-2" />下载
                        </Button>
                        <Button variant="outline" onClick={handleCopyUrl} className="border-white/20">
                          <Copy className="w-4 h-4 mr-2" />复制链接
                        </Button>
                        {mediaJob?.subtitle_track_id && (
                          <Button variant="outline" onClick={() => handleExportSubtitle(mediaJob.subtitle_track_id)} className="border-white/20">
                            <Download className="w-4 h-4 mr-2" />字幕
                          </Button>
                        )}
                      </div>
                    </div>
                  )}

                  {status === 'error' && (
                    <div className="text-center">
                      <AlertCircle className="w-16 h-16 mx-auto mb-4 text-red-400" />
                      <p className="text-red-400">生成失败</p>
                      <p className="text-white/60 text-sm mt-2">{error}</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* 历史筛选 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Filter className="w-5 h-5 text-cyan-300" />
                  历史筛选
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setSelectedNovel('');
                      setSelectedChapter('');
                      setScriptId('');
                      setStoryboardId('');
                      setCurrentShotId('');
                      setSelectedShotId('');
                      setShot(null);
                      setChapters([]);
                      setStoryboards([]);
                      setShots([]);
                    }}
                    className="ml-auto text-white/60"
                  >
                    清空
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
                  <div>
                    <label className="text-white/50 text-xs mb-1 block">小说</label>
                    <select
                      value={selectedNovel}
                      onChange={(event) => {
                        const nextNovelId = event.target.value;
                        setSelectedNovel(nextNovelId);
                        setSelectedChapter('');
                        setScriptId('');
                        setStoryboardId('');
                        setCurrentShotId('');
                        setSelectedShotId('');
                        setShot(null);
                        setShots([]);
                        loadChaptersByNovel(nextNovelId);
                        loadCharacters(nextNovelId);
                        loadStoryboardsForScripts(nextNovelId ? scripts.filter((script) => script.novel_id === nextNovelId) : scripts);
                      }}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                    >
                      <option value="">全部小说</option>
                      {novels.map((novel) => (
                        <option key={novel.id} value={novel.id}>{novel.title}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-white/50 text-xs mb-1 block">章节</label>
                    <select
                      value={selectedChapter}
                      onChange={(event) => chooseChapter(event.target.value)}
                      disabled={!selectedNovel}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm disabled:opacity-50"
                    >
                      <option value="">全部章节</option>
                      {chapters.map((chapter) => (
                        <option key={chapter.id} value={chapter.id}>
                          第{chapter.chapter_number}章 {chapter.title}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-white/50 text-xs mb-1 block">剧本</label>
                    <select
                      value={scriptId}
                      onChange={(event) => {
                        const nextScriptId = event.target.value;
                        setScriptId(nextScriptId);
                        setStoryboardId('');
                        setCurrentShotId('');
                        setSelectedShotId('');
                        setShot(null);
                        const selectedScript = scripts.find((script) => script.id === nextScriptId);
                        if (selectedScript?.novel_id) {
                          setSelectedNovel(selectedScript.novel_id);
                          loadCharacters(selectedScript.novel_id);
                          loadChaptersByNovel(selectedScript.novel_id);
                        }
                        if (selectedScript?.chapter_id) {
                          setSelectedChapter(selectedScript.chapter_id);
                        }
                        if (nextScriptId) {
                          loadStoryboardsByScript(nextScriptId);
                        } else {
                          const nextScripts = selectedNovel
                            ? scripts.filter((script) => script.novel_id === selectedNovel && (!selectedChapter || !script.chapter_id || script.chapter_id === selectedChapter))
                            : scripts;
                          loadStoryboardsForScripts(nextScripts);
                        }
                      }}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                    >
                      <option value="">全部剧本</option>
                      {scriptOptionsForPage.map((script) => (
                        <option key={script.id} value={script.id}>{script.title}</option>
                      ))}
                    </select>
                    {renderScriptPager()}
                  </div>
                  <div>
                    <label className="text-white/50 text-xs mb-1 block">分镜</label>
                    <select
                      value={storyboardId}
                      onChange={(event) => {
                        const nextStoryboardId = event.target.value;
                        setStoryboardId(nextStoryboardId);
                        setCurrentShotId('');
                        setSelectedShotId('');
                        setShot(null);
                        const selectedStoryboard = storyboards.find((storyboard) => storyboard.id === nextStoryboardId);
                        if (selectedStoryboard?.chapter_id) setSelectedChapter(selectedStoryboard.chapter_id);
                        if (selectedStoryboard?.novel_id) {
                          setSelectedNovel(selectedStoryboard.novel_id);
                          loadCharacters(selectedStoryboard.novel_id);
                          loadChaptersByNovel(selectedStoryboard.novel_id);
                        }
                        if (nextStoryboardId) {
                          loadShotsByStoryboard(nextStoryboardId);
                        } else {
                          setShots([]);
                        }
                      }}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                    >
                      <option value="">全部分镜</option>
                      {filteredStoryboards.map((storyboard) => (
                        <option key={storyboard.id} value={storyboard.id}>{storyboard.title}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-white/50 text-xs mb-1 block">镜头</label>
                    <select
                      value={selectedShotId}
                      onChange={(event) => handleShotChange(event.target.value)}
                      disabled={!storyboardId}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm disabled:opacity-50"
                    >
                      <option value="">全部镜头</option>
                      {shots.map((item) => (
                        <option key={item.id} value={item.id}>
                          镜头{item.shot_number} - {item.prompt?.slice(0, 18) || '无描述'}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="text-xs text-white/40">
                  当前筛选会同时作用于“生成历史”和“音视频直生历史”，用于核对同一小说、章节、剧本、分镜和镜头下的产物。
                </div>
              </CardContent>
            </Card>

            {/* 生成历史 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Clock className="w-5 h-5" />
                  生成历史
                  <Button variant="ghost" size="sm" onClick={loadHistory} disabled={isLoadingHistory} className="ml-auto text-white/60">
                    <RefreshCw className={`w-4 h-4 ${isLoadingHistory ? 'animate-spin' : ''}`} />
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {isLoadingHistory && history.length === 0 ? (
                  <div className="text-center py-8">
                    <Loader2 className="w-8 h-8 mx-auto mb-2 animate-spin text-white/40" />
                    <p className="text-white/40">加载中…</p>
                  </div>
                ) : history.length > 0 ? (
                  <div className="space-y-3 max-h-80 overflow-y-auto">
                    {history.map(job => (
                      <div key={job.id} className="flex items-center justify-between p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <div className="w-12 h-12 rounded bg-violet-500/20 flex items-center justify-center flex-shrink-0">
                            {job.status === 'succeeded' ? (
                              <Video className="w-6 h-6 text-violet-400" />
                            ) : job.status === 'failed' ? (
                              <AlertCircle className="w-6 h-6 text-red-400" />
                            ) : job.status === 'running' ? (
                              <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
                            ) : (
                              <Clock className="w-6 h-6 text-yellow-400" />
                            )}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="text-white font-medium truncate">
                              {job.title || job.prompt?.slice(0, 40) || '视频生成'}
                            </div>
                            <div className="text-white/60 text-sm flex items-center gap-2">
                              <span>{formatTime(job.created_at)}</span>
                              {job.duration && <span>{job.duration}秒</span>}
                              {job.resolution && <span>{job.resolution}</span>}
                            </div>
                            {(job.provider_id || job.api_model_id || job.model_endpoint_id || job.model_test_status) && (
                              <div className="text-white/40 text-xs flex flex-wrap gap-2">
                                {job.provider_id && <span>Provider: {job.provider_id}</span>}
                                {job.api_model_id && <span>API模型: {job.api_model_id}</span>}
                                {job.model_endpoint_id && <span>Endpoint: {job.model_endpoint_id}</span>}
                                {job.model_test_status && <span>验证: {statusLabel(job.model_test_status)}</span>}
                              </div>
                            )}
                            {job.prompt_parameters && Object.keys(job.prompt_parameters).length > 0 && (
                              <div className="text-white/35 text-xs">
                                参数：{job.prompt_parameters.duration || job.duration}秒 · {job.prompt_parameters.resolution || job.resolution} · seed {job.prompt_parameters.seed || job.seed || '自动'} · 参考图{job.prompt_parameters.image_url_sent ? '已传入' : '未传入'}
                              </div>
                            )}
                            {(job.novel_title || job.chapter_title || job.script_title || job.shot_number) && (
                              <div className="text-white/40 text-xs flex items-center gap-2">
                                {job.novel_title && <span>{job.novel_title}</span>}
                                {job.chapter_title && <span> / 第{job.chapter_number || ''}章 {job.chapter_title}</span>}
                                {job.script_title && <span> / {job.script_title}</span>}
                                {job.shot_number && <span> / 镜头{job.shot_number}</span>}
                              </div>
                            )}
                            {(refNames(job.character_refs) || refNames(job.scene_refs) || refNames(job.prop_refs) || refNames(job.event_refs) || job.subtitle_text) && (
                              <div className="mt-1 text-white/40 text-xs space-y-0.5">
                                {refNames(job.character_refs) && <div>人物：{refNames(job.character_refs)}</div>}
                                {refNames(job.scene_refs) && <div>场景：{refNames(job.scene_refs)}</div>}
                                {refNames(job.prop_refs) && <div>道具：{refNames(job.prop_refs)}</div>}
                                {refNames(job.event_refs) && <div>事件：{refNames(job.event_refs)}</div>}
                                {job.subtitle_text && <div className="text-green-200/70">字幕：{job.subtitle_text}</div>}
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <span className={`px-2 py-1 text-xs rounded ${
                            job.status === 'succeeded' ? 'bg-green-500/20 text-green-400' :
                            job.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                            job.status === 'running' ? 'bg-blue-500/20 text-blue-400' :
                            'bg-yellow-500/20 text-yellow-400'
                          }`}>
                            {job.status === 'succeeded' ? '已完成' :
                             job.status === 'failed' ? '失败' :
                             job.status === 'running' ? '生成中' : '等待'}
                          </span>
                          {(job.status === 'pending' || job.status === 'running') && (
                            <Button variant="ghost" size="sm" onClick={() => handleRefreshStatus(job)}>
                              <RefreshCw className="w-4 h-4" />
                            </Button>
                          )}
                          {job.video_url && (
                            <Button variant="ghost" size="sm" title="播放视频" onClick={() => handlePlayVideo(job.video_url)}>
                              <Play className="w-4 h-4" />
                            </Button>
                          )}
                          {job.video_url && (
                            <Button
                              variant="ghost"
                              size="sm"
                              title="下载视频"
                              onClick={() => handleDownload(job.video_url, job.title || job.task_id || 'video')}
                            >
                              <Download className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-white/40">
                    <Clock className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>暂无生成历史</p>
                    <p className="text-sm">生成视频后会显示在这里</p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Sparkles className="w-5 h-5" />
                  音视频直生历史
                </CardTitle>
              </CardHeader>
              <CardContent>
                {mediaHistory.length > 0 ? (
                  <div className="space-y-3 max-h-72 overflow-y-auto">
                    {mediaHistory.map(job => (
                      <div key={job.id} className="flex items-center justify-between p-3 rounded-lg bg-white/5">
                        <div className="min-w-0">
                          <div className="text-white font-medium truncate">{job.title || '音视频直生'}</div>
                          <div className="text-white/50 text-xs">
                            {formatTime(job.created_at)} · {job.duration_seconds || duration}秒 · {job.model_name || job.model_id}
                          </div>
                          {mediaLineageText(job) && (
                            <div className="mt-1 text-white/40 text-xs">
                              {mediaLineageText(job)}
                            </div>
                          )}
                          {(job.provider_id || job.extra_data?.external_config_id || job.extra_data?.lip_sync_mode || job.extra_data?.asset_version_locks?.length || job.extra_data?.keyframes?.length) && (
                            <div className="mt-1 flex flex-wrap gap-1.5 text-xs text-white/40">
                              {job.provider_id && <span>Provider: {job.provider_id}</span>}
                              {job.extra_data?.external_config_id && <span>适配配置已传入</span>}
                              {job.extra_data?.asset_version_locks?.length > 0 && <span>资产锁 {job.extra_data.asset_version_locks.length}</span>}
                              {job.extra_data?.keyframes?.length > 0 && <span>关键帧 {job.extra_data.keyframes.length}</span>}
                              {job.extra_data?.character_multiview_refs?.length > 0 && <span>多视图 {job.extra_data.character_multiview_refs.length}</span>}
                              {job.extra_data?.lip_sync_mode && job.extra_data.lip_sync_mode !== 'off' && <span>口型 {job.extra_data.lip_sync_mode}</span>}
                            </div>
                          )}
                          {job.extra_data?.subtitle_text && (
                            <div className="text-green-200/70 text-xs mt-1">字幕：{job.extra_data.subtitle_text}</div>
                          )}
                        </div>
                        <div className="flex gap-2">
                          {job.output_video_url && (
                            <Button variant="ghost" size="sm" title="播放音视频" onClick={() => handlePlayVideo(job.output_video_url)}>
                              <Play className="w-4 h-4" />
                            </Button>
                          )}
                          {job.subtitle_track_id && (
                            <Button variant="ghost" size="sm" title="导出字幕" onClick={() => handleExportSubtitle(job.subtitle_track_id)}>
                              <Download className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-6 text-white/40">
                    <Sparkles className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>暂无音视频直生任务</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* 模型信息 */}
            <Card className="bg-blue-600/10 border-blue-500/30">
              <CardContent className="p-4">
                <h4 className="font-medium text-blue-300 mb-2 flex items-center gap-2">
                  <Settings className="w-4 h-4" /> 当前使用
                </h4>
                <ul className="text-sm text-white/60 space-y-1">
                  <li>• <strong className="text-white/80">生成模式:</strong> {generationMode === 'audio_video' ? '直生音视频（消费生产适配和字幕轨）' : '静音视频（火山视频模型）'}</li>
                  <li>• <strong className="text-white/80">模型:</strong> {selectedVideoModel?.name_cn || selectedVideoModel?.name || selectedModel}</li>
                  <li>• <strong className="text-white/80">API模型:</strong> {selectedVideoModel?.api_model_id || selectedModel}</li>
                  <li>• <strong className="text-white/80">提供商:</strong> {generationMode === 'audio_video' ? (selectedExternalConfig?.provider_name || '直生音视频默认适配') : (selectedVideoModel?.provider_id || 'volcano')}</li>
                  <li>• <strong className="text-white/80">验证状态:</strong> {generationMode === 'audio_video' ? (selectedExternalConfig ? statusLabel(selectedExternalConfig.test_status) : 'DEV_MODE/默认') : statusLabel(selectedVideoModel?.test_status)}</li>
                  <li>• <strong className="text-white/80">支持:</strong> {generationMode === 'audio_video' ? '音视频直生、字幕、资产锁、关键帧、多视图、口型/审核参数' : '文生视频、图生视频、一致性提示词'}</li>
                  {selectedNovel && <li>• <strong className="text-white/80">小说ID:</strong> {selectedNovel.slice(0, 8)}...</li>}
                  {selectedChapter && <li>• <strong className="text-white/80">章节ID:</strong> {selectedChapter.slice(0, 8)}...</li>}
                  {currentShotId && <li>• <strong className="text-white/80">镜头ID:</strong> {currentShotId.slice(0, 8)}...</li>}
                  {storyboardId && <li>• <strong className="text-white/80">分镜ID:</strong> {storyboardId.slice(0, 8)}...</li>}
                  {scriptId && <li>• <strong className="text-white/80">剧本ID:</strong> {scriptId.slice(0, 8)}...</li>}
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}

// 包装 Suspense
export default function VideoGenerationPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center py-20"><span className="text-white/60">加载中…</span></div>}>
      <VideoGenerationPageInner />
    </Suspense>
  );
}
