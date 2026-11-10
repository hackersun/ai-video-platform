/**
 * 全站共享术语表：面向新手的白话说法。
 * 新页面/文案直接引用这里的常量，保证同一个概念在各处叫法一致。
 * 专业页面需要保留原词时，可用 `${TERMS.storyBible}（Story Bible）` 的形式附注；主路径默认 UI 不出现英文行话。
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
  readiness: '就绪度',
  demoMode: '演示模式',
  stepMode: '分步制作（专业）',
  proMode: '专业模式',
  productionBible: '制作设定本',
  seriesStudio: '分集工作台',
  producer: 'AI 制片',
  gate: '发布检查',
  stateMachine: '人物场景规则',
  tts: '配音',
  seed: '随机种子',
  oneClick: '一键生成视频',
} as const;

export type GlossaryKey = keyof typeof TERMS;
