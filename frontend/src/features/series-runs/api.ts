import { apiClient } from '@/lib/api-client';
import type { RecoveryAcknowledgement, SeriesRunRecovery } from './types/recovery';

export function getSeriesRunRecovery(runId: string) {
  return apiClient.request<SeriesRunRecovery>(`/series-runs/${runId}/recovery`);
}

export function acknowledgeSeriesRunRecovery(
  runId: string, actionCode: string, operationId: string, expectedRunVersion: number,
) {
  return apiClient.request<RecoveryAcknowledgement>(
    `/series-runs/${runId}/recovery/actions/${actionCode}`,
    { method: 'POST', body: JSON.stringify({ operation_id: operationId, expected_run_version: expectedRunVersion }) },
  );
}
