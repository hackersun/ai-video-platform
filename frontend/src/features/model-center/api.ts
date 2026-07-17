import { apiClient } from '@/lib/api-client';

import type {
  CertificationRun,
  CertificationRunInput,
  ModelBindingInput,
  ModelBindingView,
  ModelCatalogView,
  ModelCenterOverview,
  ModelConnectionInput,
  ModelConnectionView,
  ModelDriverView,
  ModelProfileInput,
  ModelProfileVersionInput,
  ModelProfileVersionView,
  ModelProviderInput,
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

function pagePath(path: string, page = 1, pageSize = 20) {
  return `${path}?page=${page}&page_size=${pageSize}`;
}

function jsonBody(input: object) {
  return JSON.stringify(input);
}

export const modelCenterApi = {
  getOverview: () => apiClient.request<ModelCenterOverview>('/model-center/overview'),
  listDrivers: () => apiClient.request<ModelDriverView[]>('/model-center/drivers'),
  createProvider: (input: ModelProviderInput) =>
    apiClient.request<ModelProviderView>('/model-center/providers', { method: 'POST', body: jsonBody(input) }),
  updateProvider: (providerId: string, input: Partial<ModelProviderInput>) =>
    apiClient.request<ModelProviderView>(`/model-center/providers/${providerId}`, { method: 'PUT', body: jsonBody(input) }),

  listConnections: (page = 1, pageSize = 20) =>
    apiClient.request<PageResponse<ModelConnectionView>>(pagePath('/model-center/connections', page, pageSize)),
  createConnection: (input: ModelConnectionInput) =>
    apiClient.request<ModelConnectionView>('/model-center/connections', { method: 'POST', body: jsonBody(input) }),
  updateConnection: (connectionId: string, input: ModelConnectionInput) =>
    apiClient.request<ModelConnectionView>(`/model-center/connections/${connectionId}`, { method: 'PUT', body: jsonBody(input) }),
  testConnection: (connectionId: string) =>
    apiClient.request<CertificationRun>(`/model-center/connections/${connectionId}/test`, { method: 'POST' }),

  listCatalog: (page = 1, pageSize = 20) =>
    apiClient.request<PageResponse<ModelCatalogView>>(pagePath('/model-center/catalog', page, pageSize)),
  createProfile: (input: ModelProfileInput) =>
    apiClient.request<ModelProfileVersionView>('/model-center/profiles', { method: 'POST', body: jsonBody(input) }),
  createProfileVersion: (profileId: string, input: ModelProfileVersionInput) =>
    apiClient.request<ModelProfileVersionView>(`/model-center/profiles/${profileId}/versions`, { method: 'POST', body: jsonBody(input) }),
  updateProfileVersion: (profileVersionId: string, input: ModelProfileVersionInput) =>
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
  updateBinding: (bindingId: string, input: ModelBindingInput) =>
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
