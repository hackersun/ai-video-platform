export type AssetWorkbenchItem = {
  id: string;
  category: string;
  name: string;
  description?: string;
  asset_type?: string;
  url?: string;
  thumbnail_url?: string;
  source_url?: string;
  project_id?: string;
  novel_id?: string;
  chapter_id?: string;
  script_id?: string;
  entity_id?: string;
  entity_type?: string;
  tags?: string[];
  style_tags?: string[];
  generation_params?: Record<string, any>;
  is_public?: boolean;
  usage_count?: number;
  version?: number;
  is_locked?: boolean;
  is_final?: boolean;
  status?: string;
  error_message?: string;
  visual_consistency?: { score?: number } | number;
  created_at?: string;
  updated_at?: string;
};

export type AssetCollectionKey =
  | 'all'
  | 'attention'
  | 'failed'
  | 'draft'
  | 'locked'
  | 'character'
  | 'scene'
  | 'prop';

const SNAPSHOT_IMAGE_SIZE_ERROR = '图像尺寸参数与当前模型不兼容，可直接重试；如仍失败，请展开“生成设置”后重建资产包。';

function userFacingFailure(rawError: string) {
  return rawError.includes('invalid_snapshot_params: image_size') ? SNAPSHOT_IMAGE_SIZE_ERROR : rawError;
}

export function getAssetFailure(asset: AssetWorkbenchItem) {
  const params = asset.generation_params || {};
  const status = asset.status || params.status;
  if (status !== 'failed' && status !== 'error') return null;
  const rawError = asset.error_message || params.error_message || params.error_reason || '生成失败，暂无详细原因';
  return {
    error: userFacingFailure(rawError),
    technicalError: rawError,
    retryable: params.retryable !== false,
    viewLabel: params.view_label || params.view_title || params.view_key,
  };
}

export function getConsistencyScore(asset: AssetWorkbenchItem) {
  const topLevel = typeof asset.visual_consistency === 'number'
    ? asset.visual_consistency
    : asset.visual_consistency?.score;
  const nested = asset.generation_params?.visual_consistency?.score;
  const score = topLevel ?? nested;
  return typeof score === 'number' && Number.isFinite(score) ? Math.round(score) : null;
}

export function matchesCollection(asset: AssetWorkbenchItem, collection: AssetCollectionKey) {
  const failed = Boolean(getAssetFailure(asset));
  if (collection === 'all') return true;
  if (collection === 'attention') return failed || !asset.is_final;
  if (collection === 'failed') return failed;
  if (collection === 'draft') return !failed && !asset.is_final;
  if (collection === 'locked') return Boolean(asset.is_locked);
  return asset.category === collection;
}

export function workbenchStatus(asset: AssetWorkbenchItem) {
  if (getAssetFailure(asset)) return { label: '生成失败', tone: 'red' as const };
  if (asset.is_locked) return { label: '已锁定', tone: 'green' as const };
  if (asset.is_final) return { label: '已定稿', tone: 'cyan' as const };
  return { label: '待定稿', tone: 'amber' as const };
}
