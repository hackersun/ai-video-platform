'use client';

import type { ModelBindingView } from '../types';
import { certificationLabel, connectionDisplayName } from '../model-center-labels';

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
  const modelName = binding.profile_name || binding.api_model_id || '已配置模型';
  const providerName = binding.provider_name || '已配置供应商';
  const connectionName = connectionDisplayName(binding.connection_name || '生产账号', providerName);
  return `${modelName}（${providerName} · ${connectionName}）`;
}

export function RecipePipeline({ bindings, values, nativeAudio, onChange }: { bindings: ModelBindingView[]; values: Partial<Record<RecipeBindingSlot, string>>; nativeAudio: boolean; onChange: (slot: RecipeBindingSlot, bindingId: string) => void }) {
  return <ol aria-label="受约束的生产管线" className="space-y-2">{slots.map((slot, index) => {
    const compatible = bindings.filter((binding) => binding.task === slot.task && binding.is_active);
    const disabled = nativeAudio && slot.key === 'audio';
    const selected = compatible.find((binding) => binding.id === values[slot.key]);
    return <li key={slot.key} className="grid gap-3 rounded-lg border border-white/10 bg-slate-950/25 p-3 sm:grid-cols-[1.4rem_minmax(10rem,1fr)_minmax(15rem,1fr)] sm:items-center"><span className="grid h-6 w-6 place-items-center rounded-full border border-violet-400/35 bg-violet-500/10 text-xs font-semibold text-violet-200">{index + 1}</span><div><p className="text-sm font-medium text-slate-100">{slot.label}</p><p className="mt-0.5 text-xs text-slate-500">{slot.optional ? '可选阶段' : '必需阶段'} · 只显示已启用的默认模型</p>{selected && <p className="mt-1 text-[11px] leading-5 text-slate-400">当前模型：{selected.api_model_id || selected.profile_name} · 账号：{selected.connection_name} · 验证：{certificationLabel(selected.certification_status)}</p>}</div><select aria-label={`${slot.label}使用的模型`} disabled={disabled} value={values[slot.key] || ''} onChange={(event) => onChange(slot.key, event.target.value)} className="model-center-input w-full"><option value="">{disabled ? '视频自带声音，无需配音模型' : compatible.length ? '选择该步骤使用的模型' : '没有可用的默认模型'}</option>{compatible.map((binding) => <option key={binding.id} value={binding.id}>{bindingLabel(binding)}</option>)}</select></li>;
  })}</ol>;
}
