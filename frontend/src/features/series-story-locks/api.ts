import { apiClient } from '@/lib/api-client';
import type { StoryAssetRepairResult, StoryLockPreparation } from './types';

export async function prepareSeriesStoryLock(runId: string, nativeAudio = false): Promise<StoryLockPreparation> {
  return apiClient.prepareSeriesRunStoryLocks(runId, nativeAudio) as Promise<StoryLockPreparation>;
}

export async function approveRequiredStoryEntities(entityIds: string[]) {
  return apiClient.bulkActionStoryEntities({
    entity_ids: entityIds,
    action: 'approve',
    approved: true,
  });
}

export async function repairSeriesStoryAssets(runId: string): Promise<StoryAssetRepairResult> {
  return apiClient.request<StoryAssetRepairResult>(`/series-runs/${runId}/story-assets/repair`, {
    method: 'POST',
  });
}
