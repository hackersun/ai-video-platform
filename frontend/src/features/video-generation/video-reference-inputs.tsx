'use client';

import type { VideoReferenceDraft } from './video-model-capabilities';

type ReferenceLimits = {
  reference_images?: number;
  reference_videos?: number;
  reference_audios?: number;
};

type Props = {
  value: VideoReferenceDraft;
  onChange: (value: VideoReferenceDraft) => void;
  limits?: ReferenceLimits;
  disabled?: boolean;
};

const FIELDS = [
  ['images', 'reference_images', '附加图片', '每行一个公网图片 URL；自动资产参考会优先占用容量。'],
  ['videos', 'reference_videos', '参考视频', '每行一个公网视频 URL，用于动作、运镜或上一段延续。'],
  ['audios', 'reference_audios', '参考音频', '每行一个公网音频 URL，用于声音、节奏或对白参考。'],
] as const;

const countUrls = (value: string) => new Set(value.split(/\r?\n/).map(item => item.trim()).filter(Boolean)).size;

export function VideoReferenceInputs({ value, onChange, limits, disabled }: Props) {
  const available = FIELDS.filter(([, limitKey]) => Number(limits?.[limitKey] || 0) > 0);
  if (!available.length) return null;

  return (
    <details className="rounded-lg border border-cyan-400/20 bg-cyan-500/5 p-3" data-testid="video-reference-inputs">
      <summary className="cursor-pointer text-sm font-medium text-cyan-100">
        多模态参考（可选）
        <span className="ml-2 text-xs font-normal text-white/45">仅填写公网可访问 URL</span>
      </summary>
      <div className="mt-3 space-y-3">
        {available.map(([draftKey, limitKey, label, hint]) => {
          const limit = Number(limits?.[limitKey] || 0);
          const count = countUrls(value[draftKey]);
          return (
            <label key={draftKey} className="block">
              <span className="flex items-center justify-between text-sm text-white/80">
                {label}<span className={count > limit ? 'text-red-300' : 'text-white/45'}>{count}/{limit}</span>
              </span>
              <textarea
                value={value[draftKey]}
                onChange={event => onChange({ ...value, [draftKey]: event.target.value })}
                disabled={disabled}
                rows={2}
                placeholder={hint}
                className="mt-1 w-full resize-y rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-white placeholder:text-white/35"
              />
              {count > limit && <span className="mt-1 block text-xs text-red-300">超出当前模型容量，请删除多余地址或更换模型。</span>}
            </label>
          );
        })}
      </div>
    </details>
  );
}
