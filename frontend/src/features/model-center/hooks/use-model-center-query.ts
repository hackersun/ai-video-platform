import { useCallback, useEffect, useRef, useState } from 'react';

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

export function createModelCenterRequestGeneration() {
  let generation = 0;
  let mounted = true;
  return {
    mount() {
      mounted = true;
    },
    begin() {
      const current = ++generation;
      return { isCurrent: () => mounted && current === generation };
    },
    unmount() {
      mounted = false;
      generation += 1;
    },
  };
}

export function useModelCenterQuery<T>(
  queryKey: ModelCenterQueryKey,
  request: () => Promise<T>,
): ModelCenterQueryState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const requestGeneration = useRef(createModelCenterRequestGeneration());
  const reload = useCallback(async () => {
    const currentRequest = requestGeneration.current.begin();
    setLoading(true);
    setError(null);
    try {
      const response = await request();
      if (currentRequest.isCurrent()) setData(response);
      return response;
    } catch (reason) {
      const requestError = reason instanceof Error ? reason : new Error('模型中心请求失败');
      if (currentRequest.isCurrent()) setError(requestError);
      throw requestError;
    } finally {
      if (currentRequest.isCurrent()) setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    requestGeneration.current.mount();
    return () => requestGeneration.current.unmount();
  }, []);

  useEffect(() => {
    void reload().catch(() => undefined);
    const unsubscribe = subscribeModelCenterQuery(queryKey, () => void reload().catch(() => undefined));
    return unsubscribe;
  }, [queryKey, reload]);

  return { data, error, loading, reload };
}
