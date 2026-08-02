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
  provider_name: string;
  provider_code: string;
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
  reason: string;
  base_url?: string | null;
  api_key?: string;
  api_secret?: string;
  enabled?: boolean;
}

type ModelConnectionUpdateFields = {
  name?: string;
  base_url?: string | null;
  enabled?: boolean;
  expected_revision: number;
};

export type ModelConnectionUpdateInput =
  | (ModelConnectionUpdateFields & { api_key?: never; api_secret?: never; reason?: string })
  | (ModelConnectionUpdateFields & { api_key: string; api_secret?: string; reason: string })
  | (ModelConnectionUpdateFields & { api_key?: string; api_secret: string; reason: string });

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
}

export type ModelProviderUpdateInput = Partial<ModelProviderInput> & {
  expected_revision: number;
  reason?: string;
};

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
  input_contract?: Record<string, unknown>;
  output_contract?: Record<string, unknown>;
  parameter_schema?: Record<string, unknown>;
  default_params?: Record<string, unknown>;
  limits?: Record<string, unknown>;
}

export interface ModelProfileView {
  id: string;
  provider_id: string;
  profile_key: string;
  display_name: string;
  enabled: boolean;
  revision: number;
}

export interface ModelProfileInput {
  provider_id: string;
  profile_key: string;
  display_name: string;
  enabled?: boolean;
}

export interface ModelProfileVersionInput {
  expected_revision: number;
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
}

export type ModelProfileVersionUpdateInput = ModelProfileVersionInput & {
  reason?: string;
};

export interface ModelCatalogView {
  provider_id: string;
  provider_name: string;
  provider_code: string;
  model_name: string;
  api_model_id: string;
  profile_version_id: string | null;
  profile_version: number | null;
  driver_key: string | null;
  legacy_model_id: string | null;
  legacy_config_id: string | null;
  certification_status: string;
  capabilities: ModelCapability[];
  input_contract?: Record<string, unknown>;
  parameter_schema?: Record<string, unknown>;
  limits?: Record<string, unknown>;
}

export interface ModelCatalogFilters {
  capability?: ModelCapability;
  providerId?: string;
  status?: string;
  query?: string;
}

export interface ModelBindingView {
  id: string;
  scope_type: BindingScope;
  scope_id: string;
  task: string;
  capability: ModelCapability;
  profile_version_id: string;
  profile_name: string;
  api_model_id: string;
  connection_id: string;
  connection_name: string;
  provider_name: string;
  priority: number;
  route_policy: string;
  fallback_profile_version_ids: string[];
  certification_status: string;
  affected_recipes: number;
  version: number;
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
  fallback_profile_version_ids?: string[];
  is_active?: boolean;
  reason: string;
}

export type ModelBindingUpdateInput = ModelBindingInput & {
  expected_revision: number;
  reason?: string;
};

export interface ProductionRecipeView {
  id: string;
  recipe_key: string;
  name: string;
  version: number;
  status: ConfigurationState;
  strategy: string;
  stages: Record<string, Record<string, unknown>>;
  spec: Record<string, unknown>;
  revision: number;
}

export interface ProductionRecipeInput {
  recipe_key: string;
  name: string;
  spec: Record<string, unknown>;
}

export interface PromptProfileView {
  id: string;
  key: string;
  name: string;
  task: string;
  head_version_id: string | null;
  head_version: number | null;
  status: ConfigurationState | null;
}

export interface PromptProfileVersionDetail {
  id: string;
  version: number;
  status: ConfigurationState;
  stage: string | null;
  content: string;
  system_contract: string;
  task_template: string;
  input_mapping: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  negative_constraints: string[];
  model_family_overrides: Record<string, unknown>;
  validation_fixtures: Array<Record<string, unknown>>;
  release_notes: string;
  checksum: string;
  created_at: string | null;
  published_at: string | null;
}

export interface PromptProfileDetail {
  id: string;
  key: string;
  name: string;
  task: string;
  head: PromptProfileVersionDetail;
  versions: PromptProfileVersionDetail[];
  legacy_skill: {
    id: string;
    is_active: boolean;
    is_builtin: boolean;
  } | null;
}

export interface PromptOptimizationResult {
  task: string;
  source: 'ai_model' | 'local_rules';
  original_content: string;
  optimized_content: string;
  suggestions: string[];
  warnings: string[];
}

export interface PromptPreviewResult {
  task: string;
  skill_count: number;
  skill_blocks: string[];
  prompt: string;
}

export interface PromptProfileInput {
  key: string;
  name: string;
  task: string;
  stage?: string | null;
  system_contract: string;
  task_template: string;
  input_mapping: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  negative_constraints: string[];
  model_family_overrides: Record<string, unknown>;
  validation_fixtures: Array<Record<string, unknown>>;
  release_notes: string;
}

export interface PromptProfileVersionInput {
  expected_revision: number;
  stage?: string | null;
  system_contract?: string;
  task_template?: string;
  input_mapping?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  negative_constraints?: string[];
  model_family_overrides?: Record<string, unknown>;
  validation_fixtures?: Array<Record<string, unknown>>;
  release_notes?: string;
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

export interface CertificationCandidate {
  id: string;
  profile: {
    id: string; name: string; api_model_id: string; provider_id: string;
    provider_name: string; capabilities: ModelCapability[];
  };
  connection: { id: string; name: string; provider_id: string; status: string };
}

export interface CertificationHistoryItem extends CertificationRun {
  profile_name: string;
  api_model_id: string;
  connection_name: string;
  provider_name: string;
}

export interface CertificationRunInput {
  profile_version_id: string;
  connection_id: string;
  level: Exclude<CertificationLevel, 'none'>;
  reason: string;
  user_scope?: string;
  recipe_version_id?: string;
  chapter_id?: string;
  run_id?: string;
  selected_shot_ids?: string[];
  budget_ceiling_rmb?: string;
  retry_policy?: string;
  storage_policy?: string;
  real_cost_acknowledged?: boolean;
}

export interface ResourceImpact {
  affected_bindings: number;
  affected_profiles?: number;
  affected_recipes: number;
  affected_prompts?: number;
  affected_prompt_profiles?: number;
}

export interface PublishInput {
  expected_revision: number;
  reason: string;
}

export interface RollbackInput extends PublishInput {
  target_version_id: string;
}

export interface PublishResult {
  published_version_id: string;
  previous_version_id: string | null;
  impact: ResourceImpact;
  audit_event_id: string;
}

export interface ModelCenterOverview {
  blocking_issues: ReadinessIssue[];
  connections: ModelConnectionView[];
  recipes: ProductionRecipeView[];
}

export interface ReadinessIssue {
  code: string;
  message: string;
  severity: 'blocker' | 'warning';
  section: ModelCenterSection;
  capability?: ModelCapability;
  resource_id: string;
  action_label: string;
}
