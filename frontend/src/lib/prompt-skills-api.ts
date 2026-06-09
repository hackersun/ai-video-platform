import { fetchJsonWithAuth } from './fetch-with-auth';

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

export async function listPromptSkills(task?: string) {
  const params = new URLSearchParams();
  if (task) params.set('task', task);
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

export async function previewPromptSkill(payload: {
  task: string;
  skill_ids?: string[];
  context?: Record<string, any>;
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
