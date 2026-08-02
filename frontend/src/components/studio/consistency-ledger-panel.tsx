'use client';

import { AlertTriangle, BarChart3, CheckCircle2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { StudioAction, StudioSnapshot } from '@/lib/studio-types';

const DIMENSION_LABELS: Record<string, string> = {
  style: '风格',
  character_visual: '人物形象',
  scene: '场景',
  prop_state: '道具状态',
  voice: '声音',
  event_continuity: '事件连续性',
  subtitle_timing: '字幕节奏',
};

function toneClass(score: number) {
  if (score >= 85) return 'text-emerald-100';
  if (score >= 70) return 'text-amber-100';
  return 'text-red-100';
}

export function ConsistencyLedgerPanel({
  snapshot,
  onRepair,
}: {
  snapshot: StudioSnapshot | null;
  onRepair?: (action: StudioAction) => void;
}) {
  const ledger = snapshot?.consistency_ledger;
  const evaluated = ledger?.evaluation_status === 'evaluated' && typeof ledger?.overall_score === 'number';
  const score = evaluated ? ledger.overall_score : null;
  const dimensions = Object.entries(ledger?.dimensions || {});
  const findings = ledger?.findings || [];
  const evaluationMessage = ledger?.evaluation_status === 'partial'
    ? '评估尚未覆盖全部六个维度'
    : !evaluated ? '尚未执行六维一致性评估' : null;

  return (
    <Card data-testid="consistency-ledger-panel" className="border-white/10 bg-white/5">
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-white">
              <BarChart3 className="h-4 w-4 text-cyan-300" />
              一致性评分
            </CardTitle>
            <div className="mt-1 text-sm text-white/55">把风格、人物、场景、道具、声音和事件风险合并为可处理清单。</div>
          </div>
          <div className={`text-3xl font-semibold ${score == null ? 'text-white/45' : toneClass(score)}`}>
            {score == null ? '未评分' : score}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {evaluationMessage ? (
          <div className="rounded-lg border border-amber-300/20 bg-amber-400/[0.06] px-3 py-2 text-sm text-amber-100/80">
            {evaluationMessage}；下方仅展示生成前预检问题，不代表成片已经通过一致性验证。
          </div>
        ) : null}
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {dimensions.map(([key, value]) => (
            <div key={key} className="min-w-0 border-t border-white/10 pt-3">
              <div className="text-xs text-white/45">{DIMENSION_LABELS[key] || key}</div>
              <div className={`mt-1 text-sm font-medium ${value == null ? 'text-white/45' : toneClass(value)}`}>{value ?? '未评分'}</div>
            </div>
          ))}
        </div>

        <div className="space-y-2">
          {findings.length ? findings.map((finding, index) => (
            <div key={`${finding.code || 'finding'}-${finding.shot_id || index}`} className="flex min-w-0 items-start justify-between gap-3 border-t border-white/10 py-3 first:border-t-0">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  {finding.severity === 'blocking' ? (
                    <AlertTriangle className="h-4 w-4 text-red-300" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4 text-amber-300" />
                  )}
                  <Badge variant="outline" className="border-white/15 text-white/65">{finding.severity || 'info'}</Badge>
                  {finding.shot_id ? <span className="text-xs text-white/45">镜头 {finding.shot_id}</span> : null}
                </div>
                <div className="mt-2 break-words text-sm text-white/75">{finding.message || finding.code}</div>
              </div>
              {finding.repair_action ? (
                <Button
                  size="sm"
                  variant="outline"
                  className="shrink-0 border-white/15 text-white"
                  onClick={() => finding.repair_action && onRepair?.(finding.repair_action)}
                >
                  {finding.repair_action.label || '修复'}
                </Button>
              ) : null}
            </div>
          )) : (
            <div className="border-t border-white/10 py-3 text-sm text-white/50">当前没有一致性阻断项。</div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
