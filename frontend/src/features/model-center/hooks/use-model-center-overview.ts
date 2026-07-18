import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import { useModelCenterQuery } from './use-model-center-query';

export function useModelCenterOverview() {
  const request = useCallback(() => modelCenterApi.getOverview(), []);
  return useModelCenterQuery('overview', request);
}
