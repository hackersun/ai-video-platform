import type { ModelCapability } from './types';

export const capabilityLabels: Record<ModelCapability, string> = {
  text_generation: '文本生成',
  vision_analysis: '视觉理解',
  image_generation: '图像生成',
  video_generation: '视频生成',
  speech_generation: '语音生成',
  subtitle_generation: '字幕生成',
  media_render: '成片合成',
  object_storage: '对象存储',
};

export const modelTaskOptions: Array<{
  key: string;
  label: string;
  capability: ModelCapability;
}> = [
  { key: 'script_generation', label: '小说理解与分镜', capability: 'text_generation' },
  { key: 'entity_extraction', label: '角色、场景与道具提取', capability: 'text_generation' },
  { key: 'shot_vision', label: '镜头视觉分析', capability: 'vision_analysis' },
  { key: 'shot_image', label: '参考资产生成', capability: 'image_generation' },
  { key: 'shot_video', label: '镜头视频生成', capability: 'video_generation' },
  { key: 'shot_speech', label: '独立配音', capability: 'speech_generation' },
  { key: 'shot_subtitle', label: '字幕生成', capability: 'subtitle_generation' },
  { key: 'workflow_render', label: '成片合成', capability: 'media_render' },
  { key: 'workflow_storage', label: '交付存储', capability: 'object_storage' },
];

export function taskLabel(task: string) {
  return modelTaskOptions.find((item) => item.key === task)?.label || task;
}

export function driverLabel(driverKey: string) {
  const labels: Record<string, string> = {
    legacy_text_v1: '通用文本接口',
    volcano_ark_text_v1: '火山方舟文本接口',
    volcano_ark_image_v1: '火山方舟图像接口',
    volcano_ark_video_v3: '火山方舟视频接口',
    dashscope_image_v1: '阿里百炼图像接口',
    dashscope_video_v1: '阿里百炼视频接口',
    doubao_tts_v2: '豆包语音 2.0 接口',
  };
  return labels[driverKey] || driverKey;
}

export function profileKeyFromModelId(modelId: string) {
  return modelId.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '');
}

export function connectionDisplayName(name: string, providerName: string) {
  if (name.startsWith('legacy:') || /^tts-provider-[0-9a-f-]{16,}$/i.test(name)) {
    return `${providerName}历史兼容账号`;
  }
  return name;
}

export function certificationLabel(status: string) {
  const labels: Record<string, string> = {
    unverified: '待验证',
    connection_verified: '账号已验证',
    contract_verified: '配置已验证',
    live_verified: '实模已验证',
    success: '已验证',
    passed: '已验证',
    failed: '验证失败',
  };
  return labels[status] || status;
}
