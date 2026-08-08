export type PromptUsageStatus =
  | 'effective'
  | 'overridden'
  | 'internal_fallback'
  | 'invalid_binding'
  | 'not_applicable';

export interface PromptUsageModel {
  profile_version_id: string;
  provider_code: string;
  provider_name: string;
  api_model_id: string;
  name: string;
  capabilities: string[];
}

export interface PromptUsageTemplate {
  id: string;
  profile_version_id: string;
  name: string;
  version: number;
}

export interface PromptUsageStage {
  id: string;
  name: string;
  uses_prompt: boolean;
  status: PromptUsageStatus;
  message: string;
  model: PromptUsageModel | null;
  template: PromptUsageTemplate | null;
  routing: { source_label: string };
}

export interface PromptUsageGroup {
  id: string;
  name: string;
  stages: PromptUsageStage[];
}

export interface PromptUsageMap {
  summary: { total: number; counts: Partial<Record<PromptUsageStatus, number>> };
  groups: PromptUsageGroup[];
}

export interface PromptUsageCandidate {
  id: string;
  profile_id: string;
  name: string;
  task: string;
  version: number;
  status: 'published';
  source_label: string;
}

export interface PromptUsageAssignmentResult {
  profile_id: string;
  version_id: string;
  name: string;
  task: string;
  version: number;
  status: 'draft';
}

const statuses = new Set<PromptUsageStatus>([
  'effective', 'overridden', 'internal_fallback', 'invalid_binding', 'not_applicable',
]);

function invalid(): never {
  throw new Error('提示词使用地图响应无效');
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid();
  return value as Record<string, unknown>;
}

function text(value: unknown): string {
  if (typeof value !== 'string') invalid();
  return value;
}

function numberValue(value: unknown): number {
  if (typeof value !== 'number') invalid();
  return value;
}

function parseModel(value: unknown): PromptUsageModel | null {
  if (value === null) return null;
  const item = record(value);
  if (!Array.isArray(item.capabilities)) invalid();
  return {
    profile_version_id: text(item.profile_version_id),
    provider_code: text(item.provider_code),
    provider_name: text(item.provider_name),
    api_model_id: text(item.api_model_id),
    name: text(item.name),
    capabilities: item.capabilities.map(text),
  };
}

function parseTemplate(value: unknown): PromptUsageTemplate | null {
  if (value === null) return null;
  const item = record(value);
  return {
    id: text(item.id), profile_version_id: text(item.profile_version_id),
    name: text(item.name), version: numberValue(item.version),
  };
}

export function parsePromptUsageStage(value: unknown): PromptUsageStage {
  const item = record(value);
  if (typeof item.uses_prompt !== 'boolean' || !statuses.has(item.status as PromptUsageStatus)) invalid();
  const routing = record(item.routing);
  return {
    id: text(item.id), name: text(item.name), uses_prompt: item.uses_prompt,
    status: item.status as PromptUsageStatus, message: text(item.message),
    model: parseModel(item.model), template: parseTemplate(item.template),
    routing: { source_label: text(routing.source_label) },
  };
}

export function parsePromptUsageMap(value: unknown): PromptUsageMap {
  const item = record(value);
  const summary = record(item.summary);
  const counts = record(summary.counts);
  if (!Array.isArray(item.groups)) invalid();
  return {
    summary: { total: numberValue(summary.total), counts: counts as Partial<Record<PromptUsageStatus, number>> },
    groups: item.groups.map((value) => {
      const group = record(value);
      if (!Array.isArray(group.stages)) invalid();
      return { id: text(group.id), name: text(group.name), stages: group.stages.map(parsePromptUsageStage) };
    }),
  };
}

export function parsePromptUsageCandidates(value: unknown): PromptUsageCandidate[] {
  const item = record(value);
  if (!Array.isArray(item.items)) invalid();
  return item.items.map((value) => {
    const candidate = record(value);
    if (candidate.status !== 'published') invalid();
    return {
      id: text(candidate.id), profile_id: text(candidate.profile_id), name: text(candidate.name),
      task: text(candidate.task), version: numberValue(candidate.version), status: 'published',
      source_label: text(candidate.source_label),
    };
  });
}

export function parsePromptUsageAssignment(value: unknown): PromptUsageAssignmentResult {
  const item = record(value);
  if (item.status !== 'draft') invalid();
  return {
    profile_id: text(item.profile_id), version_id: text(item.version_id),
    name: text(item.name), task: text(item.task), version: numberValue(item.version), status: 'draft',
  };
}
