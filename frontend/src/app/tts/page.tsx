'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import { MainLayout } from '@/components/layout/main-layout';
import { 
  Volume2, 
  Play, 
  Pause, 
  Download, 
  Loader2,
  AlertCircle,
  Copy,
  RefreshCw,
  Clock,
  Settings
} from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// TTS提供商配置
const TTS_PROVIDERS = [
  { id: 'volcano', name: '火山引擎', icon: '🔥', description: '豆包语音合成' },
  { id: 'azure', name: 'Azure TTS', icon: '☁️', description: '微软Azure语音服务' },
];

interface TTSJob {
  id: string;
  title: string;
  text_content: string;
  voice_model: string;
  status: string;
  audio_url?: string;
  duration?: number;
  created_at: string;
}

export default function TTSPage() {
  const [selectedProvider, setSelectedProvider] = useState('volcano');
  const [text, setText] = useState('');
  const [voiceSpeed, setVoiceSpeed] = useState(1.0);
  const [voicePitch, setVoicePitch] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [currentAudio, setCurrentAudio] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // 历史记录
  const [history, setHistory] = useState<TTSJob[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // 页面加载时获取历史记录
  useEffect(() => {
    loadHistory();
  }, []);

  const handleGenerate = async () => {
    if (!text.trim()) {
      alert('请输入要转换的文本');
      return;
    }
    
    setGenerating(true);
    setError(null);
    
    try {
      const token = localStorage.getItem('token');
      
      // 调用TTS生成API
      const response = await fetch(`${API_BASE}/api/v1/tts/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          text_content: text,
          voice_model: 'default',
          api_provider: selectedProvider,
          speed: voiceSpeed,
          pitch: voicePitch
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        setCurrentAudio(data.audio_url);
        loadHistory();
      } else {
        const errData = await response.json();
        throw new Error(errData.detail || '生成失败');
      }
    } catch (err: any) {
      setError(err.message || '生成失败，请稍后重试');
    } finally {
      setGenerating(false);
    }
  };

  const loadHistory = async () => {
    setLoadingHistory(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_BASE}/api/v1/tts/jobs`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        setHistory(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      console.error('加载历史失败:', err);
    } finally {
      setLoadingHistory(false);
    }
  };

  const togglePlayback = () => {
    if (!currentAudio) return;
    
    // 简单的播放/暂停逻辑
    setPlaying(!playing);
  };

  const downloadAudio = () => {
    if (currentAudio) {
      window.open(currentAudio, '_blank');
    }
  };

  const copyText = () => {
    navigator.clipboard.writeText(text);
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Volume2 className="w-6 h-6" />
            语音合成 (TTS)
          </h1>
          <p className="text-white/60 mt-1">将文本转换为自然语音</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧：TTS配置 */}
          <div className="lg:col-span-1 space-y-4">
            {/* 提供商选择 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Settings className="w-5 h-5" />
                  提供商
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {TTS_PROVIDERS.map((provider) => (
                  <div
                    key={provider.id}
                    onClick={() => setSelectedProvider(provider.id)}
                    className={`p-4 rounded-lg border cursor-pointer transition-all ${
                      selectedProvider === provider.id
                        ? 'border-violet-500 bg-violet-500/10'
                        : 'border-white/10'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{provider.icon}</span>
                      <div>
                        <div className="text-white font-medium">{provider.name}</div>
                        <div className="text-white/60 text-sm">{provider.description}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* 参数配置 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white">语音参数</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* 语速 */}
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-white/80">语速</label>
                    <span className="text-white">{voiceSpeed}x</span>
                  </div>
                  <Slider
                    value={[voiceSpeed * 10]}
                    onValueChange={(v) => setVoiceSpeed(v[0] / 10)}
                    min={5}
                    max={20}
                    step={1}
                    className="w-full"
                  />
                  <div className="flex justify-between text-white/40 text-xs mt-1">
                    <span>0.5x</span>
                    <span>2.0x</span>
                  </div>
                </div>

                {/* 音调 */}
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-white/80">音调</label>
                    <span className="text-white">{voicePitch > 0 ? '+' : ''}{voicePitch}</span>
                  </div>
                  <Slider
                    value={[voicePitch + 50]}
                    onValueChange={(v) => setVoicePitch(v[0] - 50)}
                    min={0}
                    max={100}
                    step={1}
                    className="w-full"
                  />
                  <div className="flex justify-between text-white/40 text-xs mt-1">
                    <span>低沉</span>
                    <span>高亢</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 右侧：文本输入和预览 */}
          <div className="lg:col-span-2 space-y-4">
            {/* 文本输入 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-white">文本内容</CardTitle>
                <Button variant="ghost" size="sm" onClick={copyText}>
                  <Copy className="w-4 h-4 mr-2" />
                  复制
                </Button>
              </CardHeader>
              <CardContent>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="输入要转换为语音的文本..."
                  disabled={generating}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder:text-white/40 min-h-[200px] resize-none"
                />
                <div className="flex justify-between items-center mt-2">
                  <span className="text-white/40 text-sm">
                    {text.length} 字符
                  </span>
                  <Button 
                    onClick={handleGenerate}
                    disabled={generating || !text.trim()}
                    className="bg-violet-600 hover:bg-violet-700"
                  >
                    {generating && <Loader2 className="w-5 h-5 mr-2 animate-spin" />}
                    生成语音
                  </Button>
                </div>
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

            {/* 音频预览 */}
            {currentAudio && (
              <Card className="bg-white/5 border-white/10">
                <CardHeader>
                  <CardTitle className="text-white">音频预览</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-4">
                    <Button
                      onClick={togglePlayback}
                      className="w-12 h-12 rounded-full bg-violet-600 hover:bg-violet-700"
                    >
                      {playing ? (
                        <Pause className="w-6 h-6" />
                      ) : (
                        <Play className="w-6 h-6 ml-1" />
                      )}
                    </Button>
                    
                    {/* 简易音频波形（占位） */}
                    <div className="flex-1 h-12 bg-white/10 rounded flex items-center justify-center">
                      <span className="text-white/60 text-sm">
                        {playing ? '播放中...' : '点击播放预览'}
                      </span>
                    </div>
                    
                    <Button variant="outline" onClick={downloadAudio}>
                      <Download className="w-4 h-4 mr-2" />
                      下载
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* 历史记录 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-white flex items-center gap-2">
                  <Clock className="w-5 h-5" />
                  生成历史
                </CardTitle>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={loadHistory}
                  disabled={loadingHistory}
                >
                  <RefreshCw className={`w-4 h-4 ${loadingHistory ? 'animate-spin' : ''}`} />
                </Button>
              </CardHeader>
              <CardContent>
                {loadingHistory && history.length === 0 ? (
                  <div className="text-center py-8">
                    <Loader2 className="w-8 h-8 mx-auto mb-2 animate-spin text-white/40" />
                    <p className="text-white/40">加载中...</p>
                  </div>
                ) : history.length > 0 ? (
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {history.map((job) => (
                      <div
                        key={job.id}
                        className="flex items-center justify-between p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors"
                      >
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <Volume2 className="w-5 h-5 text-violet-400 flex-shrink-0" />
                          <div className="min-w-0 flex-1">
                            <div className="text-white font-medium truncate">
                              {job.title || job.text_content?.slice(0, 30) || 'TTS音频'}
                            </div>
                            <div className="text-white/60 text-sm flex items-center gap-2">
                              <span>{new Date(job.created_at).toLocaleString()}</span>
                              {job.duration && <span>{job.duration}秒</span>}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <span className={`px-2 py-1 text-xs rounded ${
                            job.status === 'succeeded' 
                              ? 'bg-green-500/20 text-green-400' 
                              : job.status === 'failed'
                              ? 'bg-red-500/20 text-red-400'
                              : 'bg-yellow-500/20 text-yellow-400'
                          }`}>
                            {job.status === 'succeeded' ? '完成' : job.status === 'failed' ? '失败' : '处理中'}
                          </span>
                          {job.audio_url && (
                            <Button 
                              variant="ghost" 
                              size="sm"
                              onClick={() => setCurrentAudio(job.audio_url!)}
                            >
                              <Play className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-white/40">
                    <Volume2 className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>暂无生成历史</p>
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
