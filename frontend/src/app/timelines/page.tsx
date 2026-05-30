'use client';

import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import {
  Captions,
  Check,
  Edit3,
  Film,
  Loader2,
  Lock,
  Music,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Save,
  Trash2,
  Unlock,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { MainLayout } from '@/components/layout/main-layout';
import { Button } from '@/components/ui/button';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/api-client';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const MEDIA_BASE = API_BASE.replace(/\/api\/v1$/, '');

type Project = {
  id: string;
  name: string;
  timeline_count?: number;
};

type Timeline = {
  id: string;
  project_id: string;
  name: string;
  description?: string;
  total_duration: number;
  fps: number;
  aspect_ratio: string;
  status: string;
  preview_url?: string;
};

type Track = {
  id: string;
  timeline_id: string;
  track_type: string;
  track_index: number;
  name?: string;
  is_locked: boolean;
  is_muted: boolean;
  is_hidden: boolean;
  volume: number;
};

type Clip = {
  id: string;
  timeline_id: string;
  track_id: string;
  source_type: string;
  source_url?: string;
  source_thumbnail?: string;
  source_duration: number;
  position: number;
  duration: number;
  volume: number;
  text_content?: string;
  name?: string;
  is_locked: boolean;
  in_point: number;
  out_point?: number;
  speed: number;
  opacity: number;
};

const trackTypeLabel: Record<string, string> = {
  video: '视频轨',
  audio: '音频轨',
  subtitle: '字幕轨',
  effect: '效果轨',
};

const trackTypeColors: Record<string, string> = {
  video: '#8B5CF6', // violet
  audio: '#10B981', // emerald
  subtitle: '#F59E0B', // amber
  effect: '#EC4899', // pink
};

const trackTypeIcon = (trackType: string) => {
  if (trackType === 'audio') return Music;
  if (trackType === 'subtitle') return Captions;
  return Film;
};

const formatTime = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

const formatSeconds = (seconds?: number) => {
  const value = Math.max(0, Number(seconds || 0));
  return formatTime(value);
};

const normalizeNumber = (value: string, fallback: number) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(0, parsed) : fallback;
};

const toMediaUrl = (url?: string) => {
  if (!url) return '';
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('blob:')) return url;
  return `${MEDIA_BASE}${url.startsWith('/') ? url : `/${url}`}`;
};

export default function TimelinesPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [timelines, setTimelines] = useState<Timeline[]>([]);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [clips, setClips] = useState<Clip[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [selectedTimelineId, setSelectedTimelineId] = useState('');
  const [loading, setLoading] = useState(true);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [savingClipId, setSavingClipId] = useState<string | null>(null);
  const [savingTrackId, setSavingTrackId] = useState<string | null>(null);
  const [addingSubtitle, setAddingSubtitle] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Clip | null>(null);
  const [clipDrafts, setClipDrafts] = useState<Record<string, Partial<Clip>>>({});

  // ========== Visual Timeline State ==========
  const [playbackTime, setPlaybackTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isGeneratingPreview, setIsGeneratingPreview] = useState(false);
  const [draggingClip, setDraggingClip] = useState<{ clipId: string; type: 'move' | 'resize-left' | 'resize-right' } | null>(null);
  const [dragStartX, setDragStartX] = useState(0);
  const [dragStartPosition, setDragStartPosition] = useState(0);
  const [dragStartDuration, setDragStartDuration] = useState(0);
  const timelineRef = useRef<HTMLDivElement>(null);
  const playIntervalRef = useRef<number | null>(null);

  // Timeline display constants
  const PIXELS_PER_SECOND = 50;
  const TRACK_HEIGHT = 60;
  const RULER_HEIGHT = 30;
  const TRACK_LABEL_WIDTH = 180;

  const selectedTimeline = useMemo(
    () => timelines.find((timeline) => timeline.id === selectedTimelineId),
    [selectedTimelineId, timelines],
  );

  const clipsByTrack = useMemo(
    () => tracks.map((track) => ({
      track,
      clips: clips
        .filter((clip) => clip.track_id === track.id)
        .sort((a, b) => (a.position || 0) - (b.position || 0)),
    })),
    [clips, tracks],
  );

  const maxDuration = useMemo(() => {
    const clipEnd = clips.reduce((max, clip) => Math.max(max, Number(clip.position || 0) + Number(clip.duration || 0)), 0);
    return Math.max(clipEnd, selectedTimeline?.total_duration || 0, 1);
  }, [clips, selectedTimeline?.total_duration]);

  const pixelsToSeconds = useCallback((pixels: number) => {
    return pixels / PIXELS_PER_SECOND;
  }, []);

  const secondsToPixels = useCallback((seconds: number) => {
    return seconds * PIXELS_PER_SECOND;
  }, []);

  // Playback controls
  const togglePlayback = useCallback(() => {
    if (isPlaying) {
      if (playIntervalRef.current) {
        clearInterval(playIntervalRef.current);
        playIntervalRef.current = null;
      }
      setIsPlaying(false);
    } else {
      if (playbackTime >= maxDuration) {
        setPlaybackTime(0);
      }
      setIsPlaying(true);
      const fps = selectedTimeline?.fps || 24;
      const interval = 1000 / fps;
      playIntervalRef.current = window.setInterval(() => {
        setPlaybackTime((prev) => {
          if (prev >= maxDuration) {
            if (playIntervalRef.current) clearInterval(playIntervalRef.current);
            setIsPlaying(false);
            return maxDuration;
          }
          return prev + 0.04;
        });
      }, interval) as unknown as number;
    }
  }, [isPlaying, playbackTime, maxDuration, selectedTimeline?.fps]);

  const seekTo = useCallback((time: number) => {
    setPlaybackTime(Math.max(0, Math.min(maxDuration, time)));
  }, [maxDuration]);

  const handleTimelineClick = useCallback((e: React.MouseEvent) => {
    if (!timelineRef.current) return;
    const rect = timelineRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left - TRACK_LABEL_WIDTH;
    if (x >= 0) {
      seekTo(pixelsToSeconds(x));
    }
  }, [pixelsToSeconds, seekTo]);

  // Clip drag handlers
  const handleClipMouseDown = useCallback((
    e: React.MouseEvent,
    clip: Clip,
    dragType: 'move' | 'resize-left' | 'resize-right'
  ) => {
    e.stopPropagation();
    if (clip.is_locked) return;

    setDraggingClip({ clipId: clip.id, type: dragType });
    setDragStartX(e.clientX);
    setDragStartPosition(clip.position);
    setDragStartDuration(clip.duration);
  }, []);

  // Drag mouse event handlers
  useEffect(() => {
    if (!draggingClip) return;

    const handleMouseMove = (e: MouseEvent) => {
      const deltaX = e.clientX - dragStartX;
      const deltaSeconds = pixelsToSeconds(deltaX);

      setClips((prev) => prev.map((clip) => {
        if (clip.id !== draggingClip.clipId) return clip;

        if (draggingClip.type === 'move') {
          const newPosition = Math.max(0, dragStartPosition + deltaSeconds);
          return { ...clip, position: newPosition };
        } else if (draggingClip.type === 'resize-right') {
          const newDuration = Math.max(0.5, dragStartDuration + deltaSeconds);
          return { ...clip, duration: newDuration };
        } else if (draggingClip.type === 'resize-left') {
          const newPosition = Math.max(0, dragStartPosition + deltaSeconds);
          const newDuration = Math.max(0.5, dragStartDuration - deltaSeconds);
          if (newDuration >= 0.5) {
            return { ...clip, position: newPosition, duration: newDuration };
          }
        }
        return clip;
      }));
    };

    const handleMouseUp = async () => {
      if (draggingClip) {
        const updatedClip = clips.find((c) => c.id === draggingClip.clipId);
        if (updatedClip && selectedTimelineId) {
          try {
            await apiClient.updateTimelineClip(selectedTimelineId, draggingClip.clipId, {
              position: updatedClip.position,
              duration: updatedClip.duration,
            });
            setMessage('片段位置已更新');
          } catch (err: any) {
            setError(err?.message || '保存失败');
          }
        }
      }
      setDraggingClip(null);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [draggingClip, dragStartX, dragStartPosition, dragStartDuration, clips, selectedTimelineId, pixelsToSeconds]);

  // Generate timeline preview
  const generatePreview = async () => {
    if (!selectedTimelineId) return;
    setIsGeneratingPreview(true);
    setError(null);
    setMessage(null);
    try {
      const response = await fetch(`${API_BASE}/timelines/${selectedTimelineId}/preview`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });
      if (!response.ok) throw new Error('生成预览失败');
      const result = await response.json();
      setMessage('预览生成成功');
      // Update timeline with new preview URL
      setTimelines((prev) => prev.map((t) =>
        t.id === selectedTimelineId ? { ...t, preview_url: result.preview_url } : t
      ));
    } catch (err: any) {
      setError(err?.message || '生成预览失败');
    } finally {
      setIsGeneratingPreview(false);
    }
  };

  // Cleanup playback on unmount
  useEffect(() => {
    return () => {
      if (playIntervalRef.current) {
        clearInterval(playIntervalRef.current);
      }
    };
  }, []);

  // Generate time ruler marks
  const timeMarks = useMemo(() => {
    const marks: { time: number; label: string; major: boolean }[] = [];
    const step = maxDuration <= 10 ? 1 : maxDuration <= 60 ? 5 : 10;
    for (let t = 0; t <= maxDuration; t += step) {
      marks.push({ time: t, label: formatTime(t), major: t % (step * 2) === 0 });
    }
    return marks;
  }, [maxDuration]);

  // Playhead position
  const playheadX = secondsToPixels(playbackTime);

  // Timeline width
  const timelineWidth = Math.max(760, secondsToPixels(maxDuration) + 200);

  const loadProjects = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getProjects();
      const activeProjects = (Array.isArray(data) ? data : []).filter((project) => project.status !== 'archived');
      setProjects(activeProjects);
      if (!selectedProjectId && activeProjects[0]?.id) {
        setSelectedProjectId(activeProjects[0].id);
      }
    } catch (err: any) {
      setError(err?.message || '加载项目失败');
    } finally {
      setLoading(false);
    }
  };

  const loadTimelines = async (projectId: string) => {
    if (!projectId) {
      setTimelines([]);
      setSelectedTimelineId('');
      return;
    }
    setTimelineLoading(true);
    setError(null);
    try {
      const data = await apiClient.getProjectTimelines(projectId);
      const nextTimelines = Array.isArray(data) ? data : [];
      setTimelines(nextTimelines);
      setSelectedTimelineId((current) => {
        if (current && nextTimelines.some((timeline: Timeline) => timeline.id === current)) return current;
        return nextTimelines[0]?.id || '';
      });
    } catch (err: any) {
      setError(err?.message || '加载时间线失败');
    } finally {
      setTimelineLoading(false);
    }
  };

  const loadTimelineDetail = async (timelineId: string) => {
    if (!timelineId) {
      setTracks([]);
      setClips([]);
      return;
    }
    setTimelineLoading(true);
    setError(null);
    setPlaybackTime(0);
    setIsPlaying(false);
    if (playIntervalRef.current) {
      clearInterval(playIntervalRef.current);
      playIntervalRef.current = null;
    }
    try {
      const [trackData, clipData] = await Promise.all([
        apiClient.getTimelineTracks(timelineId),
        apiClient.getTimelineClips(timelineId),
      ]);
      setTracks(Array.isArray(trackData) ? trackData : []);
      setClips(Array.isArray(clipData) ? clipData : []);
      setClipDrafts({});
    } catch (err: any) {
      setError(err?.message || '加载时间线轨道失败');
    } finally {
      setTimelineLoading(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  useEffect(() => {
    loadTimelines(selectedProjectId);
  }, [selectedProjectId]);

  useEffect(() => {
    loadTimelineDetail(selectedTimelineId);
  }, [selectedTimelineId]);

  const updateClipDraft = (clipId: string, patch: Partial<Clip>) => {
    setClipDrafts((prev) => ({
      ...prev,
      [clipId]: {
        ...prev[clipId],
        ...patch,
      },
    }));
  };

  const saveClip = async (clip: Clip) => {
    if (!selectedTimelineId) return;
    const draft = clipDrafts[clip.id] || {};
    setSavingClipId(clip.id);
    setError(null);
    setMessage(null);
    try {
      const payload = {
        position: Number(draft.position ?? clip.position),
        duration: Math.max(0.1, Number(draft.duration ?? clip.duration)),
        text_content: draft.text_content ?? clip.text_content ?? '',
        name: draft.name ?? clip.name,
        volume: Number(draft.volume ?? clip.volume ?? 1),
      };
      const updated = await apiClient.updateTimelineClip(selectedTimelineId, clip.id, payload);
      setClips((prev) => prev.map((item) => (item.id === clip.id ? updated : item)));
      setClipDrafts((prev) => {
        const next = { ...prev };
        delete next[clip.id];
        return next;
      });
      setMessage('片段已保存');
    } catch (err: any) {
      setError(err?.message || '保存片段失败');
    } finally {
      setSavingClipId(null);
    }
  };

  const deleteClip = async (clip: Clip) => {
    if (!selectedTimelineId) return;
    setSavingClipId(clip.id);
    setError(null);
    setMessage(null);
    try {
      await apiClient.deleteTimelineClip(selectedTimelineId, clip.id);
      setClips((prev) => prev.filter((item) => item.id !== clip.id));
      setMessage('片段已删除');
    } catch (err: any) {
      setError(err?.message || '删除片段失败');
    } finally {
      setSavingClipId(null);
    }
  };

  const toggleTrack = async (track: Track, patch: Partial<Track>) => {
    if (!selectedTimelineId) return;
    setSavingTrackId(track.id);
    setError(null);
    setMessage(null);
    try {
      const updated = await apiClient.updateTimelineTrack(selectedTimelineId, track.id, patch);
      setTracks((prev) => prev.map((item) => (item.id === track.id ? updated : item)));
      setMessage('轨道状态已保存');
    } catch (err: any) {
      setError(err?.message || '保存轨道失败');
    } finally {
      setSavingTrackId(null);
    }
  };

  const addSubtitleClip = async () => {
    if (!selectedTimelineId) return;
    const subtitleTrack = tracks.find((track) => track.track_type === 'subtitle');
    if (!subtitleTrack) {
      setError('当前时间线缺少字幕轨');
      return;
    }

    setAddingSubtitle(true);
    setError(null);
    setMessage(null);
    try {
      const created = await apiClient.createTimelineClip(selectedTimelineId, {
        track_id: subtitleTrack.id,
        source_type: 'subtitle',
        position: maxDuration,
        duration: 4,
        name: `字幕 ${clips.filter((clip) => clip.source_type === 'subtitle').length + 1}`,
        text_content: '请输入字幕',
        font_size: 28,
        font_color: '#FFFFFF',
      });
      setClips((prev) => [...prev, created]);
      setMessage('字幕片段已添加');
    } catch (err: any) {
      setError(err?.message || '添加字幕片段失败');
    } finally {
      setAddingSubtitle(false);
    }
  };

  return (
    <MainLayout>
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-violet-200">
              <Film className="h-5 w-5" />
              <span className="text-sm font-medium">Timeline Editor</span>
            </div>
            <h1 className="mt-2 text-3xl font-bold text-white">时间线编辑</h1>
            <p className="mt-2 max-w-3xl text-sm text-white/60">
              可视化轨道编辑：拖拽调整片段位置和时长，预览播放，与 SynthesisJob 联动生成成片。
            </p>
          </div>
          <Button variant="outline" onClick={() => selectedTimelineId ? loadTimelineDetail(selectedTimelineId) : loadProjects()} disabled={loading || timelineLoading}>
            {(loading || timelineLoading) ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            刷新
          </Button>
        </div>

        {(message || error) && (
          <div className={`rounded-lg border px-4 py-3 text-sm ${error ? 'border-red-500/30 bg-red-500/10 text-red-100' : 'border-green-500/30 bg-green-500/10 text-green-100'}`}>
            {error || message}
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
          <aside className="space-y-4">
            <section className="rounded-lg border border-white/10 bg-white/5 p-4">
              <label className="text-xs font-medium text-white/50">项目</label>
              <select
                value={selectedProjectId}
                onChange={(event) => setSelectedProjectId(event.target.value)}
                className="mt-2 w-full rounded-md border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-violet-400"
              >
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>{project.name}</option>
                ))}
              </select>
              {projects.length === 0 && !loading && (
                <div className="mt-3 text-sm text-white/45">暂无项目。可先通过工作流生成连续成片并同步时间线。</div>
              )}
            </section>

            <section className="rounded-lg border border-white/10 bg-white/5 p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium text-white">时间线</div>
                {timelineLoading && <Loader2 className="h-4 w-4 animate-spin text-white/50" />}
              </div>
              <div className="mt-3 space-y-2">
                {timelines.map((timeline) => (
                  <button
                    key={timeline.id}
                    type="button"
                    onClick={() => setSelectedTimelineId(timeline.id)}
                    className={`w-full rounded-md border px-3 py-2 text-left transition ${selectedTimelineId === timeline.id ? 'border-violet-400 bg-violet-500/15' : 'border-white/10 bg-black/20 hover:border-white/25'}`}
                  >
                    <div className="truncate text-sm font-medium text-white">{timeline.name}</div>
                    <div className="mt-1 text-xs text-white/45">{timeline.aspect_ratio} · {timeline.fps}fps · {formatSeconds(timeline.total_duration)}</div>
                  </button>
                ))}
                {timelines.length === 0 && selectedProjectId && !timelineLoading && (
                  <div className="rounded-md border border-white/10 bg-black/20 p-3 text-sm text-white/45">
                    当前项目暂无时间线。可在工作流合成步骤点击"生成可编辑时间线"。
                  </div>
                )}
              </div>
            </section>

            {/* Quick Stats */}
            {selectedTimeline && (
              <section className="rounded-lg border border-white/10 bg-white/5 p-4">
                <div className="text-sm font-medium text-white mb-3">统计信息</div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-white/50">视频轨</span>
                    <span className="text-white">{tracks.filter((t) => t.track_type === 'video').length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/50">音频轨</span>
                    <span className="text-white">{tracks.filter((t) => t.track_type === 'audio').length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/50">字幕轨</span>
                    <span className="text-white">{tracks.filter((t) => t.track_type === 'subtitle').length}</span>
                  </div>
                  <div className="border-t border-white/10 pt-2 mt-2">
                    <div className="flex justify-between">
                      <span className="text-white/50">总片段</span>
                      <span className="text-white">{clips.length}</span>
                    </div>
                    <div className="flex justify-between mt-1">
                      <span className="text-white/50">总时长</span>
                      <span className="text-white">{formatSeconds(maxDuration)}</span>
                    </div>
                  </div>
                </div>
              </section>
            )}
          </aside>

          <section className="min-w-0 space-y-4">
            {selectedTimeline ? (
              <>
                {/* Header with controls */}
                <div className="rounded-lg border border-white/10 bg-white/5 p-4">
                  <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div className="min-w-0">
                      <h2 className="truncate text-xl font-semibold text-white">{selectedTimeline.name}</h2>
                      <div className="mt-1 flex flex-wrap gap-3 text-sm text-white/50">
                        <span>{selectedTimeline.aspect_ratio}</span>
                        <span>{selectedTimeline.fps}fps</span>
                        <span>片段 {clips.length}</span>
                        <span>时长 {formatSeconds(maxDuration)}</span>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {/* Playback Controls */}
                      <div className="flex items-center gap-1 rounded-md border border-white/10 bg-black/30 p-1">
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={togglePlayback}
                          className="h-8 w-8 text-white hover:bg-white/10"
                        >
                          {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                        </Button>
                        <div className="px-2 text-sm font-mono text-white/70">
                          {formatTime(playbackTime)} / {formatTime(maxDuration)}
                        </div>
                      </div>

                      {/* Generate Preview Button */}
                      <Button
                        variant="outline"
                        onClick={generatePreview}
                        disabled={isGeneratingPreview || clips.length === 0}
                        className="border-white/15"
                      >
                        {isGeneratingPreview ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Film className="mr-2 h-4 w-4" />}
                        生成预览
                      </Button>

                      {/* Open Preview Button */}
                      {selectedTimeline.preview_url && (
                        <a
                          href={toMediaUrl(selectedTimeline.preview_url)}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center gap-2 rounded-md border border-white/15 px-3 py-2 text-sm text-white/70 hover:bg-white/10 hover:text-white"
                        >
                          <Play className="h-4 w-4" />
                          打开预览
                        </a>
                      )}

                      {/* Add Subtitle Button */}
                      <Button
                        variant="outline"
                        onClick={addSubtitleClip}
                        disabled={addingSubtitle || tracks.every((track) => track.track_type !== 'subtitle')}
                        className="border-white/15"
                      >
                        {addingSubtitle ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                        添加字幕
                      </Button>
                    </div>
                  </div>
                </div>

                {/* Visual Timeline Editor */}
                <div className="rounded-lg border border-white/10 bg-slate-950/70 overflow-hidden">
                  {/* Time Ruler */}
                  <div
                    className="relative bg-slate-900/50 border-b border-white/5 cursor-pointer select-none"
                    style={{ height: RULER_HEIGHT, marginLeft: TRACK_LABEL_WIDTH }}
                    onClick={handleTimelineClick}
                  >
                    {/* Time marks */}
                    {timeMarks.map(({ time, label, major }) => (
                      <div
                        key={time}
                        className="absolute top-0 flex flex-col items-center"
                        style={{ left: secondsToPixels(time), transform: 'translateX(-50%)' }}
                      >
                        <div className={`w-px ${major ? 'h-3 bg-white/40' : 'h-2 bg-white/20'}`} />
                        <span className={`text-[10px] ${major ? 'text-white/50' : 'text-white/30'}`}>
                          {label}
                        </span>
                      </div>
                    ))}

                    {/* Playhead marker on ruler */}
                    <div
                      className="absolute top-0 w-0.5 bg-red-500 z-10 pointer-events-none"
                      style={{ left: playheadX, height: RULER_HEIGHT }}
                    >
                      <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-3 h-3 bg-red-500 rounded-full" />
                    </div>
                  </div>

                  {/* Tracks */}
                  <div
                    ref={timelineRef}
                    className="relative overflow-x-auto"
                    style={{ minWidth: timelineWidth + TRACK_LABEL_WIDTH }}
                  >
                    <div style={{ width: timelineWidth + TRACK_LABEL_WIDTH, minWidth: timelineWidth + TRACK_LABEL_WIDTH }}>
                      {clipsByTrack.map(({ track, clips: trackClips }) => {
                        const Icon = trackTypeIcon(track.track_type);
                        const trackColor = trackTypeColors[track.track_type] || '#8B5CF6';

                        return (
                          <div
                            key={track.id}
                            className="flex border-b border-white/5"
                            style={{ height: TRACK_HEIGHT }}
                          >
                            {/* Track Label */}
                            <div
                              className="flex-shrink-0 flex items-center gap-2 px-3 border-r border-white/5"
                              style={{ width: TRACK_LABEL_WIDTH, backgroundColor: `${trackColor}08` }}
                            >
                              <Icon className="h-4 w-4 flex-shrink-0" style={{ color: trackColor }} />
                              <div className="min-w-0 flex-1">
                                <div className="truncate text-sm font-medium text-white">
                                  {track.name || trackTypeLabel[track.track_type]}
                                </div>
                                <div className="text-[10px] text-white/40">{trackTypeLabel[track.track_type]}</div>
                              </div>
                              {track.is_locked && <Lock className="h-3 w-3 text-white/30 flex-shrink-0" />}
                            </div>

                            {/* Track Content */}
                            <div
                              className="relative flex-1 bg-black/20 cursor-pointer"
                              style={{ width: timelineWidth }}
                              onClick={handleTimelineClick}
                            >
                              {/* Grid lines */}
                              {timeMarks.filter((m) => m.major).map(({ time }) => (
                                <div
                                  key={time}
                                  className="absolute top-0 bottom-0 w-px bg-white/5 pointer-events-none"
                                  style={{ left: secondsToPixels(time) }}
                                />
                              ))}

                              {/* Clips */}
                              {trackClips.map((clip) => {
                                const clipX = secondsToPixels(clip.position);
                                const clipWidth = Math.max(20, secondsToPixels(clip.duration));

                                return (
                                  <div
                                    key={clip.id}
                                    className={`absolute top-1 bottom-1 rounded-md border-2 cursor-move select-none transition-shadow ${
                                      clip.is_locked
                                        ? 'opacity-50 cursor-not-allowed'
                                        : 'hover:shadow-lg hover:shadow-black/30'
                                    } ${draggingClip?.clipId === clip.id ? 'ring-2 ring-white/50' : ''}`}
                                    style={{
                                      left: clipX,
                                      width: clipWidth,
                                      backgroundColor: `${trackColor}30`,
                                      borderColor: trackColor,
                                    }}
                                    onMouseDown={(e) => handleClipMouseDown(e, clip, 'move')}
                                  >
                                    {/* Resize handles */}
                                    <div
                                      className="absolute left-0 top-0 bottom-0 w-2 cursor-ew-resize hover:bg-white/20 rounded-l-md"
                                      onMouseDown={(e) => handleClipMouseDown(e, clip, 'resize-left')}
                                    />
                                    <div
                                      className="absolute right-0 top-0 bottom-0 w-2 cursor-ew-resize hover:bg-white/20 rounded-r-md"
                                      onMouseDown={(e) => handleClipMouseDown(e, clip, 'resize-right')}
                                    />

                                    {/* Clip Content */}
                                    <div className="px-2 py-1 overflow-hidden relative z-10">
                                      {track.track_type === 'subtitle' ? (
                                        <div className="text-[11px] text-white truncate">{clip.text_content}</div>
                                      ) : (
                                        <div className="text-[11px] text-white truncate">
                                          {clip.name || clip.source_type}
                                        </div>
                                      )}
                                      <div className="text-[10px] text-white/40">
                                        {formatSeconds(clip.duration)}
                                      </div>
                                    </div>

                                    {/* Thumbnail if available */}
                                    {clip.source_thumbnail && (
                                      <div
                                        className="absolute inset-0 opacity-30 bg-cover bg-center rounded-md pointer-events-none"
                                        style={{ backgroundImage: `url(${toMediaUrl(clip.source_thumbnail)})` }}
                                      />
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })}

                      {/* Playhead line */}
                      <div
                        className="absolute top-0 bottom-0 w-0.5 bg-red-500 pointer-events-none z-20"
                        style={{ left: TRACK_LABEL_WIDTH + playheadX }}
                      >
                        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-2 h-2 bg-red-500 rounded-full" />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Clip Properties Panel */}
                <div className="rounded-lg border border-white/10 bg-white/5 p-4">
                  <div className="text-sm font-medium text-white mb-3">片段详情</div>
                  {clips.length === 0 ? (
                    <div className="text-sm text-white/45">暂无片段 - 拖拽下方片段进行调整</div>
                  ) : (
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {clips.map((clip) => {
                        const track = tracks.find((t) => t.id === clip.track_id);
                        return (
                          <div
                            key={clip.id}
                            className="flex items-center gap-3 rounded-md border border-white/10 bg-black/20 p-2"
                          >
                            <div
                              className="w-3 h-3 rounded-sm flex-shrink-0"
                              style={{ backgroundColor: trackTypeColors[track?.track_type || 'video'] }}
                            />
                            <div className="flex-1 min-w-0">
                              <div className="text-sm text-white truncate">
                                {clip.name || clip.source_type}
                              </div>
                              <div className="text-xs text-white/40">
                                {formatSeconds(clip.position)} - {formatSeconds(clip.position + clip.duration)}
                              </div>
                            </div>
                            <div className="flex gap-1">
                              <Button
                                size="icon"
                                variant="ghost"
                                onClick={() => seekTo(clip.position)}
                                className="h-7 w-7 text-white/50 hover:bg-white/10 hover:text-white"
                              >
                                <Play className="h-3 w-3" />
                              </Button>
                              <Button
                                size="icon"
                                variant="ghost"
                                onClick={() => setDeleteTarget(clip)}
                                className="h-7 w-7 text-red-200 hover:bg-red-500/10 hover:text-red-100"
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Stats Cards */}
                <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                  <div className="rounded-lg border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center gap-2 text-sm text-white/50"><Check className="h-4 w-4" />已落库</div>
                    <div className="mt-2 text-2xl font-semibold text-white">{clips.length}</div>
                    <div className="mt-1 text-xs text-white/45">可编辑 Clip</div>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center gap-2 text-sm text-white/50"><Captions className="h-4 w-4" />字幕片段</div>
                    <div className="mt-2 text-2xl font-semibold text-white">{clips.filter((clip) => clip.source_type === 'subtitle').length}</div>
                    <div className="mt-1 text-xs text-white/45">支持直接修改字幕文本</div>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center gap-2 text-sm text-white/50"><Edit3 className="h-4 w-4" />轨道控制</div>
                    <div className="mt-2 text-2xl font-semibold text-white">{tracks.length}</div>
                    <div className="mt-1 text-xs text-white/45">锁定和静音会即时保存</div>
                  </div>
                  <div className="rounded-lg border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center gap-2 text-sm text-white/50"><Play className="h-4 w-4" />可视化</div>
                    <div className="mt-2 text-2xl font-semibold text-white">{formatSeconds(maxDuration)}</div>
                    <div className="mt-1 text-xs text-white/45">拖拽调整，实时预览</div>
                  </div>
                </div>
              </>
            ) : (
              <div className="rounded-lg border border-white/10 bg-white/5 p-8 text-center">
                <Film className="mx-auto h-10 w-10 text-white/30" />
                <div className="mt-3 text-lg font-medium text-white">请选择时间线</div>
                <div className="mt-2 text-sm text-white/50">如果列表为空，请先在工作流合成步骤生成连续成片清单，并同步为可编辑 Timeline。</div>
              </div>
            )}
          </section>
        </div>
      </div>
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="删除时间线片段"
        description={`确认删除片段"${deleteTarget?.name || deleteTarget?.source_type || ''}"？删除后该片段会从当前时间线移除。`}
        confirmText="删除片段"
        destructive
        loading={Boolean(deleteTarget && savingClipId === deleteTarget.id)}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        onConfirm={async () => {
          if (!deleteTarget) return;
          await deleteClip(deleteTarget);
          setDeleteTarget(null);
        }}
      />
    </MainLayout>
  );
}