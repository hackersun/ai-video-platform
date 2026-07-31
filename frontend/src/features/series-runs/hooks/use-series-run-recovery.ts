import { useCallback, useEffect, useState } from 'react';

import { acknowledgeSeriesRunRecovery, getSeriesRunRecovery } from '../api';
import type { RecoveryAction, RecoveryOperation, SeriesRunRecovery } from '../types/recovery';
import type { ReferencePreparation } from '@/lib/api-client';

type Inputs = {
  runId?: string;
  selectedShotCount: number;
  projectedIncrement?: string;
  retryFailedStage: () => Promise<void>;
  onReferenceRecovered: (reference: ReferencePreparation) => void | Promise<void>;
};

export function useSeriesRunRecovery({
  runId, selectedShotCount, projectedIncrement, retryFailedStage, onReferenceRecovered,
}: Inputs) {
  const [data, setData] = useState<SeriesRunRecovery | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionBusy, setActionBusy] = useState('');
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    if (!runId) { setData(null); return; }
    setLoading(true);
    try { setData(await getSeriesRunRecovery(runId)); setError(''); }
    catch (reason: any) { setError(reason?.message || '恢复状态读取失败'); }
    finally { setLoading(false); }
  }, [runId]);

  useEffect(() => {
    void refresh();
    if (!runId) return;
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(timer);
  }, [runId, refresh]);

  const execute = async (operation: RecoveryOperation, action: RecoveryAction) => {
    if (!runId || !data) return;
    if (action.code === 'retry_failed_stage') {
      const estimate = projectedIncrement || '待服务端重新估算';
      if (!window.confirm(`确认仅重试失败阶段？所选 ${selectedShotCount} 个镜头，预计新增成本 ¥${estimate}。已锁定参考图不会重新生成。`)) return;
    }
    setActionBusy(action.code); setError('');
    try {
      const latest = await getSeriesRunRecovery(runId);
      const current = latest.operations.find((item) => item.operation_id === operation.operation_id);
      if (!current?.actions.some((item) => item.code === action.code)) {
        throw new Error('该问题已被处理或状态已变化，请按最新提示继续');
      }
      const result = await acknowledgeSeriesRunRecovery(runId, action.code, operation.operation_id, latest.run_version);
      if (result.reference_preparation) await onReferenceRecovered(result.reference_preparation);
      if (action.code === 'edit_voice') document.querySelector<HTMLSelectElement>('[aria-label="配音声线"]')?.focus();
      if (action.code === 'retest_config') window.location.assign('/llm-config?capability=audio');
      if (action.code === 'retry_failed_stage') await retryFailedStage();
      await refresh();
    } catch (reason: any) { setError(reason?.message || '恢复操作失败，请刷新后重试'); }
    finally { setActionBusy(''); }
  };

  return { data, loading, actionBusy, error, refresh, execute };
}
