import { fetchJsonWithAuth } from './fetch-with-auth';
import type { SavedModelConfig } from './model-configs';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export type PromptSkill = {
  id: string;
  name: string;
  description?: string | null;
  task: string;
  stage?: string | null;
  content: string;
  variables?: Record<string, any>;
  priority?: number;
  inject_position?: string;
  version?: number;
  is_active?: boolean;
  is_builtin?: boolean;
  tags?: string[];
};

export type PromptSkillPayload = {
  name: string;
  description?: string;
  task: string;
  stage?: string;
  content: string;
  variables?: Record<string, any>;
  priority?: number;
  inject_position?: string;
  is_active?: boolean;
  tags?: string[];
};

export async function listPromptSkills(task?: string, options: { active?: boolean } = {}) {
  const params = new URLSearchParams();
  if (task) params.set('task', task);
  if (options.active !== undefined) params.set('active', String(options.active));
  const qs = params.toString();
  return fetchJsonWithAuth<{ items: PromptSkill[]; count: number }>(
    `${API_BASE}/prompt-skills${qs ? `?${qs}` : ''}`
  );
}

export async function createPromptSkill(payload: PromptSkillPayload) {
  return fetchJsonWithAuth<PromptSkill>(`${API_BASE}/prompt-skills`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updatePromptSkill(skillId: string, payload: PromptSkillPayload) {
  return fetchJsonWithAuth<PromptSkill>(`${API_BASE}/prompt-skills/${skillId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function clonePromptSkill(skillId: string) {
  return fetchJsonWithAuth<PromptSkill>(`${API_BASE}/prompt-skills/${skillId}/clone`, {
    method: 'POST',
  });
}

export async function activatePromptSkill(skillId: string) {
  return fetchJsonWithAuth<PromptSkill>(`${API_BASE}/prompt-skills/${skillId}/activate`, {
    method: 'POST',
  });
}

export async function deletePromptSkill(skillId: string) {
  return fetchJsonWithAuth<{ deleted: boolean; id: string }>(`${API_BASE}/prompt-skills/${skillId}`, {
    method: 'DELETE',
  });
}

export async function listPromptSkillOptimizationModelConfigs() {
  return fetchJsonWithAuth<SavedModelConfig[]>(`${API_BASE}/llm/configs`);
}

export async function previewPromptSkill(payload: {
  task: string;
  skill_ids?: string[];
  context?: Record<string, any>;
  draft_name?: string;
  draft_content?: string;
  draft_stage?: string;
}) {
  return fetchJsonWithAuth<{
    task: string;
    skill_count: number;
    skill_blocks: string[];
    prompt: string;
  }>(`${API_BASE}/prompt-skills/preview`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function optimizePromptSkill(payload: {
  task: string;
  name?: string;
  description?: string;
  content: string;
  mode?: 'polish' | 'tighten' | 'productionize';
  model_config_id?: string;
}) {
  return fetchJsonWithAuth<{
    task: string;
    source: 'ai_model' | 'local_rules';
    original_content: string;
    optimized_content: string;
    suggestions: string[];
    warnings: string[];
  }>(`${API_BASE}/prompt-skills/optimize`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
