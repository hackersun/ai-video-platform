import { apiClient } from '@/lib/api-client';
import type { ReanalysisResult, RebuildResult, ReviewEntity, ReviewPage, ReviewSummary } from './types';

export type ReviewQuery = {
  page: number;
  pageSize: number;
  type?: string;
  status?: string;
  query?: string;
};

export const entityReviewApi = {
  list(novelId: string, params: ReviewQuery) {
    return apiClient.getEntityReviewPage(novelId, params) as Promise<ReviewPage>;
  },
  bulk(novelId: string, entityIds: string[], action: 'approve' | 'reject') {
    return apiClient.bulkReviewEntities({ novel_id: novelId, entity_ids: entityIds, action }) as Promise<{
      updated: ReviewEntity[]; skipped: Array<{ id: string; reason: string; repair_action?: string }>;
      summary: ReviewSummary;
    }>;
  },
  update(entityId: string, data: Partial<ReviewEntity>) {
    return apiClient.updateStoryEntity(entityId, data) as Promise<ReviewEntity>;
  },
  reanalyze(entityId: string, data: { mode: 'preview' | 'apply'; preview_run_id?: string }) {
    return apiClient.reanalyzeReviewEntity(entityId, data) as Promise<ReanalysisResult>;
  },
  rebuild(novelId: string, data: { mode: 'preview' | 'apply'; preview_run_id?: string }) {
    return apiClient.rebuildReviewCandidates(novelId, data) as Promise<RebuildResult>;
  },
};
