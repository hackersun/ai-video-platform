'use client';

import { AlertTriangle, CheckCircle2, CircleDotDashed, Route } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { getStudioGuidance } from '@/lib/studio-guidance';
import { cn } from '@/lib/utils';
import type { StudioGuidanceStage, StudioSnapshot } from '@/lib/studio-types';

const stageOrder = ['content', 'bible', 'episode', 'draft', 'review'];

function stageTone(status?: string) {
  if (status === 'ready') return 'border-emerald-400/25 bg-emerald-500/10 text-emerald-50';
  if (status === 'blocked') return 'border-amber-400/25 bg-amber-500/10 text-amber-50';
  return 'border-cyan-400/20 bg-cyan-500/10 text-cyan-50';
}

function StageIcon({ status }: { status?: string }) {
  if (status === 'ready') return <CheckCircle2 aria-hidden className="h-4 w-4 shrink-0 text-emerald-300" />;
  if (status === 'blocked') return <AlertTriangle aria-hidden className="h-4 w-4 shrink-0 text-amber-300" />;
  return <CircleDotDashed aria-hidden className="h-4 w-4 shrink-0 text-cyan-300" />;
}

function sortStages(stages: StudioGuidanceStage[]) {
  return [...stages].sort((a, b) => {
    const aIndex = stageOrder.indexOf(a.id);
    const bIndex = stageOrder.indexOf(b.id);
    return (aIndex === -1 ? stageOrder.length : aIndex) - (bIndex === -1 ? stageOrder.length : bIndex);
  });
}

export function StudioStageFlow({ snapshot }: { snapshot: StudioSnapshot | null }) {
  const stages = sortStages(getStudioGuidance(snapshot).stages || []);

  if (!stages.length) {
    return (
      <Card className="border-white/10 bg-white/[0.04]" data-testid="studio-stage-flow">
        <CardContent className="space-y-2 p-3">
          <div className="flex min-w-0 items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2 text-sm font-medium text-white">
              <Route aria-hidden className="h-4 w-4 shrink-0 text-cyan-300" />
              <span className="truncate">制作主线</span>
            </div>
            <Badge variant="outline" className="shrink-0 border-white/15 text-white/60">
              0阶段
            </Badge>
          </div>
          <div className="text-xs text-white/45">暂无阶段流数据。</div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-white/10 bg-white/[0.04]" data-testid="studio-stage-flow">
      <CardContent className="space-y-2 p-3">
        <div className="flex min-w-0 items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2 text-sm font-medium text-white">
            <Route aria-hidden className="h-4 w-4 shrink-0 text-cyan-300" />
            <span className="truncate">制作主线</span>
          </div>
          <Badge variant="outline" className="shrink-0 border-white/15 text-white/60">
            {stages.length}阶段
          </Badge>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          {stages.map((stage) => (
            <div key={stage.id} className={cn('min-w-0 rounded-lg border px-3 py-2', stageTone(stage.status))}>
              <div className="flex min-w-0 items-center gap-2">
                <StageIcon status={stage.status} />
                <div className="min-w-0 truncate text-sm font-medium">{stage.label}</div>
              </div>
              {stage.description ? (
                <div className="mt-1 line-clamp-2 break-words text-xs leading-5 text-white/50">{stage.description}</div>
              ) : null}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
