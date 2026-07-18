import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import { useModelCenterQuery } from './use-model-center-query';

export function useModelProviders(page = 1, pageSize = 100) {
  const request = useCallback(
    () => modelCenterApi.listProviders(page, pageSize),
    [page, pageSize],
  );
  return useModelCenterQuery('providers', request);
}
