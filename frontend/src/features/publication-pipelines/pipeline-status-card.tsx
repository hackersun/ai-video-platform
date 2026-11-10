'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Film, Loader2, Pause, Play, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { resolveMediaUrl, type PublicationPipeline } from '@/lib/api-client';
import { blockerInfo } from '@/lib/blocker-messages';
import { PIPELINE_PHASES, PIPELINE_STEPS, pipelinePhaseIndex, stageLabel } from '@/lib/stage-labels';
import { isPipelineActive } from './use-publication-pipeline';
import { AiGeneratedLabel } from '@/features/legal/ai-generated-label';

const STAGE_ALIAS: Record<string, string> = { ensuring_plan: 'ensuring_run' };

function stepIndex(p: PublicationPipeline) {
  if (p.status === 'succeeded') return PIPELINE_STEPS.length - 1;
  const stage = STAGE_ALIAS[p.stage] || p.stage;
  const idx = PIPELINE_STEPS.indexOf(stage as (typeof PIPELINE_STEPS)[number]);
  return idx < 0 ? 0 : idx;
}

const QUEUE_HINT_AFTER_MS = 20_000;
const STALL_HINT_AFTER_MS = 90_000;

/** 客户端观察到的“无进展时长”，用于在处理节点繁忙/停机时给出明确提示（不依赖服务端时钟）。 */
function useStalledMs(pipeline: PublicationPipeline | null) {
  const signature = pipeline ? `${pipeline.pipeline_id}|${pipeline.status}|${pipeline.stage}|${pipeline.updated_at || ''}` : '';
  const [since, setSince] = useState(() => Date.now());
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { setSince(Date.now()); setNow(Date.now()); }, [signature]);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 5000);
    return () => clearInterval(timer);
  }, []);
  return now - since;
}

/** 后端对 ?download=1 返回 Content-Disposition: attachment，前后端分域时也能直接保存。 */
function downloadUrl(url: string) {
  return `${url}${url.includes('?') ? '&' : '?'}download=1`;
}

function resolveHref(href: string, novelId: string) {
  return href.startsWith('?') ? `/novels/${novelId}${href}` : href;
}

export function PipelineStatusCard({
  novelId, pipeline, loading, busy, error, onPause, onResume, onCancel,
}: {
  novelId: string; pipeline: PublicationPipeline | null; loading: boolean; busy: boolean; error: string;
  onPause: () => void; onResume: () => void; onCancel: () => void;
}) {
  const stalledMs = useStalledMs(pipeline);
  if (loading) return null;
  if (!pipeline) {
    return (
      <div data-testid="pipeline-status-card" className="rounded-xl border border-white/10 bg-white/[0.04] p-4 text-sm text-white/60">
        <div className="flex items-center gap-2 font-medium text-white"><Film className="h-4 w-4" />还没有生成过视频</div>
        <p className="mt-1">准备好 2 章以上内容后，点右上角「一键生成视频」，系统会自动完成剧本、分镜、画面、配音和拼接。</p>
        {error && <p className="mt-2 text-red-200">{error}</p>}
      </div>
    );
  }
  const current = stepIndex(pipeline);
  const active = isPipelineActive(pipeline);
  const done = pipeline.status === 'succeeded';
  const needsHelp = pipeline.status === 'blocked' || pipeline.status === 'failed';
  const blocker = needsHelp ? blockerInfo(pipeline.blocker_code, pipeline.blocker_detail) : null;
  const videoUrl = resolveMediaUrl(pipeline.final_video_url);
  const queued = pipeline.status === 'queued' || (active && pipeline.stage === 'accepted');
  const statusText = done ? '已完成' : pipeline.status === 'paused' ? '已暂停' : pipeline.status === 'cancelled' ? '已取消' : needsHelp ? '需处理' : queued ? '排队中，等待处理' : `进行中：${PIPELINE_PHASES[pipelinePhaseIndex(STAGE_ALIAS[pipeline.stage] || pipeline.stage)].label}`;
  const waitHint = !active ? '' : queued && stalledMs >= QUEUE_HINT_AFTER_MS
    ? '处理节点繁忙或暂未启动。任务已保存，节点恢复后会自动开始，无需重复提交。'
    : !queued && stalledMs >= STALL_HINT_AFTER_MS ? '当前步骤暂无新进展，正在等待处理节点响应；中断的任务会被自动接管继续。' : '';
  const tone = done ? 'border-emerald-400/25 bg-emerald-500/10' : needsHelp ? 'border-amber-400/30 bg-amber-500/10' : 'border-violet-400/25 bg-violet-500/10';

  return (
    <div data-testid="pipeline-status-card" className={`space-y-4 rounded-xl border p-4 ${tone}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 font-medium text-white">
          {done ? <CheckCircle2 className="h-5 w-5 text-emerald-300" /> : needsHelp ? <AlertCircle className="h-5 w-5 text-amber-300" /> : active ? <Loader2 className="h-5 w-5 animate-spin text-violet-300" /> : <Film className="h-5 w-5" />}
          一键生成视频 · {statusText}
        </div>
        <div className="flex gap-2">
          {active && <Button size="sm" variant="outline" disabled={busy} onClick={onPause}><Pause className="mr-1 h-4 w-4" />暂停</Button>}
          {(pipeline.status === 'paused' || needsHelp) && <Button size="sm" disabled={busy} onClick={onResume}><Play className="mr-1 h-4 w-4" />继续</Button>}
          {(active || pipeline.status === 'paused' || needsHelp) && <Button size="sm" variant="ghost" disabled={busy} onClick={onCancel}><X className="mr-1 h-4 w-4" />取消</Button>}
        </div>
      </div>

      <ol className="grid grid-cols-2 gap-1 sm:grid-cols-4" aria-label="生成进度" data-testid="pipeline-phases">
        {PIPELINE_PHASES.map((phase, i) => {
          const currentPhase = done ? PIPELINE_PHASES.length : pipelinePhaseIndex(PIPELINE_STEPS[current]);
          const state = i < currentPhase ? 'done' : i === currentPhase ? (needsHelp ? 'blocked' : 'current') : 'todo';
          const cls = state === 'done' ? 'bg-emerald-500/25 text-emerald-100' : state === 'current' ? 'bg-violet-500/40 text-white' : state === 'blocked' ? 'bg-amber-500/40 text-white' : 'bg-white/5 text-white/40';
          return <li key={phase.id} className={`rounded px-2 py-1 text-center text-xs ${cls}`}>{phase.label}</li>;
        })}
      </ol>
      <details className="text-xs text-white/50" data-testid="pipeline-step-details">
        <summary className="cursor-pointer select-none">查看详情</summary>
        <ol className="mt-2 grid grid-cols-3 gap-1 sm:grid-cols-5 lg:grid-cols-9" aria-label="详细步骤">
          {PIPELINE_STEPS.map((step, i) => {
            const state = i < current || done ? 'done' : i === current ? (needsHelp ? 'blocked' : 'current') : 'todo';
            const cls = state === 'done' ? 'bg-emerald-500/15 text-emerald-100/80' : state === 'current' ? 'bg-violet-500/30 text-white' : state === 'blocked' ? 'bg-amber-500/30 text-white' : 'bg-white/5 text-white/30';
            return <li key={step} className={`rounded px-2 py-1 text-center ${cls}`}>{stageLabel(step)}</li>;
          })}
        </ol>
      </details>

      {waitHint && <p data-testid="pipeline-wait-hint" role="status" className="rounded-md bg-black/20 p-3 text-sm text-white/80">{waitHint}</p>}
      {blocker && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-black/20 p-3 text-sm">
          <div><div className="font-medium text-amber-100">{blocker.title}</div><div className="text-white/70">{blocker.hint}</div></div>
          {blocker.href && <Button asChild size="sm"><Link href={resolveHref(blocker.href, novelId)}>{blocker.action || '去处理'}</Link></Button>}
        </div>
      )}
      {error && <div role="alert" className="text-sm text-red-200">{error}</div>}

      {done && videoUrl && (
        <div className="space-y-2">
          <AiGeneratedLabel />
          <video data-testid="pipeline-final-video" src={videoUrl} controls className="w-full max-w-2xl rounded-lg bg-black" />
          <div className="flex gap-2">
            {pipeline.publication_id && <Button asChild size="sm" className="bg-emerald-600 hover:bg-emerald-700"><Link href={`/synthesis?publication_id=${pipeline.publication_id}`}>查看发布</Link></Button>}
            <Button asChild size="sm" variant="outline"><a href={downloadUrl(videoUrl)} download>下载视频</a></Button>
          </div>
        </div>
      )}
    </div>
  );
}
