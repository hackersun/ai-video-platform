'use client';

import type { ModelBindingView } from '../types';

export type RecipeBindingSlot = 'text' | 'vision' | 'image' | 'video' | 'audio' | 'render' | 'storage';

const slots: Array<{ key: RecipeBindingSlot; label: string; task: string; optional?: boolean }> = [
  { key: 'text', label: '小说理解与分镜', task: 'script_generation', optional: true },
  { key: 'vision', label: '镜头视觉分析', task: 'shot_vision', optional: true },
  { key: 'image', label: '参考资产', task: 'shot_image', optional: true },
  { key: 'video', label: '镜头视频', task: 'shot_video' },
  { key: 'audio', label: '独立配音', task: 'shot_speech' },
  { key: 'render', label: '合成', task: 'workflow_render' },
  { key: 'storage', label: '交付存储', task: 'workflow_storage' },
];

function bindingLabel(binding: ModelBindingView) {
  return `${binding.task} · ${binding.route_policy} · ${binding.scope_type} 作用域`;
}

export function RecipePipeline({ bindings, values, nativeAudio, onChange }: { bindings: ModelBindingView[]; values: Partial<Record<RecipeBindingSlot, string>>; nativeAudio: boolean; onChange: (slot: RecipeBindingSlot, bindingId: string) => void }) {
  return <ol aria-label="受约束的生产管线" className="space-y-2">{slots.map((slot, index) => {
    const compatible = bindings.filter((binding) => binding.task === slot.task && binding.is_active);
    const disabled = nativeAudio && slot.key === 'audio';
    return <li key={slot.key} className="grid gap-3 rounded-lg border border-white/10 bg-slate-950/25 p-3 sm:grid-cols-[1.4rem_minmax(10rem,1fr)_minmax(15rem,1fr)] sm:items-center"><span className="grid h-6 w-6 place-items-center rounded-full border border-violet-400/35 bg-violet-500/10 text-xs font-semibold text-violet-200">{index + 1}</span><div><p className="text-sm font-medium text-slate-100">{slot.label}</p><p className="mt-0.5 text-xs text-slate-500">{slot.optional ? '可选阶段' : '必需阶段'} · 仅选择已启用能力绑定</p></div><select aria-label={`${slot.label}绑定`} disabled={disabled} value={values[slot.key] || ''} onChange={(event) => onChange(slot.key, event.target.value)} className="model-center-input w-full"><option value="">{disabled ? '内生语音已启用，不需要独立 TTS' : compatible.length ? '选择能力绑定' : '没有可用绑定'}</option>{compatible.map((binding) => <option key={binding.id} value={binding.id}>{bindingLabel(binding)}</option>)}</select></li>;
  })}</ol>;
}
