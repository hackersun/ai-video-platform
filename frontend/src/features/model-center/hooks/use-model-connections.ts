import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import type { ModelConnectionInput, ModelConnectionUpdateInput } from '../types';
import { modelCenterMutationInvalidations } from './model-center-query-store';
import { runModelCenterMutation } from './run-model-center-mutation';
import { useModelCenterQuery } from './use-model-center-query';

export function useModelConnections(page = 1, pageSize = 20) {
  const request = useCallback(() => modelCenterApi.listConnections(page, pageSize), [page, pageSize]);
  const query = useModelCenterQuery('connections', request);
  const createConnection = useCallback(async (input: ModelConnectionInput) => {
    return runModelCenterMutation(
      () => modelCenterApi.createConnection(input),
      modelCenterMutationInvalidations.connectionCreate,
    );
  }, []);
  const updateConnection = useCallback(async (connectionId: string, input: ModelConnectionUpdateInput) => {
    return runModelCenterMutation(
      () => modelCenterApi.updateConnection(connectionId, input),
      modelCenterMutationInvalidations.connectionUpdate,
    );
  }, []);
  const testConnection = useCallback(async (connectionId: string) => {
    return runModelCenterMutation(
      () => modelCenterApi.testConnection(connectionId),
      modelCenterMutationInvalidations.connectionTest,
    );
  }, []);

  return { ...query, createConnection, updateConnection, testConnection };
}
