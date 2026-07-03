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
    label: '快速预览',
    shortLabel: '草稿',
    description: '先快速生成几秒到一集草片，用来确认故事节奏、画风和镜头是否对味。',
    modelHint: '未选择模型时将自动使用 Seedance 快速档（如已配置并验证）。',
    contractHint: '快速预览可先生成，但结果需要标记未锁定的角色资产、场景/道具资产和角色声线缺口，便于终稿前补齐。',
    generationStrategy: 'separate_video_tts',
  },
  final_quality: {
    value: 'final_quality',
    label: '高质量成片',
    shortLabel: '终稿',
    description: '草片确认后再生成关键镜头，优先画面质量、角色稳定和发布前一致性。',
    modelHint: '未选择模型时将自动使用 Seedance 高质量档（如已配置并验证）。',
    contractHint: '高质量成片是发布前路径，开拍前应完成角色/场景/道具资产锁、角色声线锁和生产快照，缺锁应作为门禁处理。',
    generationStrategy: 'separate_video_tts',
  },
  low_cost: {
    value: 'low_cost',
    label: '低成本试错',
    shortLabel: '低成本',
    description: '用于大量试镜头、长章节批处理或风格探索，优先控制成本。',
    modelHint: '建议选择低成本视频配置；没有具体配置时使用后端默认路由。',
    contractHint: '低成本模式仍需保留资产和声线缺口提示，不能覆盖已锁定的终稿快照。',
    generationStrategy: 'separate_video_tts',
  },
  separate_video_tts: {
    value: 'separate_video_tts',
    label: '视频配音分步',
    shortLabel: '分步',
    description: '视频和配音分开生成，后期更容易替换声线、字幕和单镜头返工。',
    modelHint: '视频与声音分别使用已选配置，适合需要多集声线一致的动漫生产。',
    contractHint: '分步模式应分别记录视频资产锁和 TTS 声线锁，便于单镜头返工时追溯。',
    generationStrategy: 'separate_video_tts',
  },
  direct_av_first: {
    value: 'direct_av_first',
    label: '音画直出优先',
    shortLabel: '直生',
    description: '优先尝试单模型直接生成音视频，适合快速验证节奏。',
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
