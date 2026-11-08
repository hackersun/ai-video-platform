/** 全站共用的制作阶段中文名（整书计划 / 分步 Series Run / 一键流水线）。 */
export const STAGE_LABELS: Record<string, string> = {
  // 制作入口
  content_prepare: '内容准备', series_plan: '整书计划', workflow_create: '本集工程',
  studio_fix: '工作室处理', studio_ready: '可继续生产', not_found: '不可用',
  // 分步控制（Series Run）
  created: '等待启动', workflow_ready: '工程就绪', script_ready: '剧本就绪',
  storyboard_ready: '分镜就绪', shots_ready: '镜头就绪', anchor_ready: '关键镜头就绪',
  media_running: '画面生成中', completed: '已完成', blocked: '需处理', failed: '失败', paused: '已暂停',
  cancelled: '已取消', running: '进行中',
  // 一键生成视频流水线
  accepted: '已提交', ensuring_plan: '准备整书计划', ensuring_run: '准备整书计划',
  run_front_to_shots: '生成剧本和分镜', run_media_quality: '生成画面和配音',
  episode_rendering: '渲染各集', book_assembling: '拼接整书', publication_gating: '质量检查',
  publishing: '发布中', succeeded: '已完成',
};

export const stageLabel = (stage?: string | null) => (stage ? STAGE_LABELS[stage] || stage : '');

/** 一键流水线步骤条顺序。 */
export const PIPELINE_STEPS = [
  'accepted', 'ensuring_run', 'run_front_to_shots', 'run_media_quality', 'episode_rendering',
  'book_assembling', 'publication_gating', 'publishing', 'succeeded',
] as const;

/** 面向新手的 4 个大阶段：把 9 个流水线步骤合并展示，细节放在「查看详情」。 */
export const PIPELINE_PHASES = [
  { id: 'prepare', label: '准备', steps: ['accepted', 'ensuring_run', 'ensuring_plan'] },
  { id: 'script', label: '写剧本', steps: ['run_front_to_shots'] },
  { id: 'media', label: '做画面和配音', steps: ['run_media_quality', 'episode_rendering'] },
  { id: 'assemble', label: '合成视频', steps: ['book_assembling', 'publication_gating', 'publishing', 'succeeded'] },
] as const;

export function pipelinePhaseIndex(stage?: string | null) {
  const idx = PIPELINE_PHASES.findIndex((phase) => (phase.steps as readonly string[]).includes(stage || ''));
  return idx < 0 ? 0 : idx;
}
