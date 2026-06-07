export type ModelCapability = 'text' | 'image' | 'audio' | 'video' | 'embedding' | 'other';

export interface SavedModelConfig {
  id: string;
  model_id: string;
  config_model_id?: string;
  api_model_id?: string;
  model_type?: string;
  model_capabilities?: string[];
  provider_id: string;
  provider_name?: string;
  model_name: string;
  name: string;
  is_default: boolean;
  test_status?: string | null;
  test_message?: string | null;
  usage_count?: number;
}

export const MODEL_CAPABILITY_LABELS: Record<ModelCapability, string> = {
  text: '文本生成',
  image: '图像生成',
  audio: '语音/声音',
  video: '视频生成',
  embedding: '向量检索',
  other: '其他能力',
};

export const MODEL_TEST_STATUS_LABELS: Record<string, string> = {
  success: '已验证',
  configured: '已配置',
  pending: '待测试',
  failed: '验证失败',
};

export function modelStatusLabel(status?: string | null) {
  return MODEL_TEST_STATUS_LABELS[status || ''] || '未验证';
}

export function modelStatusClass(status?: string | null) {
  if (status === 'success') return 'bg-emerald-500/15 text-emerald-100 border-emerald-400/20';
  if (status === 'failed') return 'bg-red-500/15 text-red-100 border-red-400/20';
  return 'bg-yellow-500/15 text-yellow-100 border-yellow-400/20';
}

export function isInternalTestModelConfig(config: Partial<SavedModelConfig> & Record<string, any>) {
  const text = [
    config.id,
    config.model_id,
    config.config_model_id,
    config.api_model_id,
    config.model_name,
    config.name,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return (
    text.includes('test-video-') ||
    text.includes('test-audio-') ||
    text.includes('test-image-') ||
    text.includes('test-text-') ||
    text.includes('doubao-seedance-test') ||
    text.includes('doubao-seedance-consistency-test') ||
    text.includes('speech-test')
  );
}

export function getModelCapability(configOrModel: { model_type?: string; model_capabilities?: string[]; capabilities?: string[] }): ModelCapability {
  const modelType = (configOrModel.model_type || '').toLowerCase();
  if (['chat', 'completion', 'text', 'text-generation', 'text_generation', 'llm', 'vision'].includes(modelType)) return 'text';
  if (['image', 'image-generation', 'image_generation'].includes(modelType)) return 'image';
  if (['tts', 'audio', 'speech'].includes(modelType)) return 'audio';
  if (['video', 'video-generation', 'video_generation'].includes(modelType)) return 'video';
  if (modelType === 'embedding') return 'embedding';

  const capabilities = (configOrModel.model_capabilities || configOrModel.capabilities || []).map(item => String(item).toLowerCase());
  if (capabilities.some(item => item.includes('text-to-speech') || item.includes('speech'))) return 'audio';
  if (capabilities.some(item => item.includes('text-to-video') || item.includes('video'))) return 'video';
  if (capabilities.some(item => item.includes('text-to-image') || item.includes('image'))) return 'image';
  if (capabilities.some(item => item.includes('embedding'))) return 'embedding';
  if (capabilities.some(item => item === 'text' || item.includes('chat') || item.includes('completion'))) return 'text';
  return 'other';
}

export function getConfigsByCapability(configs: SavedModelConfig[], capability: ModelCapability) {
  return configs.filter(config => !isInternalTestModelConfig(config) && getModelCapability(config) === capability);
}

export function getDefaultConfigForCapability(configs: SavedModelConfig[], capability: ModelCapability) {
  const scoped = getConfigsByCapability(configs, capability);
  return scoped.find(config => config.is_default) || scoped.find(config => config.test_status === 'success') || scoped[0];
}

export function getVerifiedConfigsByCapability(configs: SavedModelConfig[], capability: ModelCapability) {
  return getConfigsByCapability(configs, capability).filter(config => config.test_status === 'success');
}
