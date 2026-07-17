function quickAction(actionId: string, label: string, pathname: string, focus: string) {
  return { actionId, label, focus, href: `${pathname}?focus=${focus}` };
}

export const STUDIO_QUICK_ACTIONS = {
  entities: quickAction('entities', '角色与道具设定', '/studio/cards', 'entities'),
  sceneAssets: quickAction('scene-assets', '场景资产准备', '/assets', 'scene-assets'),
  referenceLocks: quickAction('reference-locks', '素材与引用锁定', '/studio/cards', 'reference-locks'),
  storyboard: quickAction('storyboard', '剧本与分镜', '/storyboards', 'storyboard'),
  voices: quickAction('voices', '配音与声音锁', '/studio/cards', 'voices'),
  subtitles: quickAction('subtitles', '字幕与文本校对', '/subtitles', 'editor'),
  videoGeneration: quickAction('video-generation', '镜头生成', '/video-generation', 'generate'),
  shotReferences: quickAction('shot-references', '镜头参考检查', '/studio/shot-review', 'references'),
  shotQuality: quickAction('shot-quality', '草片质量', '/studio/shot-review', 'quality'),
  continuityReview: quickAction('continuity-review', '一致性评审', '/studio/continuity-review', 'findings'),
  timeline: quickAction('timeline', '时间线与精修', '/workflow', 'timeline'),
  output: quickAction('output', '成片输出', '/workflow', 'output'),
} as const;

export function studioQuickTaskLabel(focus: string) {
  return Object.values(STUDIO_QUICK_ACTIONS).find((action) => action.focus === focus)?.label;
}
