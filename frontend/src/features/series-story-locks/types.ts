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
