import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import type { PromptProfileInput, PromptProfileVersionInput, PublishInput, RollbackInput } from '../types';
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
  const createPromptProfileVersion = useCallback(async (profileId: string, input: PromptProfileVersionInput) => {
    return runModelCenterMutation(
      () => modelCenterApi.createPromptProfileVersion(profileId, input),
      modelCenterMutationInvalidations.promptProfileCreate,
    );
  }, []);
  const rollbackPromptProfile = useCallback(async (profileId: string, input: RollbackInput) => {
    return runModelCenterMutation(
      () => modelCenterApi.rollbackPromptProfile(profileId, input),
      modelCenterMutationInvalidations.promptProfilePublish,
    );
  }, []);

  return { ...query, createPromptProfile, createPromptProfileVersion, publishPromptProfileVersion, rollbackPromptProfile };
}
