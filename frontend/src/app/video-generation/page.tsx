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
  ChevronRight,
  BookOpen,
  FileText,
  LayoutGrid
} from 'lucide-react';
import Link from 'next/link';
import { fetchWithAuth } from '@/lib/fetch-with-auth';

// 视频生成状态
type GenerationStatus = 'idle' | 'submitting' | 'generating' | 'completed' | 'error';

// 视频模型配置（从后端动态加载）
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// 视频模型类型（从后端加载后填充）
interface VideoModelOption {
  id: string;
  name: string;
  name_cn: string;
  desc: string;
  duration: string;
  model_id: string; // API调用用的model_id
}

// 角色类型
interface Character {
  id: string;
  name: string;
  avatar?: string;
  appearance?: string;
}

// 镜头类型
interface Shot {
  id: string;
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
}

// 小说类型
interface Novel {
  id: string;
  title: string;
}

// 剧本类型
interface Script {
  id: string;
  title: string;
  novel_id?: string;
}

// 分镜类型
interface Storyboard {
  id: string;
  title: string;
  script_id: string;
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
  script_id?: string;
  script_title?: string;
  storyboard_id?: string;
  shot_id?: string;
  shot_number?: number;
  extra_data?: any;
}

// 视频生成参数
interface VideoGenerateParams {
  shot_id?: string;
  storyboard_id?: string;
  script_id?: string;
  novel_id?: string;
  prompt: string;
  duration: number;
  resolution: string;
  image_url?: string;
  model: string;
}

function VideoGenerationPageInner() {
  const searchParams = useSearchParams();

  // ====== URL 参数 ======
  const urlScriptId = searchParams.get('script_id');
  const urlStoryboardId = searchParams.get('storyboard_id');
  const urlShotId = searchParams.get('shot_id');

  // ====== 状态 ======
  const [status, setStatus] = useState<GenerationStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [apiKeyLoading, setApiKeyLoading] = useState(true);
  const [videoModels, setVideoModels] = useState<VideoModelOption[]>([]);
  const [videoModelsLoading, setVideoModelsLoading] = useState(true);

  // 关联数据
  const [novels, setNovels] = useState<Novel[]>([]);
  const [selectedNovel, setSelectedNovel] = useState<string>('');
  const [shot, setShot] = useState<Shot | null>(null);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [selectedCharacterId, setSelectedCharacterId] = useState<string>('');
  const [scripts, setScripts] = useState<Script[]>([]);
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

  // 历史记录
  const [history, setHistory] = useState<VideoJob[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // 加载火山引擎 API Key
  const loadApiKey = async () => {
    setApiKeyLoading(true);
    try {
      // 使用专用端点获取解密后的 API Key
      const response = await fetchWithAuth(`${API_BASE}/llm/api-key/volcano`);
      if (response.ok) {
        const data = await response.json();
        if (data.configured && data.api_key) {
          setApiKey(data.api_key);
        }
      }
    } catch (err) {
      console.error('加载API Key失败:', err);
    } finally {
      setApiKeyLoading(false);
    }
  };

  // 加载视频模型列表和默认模型
  const loadVideoModels = async () => {
    setVideoModelsLoading(true);
    try {
      // 并行加载：火山引擎模型列表 + 用户默认配置
      const [modelsRes, defaultRes] = await Promise.all([
        fetchWithAuth(`${API_BASE}/llm/models?provider=volcano`),
        fetchWithAuth(`${API_BASE}/llm/configs`),
      ]);

      // 解析视频模型列表
      if (modelsRes.ok) {
        const allModels = await modelsRes.json();
        const videoOnly = (allModels as any[]).filter(
          (m: any) => m.model_type === 'video-generation'
        );
        const mapped: VideoModelOption[] = videoOnly.map((m: any) => ({
          id: m.model_id,           // API调用用model_id
          name: m.model_name || m.model_id,
          name_cn: m.model_name_cn || m.model_name || m.model_id,
          desc: m.description || m.capabilities?.join('/') || '',
          duration: '4/5/8/10秒',
          model_id: m.model_id,
        }));
        setVideoModels(mapped);
      }

      // 解析用户默认视频模型
      if (defaultRes.ok) {
        const configs = await defaultRes.json();
        const defaultConfig = (configs as any[]).find(
          (c: any) => c.is_default && c.provider_id === 'volcano'
        );
        if (defaultConfig) {
          setSelectedModel(defaultConfig.model_id);
        } else if (videoModels.length > 0 && !selectedModel) {
          // 没有默认配置，选第一个
          setSelectedModel(videoModels[0].id);
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
        setScripts(Array.isArray(data) ? data : []);
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

  // 加载角色的函数（会过滤没有avatar的）
  const loadCharacters = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/characters`);
      if (res.ok) {
        const data = await res.json();
        // 只保留有avatar的角色
        setCharacters((Array.isArray(data) ? data : []).filter((c: Character) => c.avatar));
      }
    } catch (err) {
      console.error('加载角色失败:', err);
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
        // 自动填充prompt
        if (data.prompt) {
          setPrompt(data.prompt);
        }
        // 如果镜头有参考图片，自动填入
        if (data.image_url) {
          setImageUrl(data.image_url);
        }
      }
    } catch (err) {
      console.error('加载镜头详情失败:', err);
    }
  };

  // 加载历史记录
  const loadHistory = async () => {
    setIsLoadingHistory(true);
    try {
      const response = await fetchWithAuth(`${API_BASE}/video/jobs`);
      if (response.ok) {
        const data = await response.json();
        setHistory(data || []);
      }
    } catch (err) {
      console.error('加载历史失败:', err);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  // 初始化
  useEffect(() => {
    loadVideoModels();
    loadApiKey();
    loadHistory();
    loadScripts();
    loadCharacters();
    loadNovels();
  }, []);

  // 根据URL参数自动加载关联数据
  useEffect(() => {
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
  }, [urlScriptId, urlStoryboardId, urlShotId]);

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
    loadShotDetail(shotId);
  };

  // 轮询任务状态
  const pollTaskStatus = async (tid: string, jid: string) => {
    try {
      const response = await fetchWithAuth(`${API_BASE}/video/status/${tid}?api_key=${apiKey}&job_id=${jid}`);
      if (!response.ok) {
        throw new Error('查询失败');
      }
      const data = await response.json();

      setProgress(data.progress || 0);

      if (data.status === 'succeeded') {
        setStatus('completed');
        setVideoUrl(data.video_url);
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
      alert('请输入视频描述');
      return;
    }
    if (!apiKey) {
      alert('请先配置火山引擎 API Key。请前往「LLM 配置」页面进行配置。');
      return;
    }

    // 私有/本地图片地址无法被火山引擎访问，直接跳过
    if (isPrivateImageUrl(imageUrl)) {
      alert('参考图片使用了本地/私有地址，火山引擎无法访问。已自动改为纯文生视频模式。');
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

      // 如果选择了镜头，传递镜头ID
      if (currentShotId) {
        params.shot_id = currentShotId;
      } else if (storyboardId) {
        params.storyboard_id = storyboardId;
      } else if (scriptId) {
        params.script_id = scriptId;
      }

      // 传递小说ID（用于关联记录）
      if (selectedNovel) {
        params.novel_id = selectedNovel;
      }

      // 发送前验证图片 URL（跳过私有地址，公网地址预检可访问性）
      let sendImageUrl = false;
      if (imageUrl && !isPrivateImageUrl(imageUrl)) {
        const accessible = await checkImageAccessible(imageUrl);
        if (accessible) {
          params.image_url = imageUrl.trim();
          sendImageUrl = true;
        } else {
          // 公网地址预检失败（跨域/超时/非图片），仍尝试发送给火山引擎
          // 火山引擎返回的 error 会更准确
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

  // 刷新单个任务状态
  const handleRefreshStatus = async (job: VideoJob) => {
    if (!job.id) return;
    try {
      const response = await fetchWithAuth(`${API_BASE}/video/jobs/${job.id}/refresh`, {
        method: 'POST',
        body: JSON.stringify({ api_key: apiKey })
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
      navigator.clipboard.writeText(videoUrl);
      alert('链接已复制');
    }
  };

  // 下载视频
  const handleDownload = () => {
    if (videoUrl) {
      window.open(videoUrl, '_blank');
    }
  };

  // 格式化时间
  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  // 判断是否有上游数据
  const hasUpstream = !!(urlScriptId || urlStoryboardId || urlShotId);

  // 根据选择的小说过滤剧本列表
  const filteredScripts = selectedNovel
    ? scripts.filter((s) => s.novel_id === selectedNovel)
    : scripts;

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
              {hasUpstream ? '基于分镜/镜头生成视频' : '使用AI生成高质量视频'}
            </p>
          </div>
          <div className="flex gap-2">
            <Link href="/scripts">
              <Button variant="outline" size="sm" className="border-white/20 text-white">
                <FileText className="w-4 h-4 mr-1" />剧本
              </Button>
            </Link>
            <Link href="/storyboards">
              <Button variant="outline" size="sm" className="border-white/20 text-white">
                <LayoutGrid className="w-4 h-4 mr-1" />分镜
              </Button>
            </Link>
          </div>
        </div>

        {/* API Key 配置提示 */}
        {apiKeyLoading ? (
          <div className="flex items-center gap-2 text-white/40 text-sm">
            <Loader2 className="w-4 h-4 animate-spin" />
            加载 API 配置...
          </div>
        ) : !apiKey ? (
          <Card className="bg-yellow-500/10 border-yellow-500/30">
            <CardContent className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-yellow-400" />
                <div>
                  <p className="text-yellow-300 font-medium">未配置 API Key</p>
                  <p className="text-yellow-400/60 text-sm">请先配置火山引擎 API Key 才能生成视频</p>
                </div>
              </div>
              <Link href="/llm-config">
                <Button variant="outline" size="sm" className="border-yellow-500/50 text-yellow-400 hover:bg-yellow-500/10">
                  前往配置
                </Button>
              </Link>
            </CardContent>
          </Card>
        ) : null}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧：关联选择 + 参数配置 */}
          <div className="lg:col-span-1 space-y-4">
            {/* 关联数据选择 */}
            {!hasUpstream && (
              <Card className="bg-white/5 border-white/10">
                <CardHeader>
                  <CardTitle className="text-white flex items-center gap-2">
                    <BookOpen className="w-5 h-5 text-violet-400" />
                    数据关联
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* 小说选择 */}
                  <div>
                    <label className="text-white/60 text-sm mb-1 block">小说</label>
                    <select
                      value={selectedNovel}
                      onChange={(e) => {
                        setSelectedNovel(e.target.value);
                        setScriptId('');
                        setStoryboardId('');
                        setCurrentShotId('');
                        setSelectedShotId('');
                        setShot(null);
                      }}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                    >
                      <option value="">-- 选择小说 --</option>
                      {novels.map((n) => (
                        <option key={n.id} value={n.id}>{n.title}</option>
                      ))}
                    </select>
                  </div>

                  {/* 剧本选择 */}
                  <div>
                    <label className="text-white/60 text-sm mb-1 block">剧本</label>
                    <select
                      value={scriptId}
                      onChange={(e) => {
                        setScriptId(e.target.value);
                        setStoryboardId('');
                        setCurrentShotId('');
                        setSelectedShotId('');
                        setShot(null);
                        if (e.target.value) {
                          loadStoryboardsByScript(e.target.value);
                        } else {
                          setStoryboards([]);
                        }
                      }}
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                    >
                      <option value="">手动输入描述</option>
                      {filteredScripts.map(s => (
                        <option key={s.id} value={s.id}>{s.title}</option>
                      ))}
                    </select>
                  </div>

                  {/* 分镜选择 */}
                  {scriptId && (
                    <div>
                      <label className="text-white/60 text-sm mb-1 block">分镜</label>
                      <select
                        value={storyboardId}
                        onChange={(e) => {
                          setStoryboardId(e.target.value);
                          setCurrentShotId('');
                          setSelectedShotId('');
                          setShot(null);
                          if (e.target.value) {
                            loadShotsByStoryboard(e.target.value);
                          } else {
                            setShots([]);
                          }
                        }}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                      >
                        <option value="">全部镜头</option>
                        {storyboards.map(sb => (
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
                        镜头{shot.shot_number} | {shot.duration}秒 | {shot.camera_angle || '无角度'}
                      </div>
                      {shot.visual_description && (
                        <div className="text-white/50 text-xs mt-1 line-clamp-2">
                          {shot.visual_description}
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

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
                  <div className="text-white/50 text-sm py-2">加载中...</div>
                ) : videoModels.length === 0 ? (
                  <div className="text-white/50 text-sm py-2">暂无可用视频模型</div>
                ) : (
                  videoModels.map(model => (
                    <div
                      key={model.id}
                      onClick={() => setSelectedModel(model.id)}
                      className={`p-3 rounded-lg border cursor-pointer transition-all ${
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
                        </div>
                        {selectedModel === model.id && (
                          <CheckCircle className="w-4 h-4 text-violet-400 flex-shrink-0" />
                        )}
                      </div>
                    </div>
                  ))
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
                    placeholder="描述你想要生成的视频内容..."
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
                    <p className="text-white/40 text-sm mb-2">暂无带图像的角色</p>
                  )}
                  {imageUrl && (
                    <div className="flex items-center gap-2">
                      <img src={imageUrl} alt="参考" className="w-16 h-16 rounded object-cover border border-white/10" />
                      <button
                        onClick={() => { setImageUrl(''); setSelectedCharacterId(''); }}
                        className="text-xs text-red-400 hover:text-red-300"
                      >
                        清除参考图
                      </button>
                    </div>
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
              onClick={handleGenerate}
              disabled={status === 'submitting' || status === 'generating' || !apiKey || apiKeyLoading}
              className="w-full bg-violet-600 hover:bg-violet-700 h-12"
            >
              {status === 'submitting' && <><Loader2 className="w-5 h-5 mr-2 animate-spin" />提交中...</>}
              {status === 'generating' && <><Loader2 className="w-5 h-5 mr-2 animate-spin" />生成中 {progress}%</>}
              {status === 'completed' && <><CheckCircle className="w-5 h-5 mr-2" />生成完成</>}
              {status === 'error' && <><AlertCircle className="w-5 h-5 mr-2" />重试</>}
              {status === 'idle' && <><Sparkles className="w-5 h-5 mr-2" />开始生成</>}
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
                      <p className="text-white">正在提交任务...</p>
                    </div>
                  )}

                  {status === 'generating' && (
                    <div className="text-center w-full px-4">
                      <Loader2 className="w-16 h-16 mx-auto mb-4 text-violet-400 animate-spin" />
                      <p className="text-white">正在生成视频...</p>
                      <p className="text-white/60 text-sm mt-2">{progress}%</p>
                      {taskId && <p className="text-white/40 text-xs mt-1">任务ID: {taskId}</p>}
                      <div className="w-64 h-2 bg-white/10 rounded-full mt-4 mx-auto">
                        <div className="h-full bg-violet-500 rounded-full transition-all" style={{ width: `${progress}%` }} />
                      </div>
                    </div>
                  )}

                  {status === 'completed' && videoUrl && (
                    <div className="text-center w-full px-4">
                      <video src={videoUrl} controls autoPlay className="w-full h-full rounded-lg max-h-[400px]" />
                      <div className="flex gap-2 mt-4 justify-center">
                        <Button onClick={handleDownload} className="bg-violet-600 hover:bg-violet-700">
                          <Download className="w-4 h-4 mr-2" />下载
                        </Button>
                        <Button variant="outline" onClick={handleCopyUrl} className="border-white/20">
                          <Copy className="w-4 h-4 mr-2" />复制链接
                        </Button>
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
                    <p className="text-white/40">加载中...</p>
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
                            {(job.novel_title || job.script_title || job.shot_number) && (
                              <div className="text-white/40 text-xs flex items-center gap-2">
                                {job.novel_title && <span>{job.novel_title}</span>}
                                {job.script_title && <span> / {job.script_title}</span>}
                                {job.shot_number && <span> / 镜头{job.shot_number}</span>}
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
                            <Button variant="ghost" size="sm" onClick={() => { setVideoUrl(job.video_url!); setStatus('completed'); }}>
                              <Play className="w-4 h-4" />
                            </Button>
                          )}
                          {job.video_url && (
                            <Button variant="ghost" size="sm" onClick={() => window.open(job.video_url, '_blank')}>
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

            {/* 模型信息 */}
            <Card className="bg-blue-600/10 border-blue-500/30">
              <CardContent className="p-4">
                <h4 className="font-medium text-blue-300 mb-2 flex items-center gap-2">
                  <Settings className="w-4 h-4" /> 当前使用
                </h4>
                <ul className="text-sm text-white/60 space-y-1">
                  <li>• <strong className="text-white/80">模型:</strong> {videoModels.find(m => m.id === selectedModel)?.name_cn || videoModels.find(m => m.id === selectedModel)?.name || selectedModel}</li>
                  <li>• <strong className="text-white/80">ID:</strong> {selectedModel}</li>
                  <li>• <strong className="text-white/80">提供商:</strong> 火山引擎</li>
                  <li>• <strong className="text-white/80">支持:</strong> 文生视频、图生视频</li>
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
    <Suspense fallback={<div className="flex items-center justify-center py-20"><span className="text-white/60">加载中...</span></div>}>
      <VideoGenerationPageInner />
    </Suspense>
  );
}
