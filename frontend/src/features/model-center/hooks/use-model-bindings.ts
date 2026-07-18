import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import type { ModelBindingInput, ModelBindingUpdateInput } from '../types';
import { modelCenterMutationInvalidations } from './model-center-query-store';
import { runModelCenterMutation } from './run-model-center-mutation';
import { useModelCenterQuery } from './use-model-center-query';

export function useModelBindings(page = 1, pageSize = 20) {
  const request = useCallback(() => modelCenterApi.listBindings(page, pageSize), [page, pageSize]);
  const query = useModelCenterQuery('bindings', request);
  const createBinding = useCallback(async (input: ModelBindingInput) => {
    return runModelCenterMutation(
      () => modelCenterApi.createBinding(input),
      modelCenterMutationInvalidations.bindingCreate,
    );
  }, []);
  const updateBinding = useCallback(async (bindingId: string, input: ModelBindingUpdateInput) => {
    return runModelCenterMutation(
      () => modelCenterApi.updateBinding(bindingId, input),
      modelCenterMutationInvalidations.bindingUpdate,
    );
  }, []);

  return { ...query, createBinding, updateBinding };
}
