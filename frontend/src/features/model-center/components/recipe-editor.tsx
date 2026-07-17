'use client';

import { FormEvent, useMemo, useState } from 'react';
import { AlertCircle, X } from 'lucide-react';

import type { ModelBindingView, ProductionRecipeInput } from '../types';
import { RecipePipeline, type RecipeBindingSlot } from './recipe-pipeline';

const strategies = ['draft_fast', 'final_quality', 'low_cost', 'direct_av_first', 'separate_video_tts'] as const;

type RecipeEditorProps = {
  bindings: ModelBindingView[];
  onClose: () => void;
  onSave: (input: ProductionRecipeInput) => Promise<void>;
};

export function RecipeEditor({ bindings, onClose, onSave }: RecipeEditorProps) {
  const [name, setName] = useState('');
  const [recipeKey, setRecipeKey] = useState('');
  const [nativeAudio, setNativeAudio] = useState(true);
  const [strategy, setStrategy] = useState<(typeof strategies)[number]>('direct_av_first');
  const [bindingIds, setBindingIds] = useState<Partial<Record<RecipeBindingSlot, string>>>({});
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const subtitleSource = nativeAudio ? 'video_dialogue_timeline' : 'tts_timeline';
  const requiredMissing = useMemo(() => ['video', 'render', 'storage'].some((key) => !bindingIds[key as RecipeBindingSlot]), [bindingIds]);

  const updateBinding = (slot: RecipeBindingSlot, bindingId: string) => setBindingIds((current) => ({ ...current, [slot]: bindingId }));
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (requiredMissing) return setError('请为视频、合成与交付存储选择已启用的能力绑定。');
    setPending(true);
    setError(null);
    const stage = (slot: RecipeBindingSlot) => bindingIds[slot] ? { binding_id: bindingIds[slot], required: ['video', 'render', 'storage'].includes(slot) } : { required: false };
    try {
      await onSave({ recipe_key: recipeKey.trim(), name: name.trim(), spec: { strategy, text: stage('text'), vision: stage('vision'), image: stage('image'), video: stage('video'), audio: nativeAudio ? { mode: 'video_native_audio' } : { mode: 'separate_tts', binding_id: bindingIds.audio }, subtitle: { source: subtitleSource }, render: stage('render'), storage: stage('storage') } });
      onClose();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '生产方案保存失败');
    } finally {
      setPending(false);
    }
  };

  return <div role="dialog" aria-modal="true" aria-label="新建生产方案" className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/80 p-4 sm:p-8"><form onSubmit={submit} className="mx-auto max-w-4xl rounded-xl border border-white/15 bg-slate-900 p-5 shadow-2xl"><header className="flex items-start justify-between gap-4"><div><h2 className="text-xl font-semibold text-white">新建生产方案</h2><p className="mt-1 text-sm text-slate-400">生产方案只保存能力绑定与版本化策略，不保存提供方或模型标识。</p></div><button type="button" onClick={onClose} aria-label="关闭生产方案编辑器" className="model-center-quiet"><X className="h-4 w-4" /></button></header><div className="mt-5 grid gap-3 sm:grid-cols-2"><label className="text-xs text-slate-400">方案名称<input required value={name} onChange={(event) => setName(event.target.value)} className="model-center-input mt-1 w-full" /></label><label className="text-xs text-slate-400">方案键<input required value={recipeKey} onChange={(event) => setRecipeKey(event.target.value)} className="model-center-input mt-1 w-full" placeholder="例如 novel-final-v1" /></label><label className="text-xs text-slate-400">生产策略<select aria-label="生产策略" value={strategy} onChange={(event) => setStrategy(event.target.value as (typeof strategies)[number])} className="model-center-input mt-1 w-full">{strategies.map((item) => <option key={item} value={item}>{item}</option>)}</select></label><div className="rounded-lg border border-violet-400/20 bg-violet-500/[0.06] px-3 py-2 text-xs text-violet-100">首帧仅作为生成约束，不进入成片</div></div><fieldset className="mt-5 grid gap-3 rounded-lg border border-white/10 p-4 sm:grid-cols-2"><legend className="px-1 text-sm font-medium text-white">声音与字幕策略</legend><label className="flex items-center gap-2 text-sm text-slate-200"><input aria-label="视频内生语音" type="checkbox" checked={nativeAudio} onChange={(event) => setNativeAudio(event.target.checked)} />视频内生语音</label><label className="flex items-center gap-2 text-sm text-slate-400"><input aria-label="独立语音合成" type="checkbox" checked={!nativeAudio} disabled={nativeAudio} onChange={(event) => setNativeAudio(!event.target.checked)} />独立语音合成</label><label className="text-xs text-slate-400">字幕来源<select aria-label="字幕来源" value={subtitleSource} disabled className="model-center-input mt-1 w-full"><option value="video_dialogue_timeline">video_dialogue_timeline</option><option value="tts_timeline">tts_timeline</option></select></label></fieldset><div className="mt-5"><h3 className="mb-2 text-sm font-medium text-white">受约束的生产管线</h3><RecipePipeline bindings={bindings} values={bindingIds} nativeAudio={nativeAudio} onChange={updateBinding} /></div>{error && <p className="mt-4 flex gap-2 rounded-md bg-rose-500/10 p-3 text-sm text-rose-100"><AlertCircle className="h-4 w-4 shrink-0" />{error}</p>}<footer className="mt-5 flex justify-end gap-2"><button type="button" onClick={onClose} className="model-center-quiet">取消</button><button type="submit" disabled={pending || !name.trim() || !recipeKey.trim()} className="model-center-primary">{pending ? '保存中' : '保存为草稿版本'}</button></footer></form></div>;
}
