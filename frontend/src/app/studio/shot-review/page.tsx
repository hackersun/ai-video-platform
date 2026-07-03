'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { AlertCircle, CheckCircle2, Film, RefreshCcw, RotateCcw } from 'lucide-react';
import { MainLayout } from '@/components/layout/main-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { HistoryReferencePackageEvidence } from '@/components/production/history-preflight-evidence';
import apiClient, { WorkflowRenderArtifacts, WorkflowShotReviewItem, WorkflowShotReviewResponse } from '@/lib/api-client';
import { resumeEpisodePreviewFromConcatenate } from '@/lib/episode-preview-production';

const API_ROOT = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1').replace(/\/api\/v1\/?$/, '');

function mediaUrl(value?: string | null) {
  if (!value) return '';
  if (/^https?:\/\//i.test(value)) return value;
  return `${API_ROOT}${value.startsWith('/') ? value : `/${value}`}`;
}

function statusLabel(status?: string) {
  if (status === 'succeeded' || status === 'completed') return '成功';
  if (status === 'failed') return '失败';
  if (status === 'running') return '生成中';
  return status || '待生成';
}

function evidenceText(value: any) {
  if (value == null || value === '') return '暂无';
  if (typeof value === 'string') return value;
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'object') {
    if (typeof value.message === 'string') return value.message;
    if (typeof value.reason === 'string') return value.reason;
    if (value.ready === true) return '预检通过';
    if (value.ready === false) return '预检未通过';
  }
  return JSON.stringify(value);
}

function visualConsistencyStatusLabel(status?: string | null) {
  if (status === 'passed') return '通过';
  if (status === 'needs_review') return '待人审';
  if (status === 'skipped') return '跳过';
  return status || '未检测';
}

function visualConsistencyScoreText(shot: WorkflowShotReviewItem) {
  const evidence = shot.evidence?.visual_consistency;
  const score = shot.visual_consistency_score ?? evidence?.score;
  if (score == null) return '未检测';
  const rounded = Math.round(Number(score));
  return `${Number.isFinite(rounded) ? rounded : score}分 · ${visualConsistencyStatusLabel(evidence?.status)}`;
}

type ArtifactLinks = {
  outputUrl?: string | null;
  manifestUrl?: string | null;
  previewUrl?: string | null;
  srtUrl?: string | null;
  timelineUrl?: string | null;
  renderManifestUrl?: string | null;
};

const artifactLinkClass = 'rounded-md border border-emerald-200/25 px-3 py-1.5 text-xs text-emerald-50 hover:bg-emerald-200/10';

function artifactsFromReview(artifacts?: WorkflowRenderArtifacts | null): ArtifactLinks {
  return {
    outputUrl: artifacts?.output_url,
    manifestUrl: artifacts?.manifest_url || artifacts?.source_manifest_url,
    previewUrl: artifacts?.preview_url,
    srtUrl: artifacts?.srt_url,
    timelineUrl: artifacts?.timeline_url,
    renderManifestUrl: artifacts?.render_manifest_url,
  };
}

function artifactsFromRenderResult(result: any): ArtifactLinks {
  return {
    outputUrl: result?.outputUrl || result?.output_url,
    manifestUrl: result?.manifestUrl || result?.manifest_url,
    previewUrl: result?.previewUrl || result?.preview_url,
    srtUrl: result?.srtUrl || result?.srt_url,
    timelineUrl: result?.timelineUrl || result?.timeline_url,
    renderManifestUrl: result?.renderManifestUrl || result?.render_manifest_url,
  };
}

function hasArtifactLinks(artifacts: ArtifactLinks) {
  return Boolean(
    artifacts.outputUrl ||
    artifacts.manifestUrl ||
    artifacts.previewUrl ||
    artifacts.srtUrl ||
    artifacts.timelineUrl ||
    artifacts.renderManifestUrl
  );
}

function ReviewArtifactLinks({ artifacts }: { artifacts: ArtifactLinks }) {
  const links = [
    { label: '打开审阅包', url: artifacts.previewUrl },
    { label: '查看成片清单', url: artifacts.manifestUrl },
    { label: '查看字幕', url: artifacts.srtUrl },
    { label: '查看时间线', url: artifacts.timelineUrl },
    { label: '查看渲染清单', url: artifacts.renderManifestUrl },
    { label: '打开成片', url: artifacts.outputUrl },
  ].filter((link) => link.url);

  if (!links.length) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {links.map((link) => (
        <a key={link.label} className={artifactLinkClass} href={mediaUrl(link.url)} target="_blank" rel="noreferrer">
          {link.label}
        </a>
      ))}
    </div>
  );
}

function ShotCard({
  shot,
  selected,
  onSelectedChange,
}: {
  shot: WorkflowShotReviewItem;
  selected: boolean;
  onSelectedChange: (checked: boolean) => void;
}) {
  const isFailed = shot.status === 'failed';
  const video = mediaUrl(shot.video_url);

  return (
    <Card className="overflow-hidden border-white/10 bg-white/[0.04] text-white shadow-none">
      <div className="relative aspect-video bg-slate-950">
        {video ? (
          <video src={video} className="h-full w-full object-cover" controls muted playsInline />
        ) : (
          <div className="flex h-full items-center justify-center text-white/35">
            <Film className="h-10 w-10" aria-hidden="true" />
          </div>
        )}
        <div className="absolute left-3 top-3 flex items-center gap-2">
          <Checkbox checked={selected} onCheckedChange={(value) => onSelectedChange(value === true)} aria-label={`选择镜头 ${shot.shot_number}`} />
          <Badge variant={isFailed ? 'danger' : 'secondary'}>{statusLabel(shot.status)}</Badge>
        </div>
      </div>

      <CardHeader className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="text-lg leading-6">镜头 {shot.shot_number}</CardTitle>
            <p className="mt-1 text-sm text-white/55">{shot.duration || 0}s</p>
          </div>
          <span className="rounded-md bg-white/[0.06] px-2.5 py-1 text-xs text-white/65">
            重生 {shot.regeneration_count || 0} 次
          </span>
        </div>
      </CardHeader>

      <CardContent className="space-y-3 p-4 pt-0">
        <p className="min-h-[2.5rem] text-sm leading-5 text-white/72">{shot.subtitle_text || '暂无字幕/对白'}</p>

        <div className="flex flex-wrap gap-2">
          {(shot.character_names || []).length ? (
            (shot.character_names || []).map((name) => (
              <span key={name} className="rounded-full bg-cyan-400/10 px-2.5 py-1 text-xs text-cyan-100">
                {name}
              </span>
            ))
          ) : (
            <span className="rounded-full bg-white/[0.06] px-2.5 py-1 text-xs text-white/50">未绑定角色</span>
          )}
        </div>

        <div className="grid gap-2 text-xs text-white/70">
          <div className="rounded-md bg-white/[0.05] px-3 py-2">
            <div className="text-white/40">策略路由</div>
            <div className="mt-1 font-medium text-white">{evidenceText(shot.evidence?.strategy_routing)}</div>
          </div>
          <div className="rounded-md bg-white/[0.05] px-3 py-2">
            <div className="text-white/40">参考包</div>
            <div className="mt-1 font-medium text-white">{evidenceText(shot.evidence?.reference_package_mode)}</div>
            <HistoryReferencePackageEvidence
              referencePackage={shot.evidence?.reference_package}
              testId={`shot-review-reference-package-${shot.shot_id}`}
            />
          </div>
          <div className="rounded-md bg-white/[0.05] px-3 py-2">
            <div className="text-white/40">预检</div>
            <div className="mt-1 font-medium text-white">{evidenceText(shot.evidence?.generation_preflight)}</div>
          </div>
          <div
            className="rounded-md bg-white/[0.05] px-3 py-2"
            data-testid={`shot-review-visual-consistency-${shot.shot_id}`}
          >
            <div className="text-white/40">视觉一致性</div>
            <div className="mt-1 font-medium text-white">{visualConsistencyScoreText(shot)}</div>
            {shot.evidence?.visual_consistency?.frame_count != null ? (
              <div className="mt-1 text-white/45">
                抽帧 {shot.evidence.visual_consistency.frame_count}
              </div>
            ) : null}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ShotReviewContent() {
  const searchParams = useSearchParams();
  const workflowId = searchParams.get('workflow_id') || '';
  const [data, setData] = useState<WorkflowShotReviewResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [characterName, setCharacterName] = useState('');
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [renderResult, setRenderResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const loadReview = async () => {
    if (!workflowId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.getWorkflowShotReview(workflowId);
      setData(response);
      setSelectedIds((current) => current.filter((id) => response.shots.some((shot) => shot.shot_id === id)));
    } catch (err: any) {
      setError(err?.message || '镜头审阅加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflowId]);

  const characterOptions = useMemo(() => {
    const values = new Set<string>();
    (data?.shots || []).forEach((shot) => (shot.character_names || []).forEach((name) => values.add(name)));
    return Array.from(values);
  }, [data]);

  const artifactLinks = useMemo(() => {
    const renderArtifacts = artifactsFromRenderResult(renderResult);
    return hasArtifactLinks(renderArtifacts) ? renderArtifacts : artifactsFromReview(data?.latest_render_artifacts);
  }, [data?.latest_render_artifacts, renderResult]);
  const hasArtifacts = hasArtifactLinks(artifactLinks);

  const toggleShot = (shotId: string, checked: boolean) => {
    setSelectedIds((current) => (
      checked ? Array.from(new Set([...current, shotId])) : current.filter((id) => id !== shotId)
    ));
  };

  const runRegeneration = async (mode: 'selected' | 'failed' | 'character') => {
    if (!workflowId) return;
    setActionLoading(mode);
    setError(null);
    setMessage('');
    setRenderResult(null);
    try {
      const payload =
        mode === 'failed'
          ? { filter: 'failed' as const }
          : mode === 'character'
          ? { filter: 'all_selected' as const, character_name: characterName || null }
          : { filter: 'all_selected' as const, shot_ids: selectedIds };
      const result = await apiClient.regenerateWorkflowShots(workflowId, {
        ...payload,
        audio_mode: 'model_audio',
      });

      if (result.ready_for_concatenate !== false && ((result.video_job_ids || []).length || (result.media_job_ids || []).length)) {
        const resumed = await resumeEpisodePreviewFromConcatenate({
          workflowId,
          videoJobIds: result.video_job_ids || [],
          mediaJobIds: result.media_job_ids || [],
          ttsJobIds: result.tts_job_ids || [],
          title: '镜头重生后连续成片',
        });
        setRenderResult(resumed);
        setMessage('已刷新连续成片并生成审阅包');
      } else {
        setMessage('重生任务已提交，等待视频/声音完成后再合成');
      }
      await loadReview();
    } catch (err: any) {
      setError(err?.message || '镜头重生失败');
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="min-h-screen bg-[#10131a] text-white">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-white/10 pb-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-normal">镜头审阅</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-white/60">
              按镜头查看生成状态、参考证据和预检结果，支持只重生需要修复的镜头。
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              onClick={() => runRegeneration('selected')}
              disabled={!selectedIds.length || Boolean(actionLoading)}
              className="bg-cyan-600 text-white hover:bg-cyan-700"
            >
              <RotateCcw className="mr-2 h-4 w-4" aria-hidden="true" />
              重生选中
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => runRegeneration('failed')}
              disabled={Boolean(actionLoading)}
              className="border-white/20 text-white hover:bg-white/10"
            >
              <RefreshCcw className="mr-2 h-4 w-4" aria-hidden="true" />
              仅重生失败
            </Button>
            <select
              value={characterName}
              onChange={(event) => setCharacterName(event.target.value)}
              className="h-10 rounded-md border border-white/15 bg-white/[0.05] px-3 text-sm text-white outline-none"
              aria-label="按角色重生"
            >
              <option value="">选择角色</option>
              {characterOptions.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
            <Button
              type="button"
              variant="outline"
              onClick={() => runRegeneration('character')}
              disabled={!characterName || Boolean(actionLoading)}
              className="border-white/20 text-white hover:bg-white/10"
            >
              按角色重生
            </Button>
          </div>
        </header>

        {!workflowId ? (
          <div className="rounded-md border border-white/10 bg-white/[0.04] p-6 text-sm text-white/65">
            请带上 workflow_id 进入镜头审阅。
          </div>
        ) : null}

        {error ? (
          <div className="flex items-center gap-2 rounded-md border border-red-300/30 bg-red-400/10 px-4 py-3 text-sm text-red-100">
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            {error}
          </div>
        ) : null}

        {(message || hasArtifacts) ? (
          <div className="rounded-md border border-emerald-300/30 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-100">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              {message || '最新审阅包'}
            </div>
            <ReviewArtifactLinks artifacts={artifactLinks} />
          </div>
        ) : null}

        {loading ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {[0, 1, 2].map((item) => <div key={item} className="h-80 animate-pulse rounded-lg bg-white/[0.05]" />)}
          </div>
        ) : null}

        {data && !loading ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.shots.map((shot) => (
              <ShotCard
                key={shot.shot_id}
                shot={shot}
                selected={selectedIds.includes(shot.shot_id)}
                onSelectedChange={(checked) => toggleShot(shot.shot_id, checked)}
              />
            ))}
            {!data.shots.length ? (
              <div className="rounded-md border border-dashed border-white/15 p-6 text-sm text-white/45">
                暂无可审阅镜头
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function StudioShotReviewPage() {
  return (
    <MainLayout>
      <Suspense fallback={<div className="p-6 text-white/60">正在加载镜头审阅…</div>}>
        <ShotReviewContent />
      </Suspense>
    </MainLayout>
  );
}
