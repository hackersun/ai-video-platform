'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Captions,
  Check,
  Clock,
  Edit3,
  Film,
  Loader2,
  Lock,
  Music,
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
  position: number;
  duration: number;
  volume: number;
  text_content?: string;
  name?: string;
  is_locked: boolean;
};

const trackTypeLabel: Record<string, string> = {
  video: '视频轨',
  audio: '音频轨',
  subtitle: '字幕轨',
  effect: '效果轨',
};

const trackTypeIcon = (trackType: string) => {
  if (trackType === 'audio') return Music;
  if (trackType === 'subtitle') return Captions;
  return Film;
};

const formatSeconds = (seconds?: number) => {
  const value = Math.max(0, Number(seconds || 0));
  const mins = Math.floor(value / 60);
  const secs = Math.round(value % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
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
              管理 workflow 生成的可编辑视频轨、对白轨和字幕轨。这里的改动会直接保存到 Timeline/Track/Clip 数据库表。
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
                    当前项目暂无时间线。可在工作流合成步骤点击“生成可编辑时间线”。
                  </div>
                )}
              </div>
            </section>
          </aside>

          <section className="min-w-0 space-y-4">
            {selectedTimeline ? (
              <>
                <div className="rounded-lg border border-white/10 bg-white/5 p-4">
                  <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div className="min-w-0">
                      <h2 className="truncate text-xl font-semibold text-white">{selectedTimeline.name}</h2>
                      <div className="mt-1 flex flex-wrap gap-3 text-sm text-white/50">
                        <span>{selectedTimeline.aspect_ratio}</span>
                        <span>{selectedTimeline.fps}fps</span>
                        <span>{trackTypeLabel.video || '视频轨'} {tracks.filter((track) => track.track_type === 'video').length}</span>
                        <span>片段 {clips.length}</span>
                        <span>时长 {formatSeconds(maxDuration)}</span>
                      </div>
                    </div>
                    {selectedTimeline.preview_url && (
                      <a
                        href={toMediaUrl(selectedTimeline.preview_url)}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-md border border-white/15 px-3 py-2 text-sm text-white/70 hover:bg-white/10 hover:text-white"
                      >
                        打开预览
                      </a>
                    )}
                    <Button
                      variant="outline"
                      onClick={addSubtitleClip}
                      disabled={addingSubtitle || tracks.every((track) => track.track_type !== 'subtitle')}
                      className="border-white/15"
                    >
                      {addingSubtitle ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Captions className="mr-2 h-4 w-4" />}
                      添加字幕片段
                    </Button>
                  </div>
                </div>

                <div className="overflow-x-auto rounded-lg border border-white/10 bg-slate-950/70 p-3">
                  <div className="min-w-[760px] space-y-3">
                    <div className="grid grid-cols-[180px_1fr] gap-3 px-2 text-xs text-white/35">
                      <div>轨道</div>
                      <div className="flex items-center justify-between">
                        <span>片段时间轴</span>
                        <span><Clock className="mr-1 inline h-3 w-3" />{formatSeconds(maxDuration)}</span>
                      </div>
                    </div>

                    {clipsByTrack.map(({ track, clips: trackClips }) => {
                      const Icon = trackTypeIcon(track.track_type);
                      return (
                        <div key={track.id} className="grid grid-cols-[180px_1fr] gap-3 rounded-lg border border-white/10 bg-white/[0.03] p-2">
                          <div className="flex min-h-24 flex-col justify-between rounded-md bg-black/25 p-3">
                            <div>
                              <div className="flex items-center gap-2 text-white">
                                <Icon className="h-4 w-4 text-violet-200" />
                                <span className="truncate text-sm font-medium">{track.name || trackTypeLabel[track.track_type] || track.track_type}</span>
                              </div>
                              <div className="mt-1 text-xs text-white/40">{trackTypeLabel[track.track_type] || track.track_type}</div>
                            </div>
                            <div className="mt-3 flex gap-2">
                              <Button
                                title={track.is_locked ? '解锁轨道' : '锁定轨道'}
                                size="icon"
                                variant="ghost"
                                onClick={() => toggleTrack(track, { is_locked: !track.is_locked })}
                                disabled={savingTrackId === track.id}
                                className="h-8 w-8 text-white/70 hover:bg-white/10 hover:text-white"
                              >
                                {track.is_locked ? <Lock className="h-4 w-4" /> : <Unlock className="h-4 w-4" />}
                              </Button>
                              <Button
                                title={track.is_muted ? '取消静音' : '静音轨道'}
                                size="icon"
                                variant="ghost"
                                onClick={() => toggleTrack(track, { is_muted: !track.is_muted })}
                                disabled={savingTrackId === track.id}
                                className="h-8 w-8 text-white/70 hover:bg-white/10 hover:text-white"
                              >
                                {track.is_muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
                              </Button>
                            </div>
                          </div>

                          <div className="relative min-h-24 rounded-md border border-white/5 bg-black/20 p-2">
                            {trackClips.length === 0 ? (
                              <div className="flex h-full min-h-20 items-center text-sm text-white/35">暂无片段</div>
                            ) : (
                              <div className="space-y-2">
                                {trackClips.map((clip) => {
                                  const draft = clipDrafts[clip.id] || {};
                                  const left = Math.min(92, Math.max(0, ((Number(draft.position ?? clip.position) || 0) / maxDuration) * 100));
                                  const width = Math.min(100 - left, Math.max(8, ((Number(draft.duration ?? clip.duration) || 0.1) / maxDuration) * 100));
                                  return (
                                    <div key={clip.id} className="rounded-md border border-violet-500/25 bg-violet-500/10 p-2">
                                      <div className="mb-2 h-3 rounded bg-white/5">
                                        <div
                                          className="h-3 rounded bg-violet-400/70"
                                          style={{ marginLeft: `${left}%`, width: `${width}%` }}
                                        />
                                      </div>
                                      <div className="grid grid-cols-1 gap-2 lg:grid-cols-[1.2fr_90px_90px_1fr_auto] lg:items-center">
                                        <Input
                                          value={String(draft.name ?? clip.name ?? '')}
                                          onChange={(event) => updateClipDraft(clip.id, { name: event.target.value })}
                                          placeholder="片段名称"
                                          className="border-white/10 bg-slate-950 text-white"
                                        />
                                        <Input
                                          type="number"
                                          min="0"
                                          step="0.1"
                                          value={String(draft.position ?? clip.position ?? 0)}
                                          onChange={(event) => updateClipDraft(clip.id, { position: normalizeNumber(event.target.value, clip.position) })}
                                          title="起始秒"
                                          className="border-white/10 bg-slate-950 text-white"
                                        />
                                        <Input
                                          type="number"
                                          min="0.1"
                                          step="0.1"
                                          value={String(draft.duration ?? clip.duration ?? 0.1)}
                                          onChange={(event) => updateClipDraft(clip.id, { duration: normalizeNumber(event.target.value, clip.duration) })}
                                          title="时长秒"
                                          className="border-white/10 bg-slate-950 text-white"
                                        />
                                        {track.track_type === 'subtitle' ? (
                                          <Input
                                            value={String(draft.text_content ?? clip.text_content ?? '')}
                                            onChange={(event) => updateClipDraft(clip.id, { text_content: event.target.value })}
                                            placeholder="字幕文本"
                                            className="border-white/10 bg-slate-950 text-white"
                                          />
                                        ) : (
                                          <div className="truncate text-xs text-white/45">{clip.source_type}</div>
                                        )}
                                        <div className="flex justify-end gap-1">
                                          <Button
                                            title="保存片段"
                                            size="icon"
                                            variant="ghost"
                                            onClick={() => saveClip(clip)}
                                            disabled={savingClipId === clip.id}
                                            className="h-9 w-9 text-green-200 hover:bg-green-500/10 hover:text-green-100"
                                          >
                                            {savingClipId === clip.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                                          </Button>
                                          <Button
                                            title="删除片段"
                                            size="icon"
                                            variant="ghost"
                                            onClick={() => setDeleteTarget(clip)}
                                            disabled={savingClipId === clip.id}
                                            className="h-9 w-9 text-red-200 hover:bg-red-500/10 hover:text-red-100"
                                          >
                                            <Trash2 className="h-4 w-4" />
                                          </Button>
                                        </div>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
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
        description={`确认删除片段「${deleteTarget?.name || deleteTarget?.source_type || ''}」？删除后该片段会从当前时间线移除。`}
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
