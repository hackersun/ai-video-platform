import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import type { PublishInput } from '../types';
import { modelCenterMutationInvalidations } from './model-center-query-store';
import { runModelCenterMutation } from './run-model-center-mutation';
import { useModelCenterQuery } from './use-model-center-query';

export function useModelCatalog(page = 1, pageSize = 20) {
  const request = useCallback(() => modelCenterApi.listCatalog(page, pageSize), [page, pageSize]);
  const query = useModelCenterQuery('catalog', request);
  const publishProfileVersion = useCallback(async (profileVersionId: string, input: PublishInput) => {
    return runModelCenterMutation(
      () => modelCenterApi.publishProfileVersion(profileVersionId, input),
      modelCenterMutationInvalidations.profilePublish,
    );
  }, []);

  return { ...query, publishProfileVersion };
}
