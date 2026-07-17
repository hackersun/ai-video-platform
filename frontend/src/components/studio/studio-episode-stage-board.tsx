'use client';

import Link from 'next/link';
import { AlertCircle, CheckCircle2, FileText, Layers3, Lock, MoreHorizontal, ShieldCheck, Video } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { withStudioContext, withStudioQuickAction } from '@/lib/studio-context-links';
import type { StudioSnapshot } from '@/lib/studio-types';
import { buildEpisodeBoard, type BoardLane } from './studio-episode-board-data';

const laneIcons = { assets: Lock, story: Layers3, shots: Video, review: ShieldCheck };

function StageLane({ lane, snapshot }: { lane: BoardLane; snapshot: StudioSnapshot }) {
  const completed = lane.items.filter((item) => item.ready).length;
  const Icon = laneIcons[lane.id];
  return (
    <article className="flex min-w-0 flex-col border-b border-white/10 p-3.5 last:border-b-0 md:border-b-0 md:border-r md:last:border-r-0">
      <div className="flex items-center justify-between gap-2"><h3 className="flex items-center gap-2 text-base font-semibold text-white"><Icon className="h-4 w-4 text-cyan-300" />{lane.title}</h3><span className="text-xs text-white/45">{completed}/{lane.items.length}</span></div>
      <div className="mt-3 flex-1 space-y-2.5">
        {lane.items.map((item) => (
          <div key={item.label} data-testid={item.testId} className={`rounded-lg border p-3 ${item.warning ? 'border-amber-400/20 bg-amber-500/[0.045]' : 'border-white/10 bg-black/20'}`}>
            <div className="flex items-start justify-between gap-2"><div className="text-sm font-medium text-white/80">{item.label}</div>{item.ready ? <CheckCircle2 aria-label="已完成" className="h-4 w-4 shrink-0 text-emerald-300" /> : <AlertCircle aria-label="待处理" className={`h-4 w-4 shrink-0 ${item.warning ? 'text-amber-300' : 'text-white/30'}`} />}</div>
            <div className="mt-2 text-xs text-white/65">{item.value}</div>
            {item.meta ? <div className="mt-1 flex items-center justify-between gap-2 text-[11px] leading-4 text-white/40"><span className="truncate">{item.meta}</span><Link data-testid={`studio-quick-action-${item.actionId}`} className="shrink-0 rounded border border-violet-400/20 px-2 py-0.5 text-violet-200/80 hover:bg-violet-500/10" href={withStudioQuickAction(item.href, snapshot)}>去处理</Link></div> : null}
            {item.details?.length ? <div className="mt-2 space-y-1 border-t border-white/10 pt-2">{item.details.map((detail) => <div key={detail} className="truncate text-[11px] text-amber-100/70">{detail}</div>)}</div> : null}
          </div>
        ))}
      </div>
    </article>
  );
}

function formatDuration(seconds: number) {
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

export function StudioEpisodeStageBoard({ snapshot }: { snapshot: StudioSnapshot }) {
  const shots = snapshot.shots || [];
  const totalShots = snapshot.production?.shot_count || shots.length;
  const completedShots = shots.filter((shot) => shot.video_status === 'succeeded').length;
  const pendingShots = Math.max(totalShots - completedShots, 0);
  const duration = shots.reduce((sum, shot) => sum + (shot.duration || 0), 0);
  const chapterTitle = snapshot.story_context?.chapter?.title || '当前集';
  const workflowId = snapshot.workflow?.id || '';
  const lanes = buildEpisodeBoard(snapshot);

  return (
    <section className="overflow-hidden rounded-xl border border-white/10 bg-white/[0.035]" data-testid="studio-episode-stage-board">
      <div className="flex flex-col gap-3 border-b border-white/10 px-4 py-3.5 lg:flex-row lg:items-center lg:justify-between" data-testid="studio-episode-board-header">
        <div><div className="flex flex-wrap items-center gap-2"><h2 className="text-lg font-semibold text-white">{chapterTitle} 制作看板</h2><Badge variant="outline" className="border-cyan-400/20 text-cyan-100">进行中</Badge></div><div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-white/45"><span>总镜头 {totalShots}</span><span>完成 {completedShots}</span><span>待处理 {pendingShots}</span><span>预计时长 {formatDuration(duration)}</span></div></div>
        <div className="flex gap-2"><Button asChild size="sm" variant="outline" className="border-white/15 text-white/70"><Link href={withStudioContext('/studio/shot-review', snapshot)}><FileText className="mr-1 h-3.5 w-3.5" />集信息</Link></Button><Button asChild size="sm" className="bg-violet-600 hover:bg-violet-500"><Link href={withStudioContext(`/workflow${workflowId ? `?workflow_id=${workflowId}` : ''}`, snapshot)}><MoreHorizontal className="mr-1 h-3.5 w-3.5" />进入成片复审</Link></Button></div>
      </div>
      <div className="grid md:grid-cols-2 xl:grid-cols-4">{lanes.map((lane) => <StageLane key={lane.id} lane={lane} snapshot={snapshot} />)}</div>
    </section>
  );
}
