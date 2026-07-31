import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import type { CertificationLevel, ModelCapability } from '../types';
import { useModelCenterQuery } from './use-model-center-query';

export function useCertificationCandidates(
  capability: ModelCapability | undefined, query: string, page = 1, pageSize = 100,
  level?: Exclude<CertificationLevel, 'none'>, profileVersionId?: string, connectionId?: string,
) {
  const request = useCallback(
    () => modelCenterApi.listCertificationCandidates(
      page, pageSize, capability, query, level, profileVersionId, connectionId,
    ),
    [capability, connectionId, level, page, pageSize, profileVersionId, query],
  );
  return useModelCenterQuery('certification-candidates', request);
}

export function useCertificationHistory(level: string, status: string, page = 1, pageSize = 10) {
  const request = useCallback(
    () => modelCenterApi.listCertifications(page, pageSize, level || undefined, status || undefined),
    [level, page, pageSize, status],
  );
  return useModelCenterQuery('certification-history', request);
}
