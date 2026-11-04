'use client';

import { AlertTriangle, CheckCircle2, Gauge, ShieldCheck } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { StudioSnapshot } from '@/lib/studio-types';

/** One-line series status strip shown under the studio header. */
export function SeriesOverviewPanel({ snapshot }: { snapshot: StudioSnapshot | null }) {
  const score = snapshot?.production_bible_summary?.readiness_score ?? 0;
  const chapterTitle = snapshot?.story_context?.chapter?.title;
  const currentEpisode = snapshot?.series_plan?.current_episode?.title || chapterTitle || '第 1 集';
  const issueCount = snapshot?.issues?.length || 0;
  const strategy = snapshot?.workflow?.latest_production_strategy_label || 'Draft Fast';
  const missingCount = snapshot?.production_bible_summary?.missing_requirements?.length || 0;

  return (
    <div
      className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-cyan-400/20 bg-cyan-500/[0.06] px-3 py-2 text-sm text-white/70"
      data-testid="series-overview-strip"
    >
      <span className="flex min-w-0 items-center gap-1.5">
        <ShieldCheck className="h-4 w-4 shrink-0 text-cyan-300" aria-hidden />
        <span className="truncate">{currentEpisode} · 连续性状态 {score}%</span>
      </span>
      <span className="flex min-w-0 items-center gap-1.5">
        <Gauge className="h-4 w-4 shrink-0 text-emerald-300" aria-hidden />
        <span className="truncate">模型策略：{strategy}</span>
      </span>
      <span className="flex items-center gap-1.5">
        {issueCount + missingCount > 0 ? (
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-300" aria-hidden />
        ) : (
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-300" aria-hidden />
        )}
        <Badge variant="outline" className="border-white/15 text-white/70">
          风险 {issueCount} · 缺项 {missingCount}
        </Badge>
      </span>
    </div>
  );
}
