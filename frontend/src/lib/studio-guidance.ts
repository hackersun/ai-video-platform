import type { StudioGuidance, StudioGuidanceStage, StudioGuidedAction, StudioSnapshot } from './studio-types';

const fallbackStages: StudioGuidanceStage[] = [
  { id: 'content', label: '内容准备', status: 'working', description: '小说、章节和整书计划上下文。' },
  { id: 'bible', label: '设定锁定', status: 'working', description: '风格、角色、场景、道具和声线。' },
  { id: 'episode', label: '本集工程', status: 'working', description: '剧本、分镜、镜头和资产锁。' },
  { id: 'draft', label: '草片生产', status: 'working', description: '视频、配音、字幕和合成。' },
  { id: 'review', label: '复审出片', status: 'working', description: '复审、质量检查和成片验证。' },
];

export function getStudioGuidance(snapshot: StudioSnapshot | null): StudioGuidance {
  if (snapshot?.guidance) return snapshot.guidance;

  const issue = snapshot?.issues?.[0];
  const action =
    issue?.repair_action || snapshot?.actions?.[0] || snapshot?.production_bible_summary?.next_actions?.[0] || null;

  return {
    readiness_score: snapshot?.production_bible_summary?.readiness_score ?? 0,
    blocker_count: snapshot?.mode_policy?.blocking_issue_count ?? snapshot?.issues?.length ?? 0,
    current_stage: 'episode',
    stages: fallbackStages,
    next_action: action
      ? {
          ...action,
          reason: issue?.message || '继续处理当前工作流的下一步。',
          scope: ['当前工作流'],
          expected_outputs: ['刷新工作台状态'],
          confirmation: { required: action.risk === 'confirm' || action.risk === 'production' },
        }
      : null,
    secondary_actions: snapshot?.actions || [],
  };
}

export function getPrimaryGuidedAction(snapshot: StudioSnapshot | null): StudioGuidedAction | null {
  return getStudioGuidance(snapshot).next_action || null;
}

export function requiresConfirmation(action: StudioGuidedAction | null | undefined) {
  return Boolean(action?.confirmation?.required || action?.risk === 'confirm' || action?.risk === 'production');
}
