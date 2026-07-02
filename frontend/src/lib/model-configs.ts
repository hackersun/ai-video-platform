export type ModelCapability = 'text' | 'image' | 'vision' | 'audio' | 'video' | 'embedding' | 'other';

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
  key_available?: boolean;
  usage_count?: number;
}

export const MODEL_CAPABILITY_LABELS: Record<ModelCapability, string> = {
  text: '文本生成',
  image: '图像生成',
  vision: '视觉多模态',
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
  const identifiers = [
    config.id,
    config.model_id,
    config.config_model_id,
    config.api_model_id,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  const displayText = [
    config.model_name,
    config.name,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  const text = `${identifiers} ${displayText}`;
  return (
    text.includes('test-video-') ||
    text.includes('test-audio-') ||
    text.includes('test-image-') ||
    text.includes('test-text-') ||
    identifiers.startsWith('tts-model-') ||
    identifiers.includes('tts-api-model') ||
    identifiers.includes('tts api model') ||
    identifiers.includes('video-api-model') ||
    identifiers.includes('video api model') ||
    identifiers.includes('image-api-model') ||
    identifiers.includes('image api model') ||
    identifiers.includes('audio-api-model') ||
    identifiers.includes('audio api model') ||
    displayText.includes('api model') ||
    identifiers.includes('-test-') ||
    identifiers.endsWith('-test') ||
    ` ${identifiers} `.includes(' test ') ||
    displayText.includes('测试') ||
    text.includes('doubao-seedance-test') ||
    text.includes('doubao-seedance-consistency-test') ||
    text.includes('speech-test')
  );
}

export function getModelCapabilities(configOrModel: { model_type?: string; model_capabilities?: string[]; capabilities?: string[] }): ModelCapability[] {
  const modelType = (configOrModel.model_type || '').toLowerCase();
  const capabilities = (configOrModel.model_capabilities || configOrModel.capabilities || []).map(item => String(item).toLowerCase());
  const detected = new Set<ModelCapability>();

  if (['chat', 'completion', 'text', 'text-generation', 'text_generation', 'llm'].includes(modelType)) detected.add('text');
  if (['image', 'image-generation', 'image_generation'].includes(modelType)) detected.add('image');
  if (modelType === 'vision') detected.add('vision');
  if (['tts', 'audio', 'speech'].includes(modelType)) detected.add('audio');
  if (['video', 'video-generation', 'video_generation'].includes(modelType)) detected.add('video');
  if (modelType === 'embedding') detected.add('embedding');

  if (capabilities.some(item => item === 'audio' || item === 'tts' || item.includes('text-to-speech') || item.includes('text_to_speech') || item.includes('speech'))) detected.add('audio');
  if (capabilities.some(item => item.includes('text-to-video') || item.includes('text_to_video') || item.includes('image-to-video') || item.includes('image_to_video') || item.includes('video'))) detected.add('video');
  if (capabilities.some(item => item.includes('text-to-image') || item.includes('text_to_image') || item.includes('image_generation') || item.includes('image-generation') || item.includes('image-edit') || item.includes('image_edit'))) detected.add('image');
  if (capabilities.some(item => item === 'vision' || item === 'multimodal' || item.includes('image_understanding'))) detected.add('vision');
  if (capabilities.some(item => item.includes('embedding'))) detected.add('embedding');
  if (capabilities.some(item => item === 'text' || item.includes('chat') || item.includes('completion') || item.includes('text_generation') || item.includes('text-generation'))) detected.add('text');

  return detected.size > 0 ? Array.from(detected) : ['other'];
}

export function getModelCapability(configOrModel: { model_type?: string; model_capabilities?: string[]; capabilities?: string[] }): ModelCapability {
  const capabilities = getModelCapabilities(configOrModel);
  const priority: ModelCapability[] = ['video', 'audio', 'image', 'text', 'vision', 'embedding', 'other'];
  return priority.find(capability => capabilities.includes(capability)) || 'other';
}

export function getConfigsByCapability(configs: SavedModelConfig[], capability: ModelCapability) {
  return configs.filter(config => !isInternalTestModelConfig(config) && getModelCapabilities(config).includes(capability));
}

export function getDefaultConfigForCapability(configs: SavedModelConfig[], capability: ModelCapability) {
  const scoped = getConfigsByCapability(configs, capability);
  return (
    scoped.find(config => config.is_default && config.test_status === 'success' && config.key_available !== false)
    || scoped.find(config => config.test_status === 'success' && config.key_available !== false)
    || scoped.find(config => config.is_default)
    || scoped[0]
  );
}

export function getVerifiedConfigsByCapability(configs: SavedModelConfig[], capability: ModelCapability) {
  return getConfigsByCapability(configs, capability).filter(config => config.test_status === 'success' && config.key_available !== false);
}
