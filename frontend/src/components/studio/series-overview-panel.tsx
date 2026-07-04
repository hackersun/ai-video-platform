'use client';

import { AlertTriangle, CheckCircle2, Film, Gauge, Wand2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import type { StudioSnapshot } from '@/lib/studio-types';

export function SeriesOverviewPanel({
  snapshot,
  onPrimaryAction,
}: {
  snapshot: StudioSnapshot | null;
  onPrimaryAction?: () => void;
}) {
  const score = snapshot?.production_bible_summary?.readiness_score ?? 0;
  const chapterTitle = snapshot?.story_context?.chapter?.title;
  const currentEpisode = snapshot?.series_plan?.current_episode?.title || chapterTitle || '第 1 集';
  const issueCount = snapshot?.issues?.length || 0;
  const strategy = snapshot?.workflow?.latest_production_strategy_label || 'Draft Fast';
  const missingCount = snapshot?.production_bible_summary?.missing_requirements?.length || 0;

  return (
    <Card className="border-cyan-400/20 bg-cyan-500/[0.08]">
      <CardContent className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,0.9fr)_minmax(0,0.8fr)_auto] lg:items-center">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-base font-semibold text-white">
            <Film className="h-5 w-5 shrink-0 text-cyan-300" />
            <span className="truncate">系列动漫工作室</span>
          </div>
          <p className="mt-1 text-sm text-white/60">
            {currentEpisode} · 连续性状态 {score}%
          </p>
        </div>
        <div className="flex min-w-0 items-center gap-2 text-sm text-white/70">
          <Gauge className="h-4 w-4 shrink-0 text-emerald-300" />
          <span className="truncate">模型策略：{strategy}</span>
        </div>
        <div className="flex items-center gap-2">
          {issueCount + missingCount > 0 ? (
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-300" />
          ) : (
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-300" />
          )}
          <Badge variant="outline" className="border-white/15 text-white/70">
            风险 {issueCount} · 缺项 {missingCount}
          </Badge>
        </div>
        <Button onClick={onPrimaryAction} className="gap-2 whitespace-nowrap">
          <Wand2 className="h-4 w-4" />
          下一步
        </Button>
      </CardContent>
    </Card>
  );
}
