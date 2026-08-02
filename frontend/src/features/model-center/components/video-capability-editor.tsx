'use client';

export type VideoCapabilityDraft = {
  family: string;
  durationMin: string;
  durationMax: string;
  referenceImages: string;
  referenceVideos: string;
  referenceAudios: string;
  resolutions: string;
  nativeAudio: boolean;
  supportsPreviousVideo: boolean;
};

export const emptyVideoCapabilityDraft: VideoCapabilityDraft = {
  family: '', durationMin: '', durationMax: '', referenceImages: '', referenceVideos: '',
  referenceAudios: '', resolutions: '', nativeAudio: false, supportsPreviousVideo: false,
};

function optionalNumber(value: string) {
  const parsed = Number(value);
  return value.trim() !== '' && Number.isFinite(parsed) ? parsed : undefined;
}

export function videoCapabilityPayload(draft: VideoCapabilityDraft) {
  const referenceCount = [draft.referenceImages, draft.referenceVideos, draft.referenceAudios]
    .some((value) => Number(value) > 0);
  const modes = ['text_to_video'];
  if (referenceCount) modes.push('multimodal_reference');
  if (draft.supportsPreviousVideo) modes.push('video_continuation');
  const resolutions = draft.resolutions.split(',').map((value) => value.trim()).filter(Boolean);
  const limits: Record<string, unknown> = {
    native_audio: draft.nativeAudio,
    supports_previous_video: draft.supportsPreviousVideo,
  };
  for (const [key, value] of Object.entries({
    duration_min: draft.durationMin, duration_max: draft.durationMax,
    reference_images: draft.referenceImages, reference_videos: draft.referenceVideos,
    reference_audios: draft.referenceAudios,
  })) {
    const parsed = optionalNumber(value);
    if (parsed !== undefined) limits[key] = parsed;
  }
  if (resolutions.length) limits.resolutions = resolutions;
  return {
    input_contract: {
      family: draft.family || 'generic_video',
      verification_status: draft.family === 'seedance_2_5' ? 'experimental' : 'unverified',
      modes,
    },
    limits,
    contract_version: draft.family === 'seedance_2_5' ? 'seedance-2.5-configurable-v1' : undefined,
  };
}

type Props = {
  value: VideoCapabilityDraft;
  onChange: (value: VideoCapabilityDraft) => void;
};

export function VideoCapabilityEditor({ value, onChange }: Props) {
  const field = (key: keyof VideoCapabilityDraft, next: string | boolean) => onChange({ ...value, [key]: next });
  const applySeedance25 = () => onChange({ ...emptyVideoCapabilityDraft, family: 'seedance_2_5' });

  return <section className="rounded-lg border border-cyan-400/20 bg-cyan-400/5 p-4">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h3 className="text-sm font-semibold text-white">视频模型能力</h3><p className="mt-1 text-xs text-slate-400">能力和上限保存到模型版本，不写死在页面或适配器中。</p></div>
      <button type="button" onClick={applySeedance25} className="model-center-quiet">未来 Seedance 2.5 兼容模板</button>
    </div>
    {value.family === 'seedance_2_5' && <p className="mt-3 rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-100">官方模型目录尚未发布 Seedance 2.5。这里仅保存未来兼容草稿，当前不能实模验证、发布或设为默认。</p>}
    <div className="mt-3 grid gap-3 sm:grid-cols-3">
      <label className="text-xs text-slate-400">最小时长（秒）<input aria-label="最小时长（秒）" type="number" min="1" value={value.durationMin} onChange={(event) => field('durationMin', event.target.value)} className="model-center-input mt-1 w-full" /></label>
      <label className="text-xs text-slate-400">最大时长（秒）<input aria-label="最大时长（秒）" type="number" min="1" value={value.durationMax} onChange={(event) => field('durationMax', event.target.value)} className="model-center-input mt-1 w-full" /></label>
      <label className="text-xs text-slate-400">输出分辨率<input aria-label="输出分辨率" value={value.resolutions} onChange={(event) => field('resolutions', event.target.value)} placeholder="720p,1080p" className="model-center-input mt-1 w-full" /></label>
      <label className="text-xs text-slate-400">参考图片上限<input aria-label="参考图片上限" type="number" min="0" value={value.referenceImages} onChange={(event) => field('referenceImages', event.target.value)} className="model-center-input mt-1 w-full" /></label>
      <label className="text-xs text-slate-400">参考视频上限<input aria-label="参考视频上限" type="number" min="0" value={value.referenceVideos} onChange={(event) => field('referenceVideos', event.target.value)} className="model-center-input mt-1 w-full" /></label>
      <label className="text-xs text-slate-400">参考音频上限<input aria-label="参考音频上限" type="number" min="0" value={value.referenceAudios} onChange={(event) => field('referenceAudios', event.target.value)} className="model-center-input mt-1 w-full" /></label>
    </div>
    <div className="mt-3 flex flex-wrap gap-5 text-xs text-slate-300">
      <label className="flex items-center gap-2"><input aria-label="支持原生音频" type="checkbox" checked={value.nativeAudio} onChange={(event) => field('nativeAudio', event.target.checked)} />支持原生音频</label>
      <label className="flex items-center gap-2"><input aria-label="支持上一段视频参考" type="checkbox" checked={value.supportsPreviousVideo} onChange={(event) => field('supportsPreviousVideo', event.target.checked)} />支持上一段视频参考</label>
    </div>
  </section>;
}
