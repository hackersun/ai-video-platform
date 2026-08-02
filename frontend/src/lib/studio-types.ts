export type StudioRunMode = 'test' | 'production';

export type StudioActionRisk = 'safe' | 'navigation' | 'confirm' | 'production' | string;

export type StudioWorkflowOption = {
  workflow_id?: string;
  id?: string;
  title?: string;
  status?: string;
  novel_id?: string | null;
  chapter_id?: string | null;
  storyboard_id?: string | null;
  current_step?: number;
  completed_steps?: number[];
  video_job_ids?: string[];
  tts_job_ids?: string[];
  synthesis_job_ids?: string[];
  metadata?: Record<string, any>;
  updated_at?: string;
};

export type StudioIssue = {
  code?: string;
  message?: string;
  severity?: 'blocking' | 'error' | 'warning' | 'confirmable' | 'info' | string;
  original_severity?: string;
  bypassed?: boolean;
  bypass_error?: string;
  repair_action?: StudioAction | null;
};

export type StudioAction = {
  code: string;
  label: string;
  href?: string;
  risk?: StudioActionRisk;
};

export type StudioGuidedAction = StudioAction & {
  description?: string;
  reason?: string;
  scope?: string[];
  expected_outputs?: string[];
  confirmation?: {
    required?: boolean;
    title?: string;
    description?: string;
    impact?: string[];
    confirm_label?: string;
  };
  params?: Record<string, any>;
  source_issue_code?: string | null;
  execution?: string;
  method?: string;
  endpoint?: string;
};

export type StudioGuidanceStage = {
  id: 'facts' | 'assets' | 'episode_contract' | 'draft' | 'review' | 'final' | 'render' | 'publish' | string;
  label: string;
  status: 'ready' | 'working' | 'blocked' | string;
  description?: string;
  action?: StudioGuidedAction | null;
};

export type StudioGuidance = {
  readiness_score?: number;
  current_stage?: string;
  next_action?: StudioGuidedAction | null;
  recommended_action?: StudioGuidedAction | null;
  stages?: StudioGuidanceStage[];
  blocker_count?: number;
  mode?: StudioRunMode | string;
  breadcrumbs?: {
    novel_id?: string | null;
    chapter_id?: string | null;
    workflow_id?: string | null;
  };
  secondary_actions?: StudioAction[];
  blockers?: StudioIssue[];
  confirmable_warnings?: StudioIssue[];
  completed_evidence?: Array<{
    stage: string;
    evidence_id?: string | null;
    evidence_ids?: string[];
    evaluation_ids?: string[];
    hash?: string | null;
    job_id?: string | null;
    artifact_id?: string | null;
    score?: number | null;
  }>;
  orchestration_resume?: {
    task_id?: string;
    status?: string;
    failed_stage?: string;
    completed_stages?: string[];
    error_message?: string | null;
    safe_retry?: boolean;
  };
};

export type NovelProductionEntry = {
  novel_id: string;
  stage: 'content_prepare' | 'series_plan' | 'workflow_create' | 'studio_fix' | 'studio_ready' | 'not_found' | string;
  label: string;
  description: string;
  primary_action: StudioGuidedAction;
  metrics?: {
    chapter_count?: number;
    episode_count?: number;
    workflow_count?: number;
  };
  workflow_id?: string | null;
  chapter_id?: string | null;
};

export type StudioActionResult = StudioAction & {
  id?: string;
  workflow_id?: string;
  status?: 'suggested' | 'running' | 'succeeded' | 'failed' | 'skipped' | string;
  source_issue_code?: string | null;
  target_type?: string | null;
  target_id?: string | null;
  params?: Record<string, any>;
  result?: Record<string, any>;
  error_message?: string | null;
  mode?: StudioRunMode;
  allow_test_bypass?: boolean;
  bypass_reason?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type SeriesStudioContract = {
  enabled: boolean;
  primary_console: 'series_studio';
  expert_drilldowns: string[];
};

export type SeriesPlanEpisode = {
  episode_index?: number;
  episode_number?: number;
  title?: string;
  chapter_ids?: string[];
  chapters?: Array<{ id?: string; title?: string; chapter_number?: number }>;
  chapter_range?: [number, number] | number[] | {
    start_number?: number;
    end_number?: number;
    label?: string;
  };
  status?: string;
  summary?: string;
  next_action?: StudioAction;
  primary_chapter_id?: string | null;
  workflow_id?: string | null;
  target_duration_seconds?: number;
  aspect_ratio?: string;
  style?: string | null;
  narrative?: Record<string, string>;
  key_characters?: string[];
  key_scenes?: string[];
  key_props?: string[];
  key_events?: string[];
  production_counts?: Record<string, number>;
  carry_over_state?: Record<string, any>;
  production_readiness?: Record<string, any>;
  continuity_summary?: Record<string, any>;
  missing_requirements?: Array<Record<string, any>>;
};

export type SeriesPlan = {
  novel_id?: string;
  generated_at?: string;
  target_duration_seconds?: number;
  aspect_ratio?: string;
  style?: string | null;
  current_episode?: SeriesPlanEpisode | null;
  episodes?: SeriesPlanEpisode[];
  production_bible_summary?: Record<string, any>;
};

export type EpisodeContract = {
  contract_id?: string;
  workflow_id?: string;
  novel_id?: string;
  chapter_id?: string | null;
  locked_at?: string;
  production_bible_hash?: string;
  style_lock?: Record<string, any>;
  entity_locks?: Array<Record<string, any>>;
  required_checks?: string[];
  episode_index?: number;
  production_graph_version?: number;
  production_graph_hash?: string;
  opening_state?: Record<string, unknown>;
  expected_closing_state?: Record<string, unknown>;
  relevant_event_ids?: string[];
};

export type ProductionGraphEvent = {
  id: string;
  event_type?: string;
  entity_id?: string | null;
  episode_index?: number | null;
  story_time?: Record<string, unknown>;
  production_time?: Record<string, unknown>;
  before_state?: Record<string, unknown>;
  after_state?: Record<string, unknown>;
  approval_status?: string;
  production_version?: number;
  event_hash?: string;
  affected_episode_indices?: number[];
  affected_entity_ids?: string[];
  affected_shots?: Array<{ id: string; review_url: string }>;
  created_at?: string | null;
};

export type ProductionGraph = {
  novel_id?: string;
  version?: number;
  hash?: string | null;
  current_state?: Record<string, unknown>;
  story_order?: ProductionGraphEvent[];
  production_revisions?: ProductionGraphEvent[];
};

export type ConsistencyLedger = {
  workflow_id?: string;
  evaluation_status?: 'not_evaluated' | 'partial' | 'evaluated' | string;
  preflight_status?: 'ready' | 'blocked' | string;
  overall_score?: number | null;
  dimensions?: Record<string, number | null>;
  evaluated_dimensions?: string[];
  findings?: Array<{
    code?: string;
    severity?: 'blocking' | 'warning' | 'info' | string;
    shot_id?: string;
    entity_id?: string;
    message?: string;
    repair_action?: StudioAction | null;
  }>;
};

export type StudioSnapshot = {
  series_studio?: SeriesStudioContract;
  guidance?: StudioGuidance | null;
  series_plan?: SeriesPlan | null;
  episode_contract?: EpisodeContract | null;
  consistency_ledger?: ConsistencyLedger | null;
  production_graph?: ProductionGraph | null;
  stage_gate?: Pick<StudioGuidance, 'current_stage' | 'stages' | 'blockers' | 'confirmable_warnings' | 'completed_evidence' | 'recommended_action' | 'orchestration_resume'>;
  workflow?: {
    id?: string;
    title?: string;
    status?: string;
    current_step?: number;
    novel_id?: string | null;
    chapter_id?: string | null;
    script_id?: string | null;
    storyboard_id?: string | null;
    latest_production_strategy?: 'draft_fast' | 'final_quality' | 'low_cost' | 'separate_video_tts' | 'direct_av_first' | string | null;
    latest_production_strategy_label?: string | null;
    latest_production_strategy_intent?: string | null;
    latest_recommended_model_hint?: string | null;
    metadata?: Record<string, any>;
    updated_at?: string;
  };
  story_context?: {
    novel?: { id?: string; title?: string; genre?: string } | null;
    chapter?: { id?: string; title?: string; chapter_number?: number } | null;
    script?: { id?: string; title?: string; status?: string } | null;
    storyboard?: { id?: string; title?: string; shot_count?: number } | null;
  };
  story_bible?: {
    id?: string;
    title?: string;
    style?: string;
    worldview?: string;
    character_rule_count?: number;
    scene_rule_count?: number;
    prop_rule_count?: number;
    event_count?: number;
  };
  production_bible_summary?: {
    version?: string;
    novel_id?: string;
    story_bible_id?: string | null;
    readiness_score?: number;
    style?: Record<string, any>;
    characters?: Array<Record<string, any>>;
    scenes?: Array<Record<string, any>>;
    props?: Array<Record<string, any>>;
    events?: Array<Record<string, any>>;
    voices?: Array<Record<string, any>>;
    next_actions?: StudioAction[];
    asset_readiness?: {
      asset_count?: number;
      missing_asset_count?: number;
      ready?: boolean;
    };
    missing_requirements?: Array<Record<string, any>>;
    counts?: Record<string, number>;
  };
  state_machine?: Record<string, any>;
  production?: {
    shot_count?: number;
    asset_lock_coverage?: number;
    entity_ref_coverage?: number;
    ready?: boolean;
  };
  shots?: Array<{
    id: string;
    shot_number?: number;
    episode_shot_number?: number | null;
    scene_index?: number | null;
    scene_title?: string | null;
    storyboard_id?: string;
    duration?: number;
    prompt?: string;
    dialogue?: string;
    image_url?: string | null;
    video_status?: string;
    audio_status?: string;
    asset_lock_count?: number;
    entity_ref_count?: number;
    quality_report?: Record<string, any>;
  }>;
  assets?: {
    total_count?: number;
    locked_count?: number;
    final_count?: number;
    by_category?: Record<string, number>;
    items?: Array<Record<string, any>>;
  };
  jobs?: {
    summary?: {
      video_count?: number;
      tts_count?: number;
      synthesis_count?: number;
      media_count?: number;
      completed_media_count?: number;
    };
    video_jobs?: Array<{
      id?: string;
      task_id?: string;
      status?: string;
      reference_package_mode?: string | null;
      reference_package?: {
        mode?: string;
        image_count?: number;
        video_count?: number;
        audio_count?: number;
        cropped_count?: number;
        dropped_count?: number;
        dropped?: Array<{
          reason?: string;
          entity_name?: string;
          view_key?: string;
        }>;
      } | null;
      created_at?: string | null;
      updated_at?: string | null;
    }>;
    tts_jobs?: Array<{ id?: string; status?: string; created_at?: string | null }>;
    synthesis_jobs?: Array<{ id?: string; status?: string; output_url?: string | null; is_publishable?: boolean }>;
    media_jobs?: Array<{ id?: string; status?: string }>;
  };
  timeline?: {
    id?: string;
    name?: string;
    status?: string;
    clip_count?: number;
    preview_url?: string;
  };
  issues?: StudioIssue[];
  actions?: StudioAction[];
  mode_policy?: {
    mode?: StudioRunMode;
    ready?: boolean;
    blocking_issue_count?: number;
    warning_issue_count?: number;
    confirmable_issue_count?: number;
    bypassed_issue_count?: number;
    bypass_audit?: Record<string, any> | null;
  };
};

export type QualityGateDimension = {
  id?: string;
  dimension: 'narrative_truth' | 'character_visual' | 'scene_prop_state' | 'motion_camera' | 'voice_lipsync' | 'delivery_integrity';
  expected_state?: Record<string, any>;
  observed_state?: Record<string, any>;
  evidence?: Record<string, any>;
  score?: number;
  confidence?: number;
  severity?: 'pass' | 'warning' | 'blocking';
  blocking?: boolean;
  artifact_id?: string;
};

export type QualityGateSummary = {
  ready: boolean;
  overall_readiness: 'ready' | 'warning' | 'blocked';
  dimensions: QualityGateDimension[];
  blockers?: Array<{ code: string; dimension?: string; artifact_id?: string }>;
  warnings?: Array<{ code: string; dimension?: string; artifact_id?: string }>;
  suggested_repair?: {
    issue_code: string;
    actions: string[];
    affected_artifact_ids: string[];
    cost_risk?: { cost?: string; risk?: string; scope?: string };
    available?: boolean;
    navigation_url?: string | null;
  } | null;
};
