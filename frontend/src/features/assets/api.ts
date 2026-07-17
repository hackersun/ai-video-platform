import { apiClient } from '@/lib/api-client';
import type { AssetEntityDeactivation, AssetEntityOption } from './types';

export async function listAssetEntityOptions(params: {
  novel_id?: string;
  chapter_id?: string;
  script_id?: string;
  entity_type?: string;
  limit?: number;
} = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value));
  });
  const query = search.toString();
  return apiClient.request<AssetEntityOption[]>(
    `/asset-maintenance/entity-options${query ? `?${query}` : ''}`
  );
}
export function deactivateAssetEntity(entityId: string, reason = '用户从资产工作台停用') {
  return apiClient.request<AssetEntityDeactivation>(
    `/asset-maintenance/entities/${entityId}/deactivate`,
    { method: 'POST', body: JSON.stringify({ reason }) }
  );
}
