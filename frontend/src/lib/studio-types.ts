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

export type StudioSnapshot = {
  workflow?: {
    id?: string;
    title?: string;
    status?: string;
    current_step?: number;
    novel_id?: string | null;
    chapter_id?: string | null;
    script_id?: string | null;
    storyboard_id?: string | null;
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
