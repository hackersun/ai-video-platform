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
  ChevronRight,
  Loader2,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Download,
  Copy,
  Image as ImageIcon,
  Loader
} from 'lucide-react';

// 视频生成状态
type GenerationStatus = 'idle' | 'submitting' | 'generating' | 'completed' | 'error';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// 提供商配置
const PROVIDERS = [
  { id: 'volcano', name: '火山引擎', icon: '🔥', cost: '约50分/秒' },
];

// 默认火山API Key
const DEFAULT_API_KEY = 'be8feb9d-6b08-406e-8447-b22b87cd907a';

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
}

function VideoGenerationPageContent() {
  const searchParams = useSearchParams();
  const novelId = searchParams.get('novel_id');
  const scriptId = searchParams.get('script');
  const storyboardId = searchParams.get('storyboard');
  const coverUrlParam = searchParams.get('cover_url');
  
  const [selectedProvider] = useState('volcano');
  const [status, setStatus] = useState<GenerationStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // 参数配置
  const [prompt, setPrompt] = useState('无人机以极快速度穿越复杂障碍或自然奇观，带来沉浸式飞行体验');
  const [duration, setDuration] = useState(5);
  const [resolution, setResolution] = useState('720p');
  const [imageUrl, setImageUrl] = useState(coverUrlParam || '');
  
  // 历史记录
  const [history, setHistory] = useState<VideoJob[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  
  // 关联信息
  const [novelInfo, setNovelInfo] = useState<{title?: string; description?: string; cover_url?: string} | null>(null);

  // 加载历史记录
  const loadHistory = async () => {
    setIsLoadingHistory(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/video/jobs`);
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

  useEffect(() => {
    loadHistory();
    
    // 如果有novel_id，加载小说信息
    if (novelId) {
      loadNovelInfo();
    }
  }, []);

  // 加载小说信息
  const loadNovelInfo = async () => {
    if (!novelId) return;
    
    try {
      const token = localStorage.getItem('token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      const response = await fetch(`${API_BASE}/api/v1/novels/${novelId}`, { headers });
      
      if (response.ok) {
        const data = await response.json();
        setNovelInfo(data);
        
        // 如果没有设置封面图，使用小说封面
        if (!imageUrl && data.cover_url) {
          setImageUrl(data.cover_url);
        }
        
        // 如果没有自定义prompt，使用小说描述
        if (!prompt || prompt === '无人机以极快速度穿越复杂障碍或自然奇观，带来沉浸式飞行体验') {
          setPrompt(data.description || `基于小说《${data.title}》的视频`);
        }
      }
    } catch (err) {
      console.error('加载小说信息失败:', err);
    }
  };

  // 轮询任务状态
  const pollTaskStatus = async (tid: string, jid: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/video/status/${tid}?api_key=${DEFAULT_API_KEY}&job_id=${jid}`);
      if (!response.ok) {
        throw new Error('查询失败');
      }
      const data = await response.json();
      
      setProgress(data.progress || 0);
      
      if (data.status === 'succeeded') {
        setStatus('completed');
        setVideoUrl(data.video_url);
        setProgress(100);
        // 刷新历史
        loadHistory();
      } else if (data.status === 'failed') {
        setStatus('error');
        setError(data.message || '生成失败');
        loadHistory();
      } else {
        // 继续轮询
        setTimeout(() => pollTaskStatus(tid, jid), 3000);
      }
    } catch (err) {
      console.error('轮询状态失败:', err);
      setTimeout(() => pollTaskStatus(tid, jid), 5000);
    }
  };

  // 生成视频
  const handleGenerate = async () => {
    if (!prompt.trim()) {
      alert('请输入视频描述');
      return;
    }

    setStatus('submitting');
    setProgress(0);
    setError(null);
    setVideoUrl(null);

    try {
      const response = await fetch(`${API_BASE}/api/v1/video/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt,
          duration: duration,
          resolution: resolution,
          api_key: DEFAULT_API_KEY,
          image_url: imageUrl || undefined,
          model: 'doubao-seedance-1-5-pro-251215'
        })
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || '提交失败');
      }

      const data = await response.json();
      setTaskId(data.task_id);
      setJobId(data.job_id);
      setStatus('generating');
      
      // 开始轮询
      pollTaskStatus(data.task_id, data.job_id);
      // 刷新历史列表
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
      const response = await fetch(`${API_BASE}/api/v1/video/jobs/${job.id}/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: DEFAULT_API_KEY })
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
  const handleDownload = async () => {
    if (videoUrl) {
      try {
        // 使用后端代理下载，解决URL特殊字符截断问题
        const response = await fetch(`${API_BASE}/api/v1/video/download`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            video_url: videoUrl,
            filename: 'ai_video.mp4'
          })
        });
        
        if (response.ok) {
          const blob = await response.blob();
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'ai_video.mp4';
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
        } else {
          alert('下载失败');
        }
      } catch (err) {
        console.error('下载失败:', err);
        // 降级：直接打开URL
        window.open(videoUrl, '_blank');
      }
    }
  };

  // 格式化时间
  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString();
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Video className="w-6 h-6" />
            视频生成
          </h1>
          <p className="text-white/60 mt-1">使用AI生成高质量视频</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧：生成配置 */}
          <div className="lg:col-span-1 space-y-4">
            {/* 提供商 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Settings className="w-5 h-5" />
                  提供商
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {PROVIDERS.map((provider) => (
                  <div
                    key={provider.id}
                    className={`p-4 rounded-lg border cursor-pointer transition-all ${
                      selectedProvider === provider.id
                        ? 'border-violet-500 bg-violet-500/10'
                        : 'border-white/10'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">{provider.icon}</span>
                        <div>
                          <div className="text-white font-medium">{provider.name}</div>
                          <div className="text-white/60 text-sm">{provider.cost}</div>
                        </div>
                      </div>
                      {selectedProvider === provider.id && (
                        <CheckCircle className="w-5 h-5 text-violet-400" />
                      )}
                    </div>
                  </div>
                ))}
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
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder:text-white/40 h-24 resize-none"
                  />
                </div>

                {/* 参考图片（可选） */}
                <div>
                  <label className="text-white/80 mb-2 block">参考图片URL（可选）</label>
                  <Input
                    placeholder="输入图片URL用于图生视频"
                    value={imageUrl}
                    onChange={(e) => setImageUrl(e.target.value)}
                    disabled={status === 'generating'}
                    className="bg-white/5 border-white/10 text-white"
                  />
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
                    {['480p', '720p', '1080p'].map((res) => (
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
              disabled={status === 'submitting' || status === 'generating'}
              className="w-full bg-violet-600 hover:bg-violet-700 h-12"
            >
              {status === 'submitting' && (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  提交中...
                </>
              )}
              {status === 'generating' && (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  生成中 {progress}%
                </>
              )}
              {status === 'completed' && (
                <>
                  <CheckCircle className="w-5 h-5 mr-2" />
                  生成完成
                </>
              )}
              {status === 'error' && (
                <>
                  <AlertCircle className="w-5 h-5 mr-2" />
                  重试
                </>
              )}
              {(status === 'idle') && (
                <>
                  <Sparkles className="w-5 h-5 mr-2" />
                  开始生成
                </>
              )}
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

          {/* 右侧：预览和结果 */}
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
                    <div className="text-center">
                      <Loader2 className="w-16 h-16 mx-auto mb-4 text-violet-400 animate-spin" />
                      <p className="text-white">正在生成视频...</p>
                      <p className="text-white/60 text-sm mt-2">{progress}%</p>
                      {taskId && (
                        <p className="text-white/40 text-xs mt-1">任务ID: {taskId}</p>
                      )}
                      
                      {/* 进度条 */}
                      <div className="w-64 h-2 bg-white/10 rounded-full mt-4 mx-auto">
                        <div 
                          className="h-full bg-violet-500 rounded-full transition-all"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                    </div>
                  )}
                  
                  {status === 'completed' && videoUrl && (
                    <div className="text-center w-full px-4">
                      <video 
                        src={videoUrl}
                        controls
                        autoPlay
                        className="w-full h-full rounded-lg max-h-[400px]"
                      />
                      <div className="flex gap-2 mt-4 justify-center">
                        <Button onClick={handleDownload} className="bg-violet-600 hover:bg-violet-700">
                          <Download className="w-4 h-4 mr-2" />
                          下载
                        </Button>
                        <Button variant="outline" onClick={handleCopyUrl} className="border-white/20">
                          <Copy className="w-4 h-4 mr-2" />
                          复制链接
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
                  <Button 
                    variant="ghost" 
                    size="sm"
                    onClick={loadHistory}
                    disabled={isLoadingHistory}
                    className="ml-auto text-white/60"
                  >
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
                    {history.map((job) => (
                      <div
                        key={job.id}
                        className="flex items-center justify-between p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors"
                      >
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
                              {job.title || job.prompt?.slice(0, 30) || '视频生成'}
                            </div>
                            <div className="text-white/60 text-sm flex items-center gap-2">
                              <span>{formatTime(job.created_at)}</span>
                              {job.duration && <span>{job.duration}秒</span>}
                              {job.resolution && <span>{job.resolution}</span>}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <span className={`px-2 py-1 text-xs rounded ${
                            job.status === 'succeeded' 
                              ? 'bg-green-500/20 text-green-400' 
                              : job.status === 'failed'
                              ? 'bg-red-500/20 text-red-400'
                              : job.status === 'running'
                              ? 'bg-blue-500/20 text-blue-400'
                              : 'bg-yellow-500/20 text-yellow-400'
                          }`}>
                            {job.status === 'succeeded' ? '已完成' : 
                             job.status === 'failed' ? '失败' : 
                             job.status === 'running' ? '生成中' : '等待'}
                          </span>
                          {(job.status === 'pending' || job.status === 'running') && (
                            <Button 
                              variant="ghost" 
                              size="sm"
                              onClick={() => handleRefreshStatus(job)}
                            >
                              <RefreshCw className="w-4 h-4" />
                            </Button>
                          )}
                          {job.video_url && (
                            <Button 
                              variant="ghost" 
                              size="sm"
                              onClick={() => {
                                setVideoUrl(job.video_url!);
                                setStatus('completed');
                              }}
                            >
                              <Play className="w-4 h-4" />
                            </Button>
                          )}
                          {job.video_url && (
                            <Button 
                              variant="ghost" 
                              size="sm"
                              onClick={async () => {
                                try {
                                  const response = await fetch(`${API_BASE}/api/v1/video/download`, {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                      video_url: job.video_url,
                                      filename: `video_${job.id}.mp4`
                                    })
                                  });
                                  if (response.ok) {
                                    const blob = await response.blob();
                                    const url = window.URL.createObjectURL(blob);
                                    const a = document.createElement('a');
                                    a.href = url;
                                    a.download = `video_${job.id}.mp4`;
                                    document.body.appendChild(a);
                                    a.click();
                                    window.URL.revokeObjectURL(url);
                                    document.body.removeChild(a);
                                  }
                                } catch (err) {
                                  console.error('下载失败:', err);
                                  window.open(job.video_url, '_blank');
                                }
                              }}
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

            {/* 模型信息 */}
            <Card className="bg-blue-600/10 border-blue-500/30">
              <CardContent className="p-4">
                <h4 className="font-medium text-blue-300 mb-2 flex items-center gap-2">
                  当前使用
                </h4>
                <ul className="text-sm text-white/60 space-y-1">
                  <li>• <strong className="text-white/80">模型:</strong> Doubao-Seedance-1.5-pro</li>
                  <li>• <strong className="text-white/80">ID:</strong> doubao-seedance-1-5-pro-251215</li>
                  <li>• <strong className="text-white/80">提供商:</strong> 火山引擎</li>
                  <li>• <strong className="text-white/80">支持:</strong> 文生视频、图生视频</li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}

// 包装组件，提供 Suspense 边界（useSearchParams 需要）
export default function VideoGenerationPage() {
  return (
    <Suspense fallback={
      <MainLayout>
        <div className="min-h-screen flex items-center justify-center">
          <Loader className="w-8 h-8 animate-spin text-violet-500" />
        </div>
      </MainLayout>
    }>
      <VideoGenerationPageContent />
    </Suspense>
  );
}
