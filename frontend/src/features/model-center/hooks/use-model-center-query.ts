import { useCallback, useEffect, useState } from 'react';

import {
  subscribeModelCenterQuery,
  type ModelCenterQueryKey,
} from './model-center-query-store';

export interface ModelCenterQueryState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  reload: () => Promise<T>;
}

export function useModelCenterQuery<T>(
  queryKey: ModelCenterQueryKey,
  request: () => Promise<T>,
): ModelCenterQueryState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await request();
      setData(response);
      return response;
    } catch (reason) {
      const requestError = reason instanceof Error ? reason : new Error('模型中心请求失败');
      setError(requestError);
      throw requestError;
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    void reload().catch(() => undefined);
    return subscribeModelCenterQuery(queryKey, () => void reload().catch(() => undefined));
  }, [queryKey, reload]);

  return { data, error, loading, reload };
}
