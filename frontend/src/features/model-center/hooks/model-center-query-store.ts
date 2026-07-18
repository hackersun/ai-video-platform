export type ModelCenterQueryKey =
  | 'overview'
  | 'connections'
  | 'providers'
  | 'drivers'
  | 'catalog'
  | 'bindings'
  | 'recipes'
  | 'prompt-profiles'
  | `prompt-profile:${string}`
  | 'test-lab'
  | 'certification-candidates'
  | 'certification-history'
  | 'impact';

type Listener = () => void;

const listeners = new Map<ModelCenterQueryKey, Set<Listener>>();

export const modelCenterMutationInvalidations = {
  connectionCreate: ['overview', 'connections'],
  connectionUpdate: ['overview', 'connections'],
  connectionTest: ['overview', 'connections'],
  profilePublish: ['overview', 'catalog', 'bindings', 'recipes', 'impact'],
  bindingCreate: ['overview', 'bindings', 'recipes', 'impact'],
  bindingUpdate: ['overview', 'bindings', 'recipes', 'impact'],
  recipeCreate: ['overview', 'recipes', 'impact'],
  recipePublish: ['overview', 'recipes', 'impact'],
  promptProfileCreate: ['overview', 'prompt-profiles', 'impact'],
  promptProfilePublish: ['overview', 'prompt-profiles', 'bindings', 'recipes', 'impact'],
  certificationRun: ['overview', 'connections', 'catalog', 'bindings', 'recipes', 'prompt-profiles', 'test-lab', 'certification-candidates', 'certification-history', 'impact'],
} as const satisfies Record<string, readonly ModelCenterQueryKey[]>;

export function subscribeModelCenterQuery(queryKey: ModelCenterQueryKey, listener: Listener) {
  const queryListeners = listeners.get(queryKey) ?? new Set<Listener>();
  queryListeners.add(listener);
  listeners.set(queryKey, queryListeners);
  return () => {
    queryListeners.delete(listener);
  };
}

export function invalidateModelCenterQueries(queryKeys: readonly ModelCenterQueryKey[]) {
  queryKeys.forEach((queryKey) => listeners.get(queryKey)?.forEach((listener) => listener()));
}
