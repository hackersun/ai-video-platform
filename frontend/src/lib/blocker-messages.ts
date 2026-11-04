/** 阻塞码 → 中文说明 + 去处理入口。未知码不再直接显示原始 code/JSON。 */
export interface BlockerInfo { title: string; hint: string; href?: string; action?: string }

const MAP: Record<string, BlockerInfo> = {
  models_not_configured: { title: '还没有配置可用的模型', hint: '请先在模型中心配置并测试文本、图片、配音、视频模型。', href: '/llm-config', action: '去模型中心' },
  model_bindings_not_fresh: { title: '模型配置需要重新验证', hint: '模型配置已变化或过期，请在模型中心重新测试。', href: '/llm-config', action: '去模型中心' },
  model_bindings_missing: { title: '还没有配置可用的模型', hint: '请先在模型中心配置模型。', href: '/llm-config', action: '去模型中心' },
  provider_binding_not_ready: { title: '模型服务暂不可用', hint: '请在模型中心检查服务状态。', href: '/llm-config', action: '去模型中心' },
  chapters_missing: { title: '章节不足', hint: '至少需要 2 章内容才能生成整书视频。', href: '?tab=chapters', action: '去添加章节' },
  series_plan_episodes_missing: { title: '整书计划为空', hint: '请先检查章节内容后重新生成整书计划。', href: '?tab=series-plan', action: '查看整书计划' },
  series_plan_build_failed: { title: '整书计划生成失败', hint: '请检查章节内容或稍后重试。', href: '?tab=series-plan', action: '查看整书计划' },
  voice_selection_required: { title: '需要为角色选择配音', hint: '请在「高级：分步控制」里为主角选择声音。', href: '?tab=series-plan', action: '去选择配音' },
  voice_selection_stale: { title: '配音选择已过期', hint: '请重新为角色选择声音。', href: '?tab=series-plan', action: '去选择配音' },
  full_shot_selection_required: { title: '部分镜头无法自动选取', hint: '请在「高级：分步控制」中手动确认关键镜头。', href: '?tab=series-plan', action: '去确认镜头' },
  anchor_selection_missing: { title: '缺少关键镜头', hint: '请在「高级：分步控制」中选择关键镜头。', href: '?tab=series-plan', action: '去选择镜头' },
  story_bible_not_approved: { title: '故事设定未确认', hint: '请先确认故事设定（人物、场景、道具）。', href: '?tab=story-bible', action: '去确认设定' },
  story_bible_missing: { title: '缺少故事设定', hint: '请先生成并确认故事设定。', href: '?tab=story-bible', action: '去生成设定' },
  production_entities_unapproved: { title: '有人物/场景未确认', hint: '请在角色页确认待审核的人物和场景。', href: '?tab=characters', action: '去确认' },
  production_entity_conflict: { title: '人物设定有冲突', hint: '请在角色页合并或修正重复的人物。', href: '?tab=characters', action: '去处理' },
  story_lock_preparation_blocked: { title: '故事设定锁定失败', hint: '人物或剧情证据需要人工确认。', href: '?tab=characters', action: '去确认' },
  story_lock_source_invalid: { title: '章节内容与设定不一致', hint: '章节修改后设定需要重新确认。', href: '?tab=characters', action: '去确认' },
  story_lock_stale: { title: '章节已修改', hint: '请重新开始以使用最新章节。' },
  reference_preparation_blocked: { title: '参考图生成失败', hint: '请检查图片模型配置后重试。', href: '/llm-config', action: '去模型中心' },
  live_canary_unavailable: { title: '预算策略不可用', hint: '请检查费用预算设置。', href: '/settings', action: '去设置' },
  projected_budget_exceeded: { title: '预计费用超过上限', hint: '请提高预算上限或减少镜头。', href: '/settings', action: '去设置' },
  trusted_budget_policy_missing: { title: '未设置费用预算', hint: '请先设置预算。', href: '/settings', action: '去设置' },
  shots_missing: { title: '没有可用的镜头', hint: '分镜为空，请检查剧本生成结果。' },
  ffmpeg_not_installed: { title: '服务器缺少视频处理工具', hint: '请联系管理员安装 ffmpeg。' },
  book_assemble_empty: { title: '没有可拼接的视频', hint: '各集都没有成功渲染，请重试。' },
  episode_media_missing: { title: '部分分集视频丢失', hint: '请重新生成。' },
  novel_not_found: { title: '小说不存在', hint: '可能已被删除。', href: '/novels', action: '返回小说列表' },
  series_run_create_failed: { title: '创建制作任务失败', hint: '请稍后重试。' },
  worker_unhandled_exception: { title: '后台任务异常', hint: '请稍后点「继续」重试，如反复出现请联系管理员。', href: '/jobs', action: '去任务中心' },
  paused: { title: '已暂停', hint: '点「继续」恢复生成。' },
};

export function blockerInfo(code?: string | null, detail?: string | null): BlockerInfo {
  if (code && MAP[code]) return MAP[code];
  return { title: '生成遇到问题', hint: detail && !detail.trim().startsWith('{') ? detail : '请稍后重试，或在「高级：分步控制」中查看详情。' };
}

/** 兼容字符串 / {code,message} / 任意对象 的阻塞描述 → 一行中文。 */
export function blockerText(blocker: unknown): string {
  if (!blocker) return '';
  if (typeof blocker === 'string') return MAP[blocker] ? `${MAP[blocker].title}：${MAP[blocker].hint}` : blocker;
  const obj = blocker as { code?: string; message?: string; detail?: string };
  if (obj.code && MAP[obj.code]) return `${MAP[obj.code].title}：${MAP[obj.code].hint}`;
  return obj.message || obj.detail || '遇到未知问题，请刷新后重试';
}
