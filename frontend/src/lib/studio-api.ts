import { fetchJsonWithAuth } from './fetch-with-auth';
import type { StudioActionResult, StudioGuidedAction, StudioRunMode, StudioSnapshot, StudioWorkflowOption } from './studio-types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function getStudioWorkflows() {
  return fetchJsonWithAuth<StudioWorkflowOption[]>(`${API_BASE}/workflow`);
}

export async function getStudioSnapshot(
  workflowId: string,
  params: {
    mode?: StudioRunMode;
    allow_test_bypass?: boolean;
    bypass_reason?: string;
  } = {}
) {
  const searchParams = new URLSearchParams();
  if (params.mode) searchParams.set('mode', params.mode);
  if (params.allow_test_bypass !== undefined) {
    searchParams.set('allow_test_bypass', String(params.allow_test_bypass));
  }
  if (params.bypass_reason) searchParams.set('bypass_reason', params.bypass_reason);
  const qs = searchParams.toString();
  return fetchJsonWithAuth<StudioSnapshot>(
    `${API_BASE}/studio/workflows/${workflowId}/snapshot${qs ? `?${qs}` : ''}`
  );
}

export async function runStudioAction(
  workflowId: string,
  payload: {
    code: string;
    params?: Record<string, any>;
    mode?: StudioRunMode;
    allow_test_bypass?: boolean;
    bypass_reason?: string;
    source_issue_code?: string;
  }
) {
  return fetchJsonWithAuth<StudioActionResult>(`${API_BASE}/studio/workflows/${workflowId}/actions`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getStudioActions(workflowId: string) {
  return fetchJsonWithAuth<{ items: StudioActionResult[]; count: number }>(
    `${API_BASE}/studio/workflows/${workflowId}/actions`
  );
}

export async function resumeStudioOrchestration(workflowId: string, taskId: string) {
  return fetchJsonWithAuth<{
    workflow_id: string;
    task_id: string;
    status: string;
    resumed_stage: string;
    completed_stages: string[];
    safe_next_action: StudioGuidedAction;
    action_result?: StudioActionResult | null;
  }>(`${API_BASE}/studio/workflows/${workflowId}/orchestration/${taskId}/resume`, {
    method: 'POST',
  });
}
