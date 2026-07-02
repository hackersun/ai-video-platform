'use client';

import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import { useToast } from '@/components/ui/toast';
import { 
  Play, 
  Pause,
  Download, 
  Loader2,
  AlertCircle,
  Video,
  Volume2,
  Combine,
  RefreshCw,
  Clock,
  Settings,
  CheckCircle,
  XCircle,
  Film,
  Trash2,
  Eye,
  ExternalLink,
  FileText,
  Filter
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, '');

const toMediaUrl = (url?: string) => {
  if (!url) return '';
  return url.startsWith('/') ? `${API_ORIGIN}${url}` : url;
};

type RenderArtifactLinks = {
  preview_url?: string;
  srt_url?: string;
  timeline_url?: string;
  render_manifest_url?: string;
  source_manifest_url?: string;
};

const createEmptyHistoryFilters = () => ({
  novel_id: '',
  chapter_id: '',
  script_id: '',
  storyboard_id: '',
  shot_id: '',
  status: '',
  render_status: '',
});

interface VideoJob {
  id: string;
  title?: string;
  prompt?: string;
  status: string;
  video_url?: string;
  duration?: number;
  created_at: string;
}

interface TTSJob {
  id: string;
  title?: string;
  text?: string;
  status: string;
  audio_url?: string;
  duration_seconds?: number;
  created_at: string;
}

interface SynthesisJob {
  id: string;
  title?: string;
  status: string;
  progress: number;
  video_url?: string;
  audio_url?: string;
  output_url?: string;
  manifest_url?: string;
  preview_url?: string;
  srt_url?: string;
  timeline_url?: string;
  render_manifest_url?: string;
  render_status?: string;
  render_backend?: string;
  is_publishable?: boolean;
  output_kind?: string;
  publication_blockers?: Array<{ code?: string; message?: string }>;
  publish_block_reason?: string;
  segment_count?: number;
  novel_id?: string;
  chapter_id?: string;
  script_id?: string;
  storyboard_id?: string;
  shot_id?: string;
  duration_seconds?: number;
  created_at: string;
}

interface Publication {
  id: string;
  title: string;
  status: string;
  export_url: string;
  provider: string;
  video_url?: string;
  synthesis_job_id?: string;
  metadata?: Record<string, any>;
  created_at: string;
}

export default function SynthesisPage() {
  const { toast } = useToast();
  const [videos, setVideos] = useState<VideoJob[]>([]);
  const [ttsAudios, setTtsAudios] = useState<TTSJob[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<string | null>(null);
  const [selectedAudio, setSelectedAudio] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  
  const [loadingVideos, setLoadingVideos] = useState(false);
  const [loadingAudios, setLoadingAudios] = useState(false);
  const [synthesizing, setSynthesizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // 当前合成结果
  const [currentSynthesis, setCurrentSynthesis] = useState<SynthesisJob | null>(null);
  const [history, setHistory] = useState<SynthesisJob[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedHistoryJob, setSelectedHistoryJob] = useState<SynthesisJob | null>(null);
  const [historyFilters, setHistoryFilters] = useState(createEmptyHistoryFilters);
  const historyFiltersRef = useRef(historyFilters);
  const [publications, setPublications] = useState<Publication[]>([]);
  const [publishingJobId, setPublishingJobId] = useState<string | null>(null);
  const [publishMessage, setPublishMessage] = useState<string | null>(null);

  useEffect(() => {
    loadVideos();
    loadAudios();
    loadHistory();
    loadPublications();
  }, []);

  const loadVideos = async () => {
    setLoadingVideos(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE}/video/jobs`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        // 只显示成功的视频
        const successfulVideos = (Array.isArray(data) ? data : []).filter(
          (v: VideoJob) => v.status === 'succeeded' && v.video_url
        );
        setVideos(successfulVideos);
      }
    } catch (err) {
      console.error('加载视频失败:', err);
    } finally {
      setLoadingVideos(false);
    }
  };

  const loadAudios = async () => {
    setLoadingAudios(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE}/tts/jobs`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        // 只显示成功的音频
        const successfulAudios = (Array.isArray(data) ? data : []).filter(
          (a: TTSJob) => (a.status === 'succeeded' || a.status === 'completed') && a.audio_url
        );
        setTtsAudios(successfulAudios);
      }
    } catch (err) {
      console.error('加载音频失败:', err);
    } finally {
      setLoadingAudios(false);
    }
  };

  const loadHistory = async (filters = historyFiltersRef.current) => {
    setHistoryLoading(true);
    try {
      const activeFilters = filters || historyFiltersRef.current;
      const params = Object.fromEntries(
        Object.entries(activeFilters).filter(([, value]) => String(value || '').trim())
      );
      const data = await apiClient.getSynthesisJobs({ ...params, limit: 100 });
      const jobs = Array.isArray(data) ? data : [];
      setHistory(jobs);
      if (selectedHistoryJob && !jobs.some((job) => job.id === selectedHistoryJob.id)) {
        setSelectedHistoryJob(null);
      }
    } catch (err) {
      console.error('加载历史失败:', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  const loadPublications = async () => {
    try {
      const data = await apiClient.getPublications();
      setPublications(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('加载发布记录失败:', err);
    }
  };

  const handleSynthesize = async () => {
    if (!selectedVideo || !selectedAudio) {
      toast({ title: '请选择视频和音频', description: '需要同时选择一个视频和一段音频后才能合成。', type: 'info' });
      return;
    }
    
    setSynthesizing(true);
    setError(null);
    
    try {
      const token = localStorage.getItem('auth_token');
      
      const response = await fetch(`${API_BASE}/synthesis/create`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          video_job_id: selectedVideo,
          tts_job_id: selectedAudio,
          title: title || '音视频合成'
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        setCurrentSynthesis(data);
        loadHistory();
      } else {
        const errData = await response.json();
        throw new Error(errData.detail || '合成失败');
      }
    } catch (err: any) {
      setError(err.message || '合成失败，请稍后重试');
    } finally {
      setSynthesizing(false);
    }
  };

  const downloadResult = () => {
    if (currentSynthesis?.output_url) {
      window.open(toMediaUrl(currentSynthesis.output_url), '_blank');
    }
  };

  const publishJob = async (job: SynthesisJob) => {
    setPublishingJobId(job.id);
    setPublishMessage(null);
    try {
      await apiClient.publishSynthesis(job.id, {
        title: job.title,
        visibility: 'private',
        metadata: {
          preview_url: job.preview_url,
          srt_url: job.srt_url,
          timeline_url: job.timeline_url,
          render_manifest_url: job.render_manifest_url,
          source_manifest_url: job.manifest_url,
          render_artifacts: {
            preview_url: job.preview_url,
            srt_url: job.srt_url,
            timeline_url: job.timeline_url,
            render_manifest_url: job.render_manifest_url,
            source_manifest_url: job.manifest_url,
          },
        },
      });
      setPublishMessage(`《${job.title}》已发布`);
      loadPublications();
    } catch (err: any) {
      setPublishMessage(publicationErrorMessage(err) || err?.message || '发布失败');
    } finally {
      setPublishingJobId(null);
    }
  };

  const exportJob = async (job: SynthesisJob) => {
    setPublishingJobId(job.id);
    setPublishMessage(null);
    try {
      const result = await apiClient.exportSynthesis(job.id, { format: 'mp4' });
      const url = result?.export_url || result?.download_url || result?.output_url || job.output_url;
      if (url) window.open(toMediaUrl(url), '_blank');
      setPublishMessage(`《${job.title}》已创建导出`);
      loadPublications();
    } catch (err: any) {
      setPublishMessage(publicationErrorMessage(err) || err?.message || '导出失败');
    } finally {
      setPublishingJobId(null);
    }
  };

  const revokePublication = async (publication: Publication) => {
    setPublishingJobId(publication.id);
    setPublishMessage(null);
    try {
      await apiClient.revokePublication(publication.id);
      setPublishMessage(`《${publication.title}》已撤销`);
      await loadPublications();
    } catch (err: any) {
      setPublishMessage(err?.message || '撤销失败');
    } finally {
      setPublishingJobId(null);
    }
  };

  const archivePublication = async (publication: Publication) => {
    setPublishingJobId(publication.id);
    setPublishMessage(null);
    try {
      await apiClient.deletePublication(publication.id);
      setPublishMessage(`《${publication.title}》已归档`);
      setPublications(prev => prev.filter(item => item.id !== publication.id));
    } catch (err: any) {
      setPublishMessage(err?.message || '归档失败');
    } finally {
      setPublishingJobId(null);
    }
  };

  const getVideoUrl = (id: string) => videos.find(v => v.id === id)?.video_url;
  const getAudioUrl = (id: string) => ttsAudios.find(a => a.id === id)?.audio_url;

  const updateHistoryFilter = (key: keyof typeof historyFilters, value: string) => {
    const nextFilters = { ...historyFiltersRef.current, [key]: value };
    historyFiltersRef.current = nextFilters;
    setHistoryFilters(nextFilters);
  };

  const resetHistoryFilters = () => {
    const emptyFilters = createEmptyHistoryFilters();
    historyFiltersRef.current = emptyFilters;
    setHistoryFilters(emptyFilters);
    loadHistory(emptyFilters);
  };

  const previewUrlFor = (job: SynthesisJob) => job.preview_url || job.output_url || job.video_url || '';
  const isFinalVideoUrl = (url?: string) => Boolean(url && /\.(mp4|mov|webm)($|\?)/i.test(url));
  const isPublishableJob = (job: SynthesisJob) => {
    if (typeof job.is_publishable === 'boolean') return job.is_publishable;
    if (job.output_kind === 'preview_package' || job.render_backend === 'local_artifact_package') return false;
    if (job.render_status === 'adapter_ready' || job.render_status === 'cloud_pending' || job.render_status === 'preflight_failed') return false;
    return isFinalVideoUrl(job.output_url);
  };
  const publicationBlockerText = (job: SynthesisJob) => {
    const firstBlocker = Array.isArray(job.publication_blockers) ? job.publication_blockers[0] : null;
    if (job.publish_block_reason) return job.publish_block_reason;
    if (firstBlocker?.message) return firstBlocker.message;
    if (job.output_kind === 'preview_package' || job.render_backend === 'local_artifact_package') return '当前只有本地预览包，生成真实视频文件后才能发布';
    if (job.render_status === 'adapter_ready' || job.render_status === 'cloud_pending') return '等待云渲染完成后才能发布';
    if (job.render_status === 'preflight_failed') return '渲染预检失败，修复问题后才能发布';
    return '缺少最终视频文件，暂不能发布';
  };
  const publicationErrorMessage = (err: any) => {
    const detail = err?.detail;
    if (detail?.code !== 'publication_not_ready') return '';
    const firstIssue = Array.isArray(detail.issues) ? detail.issues[0] : null;
    return firstIssue?.message || detail.message || '最终成片尚未准备好，无法发布';
  };
  const publicationArtifactLinks = (publication: Publication): RenderArtifactLinks => {
    const metadata = publication.metadata || {};
    const nestedMetadata = metadata.metadata && typeof metadata.metadata === 'object' ? metadata.metadata : {};
    const artifacts = metadata.render_artifacts && typeof metadata.render_artifacts === 'object'
      ? metadata.render_artifacts
      : nestedMetadata.render_artifacts && typeof nestedMetadata.render_artifacts === 'object'
        ? nestedMetadata.render_artifacts
        : {};
    return {
      preview_url: artifacts.preview_url || metadata.preview_url || nestedMetadata.preview_url || publication.video_url,
      srt_url: artifacts.srt_url || metadata.srt_url || nestedMetadata.srt_url,
      timeline_url: artifacts.timeline_url || metadata.timeline_url || nestedMetadata.timeline_url,
      render_manifest_url: artifacts.render_manifest_url || metadata.render_manifest_url || nestedMetadata.render_manifest_url,
      source_manifest_url: artifacts.source_manifest_url || metadata.source_manifest_url || nestedMetadata.source_manifest_url,
    };
  };
  const isHtmlPreview = (url: string) => /\.html?($|\?)/i.test(url);
  const statusText = (status: string) => {
    if (status === 'succeeded') return '成功';
    if (status === 'failed') return '失败';
    if (status === 'running') return '处理中';
    return status || '未知';
  };
  const renderStatusText = (status?: string) => {
    if (status === 'rendered') return '已渲染';
    if (status === 'ready') return '待渲染';
    if (status === 'preflight_failed') return '预检失败';
    if (status === 'adapter_ready') return '云渲染待提交';
    return status || '未渲染';
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Combine className="w-6 h-6" />
            音视频合成
          </h1>
          <p className="text-white/60 mt-1">将视频与音频合并为完整作品</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 左侧：选择源 */}
          <div className="space-y-4">
            {/* 视频选择 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Video className="w-5 h-5" />
                  选择视频
                  {selectedVideo && <CheckCircle className="w-4 h-4 text-green-400 ml-auto" />}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {loadingVideos ? (
                  <div className="text-center py-8">
                    <Loader2 className="w-8 h-8 mx-auto mb-2 animate-spin text-white/40" />
                    <p className="text-white/40">加载中…</p>
                  </div>
                ) : videos.length === 0 ? (
                  <div className="text-center py-8 text-white/40">
                    <Video className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>暂无可用视频</p>
                    <p className="text-sm">请先在视频生成页面创建视频</p>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {videos.map((video) => (
                      <div
                        key={video.id}
                        onClick={() => setSelectedVideo(video.id)}
                        className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                          selectedVideo === video.id
                            ? 'border-violet-500 bg-violet-500/10'
                            : 'border-white/10 hover:bg-white/5'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <Film className="w-5 h-5 text-violet-400" />
                          <div className="flex-1 min-w-0">
                            <div className="text-white font-medium truncate">
                              {video.title || video.prompt?.slice(0, 30) || '视频'}
                            </div>
                            <div className="text-white/60 text-sm">
                              {video.duration || 0}秒 · {new Date(video.created_at).toLocaleDateString()}
                            </div>
                          </div>
                          {selectedVideo === video.id && (
                            <CheckCircle className="w-5 h-5 text-violet-400" />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="mt-2"
                  onClick={loadVideos}
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  刷新
                </Button>
              </CardContent>
            </Card>

            {/* 音频选择 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Volume2 className="w-5 h-5" />
                  选择音频
                  {selectedAudio && <CheckCircle className="w-4 h-4 text-green-400 ml-auto" />}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {loadingAudios ? (
                  <div className="text-center py-8">
                    <Loader2 className="w-8 h-8 mx-auto mb-2 animate-spin text-white/40" />
                    <p className="text-white/40">加载中…</p>
                  </div>
                ) : ttsAudios.length === 0 ? (
                  <div className="text-center py-8 text-white/40">
                    <Volume2 className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>暂无可用音频</p>
                    <p className="text-sm">请先在TTS页面创建语音</p>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {ttsAudios.map((audio) => (
                      <div
                        key={audio.id}
                        onClick={() => setSelectedAudio(audio.id)}
                        className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                          selectedAudio === audio.id
                            ? 'border-blue-500 bg-blue-500/10'
                            : 'border-white/10 hover:bg-white/5'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <Volume2 className="w-5 h-5 text-blue-400" />
                          <div className="flex-1 min-w-0">
                            <div className="text-white font-medium truncate">
                              {audio.title || audio.text?.slice(0, 30) || '音频'}
                            </div>
                            <div className="text-white/60 text-sm">
                              {audio.duration_seconds || 0}秒 · {new Date(audio.created_at).toLocaleDateString()}
                            </div>
                          </div>
                          {selectedAudio === audio.id && (
                            <CheckCircle className="w-5 h-5 text-blue-400" />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="mt-2"
                  onClick={loadAudios}
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  刷新
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* 右侧：预览和合成 */}
          <div className="space-y-4">
            {/* 合成配置 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Settings className="w-5 h-5" />
                  合成设置
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-white/80 mb-2 block">作品标题</label>
                  <Input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="给作品起个名字（可选）"
                    className="bg-white/10 border-white/20 text-white"
                  />
                </div>
                
                {/* 预览 */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-white/5 rounded-lg">
                    <div className="text-white/60 text-sm mb-1">视频</div>
                    <div className="text-white font-medium truncate">
                      {selectedVideo 
                        ? (videos.find(v => v.id === selectedVideo)?.title || '已选择')
                        : '未选择'}
                    </div>
                  </div>
                  <div className="p-3 bg-white/5 rounded-lg">
                    <div className="text-white/60 text-sm mb-1">音频</div>
                    <div className="text-white font-medium truncate">
                      {selectedAudio 
                        ? (ttsAudios.find(a => a.id === selectedAudio)?.title || '已选择')
                        : '未选择'}
                    </div>
                  </div>
                </div>

                <Button 
                  onClick={handleSynthesize}
                  disabled={synthesizing || !selectedVideo || !selectedAudio}
                  className="w-full bg-violet-600 hover:bg-violet-700 h-12"
                >
                  {synthesizing ? (
                    <>
                      <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                      合成中...
                    </>
                  ) : (
                    <>
                      <Combine className="w-5 h-5 mr-2" />
                      开始合成
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {/* 错误提示 */}
            {error && (
              <Card className="bg-red-500/10 border-red-500/30">
                <CardContent className="p-3 flex items-center gap-2">
                  <AlertCircle className="w-5 h-5 text-red-400" />
                  <p className="text-red-400 text-sm">{error}</p>
                </CardContent>
              </Card>
            )}

            {publishMessage && (
              <Card className="bg-white/5 border-white/10">
                <CardContent className="p-3 flex items-center gap-2">
                  <AlertCircle className="w-5 h-5 text-yellow-400" />
                  <p className="text-white/70 text-sm">{publishMessage}</p>
                </CardContent>
              </Card>
            )}

            {/* 当前合成结果 */}
            {currentSynthesis && (
              <Card className="bg-white/5 border-white/10">
                <CardHeader>
                  <CardTitle className="text-white">合成结果</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-white font-medium">{currentSynthesis.title}</div>
                      <div className="text-white/60 text-sm">
                        {currentSynthesis.status === 'succeeded' ? (
                          <span className="text-green-400">合成成功</span>
                        ) : currentSynthesis.status === 'failed' ? (
                          <span className="text-red-400">合成失败</span>
                        ) : (
                          <span className="text-yellow-400">处理中…</span>
                        )}
                      </div>
                    </div>
                    {currentSynthesis.status === 'succeeded' && (
                      <div className="flex gap-2">
                        <Button variant="outline" onClick={() => publishJob(currentSynthesis)} disabled={publishingJobId === currentSynthesis.id}>
                          {publishingJobId === currentSynthesis.id ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
                          发布
                        </Button>
                        <Button variant="outline" onClick={() => exportJob(currentSynthesis)} disabled={publishingJobId === currentSynthesis.id}>
                          {publishingJobId === currentSynthesis.id ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
                          导出
                        </Button>
                        <Button onClick={downloadResult}>
                          <Download className="w-4 h-4 mr-2" />
                          下载
                        </Button>
                      </div>
                    )}
                  </div>
                  
                  {currentSynthesis.status === 'succeeded' && currentSynthesis.output_url && (
                    <video 
                      src={toMediaUrl(currentSynthesis.output_url)}
                      controls
                      className="w-full rounded-lg bg-black"
                    />
                  )}
                </CardContent>
              </Card>
            )}

            {/* 历史记录 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-white flex items-center gap-2">
                  <Clock className="w-5 h-5" />
                  合成历史
                </CardTitle>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => loadHistory()}
                  disabled={historyLoading}
                >
                  <RefreshCw className={`w-4 h-4 ${historyLoading ? 'animate-spin' : ''}`} />
                </Button>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-lg border border-white/10 bg-black/20 p-4">
                  <div className="mb-3 flex items-center gap-2 text-white font-medium">
                    <Filter className="w-4 h-4 text-violet-300" />
                    合成历史筛选
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <label className="space-y-1 text-sm text-white/70">
                      <span>小说ID</span>
                      <Input
                        aria-label="小说ID"
                        value={historyFilters.novel_id}
                        onChange={(event) => updateHistoryFilter('novel_id', event.target.value)}
                        placeholder="按小说过滤"
                        className="bg-white/10 border-white/20 text-white"
                      />
                    </label>
                    <label className="space-y-1 text-sm text-white/70">
                      <span>章节ID</span>
                      <Input
                        aria-label="章节ID"
                        value={historyFilters.chapter_id}
                        onChange={(event) => updateHistoryFilter('chapter_id', event.target.value)}
                        placeholder="按章节过滤"
                        className="bg-white/10 border-white/20 text-white"
                      />
                    </label>
                    <label className="space-y-1 text-sm text-white/70">
                      <span>剧本ID</span>
                      <Input
                        aria-label="剧本ID"
                        value={historyFilters.script_id}
                        onChange={(event) => updateHistoryFilter('script_id', event.target.value)}
                        placeholder="按剧本过滤"
                        className="bg-white/10 border-white/20 text-white"
                      />
                    </label>
                    <label className="space-y-1 text-sm text-white/70">
                      <span>分镜ID</span>
                      <Input
                        aria-label="分镜ID"
                        value={historyFilters.storyboard_id}
                        onChange={(event) => updateHistoryFilter('storyboard_id', event.target.value)}
                        placeholder="按分镜过滤"
                        className="bg-white/10 border-white/20 text-white"
                      />
                    </label>
                    <label className="space-y-1 text-sm text-white/70">
                      <span>镜头ID</span>
                      <Input
                        aria-label="镜头ID"
                        value={historyFilters.shot_id}
                        onChange={(event) => updateHistoryFilter('shot_id', event.target.value)}
                        placeholder="按镜头过滤"
                        className="bg-white/10 border-white/20 text-white"
                      />
                    </label>
                    <label className="space-y-1 text-sm text-white/70">
                      <span>任务状态</span>
                      <select
                        aria-label="任务状态"
                        value={historyFilters.status}
                        onChange={(event) => updateHistoryFilter('status', event.target.value)}
                        className="w-full rounded-md border border-white/20 bg-white/10 px-3 py-2 text-sm text-white outline-none"
                      >
                        <option value="">全部状态</option>
                        <option value="succeeded">成功</option>
                        <option value="running">处理中</option>
                        <option value="pending">排队中</option>
                        <option value="failed">失败</option>
                      </select>
                    </label>
                    <label className="space-y-1 text-sm text-white/70 md:col-span-2">
                      <span>渲染状态</span>
                      <select
                        aria-label="渲染状态"
                        value={historyFilters.render_status}
                        onChange={(event) => updateHistoryFilter('render_status', event.target.value)}
                        className="w-full rounded-md border border-white/20 bg-white/10 px-3 py-2 text-sm text-white outline-none"
                      >
                        <option value="">全部渲染状态</option>
                        <option value="rendered">已渲染</option>
                        <option value="ready">待渲染</option>
                        <option value="adapter_ready">云渲染待提交</option>
                        <option value="preflight_failed">预检失败</option>
                      </select>
                    </label>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button size="sm" onClick={() => loadHistory(historyFiltersRef.current)} disabled={historyLoading}>
                      {historyLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Filter className="w-4 h-4 mr-2" />}
                      筛选历史
                    </Button>
                    <Button size="sm" variant="outline" onClick={resetHistoryFilters} disabled={historyLoading}>
                      重置
                    </Button>
                  </div>
                </div>

                {selectedHistoryJob && (
                  <div data-testid="synthesis-history-preview" className="rounded-lg border border-violet-400/30 bg-violet-500/10 p-4 space-y-3">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="text-white font-semibold">历史预览：{selectedHistoryJob.title}</div>
                        <div className="mt-1 text-sm text-white/60">
                          {statusText(selectedHistoryJob.status)} · {renderStatusText(selectedHistoryJob.render_status)} · {selectedHistoryJob.segment_count || 0} 个片段
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {selectedHistoryJob.srt_url && (
                          <a className="inline-flex items-center rounded-md border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10" href={toMediaUrl(selectedHistoryJob.srt_url)} target="_blank" rel="noreferrer">
                            <FileText className="w-4 h-4 mr-2" />
                            字幕 SRT
                          </a>
                        )}
                        {selectedHistoryJob.timeline_url && (
                          <a className="inline-flex items-center rounded-md border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10" href={toMediaUrl(selectedHistoryJob.timeline_url)} target="_blank" rel="noreferrer">
                            <ExternalLink className="w-4 h-4 mr-2" />
                            时间线
                          </a>
                        )}
                        {selectedHistoryJob.render_manifest_url && (
                          <a className="inline-flex items-center rounded-md border border-white/20 px-3 py-2 text-sm text-white hover:bg-white/10" href={toMediaUrl(selectedHistoryJob.render_manifest_url)} target="_blank" rel="noreferrer">
                            <ExternalLink className="w-4 h-4 mr-2" />
                            渲染清单
                          </a>
                        )}
                      </div>
                    </div>
                    {previewUrlFor(selectedHistoryJob) ? (
                      isHtmlPreview(previewUrlFor(selectedHistoryJob)) ? (
                        <iframe
                          title="合成历史预览"
                          src={toMediaUrl(previewUrlFor(selectedHistoryJob))}
                          className="h-72 w-full rounded-lg border border-white/10 bg-black"
                        />
                      ) : (
                        <video
                          src={toMediaUrl(previewUrlFor(selectedHistoryJob))}
                          controls
                          className="w-full rounded-lg bg-black"
                        />
                      )
                    ) : (
                      <div className="rounded-lg border border-white/10 bg-black/30 p-6 text-center text-white/50">
                        该记录暂未生成可预览文件
                      </div>
                    )}
                  </div>
                )}

                {history.length === 0 ? (
                  <div className="text-center py-8 text-white/40">
                    <Combine className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>暂无合成记录</p>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {history.map((job) => {
                      const publishable = isPublishableJob(job);
                      return (
                      <div
                        key={job.id}
                        data-testid={`synthesis-job-row-${job.id}`}
                        className={`rounded-lg border p-3 transition-colors ${
                          selectedHistoryJob?.id === job.id
                            ? 'border-violet-400/50 bg-violet-500/10'
                            : 'border-white/10 bg-white/5 hover:bg-white/10'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-start gap-3 min-w-0">
                            <Combine className="w-5 h-5 text-violet-400 mt-1" />
                            <div className="min-w-0">
                              <div className="text-white font-medium truncate">
                                {job.title}
                              </div>
                              <div className="mt-1 text-white/60 text-sm">
                                {new Date(job.created_at).toLocaleString()} · {statusText(job.status)} · {renderStatusText(job.render_status)}
                              </div>
                              {!publishable && (
                                <div className="mt-2 rounded border border-yellow-500/25 bg-yellow-500/10 px-2 py-1 text-xs text-yellow-100">
                                  {publicationBlockerText(job)}
                                </div>
                              )}
                              <div className="mt-2 flex flex-wrap gap-2 text-xs text-white/50">
                                {job.novel_id && <span className="rounded bg-white/10 px-2 py-1">小说 {job.novel_id.slice(0, 8)}</span>}
                                {job.chapter_id && <span className="rounded bg-white/10 px-2 py-1">章节 {job.chapter_id.slice(0, 8)}</span>}
                                {job.storyboard_id && <span className="rounded bg-white/10 px-2 py-1">分镜 {job.storyboard_id.slice(0, 8)}</span>}
                                {job.shot_id && <span className="rounded bg-white/10 px-2 py-1">镜头 {job.shot_id.slice(0, 8)}</span>}
                                {job.segment_count ? <span className="rounded bg-white/10 px-2 py-1">{job.segment_count} 段</span> : null}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {job.status === 'succeeded' ? (
                              <CheckCircle className="w-5 h-5 text-green-400" />
                            ) : job.status === 'failed' ? (
                              <XCircle className="w-5 h-5 text-red-400" />
                            ) : (
                              <Loader2 className="w-5 h-5 text-yellow-400 animate-spin" />
                            )}
                            {(job.output_url || job.preview_url || job.video_url) && (
                              <Button
                                title="预览"
                                aria-label={`预览 ${job.title}`}
                                variant="ghost"
                                size="sm"
                                onClick={() => setSelectedHistoryJob(job)}
                              >
                                <Eye className="w-4 h-4" />
                              </Button>
                            )}
                            {publishable && job.output_url && (
                              <>
                                <Button
                                  title="发布"
                                  aria-label="发布"
                                  variant="ghost"
                                  size="sm"
                                  disabled={publishingJobId === job.id}
                                  onClick={() => publishJob(job)}
                                >
                                  {publishingJobId === job.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                                </Button>
                                <Button
                                  title="导出"
                                  aria-label="导出"
                                  variant="ghost"
                                  size="sm"
                                  disabled={publishingJobId === job.id}
                                  onClick={() => exportJob(job)}
                                >
                                  <Download className="w-4 h-4" />
                                </Button>
                              </>
                            )}
                            {job.manifest_url && (
                              <Button
                                title="打开成片清单"
                                variant="ghost"
                                size="sm"
                                onClick={() => window.open(toMediaUrl(job.manifest_url), '_blank')}
                              >
                                <ExternalLink className="w-4 h-4" />
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="bg-white/5 border-white/10" data-testid="publication-history">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-white flex items-center gap-2">
                  <Download className="w-5 h-5" />
                  发布记录
                </CardTitle>
                <Button variant="ghost" size="sm" onClick={loadPublications}>
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </CardHeader>
              <CardContent>
                {publications.length === 0 ? (
                  <div className="text-center py-8 text-white/40">
                    <Download className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>暂无发布记录</p>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-72 overflow-y-auto">
                    {publications.map((publication) => {
                      const artifactLinks = publicationArtifactLinks(publication);
                      return (
                        <div
                          key={publication.id}
                          data-testid={`publication-row-${publication.id}`}
                          className="flex flex-col gap-3 p-3 bg-white/5 rounded-lg sm:flex-row sm:items-center sm:justify-between"
                        >
                          <div className="min-w-0 flex-1">
                            <div className="text-white font-medium truncate">{publication.title}</div>
                            <div className="text-white/50 text-sm">
                              {publication.provider} · {publication.status} · {new Date(publication.created_at).toLocaleString()}
                            </div>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {artifactLinks.preview_url && (
                                <a className="inline-flex items-center rounded-md border border-white/20 px-2 py-1 text-xs text-white hover:bg-white/10" href={toMediaUrl(artifactLinks.preview_url)} target="_blank" rel="noreferrer">
                                  <Eye className="w-3.5 h-3.5 mr-1" />
                                  发布预览
                                </a>
                              )}
                              {artifactLinks.srt_url && (
                                <a className="inline-flex items-center rounded-md border border-white/20 px-2 py-1 text-xs text-white hover:bg-white/10" href={toMediaUrl(artifactLinks.srt_url)} target="_blank" rel="noreferrer">
                                  <FileText className="w-3.5 h-3.5 mr-1" />
                                  发布字幕 SRT
                                </a>
                              )}
                              {artifactLinks.timeline_url && (
                                <a className="inline-flex items-center rounded-md border border-white/20 px-2 py-1 text-xs text-white hover:bg-white/10" href={toMediaUrl(artifactLinks.timeline_url)} target="_blank" rel="noreferrer">
                                  <ExternalLink className="w-3.5 h-3.5 mr-1" />
                                  发布时间线
                                </a>
                              )}
                              {artifactLinks.render_manifest_url && (
                                <a className="inline-flex items-center rounded-md border border-white/20 px-2 py-1 text-xs text-white hover:bg-white/10" href={toMediaUrl(artifactLinks.render_manifest_url)} target="_blank" rel="noreferrer">
                                  <ExternalLink className="w-3.5 h-3.5 mr-1" />
                                  发布渲染清单
                                </a>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2 self-end sm:self-auto">
                            <Button title="打开发布文件" variant="ghost" size="sm" disabled={publishingJobId === publication.id} onClick={() => window.open(toMediaUrl(publication.export_url), '_blank')}>
                              <Download className="w-4 h-4" />
                            </Button>
                            <Button title="撤销发布" variant="ghost" size="sm" disabled={publishingJobId === publication.id || publication.status === 'revoked'} onClick={() => revokePublication(publication)}>
                              <XCircle className="w-4 h-4" />
                            </Button>
                            <Button title="归档发布记录" variant="ghost" size="sm" className="text-red-300 hover:text-red-200" disabled={publishingJobId === publication.id} onClick={() => archivePublication(publication)}>
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
