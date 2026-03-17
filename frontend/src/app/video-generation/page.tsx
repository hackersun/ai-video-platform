'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import { MainLayout } from '@/components/layout/main-layout';
import { 
  Video, 
  Play, 
  Pause,
  Settings,
  Clock,
  Film,
  Sparkles,
  Wand2,
  ChevronRight,
  Loader2,
  CheckCircle,
  AlertCircle,
  Image as ImageIcon,
  Music
} from 'lucide-react';

// 视频生成状态
type GenerationStatus = 'idle' | 'generating' | 'completed' | 'error';

// 提供商配置
const PROVIDERS = [
  { id: 'volcano', name: '火山引擎', icon: '🔥', cost: '50分/秒' },
  { id: 'runway', name: 'Runway', icon: '🎬', cost: '$0.20/秒' },
];

export default function VideoGenerationPage() {
  const [selectedProvider, setSelectedProvider] = useState('volcano');
  const [status, setStatus] = useState<GenerationStatus>('idle');
  const [progress, setProgress] = useState(0);
  
  // 参数配置
  const [duration, setDuration] = useState(4);
  const [fps, setFps] = useState(24);
  const [resolution, setResolution] = useState('1080p');
  const [motionStrength, setMotionStrength] = useState(50);
  
  // 模拟生成
  const handleGenerate = async () => {
    setStatus('generating');
    setProgress(0);
    
    // 模拟进度
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setStatus('completed');
          return 100;
        }
        return prev + 10;
      });
    }, 500);
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
            {/* 提供商选择 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Settings className="w-5 h-5" />
                  选择提供商
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {PROVIDERS.map((provider) => (
                  <div
                    key={provider.id}
                    onClick={() => setSelectedProvider(provider.id)}
                    className={`p-4 rounded-lg border cursor-pointer transition-all ${
                      selectedProvider === provider.id
                        ? 'border-violet-500 bg-violet-500/10'
                        : 'border-white/10 hover:border-white/20'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">{provider.icon}</span>
                        <div>
                          <div className="text-white font-medium">
                            {provider.name}
                          </div>
                          <div className="text-white/60 text-sm">
                            {provider.cost}
                          </div>
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
                {/* 时长 */}
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-white/80">时长</label>
                    <span className="text-white">{duration}秒</span>
                  </div>
                  <Slider
                    value={[duration]}
                    onValueChange={(v) => setDuration(v[0])}
                    min={2}
                    max={10}
                    step={1}
                    className="w-full"
                  />
                  <div className="flex justify-between text-white/40 text-xs mt-1">
                    <span>2s</span>
                    <span>10s</span>
                  </div>
                </div>

                {/* 帧率 */}
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-white/80">帧率</label>
                    <span className="text-white">{fps}fps</span>
                  </div>
                  <div className="flex gap-2">
                    {[24, 30, 60].map((f) => (
                      <Button
                        key={f}
                        variant={fps === f ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setFps(f)}
                        className={fps === f ? 'bg-violet-600' : 'border-white/10'}
                      >
                        {f}fps
                      </Button>
                    ))}
                  </div>
                </div>

                {/* 分辨率 */}
                <div>
                  <label className="text-white/80 mb-2 block">分辨率</label>
                  <div className="flex gap-2">
                    {['720p', '1080p', '4K'].map((res) => (
                      <Button
                        key={res}
                        variant={resolution === res ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setResolution(res)}
                        className={resolution === res ? 'bg-violet-600' : 'border-white/10'}
                      >
                        {res}
                      </Button>
                    ))}
                  </div>
                </div>

                {/* 运动强度 */}
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-white/80">运动强度</label>
                    <span className="text-white">{motionStrength}%</span>
                  </div>
                  <Slider
                    value={[motionStrength]}
                    onValueChange={(v) => setMotionStrength(v[0])}
                    min={0}
                    max={100}
                    step={10}
                    className="w-full"
                  />
                  <div className="flex justify-between text-white/40 text-xs mt-1">
                    <span>静态</span>
                    <span>动态</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* 生成按钮 */}
            <Button
              onClick={handleGenerate}
              disabled={status === 'generating'}
              className="w-full bg-violet-600 hover:bg-violet-700 h-12"
            >
              {status === 'generating' ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  生成中 {progress}%
                </>
              ) : status === 'completed' ? (
                <>
                  <CheckCircle className="w-5 h-5 mr-2" />
                  生成完成
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5 mr-2" />
                  开始生成
                </>
              )}
            </Button>
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
                      <p>点击"开始生成"创建视频</p>
                    </div>
                  )}
                  
                  {status === 'generating' && (
                    <div className="text-center">
                      <Loader2 className="w-16 h-16 mx-auto mb-4 text-violet-400 animate-spin" />
                      <p className="text-white">正在生成视频...</p>
                      <p className="text-white/60 text-sm mt-2">{progress}%</p>
                      
                      {/* 进度条 */}
                      <div className="w-64 h-2 bg-white/10 rounded-full mt-4 mx-auto">
                        <div 
                          className="h-full bg-violet-500 rounded-full transition-all"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                    </div>
                  )}
                  
                  {status === 'completed' && (
                    <div className="text-center">
                      <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-green-500/20 flex items-center justify-center">
                        <CheckCircle className="w-10 h-10 text-green-400" />
                      </div>
                      <p className="text-white text-lg">视频生成完成！</p>
                      <div className="flex gap-2 mt-4 justify-center">
                        <Button>
                          <Play className="w-4 h-4 mr-2" />
                          播放
                        </Button>
                        <Button variant="outline">
                          下载
                        </Button>
                      </div>
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
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {[
                    { id: 1, name: '修仙之路第一集', status: 'completed', time: '2分钟前' },
                    { id: 2, name: '角色介绍视频', status: 'completed', time: '1小时前' },
                  ].map((video) => (
                    <div
                      key={video.id}
                      className="flex items-center justify-between p-3 rounded-lg bg-white/5"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded bg-violet-500/20 flex items-center justify-center">
                          <Video className="w-6 h-6 text-violet-400" />
                        </div>
                        <div>
                          <div className="text-white font-medium">{video.name}</div>
                          <div className="text-white/60 text-sm">{video.time}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-1 text-xs bg-green-500/20 text-green-400 rounded">
                          已完成
                        </span>
                        <Button variant="ghost" size="sm">
                          <ChevronRight className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
