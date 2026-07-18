import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import type { CertificationRunInput } from '../types';
import { modelCenterMutationInvalidations } from './model-center-query-store';
import { runModelCenterMutation } from './run-model-center-mutation';
import { useModelCenterQuery } from './use-model-center-query';

export function useCertificationRun(runId?: string) {
  const request = useCallback(
    () => runId ? modelCenterApi.getCertification(runId) : Promise.resolve(null),
    [runId],
  );
  const query = useModelCenterQuery('test-lab', request);
  const createCertification = useCallback(async (input: CertificationRunInput) => {
    return runModelCenterMutation(
      () => modelCenterApi.createCertification(input),
      modelCenterMutationInvalidations.certificationRun,
    );
  }, []);

  return { ...query, createCertification };
}
