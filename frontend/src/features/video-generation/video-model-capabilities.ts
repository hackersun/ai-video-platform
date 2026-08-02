type VideoLimits = {
  durations?: number[];
  duration_min?: number;
  duration_max?: number;
};

type VideoModelBinding = {
  config_id?: string | null;
  model_profile_version_id?: string | null;
  limits?: {
    reference_images?: number;
    reference_videos?: number;
    reference_audios?: number;
  };
};

export type VideoReferenceDraft = { images: string; videos: string; audios: string };

export interface VideoGenerateParams {
  shot_id?: string;
  storyboard_id?: string;
  script_id?: string;
  chapter_id?: string;
  novel_id?: string;
  workflow_id?: string;
  prompt: string;
  duration: number;
  resolution: string;
  image_url?: string;
  model: string;
  character_ids?: string[];
  model_config_id?: string;
  model_profile_version_id?: string;
  reference_image_urls?: string[];
  reference_video_urls?: string[];
  reference_audio_urls?: string[];
}

const COMMON_DURATIONS = [4, 5, 8, 10, 15, 20, 30, 60];

export function supportedVideoDurations(limits?: VideoLimits) {
  if (limits?.durations?.length) return limits.durations;
  const minimum = Number(limits?.duration_min);
  const maximum = Number(limits?.duration_max);
  if (minimum > 0 && maximum >= minimum) {
    return Array.from(new Set([
      minimum,
      ...COMMON_DURATIONS.filter((value) => value > minimum && value < maximum),
      maximum,
    ])).sort((left, right) => left - right);
  }
  return [4, 5, 8, 10];
}

export function videoModelRequestBinding(model?: VideoModelBinding | null) {
  if (model?.model_profile_version_id) {
    return { model_profile_version_id: model.model_profile_version_id };
  }
  return model?.config_id ? { model_config_id: model.config_id } : {};
}

const REFERENCE_FIELDS = [
  ['images', 'reference_images', 'reference_image_urls', '图片'],
  ['videos', 'reference_videos', 'reference_video_urls', '视频'],
  ['audios', 'reference_audios', 'reference_audio_urls', '音频'],
] as const;

export function buildVideoReferencePayload(
  model: VideoModelBinding | null | undefined,
  draft: VideoReferenceDraft,
) {
  const payload: Record<string, string[]> = {};
  for (const [draftKey, limitKey, requestKey, label] of REFERENCE_FIELDS) {
    const urls = Array.from(new Set(draft[draftKey].split(/\r?\n/).map(value => value.trim()).filter(Boolean)));
    const limit = Number(model?.limits?.[limitKey] || 0);
    if (urls.length > limit) throw new Error(`当前模型最多支持 ${limit} 个${label}参考，请删除多余地址或更换模型。`);
    payload[requestKey] = urls;
  }
  return payload;
}

export function videoApiErrorMessage(payload: unknown, fallback: string) {
  if (!payload || typeof payload !== 'object') return fallback;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (!detail || typeof detail !== 'object') return fallback;
  const value = detail as { message?: unknown; issues?: unknown[] };
  const message = typeof value.message === 'string' ? value.message : fallback;
  const issue = Array.isArray(value.issues)
    ? value.issues.find(item => item && typeof item === 'object' && typeof (item as { message?: unknown }).message === 'string')
    : undefined;
  return issue ? `${message}：${(issue as { message: string }).message}` : message;
}
