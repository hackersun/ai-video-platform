import type { ModelCatalogView } from '../types';

function numberValue(values: Record<string, unknown>, key: string) {
  const value = Number(values[key]);
  return Number.isFinite(value) ? value : 0;
}

export function VideoContractSummary({ model }: { model: ModelCatalogView }) {
  if (!model.capabilities.includes('video_generation')) return null;
  const contract = model.input_contract || {};
  const limits = model.limits || {};
  const experimental = contract.verification_status === 'experimental';
  const minimum = numberValue(limits, 'duration_min');
  const maximum = numberValue(limits, 'duration_max');
  const referencesConfigured = ['reference_images', 'reference_videos', 'reference_audios']
    .some((key) => key in limits);
  const references = referencesConfigured ? [
    `图片 ${numberValue(limits, 'reference_images')}`,
    `视频 ${numberValue(limits, 'reference_videos')}`,
    `音频 ${numberValue(limits, 'reference_audios')}`,
  ].join(' · ') : '未配置';

  return <section className="mt-4 rounded-lg border border-cyan-400/20 bg-cyan-400/5 p-3 text-xs text-slate-300">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="font-medium text-white">视频能力契约</p>
      <span className={experimental ? 'rounded bg-amber-500/15 px-2 py-1 text-amber-100' : 'text-emerald-300'}>{experimental ? '实验能力契约' : '已配置能力契约'}</span>
    </div>
    <div className="mt-3 grid gap-2 sm:grid-cols-2">
      <p><span className="text-slate-500">单次时长</span><br /><span className="text-white">{minimum && maximum ? `${minimum}–${maximum} 秒` : '未配置'}</span></p>
      <p><span className="text-slate-500">多模态参考上限</span><br /><span className="text-white">{references}</span></p>
    </div>
    {experimental && <p className="mt-3 text-amber-100/90">上限来自当前模型版本配置；完成供应商实模认证前不会标记为生产可用。</p>}
  </section>;
}
