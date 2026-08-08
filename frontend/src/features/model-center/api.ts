import { apiClient } from '@/lib/api-client';

import type {
  CertificationRun,
  CertificationRunInput,
  CertificationCandidate,
  CertificationHistoryItem,
  CertificationLevel,
  ConfigurationState,
  ModelCapability,
  ModelCatalogFilters,
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
  ModelProfileView,
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
  PromptOptimizationResult,
  PromptPreviewResult,
  PromptProfileDetail,
  PromptProfileVersionInput,
  PromptProfileView,
  PublishInput,
  PublishResult,
  ResourceImpact,
  RollbackInput,
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

function catalogPath(page = 1, pageSize = 20, filters: ModelCatalogFilters = {}) {
  const params = new URLSearchParams(pagePath('', page, pageSize).slice(1));
  if (filters.capability) params.set('capability', filters.capability);
  if (filters.providerId) params.set('provider_id', filters.providerId);
  if (filters.status) params.set('status', filters.status);
  if (filters.query?.trim()) params.set('q', filters.query.trim());
  return `/model-center/catalog?${params.toString()}`;
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
    provider_name: stringValue(input, 'provider_name', '连接'),
    provider_code: stringValue(input, 'provider_code', '连接'),
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
  const spec = record(input.spec, '生产方案');
  const stages = input.stages === undefined ? spec : record(input.stages, '生产方案阶段');
  return {
    id: stringValue(input, 'id', '生产方案'),
    recipe_key: stringValue(input, 'recipe_key', '生产方案'),
    name: stringValue(input, 'name', '生产方案'),
    version: numberValue(input, 'version', '生产方案'),
    status: configurationState(input.status, '生产方案'),
    strategy: typeof input.strategy === 'string' ? input.strategy : typeof spec.strategy === 'string' ? spec.strategy : '',
    stages: stages as Record<string, Record<string, unknown>>,
    spec,
    revision: numberValue(input, 'revision', '生产方案'),
  };
}

function certificationCandidatePage(value: unknown): PageResponse<CertificationCandidate> {
  const input = record(value, '认证候选列表');
  const meta = record(input.meta, '认证候选分页');
  const items = arrayValue(input, 'items', '认证候选列表').map((value) => {
    const item = record(value, '认证候选');
    const profile = record(item.profile, '认证候选模型');
    const connection = record(item.connection, '认证候选连接');
    return {
      id: stringValue(item, 'id', '认证候选'),
      profile: {
        id: stringValue(profile, 'id', '认证候选模型'), name: stringValue(profile, 'name', '认证候选模型'),
        api_model_id: stringValue(profile, 'api_model_id', '认证候选模型'),
        provider_id: stringValue(profile, 'provider_id', '认证候选模型'),
        provider_name: stringValue(profile, 'provider_name', '认证候选模型'),
        capabilities: arrayValue(profile, 'capabilities', '认证候选模型').map((entry) => modelCapability(entry, '认证候选模型')),
      },
      connection: {
        id: stringValue(connection, 'id', '认证候选连接'), name: stringValue(connection, 'name', '认证候选连接'),
        provider_id: stringValue(connection, 'provider_id', '认证候选连接'), status: stringValue(connection, 'status', '认证候选连接'),
      },
    };
  });
  return { items, meta: { page: numberValue(meta, 'page', '认证候选分页'), page_size: numberValue(meta, 'page_size', '认证候选分页'), total: numberValue(meta, 'total', '认证候选分页') } };
}

function certificationHistoryPage(value: unknown): PageResponse<CertificationHistoryItem> {
  const input = record(value, '认证历史列表');
  const meta = record(input.meta, '认证历史分页');
  const items = arrayValue(input, 'items', '认证历史列表').map((value) => {
    const item = record(value, '认证历史');
    return {
      id: stringValue(item, 'id', '认证历史'), profile_version_id: stringValue(item, 'profile_version_id', '认证历史'),
      connection_id: stringValue(item, 'connection_id', '认证历史'), profile_name: stringValue(item, 'profile_name', '认证历史'),
      api_model_id: stringValue(item, 'api_model_id', '认证历史'), connection_name: stringValue(item, 'connection_name', '认证历史'),
      provider_name: stringValue(item, 'provider_name', '认证历史'), level: item.level as CertificationHistoryItem['level'],
      status: stringValue(item, 'status', '认证历史'), sanitized_evidence: record(item.sanitized_evidence, '认证历史证据'),
      estimated_cost_rmb: stringValue(item, 'estimated_cost_rmb', '认证历史'), actual_cost_rmb: stringValue(item, 'actual_cost_rmb', '认证历史'),
      created_at: stringValue(item, 'created_at', '认证历史'), completed_at: typeof item.completed_at === 'string' ? item.completed_at : null,
    };
  });
  return { items, meta: { page: numberValue(meta, 'page', '认证历史分页'), page_size: numberValue(meta, 'page_size', '认证历史分页'), total: numberValue(meta, 'total', '认证历史分页') } };
}

function modelCenterOverview(value: unknown): ModelCenterOverview {
  const input = record(value, '概览');
  return {
    blocking_issues: arrayValue(input, 'blocking_issues', '概览').map((issue) => {
      const item = record(issue, '概览问题');
      const capability = item.capability === undefined ? undefined : modelCapability(item.capability, '概览问题');
      const section = typeof item.section === 'string' ? item.section as ModelCenterOverview['blocking_issues'][number]['section'] : 'catalog';
      return {
        code: stringValue(item, 'code', '概览问题'), message: stringValue(item, 'message', '概览问题'),
        capability, severity: item.severity === 'warning' ? 'warning' : 'blocker', section,
        resource_id: typeof item.resource_id === 'string' ? item.resource_id : '',
        action_label: typeof item.action_label === 'string' ? item.action_label : capability ? '查看对应能力' : '去处理',
      };
    }),
    connections: arrayValue(input, 'connections', '概览').map(connectionView),
    recipes: arrayValue(input, 'recipes', '概览').map(productionRecipeView),
  };
}

export const modelCenterApi = {
  getOverview: async () => modelCenterOverview(await apiClient.request<unknown>('/model-center/overview')),
  listDrivers: (page = 1, pageSize = 20) =>
    apiClient.request<PageResponse<ModelDriverView>>(pagePath('/model-center/drivers', page, pageSize)),
  listProviders: (page = 1, pageSize = 100) =>
    apiClient.request<PageResponse<ModelProviderView>>(pagePath('/model-center/providers', page, pageSize)),
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
  removeConnection: (connectionId: string, input: PublishInput) =>
    apiClient.request<{ id: string; status: 'disabled'; revision: number; credentials_removed: boolean }>(
      `/model-center/connections/${connectionId}`,
      { method: 'DELETE', body: jsonBody(input) },
    ),
  testConnection: (connectionId: string) =>
    apiClient.request<CertificationRun>(`/model-center/connections/${connectionId}/test`, { method: 'POST' }),

  listCatalog: (page = 1, pageSize = 20, filters: ModelCatalogFilters = {}) =>
    apiClient.request<PageResponse<ModelCatalogView>>(catalogPath(page, pageSize, filters)),
  createProfile: (input: ModelProfileInput) =>
    apiClient.request<ModelProfileView>('/model-center/profiles', { method: 'POST', body: jsonBody(input) }),
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
  validateProfileVersion: (profileVersionId: string) =>
    apiClient.request<{ valid: boolean; errors: Array<Record<string, unknown>>; audit_event_id: string }>(`/model-center/profile-versions/${profileVersionId}/validate`, { method: 'POST' }),

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
  validateRecipeVersion: (recipeVersionId: string) =>
    apiClient.request<{ valid: boolean; errors: Array<{ code: string; message: string }> }>(`/model-center/recipe-versions/${recipeVersionId}/validate`, { method: 'POST' }),
  publishRecipeVersion: (recipeVersionId: string, input: PublishInput) =>
    apiClient.request<PublishResult>(`/model-center/recipe-versions/${recipeVersionId}/publish`, { method: 'POST', body: jsonBody(input) }),
  disableRecipeVersion: (recipeVersionId: string, input: PublishInput) =>
    apiClient.request<PublishResult>(`/model-center/recipe-versions/${recipeVersionId}/disable`, { method: 'POST', body: jsonBody(input) }),
  rollbackRecipe: (recipeKey: string, input: RollbackInput) =>
    apiClient.request<PublishResult>(`/model-center/recipes/${recipeKey}/rollback`, { method: 'POST', body: jsonBody(input) }),

  listPromptProfiles: (page = 1, pageSize = 20) =>
    apiClient.request<PageResponse<PromptProfileView>>(pagePath('/model-center/prompt-profiles', page, pageSize)),
  getPromptProfile: (profileId: string) =>
    apiClient.request<PromptProfileDetail>(`/model-center/prompt-profiles/${profileId}`),
  optimizePromptProfile: (
    profileId: string,
    input: { version_id: string; mode?: string; model_config_id?: string | null },
  ) => apiClient.request<PromptOptimizationResult>(`/model-center/prompt-profiles/${profileId}/optimize`, {
    method: 'POST', body: jsonBody(input),
  }),
  previewPromptProfile: (
    profileId: string,
    input: { version_id: string; task_template?: string; context?: Record<string, unknown> },
  ) => apiClient.request<PromptPreviewResult>(`/model-center/prompt-profiles/${profileId}/preview`, {
    method: 'POST', body: jsonBody(input),
  }),
  createPromptProfile: (input: PromptProfileInput) =>
    apiClient.request<PromptProfileView>('/model-center/prompt-profiles', { method: 'POST', body: jsonBody(input) }),
  createPromptProfileVersion: (profileId: string, input: PromptProfileVersionInput) =>
    apiClient.request<PromptProfileView>(`/model-center/prompt-profiles/${profileId}/versions`, { method: 'POST', body: jsonBody(input) }),
  publishPromptProfileVersion: (versionId: string, input: PublishInput) =>
    apiClient.request<PublishResult>(`/model-center/prompt-profile-versions/${versionId}/publish`, { method: 'POST', body: jsonBody(input) }),
  disablePromptProfileVersion: (versionId: string, input: PublishInput) =>
    apiClient.request<PublishResult>(`/model-center/prompt-profile-versions/${versionId}/disable`, { method: 'POST', body: jsonBody(input) }),
  rollbackPromptProfile: (profileId: string, input: RollbackInput) =>
    apiClient.request<PublishResult>(`/model-center/prompt-profiles/${profileId}/rollback`, { method: 'POST', body: jsonBody(input) }),

  createCertification: (input: CertificationRunInput) =>
    apiClient.request<CertificationRun>('/model-center/certifications', { method: 'POST', body: jsonBody(input) }),
  listCertificationCandidates: (
    page = 1, pageSize = 100, capability?: ModelCapability, query?: string,
    level?: Exclude<CertificationLevel, 'none'>, profileVersionId?: string, connectionId?: string,
  ) => {
    const params = new URLSearchParams(pagePath('/model-center/certification-candidates', page, pageSize).split('?')[1]);
    if (capability) params.set('capability', capability);
    if (query?.trim()) params.set('q', query.trim());
    if (level) params.set('level', level);
    if (profileVersionId) params.set('profile_version_id', profileVersionId);
    if (connectionId) params.set('connection_id', connectionId);
    return apiClient.request<unknown>(`/model-center/certification-candidates?${params.toString()}`).then(certificationCandidatePage);
  },
  listCertifications: (page = 1, pageSize = 10, level?: string, status?: string) => {
    const params = new URLSearchParams(pagePath('/model-center/certifications', page, pageSize).split('?')[1]);
    if (level) params.set('level', level);
    if (status) params.set('status', status);
    return apiClient.request<unknown>(`/model-center/certifications?${params.toString()}`).then(certificationHistoryPage);
  },
  getCertification: (runId: string) => apiClient.request<CertificationRun>(`/model-center/certifications/${runId}`),
  getImpact: (resourceType?: 'prompt_profile' | 'recipe', resourceId?: string) => {
    const params = new URLSearchParams();
    if (resourceType) params.set('resource_type', resourceType);
    if (resourceId) params.set('resource_id', resourceId);
    return apiClient.request<ResourceImpact>(`/model-center/impact${params.size ? `?${params.toString()}` : ''}`);
  },
};
