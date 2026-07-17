import { apiClient } from '@/lib/api-client';

import type {
  CertificationRun,
  CertificationRunInput,
  ConfigurationState,
  ModelCapability,
  ModelBindingInput,
  ModelBindingUpdateInput,
  ModelBindingView,
  ModelCatalogView,
  ModelCenterOverview,
  ModelConnectionInput,
  ModelConnectionUpdateInput,
  ModelConnectionView,
  ModelDriverView,
  ModelProfileInput,
  ModelProfileVersionInput,
  ModelProfileVersionUpdateInput,
  ModelProfileVersionView,
  ModelProviderInput,
  ModelProviderUpdateInput,
  ModelProviderView,
  PageResponse,
  ProductionRecipeInput,
  ProductionRecipeView,
  PromptProfileInput,
  PromptProfileView,
  PublishInput,
  PublishResult,
  ResourceImpact,
} from './types';

function boundedInteger(value: number, fallback: number, maximum: number) {
  if (!Number.isFinite(value)) return fallback;
  return Math.min(Math.max(Math.floor(value), 1), maximum);
}

function pagePath(path: string, page = 1, pageSize = 20) {
  const safePage = boundedInteger(page, 1, Number.MAX_SAFE_INTEGER);
  const safePageSize = boundedInteger(pageSize, 20, 100);
  return `${path}?page=${safePage}&page_size=${safePageSize}`;
}

function jsonBody(input: object) {
  return JSON.stringify(input);
}

function record(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`无效的模型中心${label}响应`);
  return Object.fromEntries(Object.entries(value));
}

function stringValue(value: Record<string, unknown>, key: string, label: string) {
  if (typeof value[key] !== 'string') throw new Error(`无效的模型中心${label}响应`);
  return value[key];
}

function nullableStringValue(value: Record<string, unknown>, key: string, label: string) {
  if (value[key] === null) return null;
  return stringValue(value, key, label);
}

function arrayValue(value: Record<string, unknown>, key: string, label: string) {
  if (!Array.isArray(value[key])) throw new Error(`无效的模型中心${label}响应`);
  return value[key];
}

function numberValue(value: Record<string, unknown>, key: string, label: string) {
  if (typeof value[key] !== 'number') throw new Error(`无效的模型中心${label}响应`);
  return value[key];
}

function configurationState(value: unknown, label: string): ConfigurationState {
  if (value === 'draft' || value === 'published' || value === 'disabled') return value;
  throw new Error(`无效的模型中心${label}响应`);
}

const modelCapabilities = new Set([
  'text_generation', 'vision_analysis', 'image_generation', 'speech_generation',
  'video_generation', 'subtitle_generation', 'media_render', 'object_storage',
]);

function isModelCapability(value: unknown): value is ModelCapability {
  return typeof value === 'string' && modelCapabilities.has(value);
}

function modelCapability(value: unknown, label: string): ModelCapability {
  if (isModelCapability(value)) return value;
  throw new Error(`无效的模型中心${label}响应`);
}

function connectionView(value: unknown): ModelConnectionView {
  const input = record(value, '连接');
  if (typeof input.has_secret !== 'boolean' || typeof input.enabled !== 'boolean' || typeof input.revision !== 'number') {
    throw new Error('无效的模型中心连接响应');
  }
  return {
    id: stringValue(input, 'id', '连接'),
    provider_id: stringValue(input, 'provider_id', '连接'),
    name: stringValue(input, 'name', '连接'),
    base_url: nullableStringValue(input, 'base_url', '连接'),
    has_secret: input.has_secret,
    secret_hint: nullableStringValue(input, 'secret_hint', '连接'),
    secret_updated_at: nullableStringValue(input, 'secret_updated_at', '连接'),
    enabled: input.enabled,
    revision: input.revision,
  };
}

function connectionPage(value: unknown): PageResponse<ModelConnectionView> {
  const input = record(value, '连接列表');
  const meta = record(input.meta, '连接列表分页');
  if (!Array.isArray(input.items) || typeof meta.page !== 'number' ||
      typeof meta.page_size !== 'number' || typeof meta.total !== 'number') {
    throw new Error('无效的模型中心连接列表响应');
  }
  return {
    items: input.items.map(connectionView),
    meta: { page: meta.page, page_size: meta.page_size, total: meta.total },
  };
}

function productionRecipeView(value: unknown): ProductionRecipeView {
  const input = record(value, '生产方案');
  return {
    id: stringValue(input, 'id', '生产方案'),
    recipe_key: stringValue(input, 'recipe_key', '生产方案'),
    name: stringValue(input, 'name', '生产方案'),
    version: numberValue(input, 'version', '生产方案'),
    status: configurationState(input.status, '生产方案'),
    spec: record(input.spec, '生产方案'),
    revision: numberValue(input, 'revision', '生产方案'),
  };
}

function modelCenterOverview(value: unknown): ModelCenterOverview {
  const input = record(value, '概览');
  return {
    blocking_issues: arrayValue(input, 'blocking_issues', '概览').map((issue) => {
      const item = record(issue, '概览问题');
      const capability = item.capability === undefined ? undefined : modelCapability(item.capability, '概览问题');
      return { code: stringValue(item, 'code', '概览问题'), message: stringValue(item, 'message', '概览问题'), capability };
    }),
    connections: arrayValue(input, 'connections', '概览').map(connectionView),
    recipes: arrayValue(input, 'recipes', '概览').map(productionRecipeView),
  };
}

export const modelCenterApi = {
  getOverview: async () => modelCenterOverview(await apiClient.request<unknown>('/model-center/overview')),
  listDrivers: (page = 1, pageSize = 20) =>
    apiClient.request<PageResponse<ModelDriverView>>(pagePath('/model-center/drivers', page, pageSize)),
  createProvider: (input: ModelProviderInput) =>
    apiClient.request<ModelProviderView>('/model-center/providers', { method: 'POST', body: jsonBody(input) }),
  updateProvider: (providerId: string, input: ModelProviderUpdateInput) =>
    apiClient.request<ModelProviderView>(`/model-center/providers/${providerId}`, { method: 'PUT', body: jsonBody(input) }),

  listConnections: async (page = 1, pageSize = 20) =>
    connectionPage(await apiClient.request<unknown>(pagePath('/model-center/connections', page, pageSize))),
  createConnection: (input: ModelConnectionInput) =>
    apiClient.request<unknown>('/model-center/connections', { method: 'POST', body: jsonBody(input) }).then(connectionView),
  updateConnection: (connectionId: string, input: ModelConnectionUpdateInput) =>
    apiClient.request<unknown>(`/model-center/connections/${connectionId}`, { method: 'PUT', body: jsonBody(input) }).then(connectionView),
  testConnection: (connectionId: string) =>
    apiClient.request<CertificationRun>(`/model-center/connections/${connectionId}/test`, { method: 'POST' }),

  listCatalog: (page = 1, pageSize = 20) =>
    apiClient.request<PageResponse<ModelCatalogView>>(pagePath('/model-center/catalog', page, pageSize)),
  createProfile: (input: ModelProfileInput) =>
    apiClient.request<ModelProfileVersionView>('/model-center/profiles', { method: 'POST', body: jsonBody(input) }),
  createProfileVersion: (profileId: string, input: ModelProfileVersionInput) =>
    apiClient.request<ModelProfileVersionView>(`/model-center/profiles/${profileId}/versions`, { method: 'POST', body: jsonBody(input) }),
  updateProfileVersion: (profileVersionId: string, input: ModelProfileVersionUpdateInput) =>
    apiClient.request<ModelProfileVersionView>(`/model-center/profile-versions/${profileVersionId}`, { method: 'PUT', body: jsonBody(input) }),
  publishProfileVersion: (profileVersionId: string, input: PublishInput) =>
    apiClient.request<PublishResult>(`/model-center/profile-versions/${profileVersionId}/publish`, { method: 'POST', body: jsonBody(input) }),
  disableProfileVersion: (profileVersionId: string, input: PublishInput) =>
    apiClient.request<PublishResult>(`/model-center/profile-versions/${profileVersionId}/disable`, { method: 'POST', body: jsonBody(input) }),
  rollbackProfile: (profileId: string, input: PublishInput) =>
    apiClient.request<PublishResult>(`/model-center/profiles/${profileId}/rollback`, { method: 'POST', body: jsonBody(input) }),

  listBindings: (page = 1, pageSize = 20) =>
    apiClient.request<PageResponse<ModelBindingView>>(pagePath('/model-center/bindings', page, pageSize)),
  createBinding: (input: ModelBindingInput) =>
    apiClient.request<ModelBindingView>('/model-center/bindings', { method: 'POST', body: jsonBody(input) }),
  updateBinding: (bindingId: string, input: ModelBindingUpdateInput) =>
    apiClient.request<ModelBindingView>(`/model-center/bindings/${bindingId}`, { method: 'PUT', body: jsonBody(input) }),

  listRecipes: (page = 1, pageSize = 20) =>
    apiClient.request<PageResponse<ProductionRecipeView>>(pagePath('/model-center/recipes', page, pageSize)),
  createRecipe: (input: ProductionRecipeInput) =>
    apiClient.request<ProductionRecipeView>('/model-center/recipes', { method: 'POST', body: jsonBody(input) }),
  publishRecipeVersion: (recipeVersionId: string, input: PublishInput) =>
    apiClient.request<PublishResult>(`/model-center/recipe-versions/${recipeVersionId}/publish`, { method: 'POST', body: jsonBody(input) }),
  disableRecipeVersion: (recipeVersionId: string, input: PublishInput) =>
    apiClient.request<PublishResult>(`/model-center/recipe-versions/${recipeVersionId}/disable`, { method: 'POST', body: jsonBody(input) }),
  rollbackRecipe: (recipeKey: string, input: PublishInput) =>
    apiClient.request<PublishResult>(`/model-center/recipes/${recipeKey}/rollback`, { method: 'POST', body: jsonBody(input) }),

  listPromptProfiles: (page = 1, pageSize = 20) =>
    apiClient.request<PageResponse<PromptProfileView>>(pagePath('/model-center/prompt-profiles', page, pageSize)),
  createPromptProfile: (input: PromptProfileInput) =>
    apiClient.request<PromptProfileView>('/model-center/prompt-profiles', { method: 'POST', body: jsonBody(input) }),
  createPromptProfileVersion: (profileId: string, input: PromptProfileInput) =>
    apiClient.request<PromptProfileView>(`/model-center/prompt-profiles/${profileId}/versions`, { method: 'POST', body: jsonBody(input) }),
  publishPromptProfileVersion: (versionId: string, input: PublishInput) =>
    apiClient.request<PublishResult>(`/model-center/prompt-profile-versions/${versionId}/publish`, { method: 'POST', body: jsonBody(input) }),
  disablePromptProfileVersion: (versionId: string, input: PublishInput) =>
    apiClient.request<PublishResult>(`/model-center/prompt-profile-versions/${versionId}/disable`, { method: 'POST', body: jsonBody(input) }),
  rollbackPromptProfile: (profileId: string, input: PublishInput) =>
    apiClient.request<PublishResult>(`/model-center/prompt-profiles/${profileId}/rollback`, { method: 'POST', body: jsonBody(input) }),

  createCertification: (input: CertificationRunInput) =>
    apiClient.request<CertificationRun>('/model-center/certifications', { method: 'POST', body: jsonBody(input) }),
  getCertification: (runId: string) => apiClient.request<CertificationRun>(`/model-center/certifications/${runId}`),
  getImpact: () => apiClient.request<ResourceImpact>('/model-center/impact'),
};
