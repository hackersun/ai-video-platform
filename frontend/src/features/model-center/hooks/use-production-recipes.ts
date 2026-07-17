import { useCallback } from 'react';

import { modelCenterApi } from '../api';
import type { ProductionRecipeInput, PublishInput } from '../types';
import {
  invalidateModelCenterQueries,
  modelCenterMutationInvalidations,
} from './model-center-query-store';
import { useModelCenterQuery } from './use-model-center-query';

export function useProductionRecipes(page = 1, pageSize = 20) {
  const request = useCallback(() => modelCenterApi.listRecipes(page, pageSize), [page, pageSize]);
  const query = useModelCenterQuery('recipes', request);
  const createRecipe = useCallback(async (input: ProductionRecipeInput) => {
    const recipe = await modelCenterApi.createRecipe(input);
    invalidateModelCenterQueries(modelCenterMutationInvalidations.recipeCreate);
    return recipe;
  }, []);
  const publishRecipeVersion = useCallback(async (recipeVersionId: string, input: PublishInput) => {
    const result = await modelCenterApi.publishRecipeVersion(recipeVersionId, input);
    invalidateModelCenterQueries(modelCenterMutationInvalidations.recipePublish);
    return result;
  }, []);

  return { ...query, createRecipe, publishRecipeVersion };
}
