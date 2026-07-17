'use client';

import { AlertTriangle, BookOpen, Gauge, Loader2, RotateCcw, ShieldCheck, TestTube2, Wand2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { getStudioGuidance } from '@/lib/studio-guidance';
import type { StudioGuidedAction, StudioRunMode, StudioSnapshot } from '@/lib/studio-types';

export function StudioCommandBar({ snapshot, mode, loading, onModeChange, onPrimaryAction }: {
  snapshot: StudioSnapshot | null;
  mode: StudioRunMode;
  loading?: boolean;
  onModeChange: (mode: StudioRunMode) => void;
  onPrimaryAction: (action: StudioGuidedAction) => void;
}) {
  const guidance = getStudioGuidance(snapshot);
  const action = guidance.recommended_action || guidance.next_action || null;
  const secondary = guidance.secondary_actions?.[0] || null;
  const novelTitle = snapshot?.story_context?.novel?.title || snapshot?.workflow?.title || '未命名小说';
  const chapterTitle = snapshot?.series_plan?.current_episode?.title || snapshot?.story_context?.chapter?.title || '当前集';
  const readiness = Math.round(guidance.readiness_score ?? snapshot?.production_bible_summary?.readiness_score ?? 0);
  const blockerCount = guidance.blocker_count ?? snapshot?.mode_policy?.blocking_issue_count ?? snapshot?.issues?.length ?? 0;
  const actionReason = action?.reason || action?.description || '当前快照没有推荐动作，可继续查看工作台状态。';

  return (
    <Card className="border-violet-400/25 bg-violet-500/[0.08]" data-testid="studio-command-bar">
      <CardContent className="flex flex-col gap-3 p-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 flex-wrap items-center gap-2"><Wand2 className="h-5 w-5 text-violet-300" /><div className="truncate text-base font-semibold text-white">{action ? `下一步：${action.label}` : '下一步：等待工作台建议'}</div></div>
          <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-white/50"><span className="inline-flex items-center gap-1"><BookOpen className="h-3.5 w-3.5" />{novelTitle}</span><span>·</span><span>{chapterTitle}</span><span className="hidden max-w-sm truncate xl:inline">· {actionReason}</span><span className="inline-flex items-center gap-1 text-emerald-200/75"><Gauge className="h-3.5 w-3.5" />Readiness {readiness}%</span><span className={blockerCount > 0 ? 'inline-flex items-center gap-1 text-amber-200/80' : 'inline-flex items-center gap-1'}><AlertTriangle className="h-3.5 w-3.5" />阻断 {blockerCount}</span></div>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="flex min-w-[190px] justify-end gap-1 rounded-lg border border-white/10 bg-black/15 p-1">
            <Button type="button" size="sm" variant="ghost" onClick={() => onModeChange('test')} className={`h-7 flex-1 text-xs ${mode === 'test' ? 'bg-amber-500/20 text-amber-100' : 'text-white/45'}`}><TestTube2 className="mr-1 h-3.5 w-3.5" />测试验证</Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => onModeChange('production')} className={`h-7 flex-1 text-xs ${mode === 'production' ? 'bg-cyan-500/20 text-cyan-100' : 'text-white/45'}`}><ShieldCheck className="mr-1 h-3.5 w-3.5" />生产出片</Button>
          </div>
          <div className="flex gap-2">
            {secondary ? <Button type="button" variant="outline" disabled={loading} onClick={() => onPrimaryAction(secondary)} className="min-h-10 border-white/20 text-white/75"><RotateCcw className="mr-1.5 h-4 w-4" />{secondary.label}</Button> : null}
            {action ? <Button type="button" disabled={loading} onClick={() => onPrimaryAction(action)} className="min-h-11 bg-violet-600 px-5 hover:bg-violet-500">{loading ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Wand2 className="mr-1.5 h-4 w-4" />}{action.label}</Button> : null}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
