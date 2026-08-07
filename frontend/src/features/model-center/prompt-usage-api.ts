import { apiClient } from '@/lib/api-client';

import {
  parsePromptUsageAssignment,
  parsePromptUsageCandidates,
  parsePromptUsageMap,
  parsePromptUsageStage,
} from './prompt-usage-types';

export const promptUsageApi = {
  async getMap() {
    return parsePromptUsageMap(
      await apiClient.request<unknown>('/model-center/prompt-usage-map'),
    );
  },
  async previewStage(stageId: string, profileVersionId: string) {
    const query = new URLSearchParams({ profile_version_id: profileVersionId });
    return parsePromptUsageStage(await apiClient.request<unknown>(
      `/model-center/prompt-usage-map/stages/${encodeURIComponent(stageId)}/resolve?${query}`,
    ));
  },
  async listCandidates(stageId: string) {
    return parsePromptUsageCandidates(await apiClient.request<unknown>(
      `/model-center/prompt-usage-map/stages/${encodeURIComponent(stageId)}/candidates`,
    ));
  },
  async createAssignmentDraft(
    stageId: string,
    input: { prompt_version_id: string; reason: string },
  ) {
    return parsePromptUsageAssignment(await apiClient.request<unknown>(
      `/model-center/prompt-usage-map/stages/${encodeURIComponent(stageId)}/assignment-drafts`,
      { method: 'POST', body: JSON.stringify(input) },
    ));
  },
};
