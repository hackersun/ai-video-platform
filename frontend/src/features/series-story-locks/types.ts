export type StoryLockPreparation = {
  story_bible_id: string;
  version: number;
  status: string;
  idempotent: boolean;
  required_entity_ids: string[];
  unresolved_entity_ids: string[];
  unrelated_candidate_count: number;
  closure_hash: string;
  auto_approved_count: number;
  manual_approved_count: number;
  unresolved_count: number;
};

export type StoryAssetRepairResult = {
  status: string;
  archived_noise_count: number;
  merged_duplicate_count: number;
  cleared_shot_count: number;
  repaired_dialogue_count: number;
  chapter_count: number;
  retry_story_lock: boolean;
};
