import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import type { PromptProfileInput, PublishInput } from '../types';
import {
  invalidateModelCenterQueries,
  modelCenterMutationInvalidations,
} from './model-center-query-store';
import { useModelCenterQuery } from './use-model-center-query';

export function usePromptProfiles(page = 1, pageSize = 20) {
  const request = useCallback(() => modelCenterApi.listPromptProfiles(page, pageSize), [page, pageSize]);
  const query = useModelCenterQuery('prompt-profiles', request);
  const createPromptProfile = useCallback(async (input: PromptProfileInput) => {
    const profile = await modelCenterApi.createPromptProfile(input);
    invalidateModelCenterQueries(modelCenterMutationInvalidations.promptProfileCreate);
    return profile;
  }, []);
  const publishPromptProfileVersion = useCallback(async (versionId: string, input: PublishInput) => {
    const result = await modelCenterApi.publishPromptProfileVersion(versionId, input);
    invalidateModelCenterQueries(modelCenterMutationInvalidations.promptProfilePublish);
    return result;
  }, []);

  return { ...query, createPromptProfile, publishPromptProfileVersion };
}
