import { modelCenterHref } from '@/features/model-center/navigation';

function quickAction(actionId: string, label: string, pathname: string, focus: string) {
  return { actionId, label, focus, href: `${pathname}?focus=${focus}` };
}

function modelCenterQuickAction(actionId: string, label: string, section: 'connections' | 'catalog' | 'recipes', capability?: 'text_generation' | 'image_generation' | 'video_generation' | 'speech_generation') {
  return { actionId, label, focus: section, href: modelCenterHref({ section, capability, returnTo: '/studio' }) };
}

export const STUDIO_QUICK_ACTIONS = {
  entities: quickAction('entities', '角色与道具设定', '/studio/cards', 'entities'),
  storyBible: quickAction('story-bible', '小说设定与一致性', '/story-bibles', 'story-bible'),
  episodeSetup: quickAction('episode-setup', '本集小说与章节关联', '/workflow', 'episode-setup'),
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
  jobs: quickAction('jobs', '失败任务处理', '/jobs', 'jobs'),
  modelCatalog: modelCenterQuickAction('model-catalog', '模型能力配置', 'catalog'),
  videoModels: modelCenterQuickAction('video-models', '视频模型配置', 'catalog', 'video_generation'),
  productionRecipes: modelCenterQuickAction('production-recipes', '生产组合预设', 'recipes'),
} as const;

export function studioQuickTaskLabel(focus: string) {
  return Object.values(STUDIO_QUICK_ACTIONS).find((action) => action.focus === focus)?.label;
}
