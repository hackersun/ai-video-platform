import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import type { CertificationRunInput } from '../types';
import {
  invalidateModelCenterQueries,
  modelCenterMutationInvalidations,
} from './model-center-query-store';
import { useModelCenterQuery } from './use-model-center-query';

export function useCertificationRun(runId?: string) {
  const request = useCallback(
    () => runId ? modelCenterApi.getCertification(runId) : Promise.resolve(null),
    [runId],
  );
  const query = useModelCenterQuery('test-lab', request);
  const createCertification = useCallback(async (input: CertificationRunInput) => {
    const certification = await modelCenterApi.createCertification(input);
    invalidateModelCenterQueries(modelCenterMutationInvalidations.certificationRun);
    return certification;
  }, []);

  return { ...query, createCertification };
}
