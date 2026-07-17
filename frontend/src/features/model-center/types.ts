export type ModelCapability =
  | 'text_generation'
  | 'vision_analysis'
  | 'image_generation'
  | 'speech_generation'
  | 'video_generation'
  | 'subtitle_generation'
  | 'media_render'
  | 'object_storage';

export type ConfigurationState = 'draft' | 'published' | 'disabled';
export type CertificationLevel = 'none' | 'connection' | 'contract' | 'live';
export type ModelCenterSection =
  | 'overview'
  | 'connections'
  | 'catalog'
  | 'bindings'
  | 'recipes'
  | 'prompts'
  | 'test-lab';
export type BindingScope = 'request' | 'series' | 'project' | 'user' | 'system';

export interface PageResponse<T> {
  items: T[];
  meta: { page: number; page_size: number; total: number };
}

export interface ModelConnectionView {
  id: string;
  provider_id: string;
  name: string;
  base_url: string | null;
  has_secret: boolean;
  secret_hint: string | null;
  secret_updated_at: string | null;
  enabled: boolean;
  revision: number;
}

export interface ModelConnectionInput {
  provider_id: string;
  name: string;
  base_url?: string | null;
  api_key?: string;
  api_secret?: string;
  enabled?: boolean;
  expected_revision?: number;
  reason?: string;
}

export interface ModelProviderView {
  id: string;
  code: string;
  display_name: string;
  provider_family: string;
  is_builtin: boolean;
  enabled: boolean;
  revision: number;
}

export interface ModelProviderInput {
  code: string;
  display_name: string;
  provider_family: string;
  is_builtin?: boolean;
  enabled?: boolean;
  expected_revision?: number;
  reason?: string;
}

export interface ModelDriverView {
  key: string;
  capabilities: ModelCapability[];
  parameter_schema: Record<string, unknown>;
  contract_version: string;
}

export interface ModelProfileVersionView {
  id: string;
  model_id: string;
  version: number;
  api_model_id: string;
  driver_key: string;
  capabilities: ModelCapability[];
  contract_version: string;
  status: ConfigurationState;
  revision: number;
}

export interface ModelProfileInput {
  provider_id: string;
  profile_key: string;
  display_name: string;
  enabled?: boolean;
}

export interface ModelProfileVersionInput {
  api_model_id: string;
  driver_key: string;
  capabilities: ModelCapability[];
  input_contract?: Record<string, unknown>;
  output_contract?: Record<string, unknown>;
  parameter_schema?: Record<string, unknown>;
  default_params?: Record<string, unknown>;
  limits?: Record<string, unknown>;
  pricing?: Record<string, unknown>;
  prompt_profile_key?: string | null;
  contract_version: string;
  expected_revision?: number;
  reason?: string;
}

export interface ModelCatalogView {
  provider: ModelProviderView;
  profile: ModelProfileVersionView;
  certification_level: CertificationLevel;
}

export interface ModelBindingView {
  id: string;
  scope_type: BindingScope;
  scope_id: string;
  task: string;
  capability: ModelCapability;
  profile_version_id: string;
  connection_id: string;
  priority: number;
  route_policy: string;
  is_active: boolean;
  revision: number;
}

export interface ModelBindingInput {
  scope_type: BindingScope;
  scope_id?: string;
  task: string;
  capability: ModelCapability;
  profile_version_id: string;
  connection_id: string;
  priority?: number;
  route_policy?: string;
  expected_revision?: number;
  reason?: string;
}

export interface ProductionRecipeView {
  id: string;
  recipe_key: string;
  name: string;
  version: number;
  status: ConfigurationState;
  spec: Record<string, unknown>;
  revision: number;
}

export interface ProductionRecipeInput {
  recipe_key: string;
  name: string;
  spec: Record<string, unknown>;
  expected_revision?: number;
  reason?: string;
}

export interface PromptProfileView {
  id: string;
  profile_key: string;
  version: number;
  status: ConfigurationState;
  content: Record<string, unknown>;
  revision: number;
}

export interface PromptProfileInput {
  profile_key: string;
  content: Record<string, unknown>;
  expected_revision?: number;
  reason?: string;
}

export interface CertificationRun {
  id: string;
  profile_version_id: string;
  connection_id: string;
  level: CertificationLevel;
  status: string;
  sanitized_evidence: Record<string, unknown>;
  estimated_cost_rmb: string;
  actual_cost_rmb: string;
  created_at: string;
  completed_at: string | null;
}

export interface CertificationRunInput {
  profile_version_id: string;
  connection_id: string;
  level: Exclude<CertificationLevel, 'none'>;
  reason?: string;
}

export interface ResourceImpact {
  affected_bindings: number;
  affected_recipes: number;
  affected_prompt_profiles: number;
}

export interface PublishInput {
  expected_revision: number;
  reason: string;
}

export interface PublishResult {
  published_version_id: string;
  previous_version_id: string | null;
  impact: ResourceImpact;
  audit_event_id: string;
}

export interface ModelCenterOverview {
  blocking_issues: Array<{ code: string; message: string; capability?: ModelCapability }>;
  connections: ModelConnectionView[];
  recipes: ProductionRecipeView[];
}
