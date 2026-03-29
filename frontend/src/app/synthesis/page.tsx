'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/select';
import { MainLayout } from '@/components/layout/main-layout';
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
  Film
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
  text_content?: string;
  status: string;
  audio_url?: string;
  duration?: number;
  created_at: string;
}

interface SynthesisJob {
  id: string;
  title: string;
  status: string;
  progress: number;
  output_url?: string;
  duration?: number;
  created_at: string;
}

export default function SynthesisPage() {
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

  useEffect(() => {
    loadVideos();
    loadAudios();
    loadHistory();
  }, []);

  const loadVideos = async () => {
    setLoadingVideos(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE}/api/v1/video/jobs`, {
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
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE}/api/v1/tts/jobs`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        // 只显示成功的音频
        const successfulAudios = (Array.isArray(data) ? data : []).filter(
          (a: TTSJob) => a.status === 'succeeded' && a.audio_url
        );
        setTtsAudios(successfulAudios);
      }
    } catch (err) {
      console.error('加载音频失败:', err);
    } finally {
      setLoadingAudios(false);
    }
  };

  const loadHistory = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE}/api/v1/synthesis/jobs`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        setHistory(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      console.error('加载历史失败:', err);
    }
  };

  const handleSynthesize = async () => {
    if (!selectedVideo || !selectedAudio) {
      alert('请选择视频和音频');
      return;
    }
    
    setSynthesizing(true);
    setError(null);
    
    try {
      const token = localStorage.getItem('token');
      
      const response = await fetch(`${API_BASE}/api/v1/synthesis/create`, {
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
      window.open(currentSynthesis.output_url, '_blank');
    }
  };

  const getVideoUrl = (id: string) => videos.find(v => v.id === id)?.video_url;
  const getAudioUrl = (id: string) => ttsAudios.find(a => a.id === id)?.audio_url;

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
                    <p className="text-white/40">加载中...</p>
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
                        className={`p-3 rounded-lg border cursor-pointer transition-all ${
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
                    <p className="text-white/40">加载中...</p>
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
                        className={`p-3 rounded-lg border cursor-pointer transition-all ${
                          selectedAudio === audio.id
                            ? 'border-blue-500 bg-blue-500/10'
                            : 'border-white/10 hover:bg-white/5'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <Volume2 className="w-5 h-5 text-blue-400" />
                          <div className="flex-1 min-w-0">
                            <div className="text-white font-medium truncate">
                              {audio.title || audio.text_content?.slice(0, 30) || '音频'}
                            </div>
                            <div className="text-white/60 text-sm">
                              {audio.duration || 0}秒 · {new Date(audio.created_at).toLocaleDateString()}
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
                          <span className="text-yellow-400">处理中...</span>
                        )}
                      </div>
                    </div>
                    {currentSynthesis.status === 'succeeded' && (
                      <Button onClick={downloadResult}>
                        <Download className="w-4 h-4 mr-2" />
                        下载
                      </Button>
                    )}
                  </div>
                  
                  {currentSynthesis.status === 'succeeded' && currentSynthesis.output_url && (
                    <video 
                      src={currentSynthesis.output_url}
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
                  onClick={loadHistory}
                >
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </CardHeader>
              <CardContent>
                {history.length === 0 ? (
                  <div className="text-center py-8 text-white/40">
                    <Combine className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>暂无合成记录</p>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {history.map((job) => (
                      <div
                        key={job.id}
                        className="flex items-center justify-between p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors"
                      >
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <Combine className="w-5 h-5 text-violet-400" />
                          <div className="min-w-0 flex-1">
                            <div className="text-white font-medium truncate">
                              {job.title}
                            </div>
                            <div className="text-white/60 text-sm">
                              {new Date(job.created_at).toLocaleString()}
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
                          {job.output_url && (
                            <Button 
                              variant="ghost" 
                              size="sm"
                              onClick={() => window.open(job.output_url, '_blank')}
                            >
                              <Download className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
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
