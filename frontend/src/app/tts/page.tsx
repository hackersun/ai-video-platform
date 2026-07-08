'use client';

import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Slider } from '@/components/ui/slider';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import { useToast } from '@/components/ui/toast';
import {
  Volume2, Play, Pause, Download, Loader2, AlertCircle,
  Copy, RefreshCw, Clock, Settings, User, BookOpen, CheckCircle,
  Headphones, Mic2, Upload, Trash2
} from 'lucide-react';
import Link from 'next/link';
import { fetchWithAuth } from '@/lib/fetch-with-auth';
import { apiClient } from '@/lib/api-client';
import { PreflightIssueList } from '@/components/production/preflight-issue-list';
import { HistoryPreflightEvidence } from '@/components/production/history-preflight-evidence';
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
  { id: 'female-shaonv', label: '少女音', gender: '女' },
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
interface StoryBible { id: string; title: string; character_rules?: any[]; }
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
  voice_source?: string; speed?: number;
  audio_url?: string; duration?: number; error?: string;
}

interface VoiceOption {
  id: string;
  label: string;
  gender: string;
  lang?: string;
  provider?: string;
  is_custom?: boolean;
  sample_audio_url?: string;
  status?: string;
  provider_ready?: boolean;
  provider_tts_model?: string;
  provider_error?: string;
  description?: string;
}

const READY_CLONE_STATUSES = new Set(['ready', 'provider_ready']);

const getVoiceCloneStatusLabel = (status?: string) => {
  if (status === 'provider_ready' || status === 'ready') return '云端可用';
  if (status === 'provider_failed') return '云端激活失败';
  if (status === 'sample_uploaded') return '样本已上传';
  if (status === 'provider_pending') return '待云端激活';
  return status || '未知状态';
};

const isMinimaxCloneBlocked = (voice: VoiceOption | undefined, provider: string | undefined) => {
  if (!voice?.is_custom || provider !== 'minimax') return false;
  return !READY_CLONE_STATUSES.has(voice.status || '');
};

export default function TTSPage() {
  const { toast } = useToast();
  const [selectedProvider, setSelectedProvider] = useState('minimax');
  const [llmConfigs, setLlmConfigs] = useState<SavedModelConfig[]>([]);
  const [selectedModelConfigId, setSelectedModelConfigId] = useState('');
  const [selectedVoice, setSelectedVoice] = useState('female-shaonv');
  const [text, setText] = useState('');
  const [voiceSpeed, setVoiceSpeed] = useState(1.0);
  const [generating, setGenerating] = useState(false);
  const [currentAudio, setCurrentAudio] = useState<string | null>(null);
  const [currentSegments, setCurrentSegments] = useState<TTSSegment[]>([]);
  const [generationPreflight, setGenerationPreflight] = useState<any>(null);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<TTSJob[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [deletingHistoryJobId, setDeletingHistoryJobId] = useState<string | null>(null);
  const [availableVoices, setAvailableVoices] = useState<VoiceOption[]>([]);
  const [previewingVoice, setPreviewingVoice] = useState(false);
  const [voicePreviewAudio, setVoicePreviewAudio] = useState<string | null>(null);
  const [cloneName, setCloneName] = useState('');
  const [cloneVoiceId, setCloneVoiceId] = useState('');
  const [cloneDescription, setCloneDescription] = useState('');
  const [cloneSampleUrl, setCloneSampleUrl] = useState('');
  const [cloneSampleFile, setCloneSampleFile] = useState<File | null>(null);
  const [cloneSampleSource, setCloneSampleSource] = useState<'upload' | 'recording' | 'url'>('upload');
  const [cloneSamplePreviewAudio, setCloneSamplePreviewAudio] = useState<string | null>(null);
  const [recordingVoiceClone, setRecordingVoiceClone] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [creatingClone, setCreatingClone] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const recordingChunksRef = useRef<Blob[]>([]);
  const recordingTimerRef = useRef<number | null>(null);
  const cloneSamplePreviewUrlRef = useRef<string | null>(null);

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
  const [storyBibles, setStoryBibles] = useState<StoryBible[]>([]);
  const [selectedStoryBible, setSelectedStoryBible] = useState('');
  const [useStoryBibleVoice, setUseStoryBibleVoice] = useState(true);

  const [loadingChain, setLoadingChain] = useState(false);

  // 音色列表
  const fallbackVoices: VoiceOption[] = selectedProvider === 'minimax' ? MINIMAX_VOICES : VOLCANO_VOICES;
  const voiceList = availableVoices.length > 0 ? availableVoices : fallbackVoices;
  const ttsConfigs = getConfigsByCapability(llmConfigs, 'audio');
  const selectedTTSConfig = ttsConfigs.find(config => config.id === selectedModelConfigId);
  const activeProvider = selectedTTSConfig?.provider_id || selectedProvider;
  const selectedVoiceOption = voiceList.find(v => v.id === selectedVoice);
  const selectedVoiceBlocked = isMinimaxCloneBlocked(selectedVoiceOption, activeProvider);

  // 加载小说列表
  useEffect(() => {
    loadNovels();
    loadHistory();
    loadLLMConfigs();
    loadVoiceOptions('minimax');
  }, []);

  useEffect(() => {
    return () => {
      if (recordingTimerRef.current) {
        window.clearInterval(recordingTimerRef.current);
        recordingTimerRef.current = null;
      }
      mediaRecorderRef.current = null;
      mediaStreamRef.current?.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
      if (cloneSamplePreviewUrlRef.current) {
        URL.revokeObjectURL(cloneSamplePreviewUrlRef.current);
        cloneSamplePreviewUrlRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    loadVoiceOptions(selectedProvider);
  }, [selectedProvider]);

  useEffect(() => {
    if (ttsConfigs.length === 0 || selectedModelConfigId) return;
      const defaultConfig = getDefaultConfigForCapability(llmConfigs, 'audio');
      if (defaultConfig) {
        setSelectedModelConfigId(defaultConfig.id);
        setSelectedProvider(defaultConfig.provider_id);
      }
  }, [llmConfigs, selectedModelConfigId]);

  useEffect(() => {
    if (voiceList.length === 0) return;
    if (!voiceList.some((voice) => voice.id === selectedVoice)) {
      setSelectedVoice(voiceList[0].id);
      setVoicePreviewAudio(null);
    }
  }, [availableVoices, selectedProvider]);

  // 小说变化 → 加载章节
  useEffect(() => {
    if (selectedNovel) {
      loadChapters(selectedNovel);
      setSelectedChapter(''); setScripts([]); setSelectedScript('');
      setStoryboards([]); setSelectedStoryboard(''); setShots([]); setSelectedShot('');
      loadStoryBibles(selectedNovel);
    } else {
      setStoryBibles([]);
      setSelectedStoryBible('');
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

  const loadStoryBibles = async (novelId: string) => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/story-bibles?novel_id=${encodeURIComponent(novelId)}`);
      if (res.ok) {
        const data = await res.json();
        const list = Array.isArray(data) ? data : [];
        setStoryBibles(list);
        setSelectedStoryBible((current) => (
          current && list.some((item: StoryBible) => item.id === current)
            ? current
            : list[0]?.id || ''
        ));
      }
    } catch {
      setStoryBibles([]);
      setSelectedStoryBible('');
    }
  };

  const loadHistory = async () => {
    setLoadingHistory(true);
    try {
      const res = await fetchWithAuth(`${API_BASE}/tts/jobs`);
      if (res.ok) setHistory(await res.json());
    } catch {} finally { setLoadingHistory(false); }
  };

  const handleDeleteHistoryJob = async (job: TTSJob) => {
    setDeletingHistoryJobId(job.id);
    try {
      await apiClient.deleteTTSJob(job.id);
      toast({ title: 'TTS记录已归档', description: '历史列表已更新。', type: 'success' });
      await loadHistory();
    } catch (err: any) {
      toast({ title: '归档失败', description: err?.message || '请稍后重试。', type: 'error' });
    } finally {
      setDeletingHistoryJobId(null);
    }
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

  const loadVoiceOptions = async (provider: string) => {
    try {
      const res = await fetchWithAuth(`${API_BASE}/tts/voices?provider=${encodeURIComponent(provider)}`);
      if (res.ok) {
        const data = await res.json();
        const voices = Array.isArray(data.voices) ? data.voices : [];
        setAvailableVoices(voices.map((voice: any) => ({
          id: voice.voice_id || voice.id,
          label: voice.label || voice.name || voice.voice_id || voice.id,
          gender: voice.gender || '未知',
          lang: voice.lang,
          provider: voice.provider,
          is_custom: Boolean(voice.is_custom),
          sample_audio_url: voice.sample_audio_url,
          status: voice.status,
          provider_ready: voice.provider_ready,
          provider_tts_model: voice.provider_tts_model,
          provider_error: voice.provider_error,
          description: voice.description,
        })).filter((voice: VoiceOption) => Boolean(voice.id)));
        return;
      }
    } catch {}
    setAvailableVoices([]);
  };

  const handleGenerate = async () => {
    if (!text.trim()) {
      toast({ title: '请输入要转换的文本', type: 'info' });
      return;
    }
    if (selectedVoiceBlocked) {
      const detail = selectedVoiceOption?.provider_error || getVoiceCloneStatusLabel(selectedVoiceOption?.status);
      toast({ title: '克隆音色未就绪', description: `当前音色不能直接用于 MiniMax 生成：${detail}`, type: 'error' });
      return;
    }
    setGenerating(true); setError(null); setCurrentAudio(null); setCurrentSegments([]); setGenerationPreflight(null);

    try {
      const preflight = await apiClient.preflightGeneration({
        task_type: 'tts_dialogue',
        model_config_id: selectedTTSConfig?.id || selectedModelConfigId || undefined,
        production_mode: true,
        novel_id: selectedNovel || undefined,
        chapter_id: selectedChapter || undefined,
        script_id: selectedScript || undefined,
        storyboard_id: selectedStoryboard || undefined,
        shot_id: selectedShot || undefined,
      });
      setGenerationPreflight(preflight);
      if (preflight?.ready === false) {
        const blockingCount = preflight.blocking_issue_count || preflight.issues?.length || 0;
        setError(`生成前预检未通过：发现 ${blockingCount} 个阻断项。`);
        toast({ title: '生成前预检未通过', description: '请先处理下方阻断项，再提交生成。', type: 'error' });
        return;
      }

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
          novel_id: selectedNovel || undefined,
          chapter_id: selectedChapter || undefined,
          story_bible_id: selectedStoryBible || undefined,
          use_story_bible_voice: useStoryBibleVoice,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.status === 'completed' || data.status === 'succeeded') {
          // 多角色
          if (data.extra_data?.segments?.length > 0) {
            setCurrentSegments(data.extra_data.segments);
          }
          if (data.audio_url) {
            setCurrentAudio(getFullAudioUrl(data.audio_url));
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

  const handlePreviewVoice = async () => {
    if (selectedVoiceBlocked) {
      const detail = selectedVoiceOption?.provider_error || getVoiceCloneStatusLabel(selectedVoiceOption?.status);
      toast({ title: '克隆音色未就绪', description: `当前音色不能直接试听：${detail}`, type: 'error' });
      return;
    }
    setPreviewingVoice(true);
    setVoicePreviewAudio(null);
    try {
      const sampleText = text.trim()
        ? text.trim().slice(0, 100)
        : `这是一段${voiceList.find(v => v.id === selectedVoice)?.label || '当前音色'}的试听。`;
      const res = await fetchWithAuth(`${API_BASE}/tts/preview`, {
        method: 'POST',
        body: JSON.stringify({
          text: sampleText,
          voice_model: selectedVoice,
          speed: voiceSpeed,
          api_provider: selectedTTSConfig?.provider_id || selectedProvider || 'minimax',
          model_config_id: selectedTTSConfig?.id || undefined,
          model_id: selectedTTSConfig?.api_model_id || selectedTTSConfig?.model_id || undefined,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || data.message || '试听失败');
      }
      setVoicePreviewAudio(getFullAudioUrl(data.audio_url));
      toast({ title: '试听音频已生成', description: data.message || '可以直接播放试听。', type: 'success' });
    } catch (err: any) {
      toast({ title: '试听失败', description: err.message || '请检查 TTS 模型配置。', type: 'error' });
    } finally {
      setPreviewingVoice(false);
    }
  };

  const formatRecordingSeconds = (seconds: number) => {
    const minutes = Math.floor(seconds / 60).toString().padStart(2, '0');
    const remain = (seconds % 60).toString().padStart(2, '0');
    return `${minutes}:${remain}`;
  };

  const setCloneSamplePreviewFromFile = (file: File | null) => {
    if (cloneSamplePreviewUrlRef.current) {
      URL.revokeObjectURL(cloneSamplePreviewUrlRef.current);
      cloneSamplePreviewUrlRef.current = null;
    }
    if (!file) {
      setCloneSamplePreviewAudio(null);
      return;
    }
    const url = URL.createObjectURL(file);
    cloneSamplePreviewUrlRef.current = url;
    setCloneSamplePreviewAudio(url);
  };

  const stopRecordingResources = () => {
    if (recordingTimerRef.current) {
      window.clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
    mediaStreamRef.current?.getTracks().forEach(track => track.stop());
    mediaStreamRef.current = null;
  };

  const handleCloneFileChange = (file: File | null) => {
    if (recordingVoiceClone) {
      toast({ title: '正在录音中', description: '请先停止录音，再选择上传文件。', type: 'info' });
      return;
    }
    setCloneSampleFile(file);
    setCloneSampleSource('upload');
    setCloneSampleUrl('');
    setRecordingSeconds(0);
    setCloneSamplePreviewFromFile(file);
  };

  const startVoiceCloneRecording = async () => {
    if (recordingVoiceClone) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      toast({ title: '当前浏览器不支持录音', description: '可以改用上传音频样本。', type: 'error' });
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const preferredMimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : '';
      const recorder = preferredMimeType
        ? new MediaRecorder(stream, { mimeType: preferredMimeType })
        : new MediaRecorder(stream);

      recordingChunksRef.current = [];
      mediaStreamRef.current = stream;
      mediaRecorderRef.current = recorder;
      setCloneSampleFile(null);
      setCloneSampleUrl('');
      setCloneSampleSource('recording');
      setCloneSamplePreviewFromFile(null);
      setRecordingSeconds(0);

      recorder.ondataavailable = event => {
        if (event.data && event.data.size > 0) {
          recordingChunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        stopRecordingResources();
        setRecordingVoiceClone(false);
        const mimeType = recorder.mimeType || 'audio/webm';
        const blob = new Blob(recordingChunksRef.current, { type: mimeType });
        recordingChunksRef.current = [];
        if (!blob.size) {
          toast({ title: '录音为空', description: '请重新录制一段清晰人声。', type: 'error' });
          return;
        }
        const extension = mimeType.includes('mp4') || mimeType.includes('m4a') ? 'm4a' : 'webm';
        const file = new File([blob], `recorded-voice-${Date.now()}.${extension}`, { type: mimeType });
        setCloneSampleFile(file);
        setCloneSampleSource('recording');
        setCloneSamplePreviewFromFile(file);
        toast({ title: '录音已读取', description: '可以先试听样本，再创建克隆音色。', type: 'success' });
      };
      recorder.onerror = () => {
        stopRecordingResources();
        setRecordingVoiceClone(false);
        toast({ title: '录音失败', description: '请检查麦克风权限后重试。', type: 'error' });
      };

      recorder.start();
      setRecordingVoiceClone(true);
      recordingTimerRef.current = window.setInterval(() => {
        setRecordingSeconds(value => value + 1);
      }, 1000);
    } catch (err: any) {
      stopRecordingResources();
      setRecordingVoiceClone(false);
      toast({ title: '无法读取麦克风', description: err?.message || '请允许浏览器访问麦克风。', type: 'error' });
    }
  };

  const stopVoiceCloneRecording = () => {
    if (!mediaRecorderRef.current || mediaRecorderRef.current.state === 'inactive') {
      stopRecordingResources();
      setRecordingVoiceClone(false);
      return;
    }
    mediaRecorderRef.current.stop();
  };

  const resetVoiceCloneRecording = () => {
    if (recordingVoiceClone) {
      stopVoiceCloneRecording();
    }
    setCloneSampleFile(null);
    setCloneSampleSource('upload');
    setRecordingSeconds(0);
    setCloneSamplePreviewFromFile(null);
  };

  const handleCreateVoiceClone = async () => {
    if (!cloneName.trim()) {
      toast({ title: '请输入克隆音色名称', type: 'info' });
      return;
    }
    if (!cloneSampleFile && !cloneSampleUrl.trim()) {
      toast({ title: '请上传声音样本或填写样本 URL', description: '建议使用 10-30 秒干净人声。', type: 'info' });
      return;
    }
    setCreatingClone(true);
    try {
      const form = new FormData();
      form.append('name', cloneName.trim());
      form.append('provider', selectedTTSConfig?.provider_id || selectedProvider || 'minimax');
      if (cloneVoiceId.trim()) form.append('voice_id', cloneVoiceId.trim());
      if (cloneDescription.trim()) form.append('description', cloneDescription.trim());
      if (cloneSampleUrl.trim()) form.append('sample_audio_url', cloneSampleUrl.trim());
      if (cloneSampleFile) form.append('sample_audio', cloneSampleFile);
      form.append('sample_source', cloneSampleFile ? cloneSampleSource : 'url');
      if (selectedNovel) form.append('novel_id', selectedNovel);

      const res = await fetchWithAuth(`${API_BASE}/tts/voice-clones`, {
        method: 'POST',
        body: form,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || data.message || '创建克隆音色失败');
      }
      await loadVoiceOptions(selectedTTSConfig?.provider_id || selectedProvider || 'minimax');
      setSelectedVoice(data.voice_id);
      setCloneName('');
      setCloneVoiceId('');
      setCloneDescription('');
      setCloneSampleUrl('');
      setCloneSampleFile(null);
      setCloneSampleSource('upload');
      setRecordingSeconds(0);
      setCloneSamplePreviewFromFile(null);
      setVoicePreviewAudio(data.sample_audio_url ? getFullAudioUrl(data.sample_audio_url) : null);
      toast({ title: '克隆音色已创建', description: '已加入音色列表；云端克隆状态以服务商验证为准。', type: 'success' });
    } catch (err: any) {
      toast({ title: '创建失败', description: err.message || '请稍后重试。', type: 'error' });
    } finally {
      setCreatingClone(false);
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
                        setSelectedVoice(config.provider_id === 'volcano' ? 'female_nvsheng' : 'female-shaonv');
                        setVoicePreviewAudio(null);
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
                <CardTitle className="text-white flex items-center gap-2">
                  <Headphones className="w-5 h-5" />
                  音色选择与试听
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <select
                    value={selectedVoice}
                    onChange={e => {
                      setSelectedVoice(e.target.value);
                      setVoicePreviewAudio(null);
                    }}
                    className="min-w-0 flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                  >
                    {voiceList.map(v => (
                      <option key={v.id} value={v.id}>
                        {v.is_custom ? `克隆/${getVoiceCloneStatusLabel(v.status)}` : v.gender} - {v.label}
                      </option>
                    ))}
                  </select>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handlePreviewVoice}
                    disabled={previewingVoice || !selectedVoice || selectedVoiceBlocked}
                    className="shrink-0 border-white/20"
                  >
                    {previewingVoice ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Play className="w-4 h-4 mr-1" />}
                    试听
                  </Button>
                </div>
                {selectedVoiceOption?.is_custom && (
                  <div className={`rounded-lg border p-2 text-xs ${
                    selectedVoiceBlocked
                      ? 'border-red-500/30 bg-red-500/10 text-red-50/85'
                      : 'border-cyan-500/20 bg-cyan-500/10 text-cyan-50/80'
                  }`}>
                    当前选择的是克隆音色，状态：{getVoiceCloneStatusLabel(selectedVoiceOption.status)}。
                    {selectedVoiceBlocked
                      ? ` 该 voice_id 尚未在 MiniMax 云端可用，不能直接试听或生成。${selectedVoiceOption.provider_error ? ` 服务商错误：${selectedVoiceOption.provider_error}` : ''}`
                      : ' 平台会把该 voice_id 传给 TTS 服务生成真实音频。'}
                  </div>
                )}
                {voicePreviewAudio && (
                  <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                    <div className="mb-2 text-xs text-white/50">音色试听</div>
                    <audio src={voicePreviewAudio} controls className="w-full" />
                  </div>
                )}
                {/* 语速 */}
                <div>
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

            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Mic2 className="w-5 h-5" />
                  声音克隆
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Input
                  value={cloneName}
                  onChange={e => setCloneName(e.target.value)}
                  placeholder="克隆音色名称，例如：主角林舟"
                  className="bg-white/5 border-white/10 text-white placeholder:text-white/35"
                />
                <Input
                  value={cloneVoiceId}
                  onChange={e => setCloneVoiceId(e.target.value)}
                  placeholder="已有/本地声线 ID，可选，例如：sunqinyue-default"
                  className="bg-white/5 border-white/10 text-white placeholder:text-white/35"
                />
                <Input
                  value={cloneDescription}
                  onChange={e => setCloneDescription(e.target.value)}
                  placeholder="声音描述，例如：少年感、冷静、语速稳定"
                  className="bg-white/5 border-white/10 text-white placeholder:text-white/35"
                />
                <Input
                  value={cloneSampleUrl}
                  onChange={e => {
                    const value = e.target.value;
                    setCloneSampleUrl(value);
                    if (value.trim()) {
                      setCloneSampleFile(null);
                      setCloneSampleSource('url');
                      setRecordingSeconds(0);
                      setCloneSamplePreviewFromFile(null);
                    }
                  }}
                  placeholder="样本音频 URL，可选，也可直接上传或录音"
                  className="bg-white/5 border-white/10 text-white placeholder:text-white/35"
                />
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <label className={`flex cursor-pointer items-center justify-between gap-3 rounded-lg border px-3 py-2 text-sm transition ${
                    cloneSampleSource === 'upload' && cloneSampleFile
                      ? 'border-cyan-400/40 bg-cyan-500/10 text-cyan-50'
                      : 'border-white/10 bg-white/5 text-white/65 hover:bg-white/10'
                  }`}>
                    <span className="min-w-0">
                      <span className="block text-xs text-white/45">上传音频克隆</span>
                      <span className="block truncate">
                        {cloneSampleSource === 'upload' && cloneSampleFile ? cloneSampleFile.name : '选择 wav/mp3/m4a/webm'}
                      </span>
                    </span>
                    <Upload className="h-4 w-4 shrink-0" />
                    <input
                      type="file"
                      accept="audio/*,.wav,.mp3,.m4a,.aac,.ogg,.webm"
                      className="hidden"
                      onChange={e => handleCloneFileChange(e.target.files?.[0] || null)}
                    />
                  </label>
                  <div className={`rounded-lg border px-3 py-2 ${
                    cloneSampleSource === 'recording'
                      ? 'border-cyan-400/40 bg-cyan-500/10'
                      : 'border-white/10 bg-white/5'
                  }`}>
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-xs text-white/45">读取录音克隆</div>
                        <div className="truncate text-sm text-white/70">
                          {recordingVoiceClone
                            ? `录音中 ${formatRecordingSeconds(recordingSeconds)}`
                            : cloneSampleSource === 'recording' && cloneSampleFile
                              ? cloneSampleFile.name
                              : '使用麦克风录一段样本'}
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={recordingVoiceClone ? stopVoiceCloneRecording : startVoiceCloneRecording}
                        disabled={creatingClone}
                        className="shrink-0 border-white/20"
                      >
                        {recordingVoiceClone ? <Pause className="h-4 w-4 mr-1" /> : <Mic2 className="h-4 w-4 mr-1" />}
                        {recordingVoiceClone ? '停止' : '录音'}
                      </Button>
                    </div>
                    {cloneSampleSource === 'recording' && cloneSampleFile && !recordingVoiceClone && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={resetVoiceCloneRecording}
                        className="h-7 px-2 text-xs text-white/65 hover:text-white"
                      >
                        <RefreshCw className="h-3.5 w-3.5 mr-1" />
                        重录
                      </Button>
                    )}
                  </div>
                </div>
                {cloneSamplePreviewAudio && (
                  <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                    <div className="mb-2 flex items-center justify-between gap-2 text-xs text-white/50">
                      <span>{cloneSampleSource === 'recording' ? '录音样本试听' : '上传样本试听'}</span>
                      <Badge className="bg-cyan-500/15 text-cyan-100 border-cyan-500/30">
                        {cloneSampleSource === 'recording' ? '录音' : '上传'}
                      </Badge>
                    </div>
                    <audio src={cloneSamplePreviewAudio} controls className="w-full" />
                  </div>
                )}
                <Button
                  type="button"
                  onClick={handleCreateVoiceClone}
                  disabled={creatingClone || recordingVoiceClone}
                  className="w-full bg-cyan-600 hover:bg-cyan-700"
                >
                  {creatingClone ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Mic2 className="w-4 h-4 mr-2" />}
                  创建克隆音色
                </Button>
                <p className="text-xs text-white/40">
                  建议使用 10-30 秒干净人声。上传、录音和 URL 都会先登记为可复用克隆音色；云端训练由对应服务商或生产适配器执行。
                </p>
              </CardContent>
            </Card>

            <Card className="bg-white/5 border-white/10">
              <CardHeader>
                <CardTitle className="text-white">角色音色锁</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge className={useStoryBibleVoice ? 'bg-green-500/20 text-green-200 border-green-500/30' : 'bg-white/10 text-white/60 border-white/10'}>
                      {useStoryBibleVoice ? '启用' : '关闭'}
                    </Badge>
                    {selectedStoryBible && (
                      <Badge className="bg-violet-500/20 text-violet-100 border-violet-500/30">
                        {storyBibles.find(item => item.id === selectedStoryBible)?.character_rules?.length || 0} 个角色
                      </Badge>
                    )}
                  </div>
                  <label className="flex items-center gap-2 text-sm text-white/70">
                    <Checkbox
                      checked={useStoryBibleVoice}
                      onCheckedChange={(checked) => setUseStoryBibleVoice(Boolean(checked))}
                      disabled={generating}
                    />
                    使用
                  </label>
                </div>
                <select
                  value={selectedStoryBible}
                  onChange={e => setSelectedStoryBible(e.target.value)}
                  disabled={generating || storyBibles.length === 0}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm disabled:opacity-50"
                >
                  <option value="">自动/未选择 Story Bible</option>
                  {storyBibles.map(item => (
                    <option key={item.id} value={item.id}>
                      {item.title}{item.character_rules?.length ? ` · ${item.character_rules.length} 角色` : ''}
                    </option>
                  ))}
                </select>
                <p className="text-white/40 text-xs">
                  多角色对白会优先按 Story Bible 的 voice 与 voice_speed 分段生成。
                </p>
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

            {generationPreflight && (
              <Card
                data-testid="tts-generation-preflight"
                className={generationPreflight.ready ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-red-500/10 border-red-500/30'}
              >
                <CardContent className="p-3 space-y-2">
                  <div className={generationPreflight.ready ? 'text-emerald-100 text-sm font-medium' : 'text-red-100 text-sm font-medium'}>
                    {generationPreflight.ready ? '生成前预检通过' : '生成前预检未通过'}
                  </div>
                  <PreflightIssueList
                    issues={generationPreflight.issues || []}
                    emptyText="预检通过，可以提交生成。"
                  />
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
                          {seg.voice_source === 'story_bible' && (
                            <Badge className="bg-green-500/20 text-green-200 border-green-500/30 text-[10px]">
                              Story Bible
                            </Badge>
                          )}
                        </div>
                        <p className="text-white/80 text-sm truncate">"{seg.text}"</p>
                        {seg.audio_url && (
                          <audio src={getFullAudioUrl(seg.audio_url)} controls className="mt-2 w-full" />
                        )}
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
                  <div className="space-y-3">
                    <audio src={currentAudio} controls className="w-full" />
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
                            <HistoryPreflightEvidence
                              preflight={job.extra_data?.generation_preflight}
                              testId={`history-preflight-${job.id}`}
                            />
                            {job.audio_url && (
                              <audio src={getFullAudioUrl(job.audio_url)} controls className="mt-2 w-full max-w-xl" />
                            )}
                            {/* 多角色片段 */}
                            {job.extra_data?.segments?.length > 0 && (
                              <div className="mt-1 space-y-1">
                                {job.extra_data.segments.map((seg: TTSSegment, i: number) => (
                                  <div key={i} className="flex items-center gap-2 text-xs">
                                    {seg.character && <span className="text-violet-400">{seg.character}:</span>}
                                    <span className="text-white/60 truncate">"{seg.text.slice(0, 30)}"</span>
                                    {seg.voice_source === 'story_bible' && (
                                      <span className="rounded border border-green-500/30 bg-green-500/10 px-1.5 py-0.5 text-[10px] text-green-200">
                                        Story Bible
                                      </span>
                                    )}
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
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`归档${job.title || 'TTS记录'}`}
                            title="归档"
                            className="text-white/60 hover:text-red-300"
                            onClick={() => handleDeleteHistoryJob(job)}
                            disabled={deletingHistoryJobId === job.id}
                          >
                            {deletingHistoryJobId === job.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </Button>
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
