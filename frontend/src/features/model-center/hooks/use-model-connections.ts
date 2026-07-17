import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import type { ModelConnectionInput } from '../types';
import {
  invalidateModelCenterQueries,
  modelCenterMutationInvalidations,
} from './model-center-query-store';
import { useModelCenterQuery } from './use-model-center-query';

export function useModelConnections(page = 1, pageSize = 20) {
  const request = useCallback(() => modelCenterApi.listConnections(page, pageSize), [page, pageSize]);
  const query = useModelCenterQuery('connections', request);
  const createConnection = useCallback(async (input: ModelConnectionInput) => {
    const connection = await modelCenterApi.createConnection(input);
    invalidateModelCenterQueries(modelCenterMutationInvalidations.connectionCreate);
    return connection;
  }, []);
  const updateConnection = useCallback(async (connectionId: string, input: ModelConnectionInput) => {
    const connection = await modelCenterApi.updateConnection(connectionId, input);
    invalidateModelCenterQueries(modelCenterMutationInvalidations.connectionUpdate);
    return connection;
  }, []);
  const testConnection = useCallback(async (connectionId: string) => {
    const certification = await modelCenterApi.testConnection(connectionId);
    invalidateModelCenterQueries(modelCenterMutationInvalidations.connectionTest);
    return certification;
  }, []);

  return { ...query, createConnection, updateConnection, testConnection };
}
