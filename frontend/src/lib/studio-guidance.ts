import type { StudioGuidance, StudioGuidanceStage, StudioGuidedAction, StudioSnapshot } from './studio-types';

const fallbackStages: StudioGuidanceStage[] = [
  { id: 'facts', label: '事实锁定', status: 'working' },
  { id: 'assets', label: '资产锁定', status: 'blocked' },
  { id: 'episode_contract', label: '剧集合约', status: 'blocked' },
  { id: 'draft', label: '草片', status: 'blocked' },
  { id: 'review', label: '复审', status: 'blocked' },
  { id: 'final', label: '终稿', status: 'blocked' },
  { id: 'render', label: '渲染', status: 'blocked' },
  { id: 'publish', label: '发布', status: 'blocked' },
];

export function getStudioGuidance(snapshot: StudioSnapshot | null): StudioGuidance {
  if (snapshot?.guidance) return snapshot.guidance;

  const issue = snapshot?.issues?.[0];
  const action =
    issue?.repair_action || snapshot?.actions?.[0] || snapshot?.production_bible_summary?.next_actions?.[0] || null;

  return {
    readiness_score: snapshot?.production_bible_summary?.readiness_score ?? 0,
    blocker_count: snapshot?.mode_policy?.blocking_issue_count ?? snapshot?.issues?.length ?? 0,
    current_stage: 'facts',
    stages: fallbackStages,
    recommended_action: action
      ? {
          ...action,
          reason: issue?.message || '继续处理当前工作流的下一步。',
          scope: ['当前工作流'],
          expected_outputs: ['刷新工作台状态'],
          confirmation: { required: action.risk === 'confirm' || action.risk === 'production' },
        }
      : null,
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
  const guidance = getStudioGuidance(snapshot);
  return guidance.recommended_action || guidance.next_action || null;
}

export function requiresConfirmation(action: StudioGuidedAction | null | undefined) {
  return Boolean(action?.confirmation?.required || action?.risk === 'confirm' || action?.risk === 'production');
}
