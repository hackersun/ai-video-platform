import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import type { PromptProfileInput, PublishInput } from '../types';
import { modelCenterMutationInvalidations } from './model-center-query-store';
import { runModelCenterMutation } from './run-model-center-mutation';
import { useModelCenterQuery } from './use-model-center-query';

export function usePromptProfiles(page = 1, pageSize = 20) {
  const request = useCallback(() => modelCenterApi.listPromptProfiles(page, pageSize), [page, pageSize]);
  const query = useModelCenterQuery('prompt-profiles', request);
  const createPromptProfile = useCallback(async (input: PromptProfileInput) => {
    return runModelCenterMutation(
      () => modelCenterApi.createPromptProfile(input),
      modelCenterMutationInvalidations.promptProfileCreate,
    );
  }, []);
  const publishPromptProfileVersion = useCallback(async (versionId: string, input: PublishInput) => {
    return runModelCenterMutation(
      () => modelCenterApi.publishPromptProfileVersion(versionId, input),
      modelCenterMutationInvalidations.promptProfilePublish,
    );
  }, []);

  return { ...query, createPromptProfile, publishPromptProfileVersion };
}
