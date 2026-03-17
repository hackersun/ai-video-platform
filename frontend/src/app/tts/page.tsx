'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import { Textarea } from '@/components/ui/textarea';
import { Slider } from '@/components/ui/slider';
import { 
  Mic, 
  Play, 
  Pause,
  Square,
  Download,
  Volume2,
  Settings,
  Clock,
  User,
  Sparkles,
  Loader2,
  CheckCircle,
  History,
  Star,
  ChevronRight
} from 'lucide-react';

// 语音角色
const VOICE_ROLES = [
  { id: 'male-young', name: '年轻男声', style: '活力' },
  { id: 'male-middle', name: '中年男声', style: '成熟' },
  { id: 'male-elder', name: '老年男声', style: '沉稳' },
  { id: 'female-young', name: '年轻女声', style: '活泼' },
  { id: 'female-middle', name: '中年女声', style: '温柔' },
  { id: 'female-elder', name: '老年女声', style: '慈祥' },
];

// 历史记录
const MOCK_HISTORY = [
  { id: '1', text: '今天天气真好，我们去郊游吧', voice: '年轻女声', duration: '0:05', createdAt: '2024-03-15 14:30' },
  { id: '2', text: '科技创新改变未来', voice: '中年男声', duration: '0:03', createdAt: '2024-03-15 14:25' },
  { id: '3', text: '人工智能引领新时代', voice: '年轻男声', duration: '0:04', createdAt: '2024-03-15 14:20' },
];

export default function TTSPage() {
  const [text, setText] = useState('');
  const [selectedVoice, setSelectedVoice] = useState('female-young');
  const [speed, setSpeed] = useState(1.0);
  const [pitch, setPitch] = useState(0);
  const [volume, setVolume] = useState(100);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedAudio, setGeneratedAudio] = useState<string | null>(null);

  // 生成语音
  const handleGenerate = async () => {
    if (!text.trim()) {
      alert('请输入要转换的文本');
      return;
    }

    setIsGenerating(true);
    try {
      // 模拟生成
      await new Promise(resolve => setTimeout(resolve, 2000));
      setGeneratedAudio('mock-audio-url');
      alert('语音生成成功！');
    } catch (error) {
      console.error('生成失败:', error);
      alert('生成失败，请重试');
    } finally {
      setIsGenerating(false);
    }
  };

  // 播放/暂停
  const handlePlayPause = () => {
    setIsPlaying(!isPlaying);
  };

  // 停止
  const handleStop = () => {
    setIsPlaying(false);
  };

  // 下载
  const handleDownload = () => {
    alert('开始下载音频文件');
  };

  // 播放历史记录
  const playHistory = (item: typeof MOCK_HISTORY[0]) => {
    setText(item.text);
    setIsPlaying(true);
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div>
          <h1 className="text-3xl font-bold text-white">语音合成</h1>
          <p className="text-white/60 mt-1">将文本转换为自然语音</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 主要编辑区 */}
          <div className="lg:col-span-2 space-y-6">
            {/* 文本输入 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Mic className="w-5 h-5 text-amber-400" />
                    文本输入
                  </div>
                  <Button 
                    variant="outline" 
                    size="sm"
                    className="border-violet-500/50 text-violet-400 hover:bg-violet-600/20"
                  >
                    <Sparkles className="w-4 h-4 mr-2" />
                    AI 优化
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Textarea
                  placeholder="请输入要转换为语音的文本..."
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={6}
                  className="bg-white/5 border-white/10 text-white placeholder:text-white/40 resize-none"
                />
                <div className="flex justify-between mt-2 text-sm text-white/40">
                  <span>当前 {text.length} 字符</span>
                  <span>预计时长约 {Math.ceil(text.length / 200)} 秒</span>
                </div>
              </CardContent>
            </Card>

            {/* 声音设置 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Settings className="w-5 h-5 text-blue-400" />
                  声音设置
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* 声音角色 */}
                <div>
                  <label className="text-sm text-white/60 mb-3 block">声音角色</label>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {VOICE_ROLES.map((voice) => (
                      <div
                        key={voice.id}
                        onClick={() => setSelectedVoice(voice.id)}
                        className={`p-3 rounded-lg border cursor-pointer transition-all ${
                          selectedVoice === voice.id
                            ? 'border-amber-500 bg-amber-500/10'
                            : 'border-white/10 hover:border-white/30'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-white font-medium">{voice.name}</span>
                          {selectedVoice === voice.id && (
                            <CheckCircle className="w-4 h-4 text-amber-400" />
                          )}
                        </div>
                        <div className="text-sm text-white/40 mt-1">{voice.style}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 语速 */}
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-sm text-white/60">语速</label>
                    <span className="text-sm text-white">{speed.toFixed(1)}x</span>
                  </div>
                  <Slider
                    value={[speed]}
                    onValueChange={([v]) => setSpeed(v)}
                    min={0.5}
                    max={2.0}
                    step={0.1}
                    className="py-2"
                  />
                  <div className="flex justify-between text-xs text-white/40">
                    <span>0.5x</span>
                    <span>1.0x</span>
                    <span>2.0x</span>
                  </div>
                </div>

                {/* 音调 */}
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-sm text-white/60">音调</label>
                    <span className="text-sm text-white">{pitch > 0 ? `+${pitch}` : pitch}</span>
                  </div>
                  <Slider
                    value={[pitch]}
                    onValueChange={([v]) => setPitch(v)}
                    min={-12}
                    max={12}
                    step={1}
                    className="py-2"
                  />
                  <div className="flex justify-between text-xs text-white/40">
                    <span>-12</span>
                    <span>0</span>
                    <span>+12</span>
                  </div>
                </div>

                {/* 音量 */}
                <div>
                  <div className="flex justify-between mb-2">
                    <label className="text-sm text-white/60">音量</label>
                    <span className="text-sm text-white">{volume}%</span>
                  </div>
                  <Slider
                    value={[volume]}
                    onValueChange={([v]) => setVolume(v)}
                    min={0}
                    max={100}
                    step={1}
                    className="py-2"
                  />
                </div>
              </CardContent>
            </Card>

            {/* 预览和生成 */}
            <Card className="bg-white/5 border-white/10">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={handlePlayPause}
                      disabled={!generatedAudio && !text}
                      className="border-white/20 text-white"
                    >
                      {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
                    </Button>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={handleStop}
                      disabled={!isPlaying}
                      className="border-white/20 text-white"
                    >
                      <Square className="w-5 h-5" />
                    </Button>
                    <div className="text-white/60">
                      {isPlaying ? '正在播放...' : generatedAudio ? '准备就绪' : '输入文本后点击生成'}
                    </div>
                  </div>
                  <div className="flex gap-3">
                    <Button
                      variant="outline"
                      onClick={handleDownload}
                      disabled={!generatedAudio}
                      className="border-white/20 text-white"
                    >
                      <Download className="w-4 h-4 mr-2" />
                      下载
                    </Button>
                    <Button
                      onClick={handleGenerate}
                      disabled={isGenerating || !text}
                      className="bg-amber-600 hover:bg-amber-700"
                    >
                      {isGenerating ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          生成中...
                        </>
                      ) : (
                        <>
                          <Mic className="w-4 h-4 mr-2" />
                          生成语音
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 侧边栏 */}
          <div className="space-y-6">
            {/* 最近使用 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <History className="w-5 h-5 text-green-400" />
                  最近使用
                </CardTitle>
              </CardHeader>
              <CardContent>
                {MOCK_HISTORY.length > 0 ? (
                  <div className="space-y-2">
                    {MOCK_HISTORY.map((item) => (
                      <div
                        key={item.id}
                        onClick={() => playHistory(item)}
                        className="p-3 rounded-lg bg-white/5 hover:bg-white/10 cursor-pointer transition-colors"
                      >
                        <div className="text-white text-sm truncate">{item.text}</div>
                        <div className="flex items-center gap-2 mt-1 text-xs text-white/40">
                          <span>{item.voice}</span>
                          <span>·</span>
                          <span>{item.duration}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-white/40 text-center py-4">暂无历史记录</p>
                )}
              </CardContent>
            </Card>

            {/* 快捷示例 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Star className="w-5 h-5 text-yellow-400" />
                  快捷示例
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {[
                    '欢迎来到AI视频创作平台',
                    '今天天气晴朗，适合外出游玩',
                    '科技创新引领未来发展'
                  ].map((sample, i) => (
                    <div
                      key={i}
                      onClick={() => setText(sample)}
                      className="p-2 rounded bg-white/5 hover:bg-white/10 cursor-pointer text-sm text-white/70 transition-colors"
                    >
                      {sample}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* 使用提示 */}
            <Card className="bg-blue-600/10 border-blue-500/30">
              <CardContent className="p-4">
                <h4 className="font-medium text-blue-300 mb-2">💡 使用技巧</h4>
                <ul className="text-sm text-white/60 space-y-1">
                  <li>• 建议单次输入不超过500字</li>
                  <li>• 适当添加标点符号改善停顿</li>
                  <li>• 使用AI优化功能改善文本</li>
                  <li>• 可调节音调模拟不同情绪</li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}