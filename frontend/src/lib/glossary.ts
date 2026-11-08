/**
 * 全站共享术语表：面向新手的白话说法。
 * 新页面/文案直接引用这里的常量，保证同一个概念在各处叫法一致。
 * 专业页面需要保留原词时，可用 `${TERMS.storyBible}（Story Bible）` 的形式附注。
 */
export const TERMS = {
  storyBible: '故事设定',
  seriesPlan: '分集计划',
  script: '剧本',
  storyboard: '画面脚本',
  assets: '角色与场景图',
  consistency: '前后统一',
  recipe: '生成方案',
  blocker: '待处理项',
  suggestion: '建议优化项',
  certification: '检测',
  readiness: '可用状态',
  demoMode: '演示模式',
  stepMode: '分步制作（专业）',
  proMode: '专业模式',
} as const;

export type GlossaryKey = keyof typeof TERMS;
