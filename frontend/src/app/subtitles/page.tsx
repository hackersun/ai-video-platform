'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Captions,
  Download,
  FilePlus2,
  Loader2,
  Plus,
  RefreshCw,
  Save,
  Trash2,
} from 'lucide-react';
import { MainLayout } from '@/components/layout/main-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import apiClient from '@/lib/api-client';
import { subtitleQueryContext } from '@/lib/subtitle-query-context';
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const MEDIA_BASE = API_BASE.replace(/\/api\/v1$/, '');

type SubtitleSegment = {
  id: string;
  track_id: string;
  shot_id?: string;
  speaker_name?: string;
  start_seconds: number;
  end_seconds: number;
  text: string;
  source: string;
  review_status: string;
  sort_order: number;
};

type SubtitleTrack = {
  id: string;
  title?: string;
  language: string;
  kind: string;
  source: string;
  status: string;
  workflow_id?: string;
  novel_id?: string;
  chapter_id?: string;
  storyboard_id?: string;
  shot_id?: string;
  media_job_id?: string;
  export_urls?: Record<string, string>;
  segments: SubtitleSegment[];
  created_at: string;
  updated_at: string;
};

type Shot = {
  id: string;
  shot_number: number;
  duration?: number;
  dialogue?: string;
  storyboard_title?: string;
};

const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'draft', label: '草稿' },
  { value: 'exported', label: '已导出' },
  { value: 'reviewed', label: '已审阅' },
];

const formatSeconds = (value?: number) => `${Math.max(0, Number(value || 0)).toFixed(1)}s`;

const mediaUrl = (url?: string) => {
  if (!url) return '';
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
  return `${MEDIA_BASE}${url.startsWith('/') ? url : `/${url}`}`;
};

export default function SubtitlesPage() {
  const [tracks, setTracks] = useState<SubtitleTrack[]>([]);
  const [selectedTrackId, setSelectedTrackId] = useState('');
  const [selectedTrack, setSelectedTrack] = useState<SubtitleTrack | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [shotIdInput, setShotIdInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [savingSegmentId, setSavingSegmentId] = useState<string | null>(null);
  const [creatingFromShot, setCreatingFromShot] = useState(false);
  const [addingSegment, setAddingSegment] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SubtitleSegment | null>(null);
  const [segmentDrafts, setSegmentDrafts] = useState<Record<string, Partial<SubtitleSegment>>>({});
  const [newSegment, setNewSegment] = useState({
    start_seconds: 0,
    end_seconds: 4,
    speaker_name: '',
    text: '',
  });

  const filteredTracks = useMemo(() => {
    if (!statusFilter) return tracks;
    return tracks.filter((track) => track.status === statusFilter);
  }, [tracks, statusFilter]);

  const loadTracks = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getSubtitleTracks(subtitleQueryContext(window.location.search));
      const list = Array.isArray(data) ? data : [];
      setTracks(list);
      setSelectedTrackId((current) => {
        if (current && list.some((track: SubtitleTrack) => track.id === current)) return current;
        return list[0]?.id || '';
      });
    } catch (err: any) {
      setError(err?.message || '加载字幕轨失败');
    } finally {
      setLoading(false);
    }
  };

  const loadTrackDetail = async (trackId: string) => {
    if (!trackId) {
      setSelectedTrack(null);
      return;
    }
    setDetailLoading(true);
    setError(null);
    try {
      const track = await apiClient.getSubtitleTrack(trackId);
      setSelectedTrack(track);
      setSegmentDrafts({});
    } catch (err: any) {
      setError(err?.message || '加载字幕详情失败');
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    loadTracks();
  }, []);

  useEffect(() => {
    loadTrackDetail(selectedTrackId);
  }, [selectedTrackId]);

  const updateDraft = (segmentId: string, patch: Partial<SubtitleSegment>) => {
    setSegmentDrafts((prev) => ({
      ...prev,
      [segmentId]: {
        ...prev[segmentId],
        ...patch,
      },
    }));
  };

  const applySegmentUpdate = (segment: SubtitleSegment) => {
    setSelectedTrack((current) => {
      if (!current) return current;
      return {
        ...current,
        segments: current.segments.map((item) => (item.id === segment.id ? segment : item)),
      };
    });
    setTracks((current) => current.map((track) => {
      if (track.id !== segment.track_id) return track;
      return {
        ...track,
        segments: track.segments.map((item) => (item.id === segment.id ? segment : item)),
      };
    }));
  };

  const saveSegment = async (segment: SubtitleSegment) => {
    const draft = segmentDrafts[segment.id] || {};
    setSavingSegmentId(segment.id);
    setMessage(null);
    setError(null);
    try {
      const payload = {
        speaker_name: draft.speaker_name ?? segment.speaker_name ?? '',
        start_seconds: Number(draft.start_seconds ?? segment.start_seconds),
        end_seconds: Number(draft.end_seconds ?? segment.end_seconds),
        text: draft.text ?? segment.text,
        review_status: draft.review_status ?? segment.review_status,
      };
      const updated = await apiClient.updateSubtitleSegment(segment.track_id, segment.id, payload);
      applySegmentUpdate(updated);
      setSegmentDrafts((prev) => {
        const next = { ...prev };
        delete next[segment.id];
        return next;
      });
      setMessage('字幕段已保存');
    } catch (err: any) {
      setError(err?.message || '保存字幕段失败');
    } finally {
      setSavingSegmentId(null);
    }
  };

  const deleteSegment = async (segment: SubtitleSegment) => {
    setSavingSegmentId(segment.id);
    setMessage(null);
    setError(null);
    try {
      await apiClient.deleteSubtitleSegment(segment.track_id, segment.id);
      setSelectedTrack((current) => {
        if (!current) return current;
        return { ...current, segments: current.segments.filter((item) => item.id !== segment.id) };
      });
      setMessage('字幕段已归档');
    } catch (err: any) {
      setError(err?.message || '归档字幕段失败');
    } finally {
      setSavingSegmentId(null);
    }
  };

  const addSegment = async () => {
    if (!selectedTrackId || !newSegment.text.trim()) {
      setError('请选择字幕轨并填写字幕文本');
      return;
    }
    setAddingSegment(true);
    setMessage(null);
    setError(null);
    try {
      const created = await apiClient.createSubtitleSegment(selectedTrackId, {
        start_seconds: Number(newSegment.start_seconds),
        end_seconds: Number(newSegment.end_seconds),
        speaker_name: newSegment.speaker_name.trim() || undefined,
        text: newSegment.text.trim(),
        source: 'manual',
        review_status: 'pending_review',
      });
      setSelectedTrack((current) => {
        if (!current) return current;
        return { ...current, segments: [...current.segments, created] };
      });
      setNewSegment({ start_seconds: 0, end_seconds: 4, speaker_name: '', text: '' });
      setMessage('字幕段已添加');
    } catch (err: any) {
      setError(err?.message || '添加字幕段失败');
    } finally {
      setAddingSegment(false);
    }
  };

  const createFromShot = async () => {
    if (!shotIdInput.trim()) {
      setError('请输入镜头 ID');
      return;
    }
    setCreatingFromShot(true);
    setMessage(null);
    setError(null);
    try {
      const track = await apiClient.createSubtitleTrackFromShot({ shot_id: shotIdInput.trim() });
      setTracks((current) => [track, ...current.filter((item) => item.id !== track.id)]);
      setSelectedTrackId(track.id);
      setMessage('已从镜头对白生成字幕轨');
    } catch (err: any) {
      setError(err?.message || '从镜头生成字幕轨失败');
    } finally {
      setCreatingFromShot(false);
    }
  };

  const exportTrack = async (format: 'srt' | 'vtt' | 'ass') => {
    if (!selectedTrackId) return;
    setExporting(format);
    setMessage(null);
    setError(null);
    try {
      const result = await apiClient.exportSubtitleTrack(selectedTrackId, format);
      const url = mediaUrl(result.url);
      setSelectedTrack((current) => current ? {
        ...current,
        status: 'exported',
        export_urls: result.export_urls || { ...(current.export_urls || {}), [format]: result.url },
      } : current);
      setTracks((current) => current.map((track) => track.id === selectedTrackId ? {
        ...track,
        status: 'exported',
        export_urls: result.export_urls || { ...(track.export_urls || {}), [format]: result.url },
      } : track));
      setMessage(`${format.toUpperCase()} 已导出`);
      if (url) window.open(url, '_blank');
    } catch (err: any) {
      setError(err?.message || '导出字幕失败');
    } finally {
      setExporting(null);
    }
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-cyan-200">
              <Captions className="h-5 w-5" />
              <span className="text-sm font-medium">Subtitle Workspace</span>
            </div>
            <h1 className="mt-2 text-3xl font-bold text-white">字幕工作台</h1>
            <p className="mt-2 max-w-3xl text-sm text-white/60">
              管理从镜头对白、TTS、直生音视频生成的字幕轨，支持逐段编辑、审阅和 SRT/VTT/ASS 导出。
            </p>
          </div>
          <Button variant="outline" onClick={loadTracks} disabled={loading}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            刷新
          </Button>
        </div>

        {(message || error) && (
          <div className={`rounded-lg border px-4 py-3 text-sm ${error ? 'border-red-500/30 bg-red-500/10 text-red-100' : 'border-green-500/30 bg-green-500/10 text-green-100'}`}>
            {error || message}
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
          <div className="space-y-4">
            <Card className="border-white/10 bg-white/5">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <FilePlus2 className="h-5 w-5 text-cyan-300" />
                  从镜头生成
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Input
                  value={shotIdInput}
                  onChange={(event) => setShotIdInput(event.target.value)}
                  placeholder="镜头 ID"
                  className="border-white/10 bg-white/5 text-white"
                />
                <Button onClick={createFromShot} disabled={creatingFromShot} className="w-full bg-cyan-600 hover:bg-cyan-700">
                  {creatingFromShot ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Captions className="mr-2 h-4 w-4" />}
                  生成字幕轨
                </Button>
              </CardContent>
            </Card>

            <Card className="border-white/10 bg-white/5">
              <CardHeader>
                <CardTitle className="text-white">字幕轨</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} options={statusOptions} />
                {loading ? (
                  <div className="py-8 text-center text-white/50">加载中…</div>
                ) : filteredTracks.length === 0 ? (
                  <div className="rounded-lg border border-white/10 bg-black/20 p-4 text-sm text-white/50">
                    暂无字幕轨。可从视频生成、工作流批量直生，或输入镜头 ID 生成。
                  </div>
                ) : (
                  <div className="space-y-2">
                    {filteredTracks.map((track) => (
                      <button
                        key={track.id}
                        type="button"
                        onClick={() => setSelectedTrackId(track.id)}
                        aria-label={`选择字幕轨 ${track.title || track.id}`}
                        className={`w-full rounded-lg border p-3 text-left transition-colors ${
                          selectedTrackId === track.id
                            ? 'border-cyan-400/50 bg-cyan-500/10'
                            : 'border-white/10 bg-black/20 hover:border-white/20'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="min-w-0 truncate text-sm font-medium text-white">{track.title || '未命名字幕轨'}</div>
                          <Badge variant={track.status === 'exported' ? 'success' : 'outline'} className="text-white/60">{track.status}</Badge>
                        </div>
                        <div className="mt-2 text-xs text-white/45">
                          {track.language} · {track.source} · {track.segments?.length || 0} 段
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="border-white/10 bg-white/5">
            <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <CardTitle className="flex items-center gap-2 text-white">
                <Captions className="h-5 w-5 text-cyan-300" />
                字幕段编辑
              </CardTitle>
              {selectedTrack && (
                <div className="flex flex-wrap gap-2">
                  {(['srt', 'vtt', 'ass'] as const).map((format) => (
                    <Button
                      key={format}
                      size="sm"
                      variant="outline"
                      onClick={() => exportTrack(format)}
                      disabled={exporting === format || selectedTrack.segments.length === 0}
                      className="border-cyan-500/30 text-cyan-100"
                    >
                      {exporting === format ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Download className="mr-1 h-3 w-3" />}
                      {format.toUpperCase()}
                    </Button>
                  ))}
                </div>
              )}
            </CardHeader>
            <CardContent>
              {!selectedTrack ? (
                <div className="py-16 text-center text-white/50">请选择一个字幕轨</div>
              ) : detailLoading ? (
                <div className="py-16 text-center text-white/50">加载字幕详情...</div>
              ) : (
                <div className="space-y-5">
                  <div className="grid grid-cols-1 gap-3 rounded-lg border border-white/10 bg-black/20 p-4 text-sm md:grid-cols-4">
                    <div>
                      <div className="text-white/45">标题</div>
                      <div className="text-white">{selectedTrack.title || '未命名字幕轨'}</div>
                    </div>
                    <div>
                      <div className="text-white/45">来源</div>
                      <div className="text-white">{selectedTrack.source}</div>
                    </div>
                    <div>
                      <div className="text-white/45">关联镜头</div>
                      <div className="text-white">{selectedTrack.shot_id ? selectedTrack.shot_id.slice(0, 8) : '-'}</div>
                    </div>
                    <div>
                      <div className="text-white/45">导出</div>
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(selectedTrack.export_urls || {}).length === 0 ? (
                          <span className="text-white/40">未导出</span>
                        ) : (
                          Object.entries(selectedTrack.export_urls || {}).map(([format, url]) => (
                            <a key={format} href={mediaUrl(url)} target="_blank" className="text-cyan-200 underline">
                              {format.toUpperCase()}
                            </a>
                          ))
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/5 p-4">
                    <div className="mb-3 flex items-center gap-2 text-sm font-medium text-white">
                      <Plus className="h-4 w-4 text-cyan-300" />
                      新增字幕段
                    </div>
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-[120px_120px_160px_minmax(0,1fr)_auto]">
                      <Input
                        type="number"
                        step="0.1"
                        value={newSegment.start_seconds}
                        onChange={(event) => setNewSegment({ ...newSegment, start_seconds: Number(event.target.value) })}
                        className="border-white/10 bg-white/5 text-white"
                      />
                      <Input
                        type="number"
                        step="0.1"
                        value={newSegment.end_seconds}
                        onChange={(event) => setNewSegment({ ...newSegment, end_seconds: Number(event.target.value) })}
                        className="border-white/10 bg-white/5 text-white"
                      />
                      <Input
                        value={newSegment.speaker_name}
                        onChange={(event) => setNewSegment({ ...newSegment, speaker_name: event.target.value })}
                        placeholder="说话人"
                        className="border-white/10 bg-white/5 text-white"
                      />
                      <Input
                        value={newSegment.text}
                        onChange={(event) => setNewSegment({ ...newSegment, text: event.target.value })}
                        placeholder="字幕文本"
                        className="border-white/10 bg-white/5 text-white"
                      />
                      <Button onClick={addSegment} disabled={addingSegment} className="bg-cyan-600 hover:bg-cyan-700">
                        {addingSegment ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                      </Button>
                    </div>
                  </div>

                  {selectedTrack.segments.length === 0 ? (
                    <div className="py-12 text-center text-white/50">当前字幕轨还没有字幕段</div>
                  ) : (
                    <div className="space-y-3">
                      {selectedTrack.segments.map((segment) => {
                        const draft = segmentDrafts[segment.id] || {};
                        return (
                          <div key={segment.id} className="rounded-lg border border-white/10 bg-black/20 p-4">
                            <div className="mb-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                              <div className="flex flex-wrap items-center gap-2 text-xs text-white/50">
                                <Badge variant="outline" className="text-white/60">#{segment.sort_order}</Badge>
                                <span>{formatSeconds(draft.start_seconds ?? segment.start_seconds)} - {formatSeconds(draft.end_seconds ?? segment.end_seconds)}</span>
                                <span>{segment.source}</span>
                                <span>{segment.review_status}</span>
                              </div>
                              <div className="flex gap-2">
                                <Button size="sm" variant="outline" onClick={() => saveSegment(segment)} disabled={savingSegmentId === segment.id} className="border-white/15 text-white/70">
                                  {savingSegmentId === segment.id ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Save className="mr-1 h-3 w-3" />}
                                  保存
                                </Button>
                                <Button size="sm" variant="ghost" onClick={() => setDeleteTarget(segment)} disabled={savingSegmentId === segment.id} className="text-red-300">
                                  <Trash2 className="mr-1 h-3 w-3" />
                                  归档
                                </Button>
                              </div>
                            </div>
                            <div className="grid grid-cols-1 gap-3 md:grid-cols-[120px_120px_160px_160px]">
                              <Input
                                type="number"
                                step="0.1"
                                value={draft.start_seconds ?? segment.start_seconds}
                                onChange={(event) => updateDraft(segment.id, { start_seconds: Number(event.target.value) })}
                                className="border-white/10 bg-white/5 text-white"
                              />
                              <Input
                                type="number"
                                step="0.1"
                                value={draft.end_seconds ?? segment.end_seconds}
                                onChange={(event) => updateDraft(segment.id, { end_seconds: Number(event.target.value) })}
                                className="border-white/10 bg-white/5 text-white"
                              />
                              <Input
                                value={draft.speaker_name ?? segment.speaker_name ?? ''}
                                onChange={(event) => updateDraft(segment.id, { speaker_name: event.target.value })}
                                placeholder="说话人"
                                className="border-white/10 bg-white/5 text-white"
                              />
                              <Select
                                value={draft.review_status ?? segment.review_status}
                                onChange={(event) => updateDraft(segment.id, { review_status: event.target.value })}
                                options={[
                                  { value: 'pending_review', label: '待审核' },
                                  { value: 'approved', label: '已通过' },
                                  { value: 'changes_requested', label: '需修改' },
                                ]}
                              />
                            </div>
                            <Textarea
                              value={draft.text ?? segment.text}
                              onChange={(event) => updateDraft(segment.id, { text: event.target.value })}
                              className="mt-3 min-h-[90px]"
                            />
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="归档字幕段"
        description="确认归档这个字幕段？归档后将从当前字幕轨列表移除。"
        confirmText="归档字幕段"
        destructive
        loading={Boolean(deleteTarget && savingSegmentId === deleteTarget.id)}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        onConfirm={async () => {
          if (!deleteTarget) return;
          await deleteSegment(deleteTarget);
          setDeleteTarget(null);
        }}
      />
    </MainLayout>
  );
}
