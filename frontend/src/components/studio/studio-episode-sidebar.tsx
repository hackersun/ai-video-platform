'use client';

import Link from 'next/link';
import { AlertTriangle, CheckCircle2, Coins, ListTodo } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { getStudioGuidance } from '@/lib/studio-guidance';
import { withStudioContext } from '@/lib/studio-context-links';
import type { StudioSnapshot } from '@/lib/studio-types';
import { StudioModelContracts } from './studio-model-contracts';

function failureEvidence(snapshot: StudioSnapshot) {
  const guidance = getStudioGuidance(snapshot);
  const failedJobs = [
    ...(snapshot.jobs?.video_jobs || []),
    ...(snapshot.jobs?.tts_jobs || []),
    ...(snapshot.jobs?.synthesis_jobs || []),
    ...(snapshot.jobs?.media_jobs || []),
  ].filter((job) => job.status === 'failed');
  return [
    ...(guidance.blockers || []).map((item) => ({ label: item.message || item.code || '未命名阻断', href: item.repair_action?.href })),
    ...failedJobs.map((job) => ({ label: `任务 ${job.id || '未知'} 失败`, href: '/jobs' })),
  ];
}

export function StudioEpisodeSidebar({ snapshot }: { snapshot: StudioSnapshot }) {
  const failures = failureEvidence(snapshot);
  const repairHref = failures.find((failure) => failure.href)?.href || '/jobs';
  return (
    <aside className="flex h-full flex-col gap-3 rounded-xl border border-white/10 bg-white/[0.025] p-3" aria-label="本集运行状态">
      <Card className="border-white/10 bg-white/[0.045]" data-testid="studio-cost-summary">
        <CardContent className="space-y-3 p-4">
          <div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-white">本集概览</h3><Coins className="h-4 w-4 text-violet-300" /></div>
          <div><div className="text-xs text-white/45">本集消耗</div><div className="mt-2 text-lg font-semibold text-white">暂无费用记录</div><div className="mt-1 text-xs leading-5 text-white/45">当前工作台快照没有可对账金额，不展示估算费用。</div></div>
          <Link href="/analytics" className="inline-block text-xs text-violet-300 hover:text-violet-200">查看费用明细 →</Link>
        </CardContent>
      </Card>

      <StudioModelContracts compact />

      <Card className="flex-1 border-white/10 bg-white/[0.045]">
        <CardContent className="space-y-3 p-4">
          <div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-white">失败任务</h3><Badge variant="outline" className={failures.length ? 'border-red-400/25 text-red-200' : 'border-emerald-400/25 text-emerald-200'}>{failures.length}</Badge></div>
          {failures.length ? <>
            <div className="text-2xl font-semibold text-red-300">{failures.length} 个</div>
            <div className="space-y-2">{failures.slice(0, 3).map((failure, index) => <div key={`${failure.label}-${index}`} className="flex items-start gap-2 text-xs leading-5 text-red-50/75"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-300" /><span className="line-clamp-2">{failure.label}</span></div>)}</div>
            <Button asChild size="sm" variant="outline" className="w-full border-violet-400/30 text-violet-200"><Link href={withStudioContext(repairHref, snapshot)}>人工处理</Link></Button>
          </> : <div className="flex items-center gap-2 rounded-lg border border-emerald-400/15 bg-emerald-500/[0.06] px-3 py-2 text-xs text-emerald-100/75"><CheckCircle2 className="h-3.5 w-3.5" />当前没有失败任务</div>}
          <Button asChild size="sm" variant="ghost" className="w-full text-xs text-white/50"><Link href="/jobs"><ListTodo className="mr-1.5 h-3.5 w-3.5" />打开任务中心</Link></Button>
        </CardContent>
      </Card>
    </aside>
  );
}
