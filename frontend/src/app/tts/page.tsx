'use client';

import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import { useToast } from '@/components/ui/toast';
import {
  Volume2, Play, Pause, Download, Loader2, AlertCircle,
  Copy, RefreshCw, Clock, Settings, User, ChevronRight, BookOpen, CheckCircle
} from 'lucide-react';
import Link from 'next/link';
import { fetchWithAuth } from '@/lib/fetch-with-auth';
import {
  getConfigsByCapability,
  getDefaultConfigForCapability,
  modelStatusClass,
  modelStatusLabel,
  type SavedModelConfig,
} from '@/lib/model-configs';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// MiniMax 音色列表
const MINIMAX_VOICES = [
  { id: 'female-shaonj', label: '少女音', gender: '女' },
  { id: 'female-tianmei', label: '甜美音', gender: '女' },
  { id: 'male-yunshu', label: '云书（男）', gender: '男' },
  { id: 'male-baba', label: '爸爸（男）', gender: '男' },
  { id: 'male-john', label: 'John（男）', gender: '男' },
  { id: 'male-yunting', label: '云庭（男）', gender: '男' },
  { id: 'male-znliang', label: '知宁（男）', gender: '男' },
];

// 火山引擎音色
const VOLCANO_VOICES = [
  { id: 'female_nvsheng', label: '女声（nvsheng）', gender: '女' },
  { id: 'female_tianmei', label: '甜美女声', gender: '女' },
  { id: 'male_jiaqi', label: '男声嘉琪', gender: '男' },
  { id: 'male_zhichang', label: '职场男声', gender: '男' },
  { id: 'male_dashu', label: '大树（旁白）', gender: '男' },
];

interface Novel { id: string; title: string; }
interface Chapter { id: string; title: string; novel_id: string; }
interface Script { id: string; title: string; novel_id?: string; chapter_id?: string; extra_data?: any; }
interface Storyboard { id: string; title: string; script_id: string; }
interface Shot {
  id: string; shot_number: number; prompt: string; dialogue?: string;
  character_refs?: any[]; storyboard_id: string;
}
interface TTSJob {
  id: string; title?: string; text?: string; voice?: string;
  api_provider?: string; status: string; progress: number;
  audio_url?: string; duration_seconds?: number; error_message?: string;
  extra_data?: any; created_at: string;
  shot_id?: string; novel_id?: string; character_id?: string;
}

interface TTSSegment {
  character: string; text: string; voice: string;
  audio_url?: string; duration?: number; error?: string;
}

export default function TTSPage() {
  const { toast } = useToast();
  const [selectedProvider, setSelectedProvider] = useState('minimax');
  const [llmConfigs, setLlmConfigs] = useState<SavedModelConfig[]>([]);
  const [selectedModelConfigId, setSelectedModelConfigId] = useState('');
  const [selectedVoice, setSelectedVoice] = useState('female-shaonj');
  const [text, setText] = useState('');
  const [voiceSpeed, setVoiceSpeed] = useState(1.0);
  const [generating, setGenerating] = useState(false);
  const [currentAudio, setCurrentAudio] = useState<string | null>(null);
  const [currentSegments, setCurrentSegments] = useState<TTSSegment[]>([]);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<TTSJob[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // 创作链路
  const [novels, setNovels] = useState<Novel[]>([]);
  const [selectedNovel, setSelectedNovel] = useState('');
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedChapter, setSelectedChapter] = useState('');
  const [scripts, setScripts] = useState<Script[]>([]);
  const [selectedScript, setSelectedScript] = useState('');
  const [storyboards, setStoryboards] = useState<Storyboard[]>([]);
  const [selectedStoryboard, setSelectedStoryboard] = useState('');
  const [shots, setShots] = useState<Shot[]>([]);
  const [selectedShot, setSelectedShot] = useState('');

  const [loadingChain, setLoadingChain] = useState(false);

  // 音色列表
  const voiceList = selectedProvider === 'minimax' ? MINIMAX_VOICES : VOLCANO_VOICES;
  const ttsConfigs = getConfigsByCapability(llmConfigs, 'audio');
  const selectedTTSConfig = ttsConfigs.find(config => config.id === selectedModelConfigId);

  // 加载小说列表
  useEffect(() => {
    loadNovels();
    loadHistory();
    loadLLMConfigs();
  }, []);

  useEffect(() => {
    if (ttsConfigs.length === 0 || selectedModelConfigId) return;
    const defaultConfig = getDefaultConfigForCapability(llmConfigs, 'audio');
    if (defaultConfig) {
      setSelectedModelConfigId(defaultConfig.id);
      setSelectedProvider(defaultConfig.provider_id);
    }
  }, [llmConfigs, selectedModelConfigId]);

  // 小说变化 → 加载章节
  useEffect(() => {
    if (selectedNovel) {
      loadChapters(selectedNovel);
      setSelectedChapter(''); setScripts([]); setSelectedScript('');
      setStoryboards([]); setSelectedStoryboard(''); setShots([]); setSelectedShot('');
    }
  }, [selectedNovel]);

  // 章节变化 → 加载剧本
  useEffect(() => {
    if (selectedChapter) {
      loadScripts(selectedChapter);
      setSelectedScript(''); setStoryboards([]); setSelectedStoryboard(''); setShots([]); setSelectedShot('');
    } else {
      setScripts([]); setSelectedScript('');
      setStoryboards([]); setSelectedStoryboard(''); setShots([]); setSelectedShot('');
    }
  }, [selectedChapter]);

  // 剧本变化 → 加载分镜
  useEffect(() => {
    if (selectedScript) {
      loadStoryboards(selectedScript);
      setSelectedStoryboard(''); setShots([]); setSelectedShot('');
    }
  }, [selectedScript]);

  // 分镜变化 → 加载镜头
  useEffect(() => {
    if (selectedStoryboard) {
      loadShots(selectedStoryboard);
      setSelectedShot('');
    }
  }, [selectedStoryboard]);

  // 镜头变化 → 自动填入对话
  useEffect(() => {
    if (selectedShot) {
      const shot = shots.find(s => s.id === selectedShot);
      if (shot && shot.dialogue) {
        setText(shot.dialogue);
      }
    }
  }, [selectedShot]);

  const loadNovels = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/novels`);
      if (res.ok) setNovels(await res.json());
    } catch {}
  };
  const loadChapters = async (novelId: string) => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/chapters/novel/${novelId}`);
      if (res.ok) setChapters(await res.json());
    } catch {}
  };
  const loadScripts = async (chapterId: string) => {
    try {
      const params = new URLSearchParams();
      if (selectedNovel) params.set('novel_id', selectedNovel);
      if (chapterId) params.set('chapter_id', chapterId);
      const res = await fetchWithAuth(`${API_BASE}/scripts${params.toString() ? `?${params}` : ''}`);
      if (res.ok) {
        const data = await res.json();
        setScripts((Array.isArray(data) ? data : []).filter((script: Script) =>
          (!selectedNovel || script.novel_id === selectedNovel) &&
          (!chapterId || script.chapter_id === chapterId || script.extra_data?.chapter_id === chapterId)
        ));
      }
    } catch {}
  };
  const loadStoryboards = async (scriptId: string) => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/storyboards/script/${scriptId}`);
      if (res.ok) setStoryboards(await res.json());
    } catch {}
  };
  const loadShots = async (storyboardId: string) => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/shots/storyboard/${storyboardId}`);
      if (res.ok) setShots(await res.json());
    } catch {}
  };

  const loadHistory = async () => {
    setLoadingHistory(true);
    try {
      const res = await fetchWithAuth(`${API_BASE}/tts/jobs`);
      if (res.ok) setHistory(await res.json());
    } catch {} finally { setLoadingHistory(false); }
  };

  const loadLLMConfigs = async () => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/llm/configs`);
      if (res.ok) {
        const configs = await res.json();
        setLlmConfigs(Array.isArray(configs) ? configs : []);
      }
    } catch {}
  };

  const handleGenerate = async () => {
    if (!text.trim()) {
      toast({ title: '请输入要转换的文本', type: 'info' });
      return;
    }
    setGenerating(true); setError(null); setCurrentAudio(null); setCurrentSegments([]);

    try {
      const res = await fetchWithAuth(`${API_BASE}/tts/generate`, {
        method: 'POST',
        body: JSON.stringify({
          text_content: text,
          title: selectedShot ? `镜头TTS_${selectedShot.slice(0, 8)}` : 'TTS任务',
          voice_model: selectedVoice,
          speed: voiceSpeed,
          api_provider: selectedTTSConfig?.provider_id || selectedProvider || undefined,
          model_config_id: selectedTTSConfig?.id || undefined,
          model_id: selectedTTSConfig?.api_model_id || selectedTTSConfig?.model_id || undefined,
          shot_id: selectedShot || undefined,
          storyboard_id: selectedStoryboard || undefined,
          script_id: selectedScript || undefined,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.status === 'completed') {
          // 多角色
          if (data.extra_data?.segments?.length > 0) {
            setCurrentSegments(data.extra_data.segments);
          }
          if (data.audio_url) {
            setCurrentAudio(`${API_BASE.replace('/api/v1', '')}${data.audio_url}`);
          }
        } else if (data.status === 'failed') {
          throw new Error(data.error_message || 'TTS生成失败');
        }
        loadHistory();
      } else {
        const errData = await res.json();
        throw new Error(errData.detail || '生成失败');
      }
    } catch (err: any) {
      setError(err.message || '生成失败，请稍后重试');
    } finally {
      setGenerating(false);
    }
  };

  const playAudio = (url: string) => {
    if (audioRef.current) { audioRef.current.pause(); }
    const fullUrl = url.startsWith('http') ? url : `${API_BASE.replace('/api/v1', '')}${url}`;
    audioRef.current = new Audio(fullUrl);
    audioRef.current.play();
    audioRef.current.onended = () => setPlaying(false);
    setPlaying(true);
  };

  const stopAudio = () => {
    audioRef.current?.pause();
    setPlaying(false);
  };

  const getFullAudioUrl = (url: string) => {
    return url.startsWith('http') ? url : `${API_BASE.replace('/api/v1', '')}${url}`;
  };

  const getStatusBadge = (status: string) => {
    if (status === 'completed' || status === 'succeeded') return 'bg-green-500/20 text-green-400';
    if (status === 'failed') return 'bg-red-500/20 text-red-400';
    return 'bg-yellow-500/20 text-yellow-400';
  };

  const getStatusText = (status: string) => {
    if (status === 'completed' || status === 'succeeded') return '完成';
    if (status === 'failed') return '失败';
    return '处理中';
  };

  return (
    <MainLayout>
      <audio ref={audioRef} />
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Volume2 className="w-6 h-6" />
            语音合成 (TTS)
          </h1>
          <p className="text-white/60 mt-1">将文本转换为自然语音，支持多角色对话分段生成</p>
        </div>

        {ttsConfigs.length > 0 && selectedTTSConfig?.test_status !== 'success' && (
          <Card className="bg-yellow-500/10 border-yellow-500/30">
            <CardContent className="p-3 text-sm text-yellow-100">
              当前语音模型配置为“{modelStatusLabel(selectedTTSConfig?.test_status)}”。建议先在大模型配置页测试通过，避免生成时才发现 Key、权限或套餐问题。
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧配置 */}
          <div className="lg:col-span-1 space-y-4">
            {/* 创作链路选择 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <BookOpen className="w-5 h-5" />
                  从创作链路选择
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {/* 小说 */}
                <select
                  value={selectedNovel}
                  onChange={e => setSelectedNovel(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                >
                  <option value="">选择小说</option>
                  {novels.map(n => <option key={n.id} value={n.id}>{n.title}</option>)}
                </select>

                {/* 章节 */}
                {chapters.length > 0 && (
                  <select
                    value={selectedChapter}
                    onChange={e => setSelectedChapter(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  >
                    <option value="">选择章节</option>
                    {chapters.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
                  </select>
                )}

                {/* 剧本 */}
                {scripts.length > 0 && (
                  <select
                    value={selectedScript}
                    onChange={e => setSelectedScript(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  >
                    <option value="">选择剧本</option>
                    {scripts.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}
                  </select>
                )}

                {/* 分镜 */}
                {storyboards.length > 0 && (
                  <select
                    value={selectedStoryboard}
                    onChange={e => setSelectedStoryboard(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  >
                    <option value="">选择分镜</option>
                    {storyboards.map(sb => <option key={sb.id} value={sb.id}>{sb.title}</option>)}
                  </select>
                )}

                {/* 镜头 */}
                {shots.length > 0 && (
                  <select
                    value={selectedShot}
                    onChange={e => setSelectedShot(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  >
                    <option value="">选择镜头（自动填入对话）</option>
                    {shots.map(s => <option key={s.id} value={s.id}>镜头{s.shot_number}: {s.dialogue?.slice(0, 30) || s.prompt?.slice(0, 30) || ''}</option>)}
                  </select>
                )}

                {shots.length > 0 && (
                  <p className="text-white/40 text-xs">
                    共 {shots.length} 个镜头，选择后可自动提取对话文本
                  </p>
                )}
              </CardContent>
            </Card>

            {/* 语音模型配置 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Settings className="w-5 h-5" />
                  语音模型配置
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {ttsConfigs.length > 0 ? (
                  ttsConfigs.map(config => (
                    <div
                      key={config.id}
                      onClick={() => {
                        setSelectedModelConfigId(config.id);
                        setSelectedProvider(config.provider_id);
                        setSelectedVoice(config.provider_id === 'volcano' ? 'female_nvsheng' : 'female-shaonj');
                      }}
                      className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                        selectedModelConfigId === config.id
                          ? 'border-violet-500 bg-violet-500/10'
                          : 'border-white/10 hover:border-white/20'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="text-white font-medium text-sm truncate">{config.name}</div>
                          <div className="text-white/50 text-xs mt-0.5">
                            {config.provider_name || config.provider_id} / {config.model_name}
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
                            <span className="rounded bg-white/10 px-2 py-0.5 text-white/55">
                              {config.is_default ? '默认语音配置' : '语音配置'}
                            </span>
                            <span className={`rounded border px-2 py-0.5 ${modelStatusClass(config.test_status)}`}>
                              {modelStatusLabel(config.test_status)}
                            </span>
                          </div>
                          {config.test_status !== 'success' && (
                            <div className="mt-1 text-xs text-yellow-100/70">
                              建议先到大模型配置页测试通过后再用于正式生成。
                            </div>
                          )}
                        </div>
                        {selectedModelConfigId === config.id && (
                          <CheckCircle className="w-4 h-4 text-violet-400 flex-shrink-0" />
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3">
                    <div className="text-yellow-100 text-sm font-medium">暂无已保存的语音模型配置</div>
                    <div className="text-yellow-100/60 text-xs mt-1">
                      请先在大模型配置中新增 TTS/语音模型，并测试通过。
                    </div>
                    <Link href="/llm-config" className="mt-3 inline-flex h-8 items-center rounded-md border border-yellow-400/40 px-3 text-xs text-yellow-100 hover:bg-yellow-500/10">
                      前往配置
                    </Link>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* 音色 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white">音色选择</CardTitle>
              </CardHeader>
              <CardContent>
                <select
                  value={selectedVoice}
                  onChange={e => setSelectedVoice(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm mb-4"
                >
                  {voiceList.map(v => (
                    <option key={v.id} value={v.id}>{v.gender} - {v.label}</option>
                  ))}
                </select>
                {/* 语速 */}
                <div className="mb-2">
                  <div className="flex justify-between mb-1">
                    <label className="text-white/80 text-sm">语速</label>
                    <span className="text-white text-sm">{voiceSpeed.toFixed(1)}x</span>
                  </div>
                  <Slider value={[voiceSpeed * 10]} onValueChange={v => setVoiceSpeed(v[0] / 10)}
                    min={5} max={20} step={1} className="w-full" />
                  <div className="flex justify-between text-white/40 text-xs mt-1">
                    <span>慢</span><span>正常</span><span>快</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 右侧：文本和预览 */}
          <div className="lg:col-span-2 space-y-4">
            {/* 文本输入 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-white">
                  文本内容
                  {selectedShot && (
                    <span className="ml-2 text-xs text-violet-400 font-normal">
                      ← 已从镜头自动填入
                    </span>
                  )}
                </CardTitle>
                <Button variant="ghost" size="sm" onClick={() => navigator.clipboard.writeText(text)}>
                  <Copy className="w-4 h-4 mr-1" />复制
                </Button>
              </CardHeader>
              <CardContent>
                <textarea
                  value={text}
                  onChange={e => setText(e.target.value)}
                  placeholder={"输入要转换为语音的文本...\n\n支持多角色对话格式：\n小明: 今天天气真好！\n小红: 是啊，我们去公园吧。\n\n每个角色会自动使用对应的音色。" + "\n"}
                  disabled={generating}
                  rows={8}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white placeholder:text-white/30 min-h-[200px] resize-none"
                />
                <div className="flex items-center justify-between mt-2">
                  <span className="text-white/40 text-sm">{text.length} 字符</span>
                  <Button onClick={handleGenerate} disabled={generating || !text.trim() || ttsConfigs.length === 0}
                    className="bg-violet-600 hover:bg-violet-700">
                    {generating && <Loader2 className="w-5 h-5 mr-2 animate-spin" />}
                    {generating ? '生成中…' : '生成语音'}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* 错误 */}
            {error && (
              <Card className="bg-red-500/10 border-red-500/30">
                <CardContent className="p-3 flex items-center gap-2">
                  <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                  <p className="text-red-400 text-sm">{error}</p>
                </CardContent>
              </Card>
            )}

            {/* 多角色结果 */}
            {currentSegments.length > 0 && (
              <Card className="bg-white/5 border-violet-500/30">
                <CardHeader>
                  <CardTitle className="text-white">多角色语音</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {currentSegments.map((seg, i) => (
                    <div key={i} className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                      <User className="w-5 h-5 text-violet-400 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          {seg.character && (
                            <span className="text-violet-400 text-sm font-medium">{seg.character}</span>
                          )}
                          <span className="text-white/40 text-xs">{voiceList.find(v => v.id === seg.voice)?.label || seg.voice}</span>
                        </div>
                        <p className="text-white/80 text-sm truncate">"{seg.text}"</p>
                      </div>
                      {seg.audio_url ? (
                        <Button variant="ghost" size="sm" onClick={() => playAudio(seg.audio_url!)}>
                          <Play className="w-4 h-4" />
                        </Button>
                      ) : (
                        <span className="text-red-400 text-xs">失败</span>
                      )}
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* 单段音频预览 */}
            {currentAudio && currentSegments.length === 0 && (
              <Card className="bg-white/5 border-white/10">
                <CardHeader><CardTitle className="text-white">音频预览</CardTitle></CardHeader>
                <CardContent>
                  <div className="flex items-center gap-4">
                    <Button onClick={() => playing ? stopAudio() : playAudio(currentAudio)}
                      className="w-12 h-12 rounded-full bg-violet-600 hover:bg-violet-700">
                      {playing ? <Pause className="w-6 h-6" /> : <Play className="w-6 h-6 ml-0.5" />}
                    </Button>
                    <div className="flex-1 h-12 bg-white/10 rounded flex items-center justify-center">
                      <span className="text-white/60 text-sm">{playing ? '播放中...' : '点击播放'}</span>
                    </div>
                    <Button variant="outline" onClick={() => window.open(getFullAudioUrl(currentAudio), '_blank')}>
                      <Download className="w-4 h-4 mr-2" />下载
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* 生成历史 */}
            <Card className="bg-white/5 border-white/10">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-white flex items-center gap-2">
                  <Clock className="w-5 h-5" />
                  生成历史
                </CardTitle>
                <Button variant="ghost" size="sm" onClick={loadHistory} disabled={loadingHistory}>
                  <RefreshCw className={`w-4 h-4 ${loadingHistory ? 'animate-spin' : ''}`} />
                </Button>
              </CardHeader>
              <CardContent>
                {loadingHistory && history.length === 0 ? (
                  <div className="text-center py-8">
                    <Loader2 className="w-8 h-8 mx-auto mb-2 animate-spin text-white/40" />
                    <p className="text-white/40">加载中…</p>
                  </div>
                ) : history.length > 0 ? (
                  <div className="space-y-2 max-h-80 overflow-y-auto">
                    {history.map(job => (
                      <div key={job.id} className="flex items-center justify-between p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <Volume2 className="w-5 h-5 text-violet-400 flex-shrink-0" />
                          <div className="min-w-0 flex-1">
                            <div className="text-white font-medium text-sm truncate">
                              {job.title || job.text?.slice(0, 40) || 'TTS音频'}
                            </div>
                            <div className="text-white/50 text-xs flex items-center gap-2">
                              <span>{new Date(job.created_at).toLocaleString()}</span>
                              {job.voice && <span>🎤 {voiceList.find(v => v.id === job.voice)?.label || job.voice}</span>}
                              {job.duration_seconds && <span>⏱ {job.duration_seconds}秒</span>}
                              {job.shot_id && <span>📷 镜头关联</span>}
                            </div>
                            {job.error_message && (
                              <div className="text-red-400 text-xs mt-0.5">{job.error_message}</div>
                            )}
                            {/* 多角色片段 */}
                            {job.extra_data?.segments?.length > 0 && (
                              <div className="mt-1 space-y-1">
                                {job.extra_data.segments.map((seg: TTSSegment, i: number) => (
                                  <div key={i} className="flex items-center gap-2 text-xs">
                                    {seg.character && <span className="text-violet-400">{seg.character}:</span>}
                                    <span className="text-white/60 truncate">"{seg.text.slice(0, 30)}"</span>
                                    {seg.audio_url ? (
                                      <button
                                        type="button"
                                        onClick={() => playAudio(seg.audio_url)}
                                        aria-label={`播放 ${seg.character || '片段'} 音频`}
                                        title="播放音频"
                                        className="ml-1 rounded text-green-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
                                      >
                                        ▶
                                      </button>
                                    ) : (
                                      <span className="text-red-400 ml-1">✗</span>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <span className={`px-2 py-1 text-xs rounded ${getStatusBadge(job.status)}`}>
                            {getStatusText(job.status)}
                          </span>
                          {job.audio_url && (
                            <Button variant="ghost" size="sm" onClick={() => playAudio(job.audio_url!)}>
                              <Play className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-white/40">
                    暂无生成记录
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
