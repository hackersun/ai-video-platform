import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import type { ModelBindingInput } from '../types';
import {
  invalidateModelCenterQueries,
  modelCenterMutationInvalidations,
} from './model-center-query-store';
import { useModelCenterQuery } from './use-model-center-query';

export function useModelBindings(page = 1, pageSize = 20) {
  const request = useCallback(() => modelCenterApi.listBindings(page, pageSize), [page, pageSize]);
  const query = useModelCenterQuery('bindings', request);
  const createBinding = useCallback(async (input: ModelBindingInput) => {
    const binding = await modelCenterApi.createBinding(input);
    invalidateModelCenterQueries(modelCenterMutationInvalidations.bindingCreate);
    return binding;
  }, []);
  const updateBinding = useCallback(async (bindingId: string, input: ModelBindingInput) => {
    const binding = await modelCenterApi.updateBinding(bindingId, input);
    invalidateModelCenterQueries(modelCenterMutationInvalidations.bindingUpdate);
    return binding;
  }, []);

  return { ...query, createBinding, updateBinding };
}
