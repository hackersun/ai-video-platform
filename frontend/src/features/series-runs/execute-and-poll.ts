import { apiClient, type SeriesProductionRun } from '@/lib/api-client';

const terminalStatuses = new Set(['shots_ready', 'anchor_ready', 'failed', 'blocked', 'paused', 'completed']);

export async function executeAndPollSeriesRun(
  runId: string,
  onUpdate: (run: SeriesProductionRun) => void,
  timeoutMs = 30 * 60_000,
) {
  const queued = await apiClient.executeSeriesRunAsync(runId);
  onUpdate(queued);
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const current = await apiClient.getSeriesRun(runId);
    onUpdate(current);
    if (terminalStatuses.has(current.status)) return current;
    await new Promise((resolve) => window.setTimeout(resolve, 3000));
  }
  throw new Error('整书任务仍在后台运行。可刷新页面读取进度，或点击“继续推进”从已完成章节恢复。');
}
