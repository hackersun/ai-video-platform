'use client';

import Link from 'next/link';
import { AlertTriangle, CheckCircle2, Coins, ListTodo } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { getStudioGuidance } from '@/lib/studio-guidance';
import { buildStudioRepairOption, type StudioRepairOption } from '@/lib/studio-repair-options';
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
    ...(guidance.blockers || []).map((item) => buildStudioRepairOption(item, snapshot)),
    ...failedJobs.map((job): StudioRepairOption => ({
      key: `failed-job-${job.id || 'unknown'}`,
      title: `任务 ${job.id || '未知'} 执行失败`,
      description: '进入任务中心查看失败原因，修正配置后再重试。',
      buttonLabel: '查看失败原因',
      href: '/jobs',
    })),
  ];
}

export function StudioEpisodeSidebar({ snapshot }: { snapshot: StudioSnapshot }) {
  const failures = failureEvidence(snapshot);
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
          <div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-white">待处理事项</h3><Badge variant="outline" className={failures.length ? 'border-red-400/25 text-red-200' : 'border-emerald-400/25 text-emerald-200'}>{failures.length}</Badge></div>
          {failures.length ? <>
            <div className="text-2xl font-semibold text-red-300">{failures.length} 个</div>
            <div className="space-y-3">{failures.slice(0, 3).map((failure) => <div key={failure.key} className="rounded-lg border border-red-400/15 bg-red-500/[0.06] p-3"><div className="flex items-start gap-2 text-xs font-medium leading-5 text-red-50"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-300" /><span>{failure.title}</span></div><p className="mt-1.5 text-xs leading-5 text-white/55">{failure.description}</p><Button asChild size="sm" variant="outline" className="mt-2 w-full border-violet-400/30 text-violet-200"><Link href={failure.href}>{failure.buttonLabel}</Link></Button></div>)}</div>
          </> : <div className="flex items-center gap-2 rounded-lg border border-emerald-400/15 bg-emerald-500/[0.06] px-3 py-2 text-xs text-emerald-100/75"><CheckCircle2 className="h-3.5 w-3.5" />当前没有失败任务</div>}
          <Button asChild size="sm" variant="ghost" className="w-full text-xs text-white/50"><Link href="/jobs"><ListTodo className="mr-1.5 h-3.5 w-3.5" />打开任务中心</Link></Button>
        </CardContent>
      </Card>
    </aside>
  );
}
