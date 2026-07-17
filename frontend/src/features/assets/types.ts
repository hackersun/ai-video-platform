export type AssetEntityOption = {
  id: string;
  name: string;
  entity_type: string;
  novel_id?: string;
  chapter_id?: string;
  script_id?: string;
  description?: string;
  appearance?: string;
  visual_prompt?: string;
  lifecycle_status: 'legacy_active' | 'approved';
  active_asset_count: number;
};

export type AssetEntityDeactivation = {
  entity_id: string;
  entity_name: string;
  lifecycle_status: 'archived';
  archived_asset_count: number;
  already_inactive: boolean;
};
