import type { AnchorGenerationResponse } from '@/lib/api-client';

type PollingClient = {
  refreshVideoJob(jobId: string): Promise<any>;
  reconcileSelectedSeriesRunAnchors(runId: string): Promise<AnchorGenerationResponse>;
};

type PollInput = {
  runId: string;
  initial: AnchorGenerationResponse;
  client: PollingClient;
  onStatus?: (status: AnchorGenerationResponse['status']) => void;
  wait?: (milliseconds: number) => Promise<void>;
  maxAttempts?: number;
};

function pendingVideoIds(response: AnchorGenerationResponse): string[] {
  const direct = response.pending_video_job_ids || [];
  if (direct.length) return direct;
  return Array.from(new Set(
    (response.workflow_batches || []).flatMap((batch) => batch.pending_video_job_ids || []),
  ));
}

export async function pollAnchorGeneration({
  runId, initial, client, onStatus,
  wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds)),
  maxAttempts = 120,
}: PollInput): Promise<AnchorGenerationResponse> {
  let current = initial;
  onStatus?.(current.status);
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    if (current.status === 'completed' || current.status === 'failed') return current;
    await Promise.all(pendingVideoIds(current).map((jobId) => client.refreshVideoJob(jobId)));
    current = await client.reconcileSelectedSeriesRunAnchors(runId);
    onStatus?.(current.status);
    if (current.status === 'completed' || current.status === 'failed') return current;
    await wait(Math.min(10_000, 2_000 + attempt * 500));
  }
  throw new Error('关键镜头云端任务等待超时，可稍后从工作台继续刷新。');
}
