'use client';

import { AlertTriangle, BookOpen, Gauge, Loader2, Wand2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { getStudioGuidance } from '@/lib/studio-guidance';
import { studioModeLabels, studioModeTone } from '@/lib/studio-mode';
import type { StudioGuidedAction, StudioRunMode, StudioSnapshot } from '@/lib/studio-types';

export function StudioCommandBar({
  snapshot,
  mode,
  loading,
  onPrimaryAction,
}: {
  snapshot: StudioSnapshot | null;
  mode: StudioRunMode;
  loading?: boolean;
  onPrimaryAction: (action: StudioGuidedAction) => void;
}) {
  const guidance = getStudioGuidance(snapshot);
  const action = guidance.next_action || null;
  const novelTitle = snapshot?.story_context?.novel?.title || snapshot?.workflow?.title || '未命名小说';
  const chapterTitle =
    snapshot?.series_plan?.current_episode?.title ||
    snapshot?.story_context?.chapter?.title ||
    snapshot?.story_context?.storyboard?.title ||
    '当前集';
  const readiness = Math.round(guidance.readiness_score ?? snapshot?.production_bible_summary?.readiness_score ?? 0);
  const blockerCount = guidance.blocker_count ?? snapshot?.mode_policy?.blocking_issue_count ?? snapshot?.issues?.length ?? 0;
  const actionReason = action?.reason || action?.description || '当前快照没有推荐动作，可继续查看工作台状态。';

  return (
    <Card className="border-white/10 bg-white/[0.06]" data-testid="studio-command-bar">
      <CardContent className="grid gap-3 p-3 sm:p-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)_auto] lg:items-center">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            <BookOpen aria-hidden className="h-4 w-4 shrink-0 text-cyan-300" />
            <div className="min-w-0 truncate text-sm font-medium text-white">{novelTitle}</div>
            <Badge variant="outline" className={`shrink-0 ${studioModeTone(mode)}`}>
              {studioModeLabels[mode]}
            </Badge>
          </div>
          <div className="mt-1 min-w-0 truncate text-xs text-white/50">{chapterTitle}</div>
        </div>

        <div className="grid min-w-0 gap-2 sm:grid-cols-[auto_auto_minmax(0,1fr)] sm:items-center">
          <Badge variant="outline" className="w-fit border-emerald-400/25 bg-emerald-500/10 text-emerald-50">
            <Gauge aria-hidden className="mr-1 h-3.5 w-3.5" />
            Readiness {readiness}%
          </Badge>
          <Badge
            variant="outline"
            className={
              blockerCount > 0
                ? 'w-fit border-amber-400/25 bg-amber-500/10 text-amber-50'
                : 'w-fit border-white/15 bg-white/5 text-white/65'
            }
          >
            <AlertTriangle aria-hidden className="mr-1 h-3.5 w-3.5" />
            阻断 {blockerCount}
          </Badge>
          <div className="line-clamp-2 min-w-0 break-words text-xs leading-5 text-white/55">{actionReason}</div>
        </div>

        {action ? (
          <Button
            type="button"
            disabled={loading}
            onClick={() => onPrimaryAction(action)}
            className="min-h-9 w-full min-w-0 gap-2 px-3 text-sm sm:w-auto"
          >
            {loading ? (
              <Loader2 aria-hidden className="h-4 w-4 shrink-0 animate-spin" />
            ) : (
              <Wand2 aria-hidden className="h-4 w-4 shrink-0" />
            )}
            <span className="min-w-0 truncate">{action.label}</span>
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}
