import {
  invalidateModelCenterQueries,
  type ModelCenterQueryKey,
} from './model-center-query-store';

export async function runModelCenterMutation<T>(
  mutation: () => Promise<T>,
  queryKeys: readonly ModelCenterQueryKey[],
) {
  const result = await mutation();
  invalidateModelCenterQueries(queryKeys);
  return result;
}
