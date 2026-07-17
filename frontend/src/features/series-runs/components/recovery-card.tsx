'use client';

import { AlertTriangle, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import type { RecoveryAction, RecoveryOperation, SeriesRunRecovery } from '../types/recovery';

const stageLabels: Record<string, string> = {
  image_submission: '参考图提交', tts_submission: '配音提交', video_submission: '视频提交',
};

function costMessage(operation: RecoveryOperation) {
  if (operation.capability === 'tts' && operation.cost_state === 'released') return '本次 TTS 未扣费，预留已释放';
  if (operation.cost_state === 'held') return '费用状态待确认，请先刷新或人工对账，禁止重复提交';
  return `费用状态：${operation.cost_state}`;
}

export function RecoveryCard({
  data, loading, actionBusy, error, onAction,
}: {
  data: SeriesRunRecovery | null; loading: boolean; actionBusy: string; error: string;
  onAction: (operation: RecoveryOperation, action: RecoveryAction) => void;
}) {
  if (data && !data.operations.length && !error) return null;
  if (!data && !loading && !error) return null;
  return <div className="space-y-3 rounded-lg border border-red-400/25 bg-red-500/5 p-4" data-testid="series-run-recovery">
    <div className="flex items-center gap-2 text-sm font-medium text-red-100"><AlertTriangle className="h-4 w-4" />阶段恢复与人工处理</div>
    {loading && !data && <div className="flex items-center gap-2 text-sm text-white/60"><Loader2 className="h-4 w-4 animate-spin" />正在读取恢复状态…</div>}
    {error && <div role="alert" className="text-sm text-red-200">{error}</div>}
    {data?.operations.map((operation) => <div key={operation.operation_id} className="space-y-2 rounded-md bg-black/20 p-3">
      <div className="font-medium text-white">{operation.title}</div>
      <div className="text-sm text-white/70">失败阶段：{stageLabels[operation.stage] || operation.stage}</div>
      <div className="text-sm text-white/70">{costMessage(operation)}</div>
      <div className="text-xs text-white/50">{operation.message}</div>
      <div className="flex flex-wrap gap-2">{operation.actions.map((action) => <Button key={action.code} size="sm" variant="outline" disabled={Boolean(actionBusy)} onClick={() => onAction(operation, action)}>{actionBusy === action.code && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}{action.label}</Button>)}</div>
    </div>)}
    {data?.preserved_artifacts.map((item) => <div key={`${item.kind}:${item.asset_id || ''}`} className="text-sm text-emerald-200">{item.message}</div>)}
  </div>;
}
