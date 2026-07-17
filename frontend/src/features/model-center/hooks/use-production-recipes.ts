import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import type { ProductionRecipeInput, PublishInput } from '../types';
import { modelCenterMutationInvalidations } from './model-center-query-store';
import { runModelCenterMutation } from './run-model-center-mutation';
import { useModelCenterQuery } from './use-model-center-query';

export function useProductionRecipes(page = 1, pageSize = 20) {
  const request = useCallback(() => modelCenterApi.listRecipes(page, pageSize), [page, pageSize]);
  const query = useModelCenterQuery('recipes', request);
  const createRecipe = useCallback(async (input: ProductionRecipeInput) => {
    return runModelCenterMutation(
      () => modelCenterApi.createRecipe(input),
      modelCenterMutationInvalidations.recipeCreate,
    );
  }, []);
  const publishRecipeVersion = useCallback(async (recipeVersionId: string, input: PublishInput) => {
    return runModelCenterMutation(
      () => modelCenterApi.publishRecipeVersion(recipeVersionId, input),
      modelCenterMutationInvalidations.recipePublish,
    );
  }, []);

  return { ...query, createRecipe, publishRecipeVersion };
}
