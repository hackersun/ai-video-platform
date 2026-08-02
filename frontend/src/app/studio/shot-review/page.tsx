'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { AlertCircle, CheckCircle2, RefreshCcw, RotateCcw } from 'lucide-react';
import { MainLayout } from '@/components/layout/main-layout';
import { Button } from '@/components/ui/button';
import { ShotReviewCard } from '@/components/studio/shot-review-card';
import apiClient, { WorkflowRenderArtifacts, WorkflowShotReviewResponse } from '@/lib/api-client';
import { resumeEpisodePreviewFromConcatenate } from '@/lib/episode-preview-production';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const API_ROOT = API_BASE.replace(/\/api\/v1\/?$/, '');

function mediaUrl(value?: string | null) {
  if (!value) return '';
  if (/^https?:\/\//i.test(value)) return value;
  return `${API_ROOT}${value.startsWith('/') ? value : `/${value}`}`;
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

type ShotReviewReferenceFields = {
  reference_image_url?: string | null;
};

function referenceRepairHref(rawQuery: string) {
  const current = new URLSearchParams(rawQuery);
  const context = new URLSearchParams();
  ['novel_id', 'chapter_id', 'script_id', 'storyboard_id'].forEach((key) => {
    const value = current.get(key);
    if (value) context.set(key, value);
  });
  context.set('source', 'studio');
  context.set('return_to', `/studio/shot-review?${current.toString()}`);
  return `/assets?${context.toString()}`;
}

function ShotReviewContent() {
  const searchParams = useSearchParams();
  const queryString = searchParams.toString();
  const workflowId = searchParams.get('workflow_id') || '';
  const targetShotId = searchParams.get('shot_id') || '';
  const focus = searchParams.get('focus') || '';
  const sourceIssueCode = searchParams.get('source_issue_code') || searchParams.get('source_issue') || '';
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
      setSelectedIds((current) => {
        const availableShotIds = new Set(response.shots.map((shot) => shot.shot_id));
        const next = current.filter((id) => availableShotIds.has(id));
        if (targetShotId && availableShotIds.has(targetShotId) && !next.includes(targetShotId)) {
          next.unshift(targetShotId);
        }
        return next;
      });
    } catch (err: any) {
      setError(err?.message || '镜头审阅加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflowId, targetShotId]);

  useEffect(() => {
    if (!targetShotId || !data || loading) return;
    document.getElementById(`shot-review-${targetShotId}`)?.scrollIntoView({ block: 'center' });
  }, [data, loading, targetShotId]);

  const characterOptions = useMemo(() => {
    const values = new Set<string>();
    (data?.shots || []).forEach((shot) => (shot.character_names || []).forEach((name) => values.add(name)));
    return Array.from(values);
  }, [data]);

  const artifactLinks = useMemo(() => {
    const renderArtifacts = artifactsFromRenderResult(renderResult);
    return hasArtifactLinks(renderArtifacts) ? renderArtifacts : artifactsFromReview(data?.latest_render_artifacts);
  }, [data?.latest_render_artifacts, renderResult]);
  const assetHref = useMemo(() => referenceRepairHref(queryString), [queryString]);
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
        native_audio: true,
      });
      const concatenateVideoJobIds = result.concatenate_video_job_ids || result.video_job_ids || [];
      const concatenateMediaJobIds = result.concatenate_media_job_ids || result.media_job_ids || [];
      const concatenateTtsJobIds = result.concatenate_tts_job_ids || result.tts_job_ids || [];

      if (result.ready_for_concatenate !== false && (concatenateVideoJobIds.length || concatenateMediaJobIds.length)) {
        const resumed = await resumeEpisodePreviewFromConcatenate({
          workflowId,
          videoJobIds: concatenateVideoJobIds,
          mediaJobIds: concatenateMediaJobIds,
          ttsJobIds: concatenateTtsJobIds,
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

  const runQualityRepair = async (shotId: string, issueCode: string) => {
    const actionKey = `quality-${shotId}`;
    setActionLoading(actionKey);
    setError(null);
    setMessage('');
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE}/workflow/${workflowId}/quality/repair`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ shot_id: shotId, issue_code: issueCode }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result?.detail || '最小返修失败');
      setMessage(`已完成最小返修；未改动 ${(result.unchanged_artifact_ids || []).length} 个无关任务`);
      await loadReview();
    } catch (err: any) {
      setError(err?.message || '最小返修失败');
    } finally {
      setActionLoading(null);
    }
  };

  const runQualityEvaluation = async (shotId: string) => {
    const actionKey = `quality-${shotId}`;
    setActionLoading(actionKey);
    setError(null);
    setMessage('');
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE}/workflow/${workflowId}/quality/evaluate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ shot_id: shotId }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result?.detail === 'string' ? result.detail : '质量评估失败');
      setMessage(result.ready ? '交付检查通过' : `交付检查发现 ${(result.blockers || []).length} 项需要处理`);
      await loadReview();
    } catch (err: any) {
      setError(err?.message || '质量评估失败');
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
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

        {focus === 'references' ? (
          <section data-testid="shot-reference-guide" className="rounded-xl border border-cyan-300/25 bg-cyan-400/[0.07] p-4 sm:p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h2 className="text-base font-semibold text-cyan-50">镜头参考检查怎么处理</h2>
                <ol className="mt-2 grid gap-2 text-sm leading-6 text-white/65 sm:grid-cols-3">
                  <li><span className="mr-2 text-cyan-300">1</span>对照参考图与当前视频</li>
                  <li><span className="mr-2 text-cyan-300">2</span>核对角色、场景和道具名字</li>
                  <li><span className="mr-2 text-cyan-300">3</span>有误先修复引用，再回来重新检查</li>
                </ol>
              </div>
              <Button asChild variant="outline" className="shrink-0"><Link href={assetHref}>打开资产工作台修复引用</Link></Button>
            </div>
          </section>
        ) : null}

        {sourceIssueCode ? (
          <div className="rounded-md border border-amber-300/25 bg-amber-400/10 px-4 py-3 text-sm text-amber-50">
            来自问题：{sourceIssueCode}
          </div>
        ) : null}

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
          <div className="space-y-4">
            {[0, 1].map((item) => <div key={item} className="h-96 animate-pulse rounded-xl bg-white/[0.05]" />)}
          </div>
        ) : null}

        {data && !loading ? (
          <div className="space-y-5">
            {data.shots.map((shot) => (
              <ShotReviewCard
                key={shot.shot_id}
                shot={shot}
                referenceImageUrl={mediaUrl((shot as typeof shot & ShotReviewReferenceFields).reference_image_url)}
                videoUrl={mediaUrl(shot.video_url)}
                assetHref={assetHref}
                selected={selectedIds.includes(shot.shot_id)}
                target={targetShotId === shot.shot_id}
                onSelectedChange={(checked) => toggleShot(shot.shot_id, checked)}
                repairLoading={actionLoading === `quality-${shot.shot_id}`}
                onQualityRepair={runQualityRepair}
                onQualityEvaluate={runQualityEvaluation}
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
