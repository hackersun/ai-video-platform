import { fetchJsonWithAuth } from './fetch-with-auth';
import type { StudioRunMode, StudioSnapshot, StudioWorkflowOption } from './studio-types';

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

export async function applyStudioAssetLocks(workflowId: string) {
  return fetchJsonWithAuth(`${API_BASE}/production-control/workflow/${workflowId}/asset-locks`, {
    method: 'POST',
    body: JSON.stringify({ create_missing_assets: true, persist: true }),
  });
}
