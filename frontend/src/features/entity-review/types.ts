export type EntityType = 'character' | 'scene' | 'prop' | 'event';
export type ReviewStatus = 'candidate' | 'approved' | 'rejected' | 'legacy_active' | 'archived';

export type ReviewEntity = {
  id: string;
  novel_id?: string | null;
  entity_type: EntityType;
  name: string;
  canonical_name?: string | null;
  aliases: string[];
  description?: string | null;
  appearance?: string | null;
  visual_prompt?: string | null;
  evidence?: string | null;
  confidence: number;
  source: string;
  review_status: ReviewStatus;
  is_approved: boolean;
  attributes: Record<string, any>;
  relations: Array<Record<string, any>>;
  extra_data: Record<string, any>;
  updated_at?: string | null;
};

export type ReviewSummary = {
  total: number;
  counts?: Record<string, number>;
  by_type?: Record<string, number>;
  candidate_count: number;
  approved_count: number;
  rejected_count: number;
  duplicate_risk_count?: number;
  missing_evidence_count?: number;
  rejected_noise_count?: number;
  asset_gap_count?: number;
};

export type ReviewPage = {
  items: ReviewEntity[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  summary: ReviewSummary;
};

export type ReanalysisResult = {
  mode: 'preview' | 'apply';
  preview_run_id: string;
  current: ReviewEntity;
  proposed: Partial<ReviewEntity>;
  differences: Record<string, { before: unknown; after: unknown }>;
  model_execution: Record<string, any>;
};

export type RebuildResult = {
  mode: 'preview' | 'apply';
  preview_run_id: string;
  proposed: Array<Record<string, any>>;
  archived_count: number;
  created_count: number;
  model_execution: Record<string, any>;
  summary: ReviewSummary;
};
