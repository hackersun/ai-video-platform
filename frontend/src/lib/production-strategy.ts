export type GenerationStrategy = 'separate_video_tts' | 'direct_av_first';

export type ProductionStrategy =
  | 'draft_fast'
  | 'final_quality'
  | 'low_cost'
  | 'separate_video_tts'
  | 'direct_av_first';

export type ProductionStrategyCopy = {
  value: ProductionStrategy;
  label: string;
  shortLabel: string;
  description: string;
  modelHint: string;
  generationStrategy: GenerationStrategy;
};

export const DEFAULT_PRODUCTION_STRATEGY: ProductionStrategy = 'draft_fast';

export const PRODUCTION_STRATEGY_COPY: Record<ProductionStrategy, ProductionStrategyCopy> = {
  draft_fast: {
    value: 'draft_fast',
    label: '快速草稿',
    shortLabel: '草稿',
    description: '用于批量生成本集草片，优先速度和可审阅性。',
    modelHint: '建议使用 Seedance-2.0-fast 语义；未选择具体配置时由后端默认策略决定。',
    generationStrategy: 'separate_video_tts',
  },
  final_quality: {
    value: 'final_quality',
    label: '高质量终稿',
    shortLabel: '终稿',
    description: '用于草片通过后重生关键镜头，优先稳定性和画面质量。',
    modelHint: '建议使用 Seedance-2.0 语义；未选择具体配置时只作为策略建议保存。',
    generationStrategy: 'separate_video_tts',
  },
  low_cost: {
    value: 'low_cost',
    label: '低成本批量',
    shortLabel: '低成本',
    description: '用于大量试错或长章节批处理，优先成本控制。',
    modelHint: '建议选择低成本视频配置；没有具体配置时不绑定真实模型 ID。',
    generationStrategy: 'separate_video_tts',
  },
  separate_video_tts: {
    value: 'separate_video_tts',
    label: '分步视频 + TTS',
    shortLabel: '分步',
    description: '视频和配音分开生成，便于替换声线、字幕和单镜头返工。',
    modelHint: '视频与声音分别使用已选配置，适合常规动漫生产。',
    generationStrategy: 'separate_video_tts',
  },
  direct_av_first: {
    value: 'direct_av_first',
    label: '音画直生优先',
    shortLabel: '直生',
    description: '优先尝试单模型直出音视频，适合快速验证节奏。',
    modelHint: '需要后端存在可用直生音视频适配；否则应回到分步视频 + TTS。',
    generationStrategy: 'direct_av_first',
  },
};

export const PRODUCTION_STRATEGY_OPTIONS = Object.values(PRODUCTION_STRATEGY_COPY).map((strategy) => ({
  value: strategy.value,
  label: strategy.label,
}));

export function getProductionStrategyCopy(strategy?: ProductionStrategy): ProductionStrategyCopy {
  return PRODUCTION_STRATEGY_COPY[strategy || DEFAULT_PRODUCTION_STRATEGY];
}

export function getGenerationStrategyForProduction(strategy?: ProductionStrategy): GenerationStrategy {
  return getProductionStrategyCopy(strategy).generationStrategy;
}
