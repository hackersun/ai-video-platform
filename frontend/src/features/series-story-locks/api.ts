import { apiClient } from '@/lib/api-client';
import type { StoryLockPreparation } from './types';

export async function prepareSeriesStoryLock(runId: string): Promise<StoryLockPreparation> {
  return apiClient.prepareSeriesRunStoryLocks(runId) as Promise<StoryLockPreparation>;
}

export async function approveRequiredStoryEntities(entityIds: string[]) {
  return apiClient.bulkActionStoryEntities({
    entity_ids: entityIds,
    action: 'approve',
    approved: true,
  });
}
