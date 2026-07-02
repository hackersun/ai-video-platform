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
  contractHint: string;
  generationStrategy: GenerationStrategy;
};

export const DEFAULT_PRODUCTION_STRATEGY: ProductionStrategy = 'draft_fast';

export const PRODUCTION_STRATEGY_COPY: Record<ProductionStrategy, ProductionStrategyCopy> = {
  draft_fast: {
    value: 'draft_fast',
    label: '快速草稿',
    shortLabel: '草稿',
    description: '用于批量生成本集草片，优先速度和可审阅性；允许先跑草稿，但必须保留资产/声线缺口提示。',
    modelHint: '建议使用 Seedance-2.0-fast 语义；未选择具体配置时由后端默认策略决定。',
    contractHint: '草稿模式可先生成，但结果需要标记未锁定的角色资产、场景/道具资产和角色声线缺口，便于终稿前补齐。',
    generationStrategy: 'separate_video_tts',
  },
  final_quality: {
    value: 'final_quality',
    label: '高质量终稿',
    shortLabel: '终稿',
    description: '用于草片通过后重生关键镜头，优先稳定性和画面质量；终稿模式要求资产锁和声线锁已就绪。',
    modelHint: '建议使用 Seedance-2.0 语义；未选择具体配置时只作为策略建议保存。',
    contractHint: '终稿模式是发布前质量路径，开拍前应完成角色/场景/道具资产锁、角色声线锁和生产快照，缺锁应作为门禁处理。',
    generationStrategy: 'separate_video_tts',
  },
  low_cost: {
    value: 'low_cost',
    label: '低成本批量',
    shortLabel: '低成本',
    description: '用于大量试错或长章节批处理，优先成本控制。',
    modelHint: '建议选择低成本视频配置；没有具体配置时不绑定真实模型 ID。',
    contractHint: '低成本模式仍需保留资产和声线缺口提示，不能覆盖已锁定的终稿快照。',
    generationStrategy: 'separate_video_tts',
  },
  separate_video_tts: {
    value: 'separate_video_tts',
    label: '分步视频 + TTS',
    shortLabel: '分步',
    description: '视频和配音分开生成，便于替换声线、字幕和单镜头返工。',
    modelHint: '视频与声音分别使用已选配置，适合常规动漫生产。',
    contractHint: '分步模式应分别记录视频资产锁和 TTS 声线锁，便于单镜头返工时追溯。',
    generationStrategy: 'separate_video_tts',
  },
  direct_av_first: {
    value: 'direct_av_first',
    label: '音画直生优先',
    shortLabel: '直生',
    description: '优先尝试单模型直出音视频，适合快速验证节奏。',
    modelHint: '需要后端存在可用直生音视频适配；否则应回到分步视频 + TTS。',
    contractHint: '直生模式也应携带同一份资产/声线锁要求；如果模型无法显式使用声线锁，需要在结果中保留缺口提示。',
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
