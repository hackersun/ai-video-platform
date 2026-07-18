import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import { useModelCenterQuery } from './use-model-center-query';

export function useModelDrivers() {
  const request = useCallback(() => modelCenterApi.listDrivers(1, 100), []);
  return useModelCenterQuery('drivers', request);
}
