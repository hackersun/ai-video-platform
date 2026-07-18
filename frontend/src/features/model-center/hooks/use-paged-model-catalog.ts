import { useCallback, useDeferredValue, useState } from 'react';

import { modelCenterApi } from '../api';
import type { ModelCapability } from '../types';
import { useModelCenterQuery } from './use-model-center-query';

export function usePagedModelCatalog(capability?: ModelCapability) {
  const [page, setPage] = useState(1);
  const [query, setQueryValue] = useState('');
  const [providerId, setProviderValue] = useState('');
  const [status, setStatusValue] = useState('');
  const deferredQuery = useDeferredValue(query);
  const pageSize = 20;
  const request = useCallback(() => modelCenterApi.listCatalog(page, pageSize, {
    capability, providerId: providerId || undefined, status: status || undefined,
    query: deferredQuery || undefined,
  }), [capability, deferredQuery, page, providerId, status]);
  const catalog = useModelCenterQuery('catalog', request);
  const reset = (change: () => void) => { setPage(1); change(); };
  return {
    ...catalog, page, pageSize, query, providerId, status, setPage,
    setQuery: (value: string) => reset(() => setQueryValue(value)),
    setProviderId: (value: string) => reset(() => setProviderValue(value)),
    setStatus: (value: string) => reset(() => setStatusValue(value)),
  };
}
