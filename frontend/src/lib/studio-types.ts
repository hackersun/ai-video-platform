export type StudioRunMode = 'test' | 'production';

export type StudioWorkflowOption = {
  workflow_id?: string;
  id?: string;
  title?: string;
  status?: string;
  novel_id?: string | null;
  chapter_id?: string | null;
  storyboard_id?: string | null;
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
  risk?: 'safe' | 'navigation' | 'confirm' | string;
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
  chapter_range?: [number, number] | number[];
  status?: string;
  summary?: string;
  workflow_id?: string | null;
  carry_over_state?: Record<string, any>;
  production_readiness?: Record<string, any>;
  continuity_summary?: Record<string, any>;
  missing_requirements?: Array<Record<string, any>>;
};

export type SeriesPlan = {
  novel_id?: string;
  generated_at?: string;
  current_episode?: SeriesPlanEpisode | null;
  episodes?: SeriesPlanEpisode[];
  production_bible_summary?: Record<string, any>;
};

export type StudioSnapshot = {
  series_studio?: SeriesStudioContract;
  series_plan?: SeriesPlan | null;
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
    prompt?: string;
    dialogue?: string;
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
