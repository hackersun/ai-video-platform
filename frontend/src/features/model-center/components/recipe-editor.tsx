'use client';

import { FormEvent, useMemo, useState } from 'react';
import { AlertCircle, X } from 'lucide-react';

import type { ModelBindingView, ProductionRecipeInput } from '../types';
import { RecipePipeline, type RecipeBindingSlot } from './recipe-pipeline';
import { DEFAULT_PRODUCTION_STRATEGY, PRODUCTION_STRATEGY_COPY, type ProductionStrategy } from '@/lib/production-strategy';

const productionGoals = ['draft_fast', 'final_quality', 'low_cost'] as const satisfies readonly ProductionStrategy[];

type RecipeEditorProps = {
  bindings: ModelBindingView[];
  onClose: () => void;
  onSave: (input: ProductionRecipeInput) => Promise<void>;
};

export function RecipeEditor({ bindings, onClose, onSave }: RecipeEditorProps) {
  const [name, setName] = useState('');
  const [recipeKey, setRecipeKey] = useState('');
  const [nativeAudio, setNativeAudio] = useState(true);
  const [strategy, setStrategy] = useState<(typeof productionGoals)[number]>(
    DEFAULT_PRODUCTION_STRATEGY as (typeof productionGoals)[number],
  );
  const [bindingIds, setBindingIds] = useState<Partial<Record<RecipeBindingSlot, string>>>({});
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const subtitleSource = nativeAudio ? 'video_dialogue_timeline' : 'tts_timeline';
  const requiredMissing = useMemo(
    () => ['video', 'render', 'storage'].some((key) => !bindingIds[key as RecipeBindingSlot]) || (!nativeAudio && !bindingIds.audio),
    [bindingIds, nativeAudio],
  );

  const updateBinding = (slot: RecipeBindingSlot, bindingId: string) => setBindingIds((current) => ({ ...current, [slot]: bindingId }));
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (requiredMissing) return setError(nativeAudio ? '请为视频、合成与交付存储选择已启用的默认模型。' : '单独生成配音时必须选择已启用的配音模型。');
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

  const strategyCopy = PRODUCTION_STRATEGY_COPY[strategy];
  return <div role="dialog" aria-modal="true" aria-label="新建生产方案" className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/80 p-4 sm:p-8"><form onSubmit={submit} className="mx-auto max-w-4xl rounded-xl border border-white/15 bg-slate-900 p-5 shadow-2xl"><header className="flex items-start justify-between gap-4"><div><h2 className="text-xl font-semibold text-white">新建生产方案</h2><p className="mt-1 text-sm text-slate-400">选择想要的生产效果，再为每个步骤指定已经配置好的模型。</p></div><button type="button" onClick={onClose} aria-label="关闭生产方案编辑器" className="model-center-quiet"><X className="h-4 w-4" /></button></header><div className="mt-5 grid gap-3 sm:grid-cols-2"><label className="text-xs text-slate-400">方案名称<input aria-label="方案名称" required value={name} onChange={(event) => setName(event.target.value)} className="model-center-input mt-1 w-full" /></label><label className="text-xs text-slate-400">方案键<input aria-label="方案键" required value={recipeKey} onChange={(event) => setRecipeKey(event.target.value)} className="model-center-input mt-1 w-full" placeholder="例如 novel-final-v1" /></label><label className="text-xs text-slate-400">生产目标<select aria-label="生产目标" value={strategy} onChange={(event) => setStrategy(event.target.value as (typeof productionGoals)[number])} className="model-center-input mt-1 w-full">{productionGoals.map((item) => <option key={item} value={item}>{PRODUCTION_STRATEGY_COPY[item].label}</option>)}</select></label><div className="rounded-lg border border-violet-400/20 bg-violet-500/[0.06] px-3 py-2 text-xs leading-5 text-violet-100"><p className="font-medium">{strategyCopy.label}</p><p className="mt-1 text-violet-200/80">{strategyCopy.description}</p><p className="mt-1 text-violet-200/60">{strategyCopy.modelHint}</p></div></div><fieldset className="mt-5 grid gap-3 rounded-lg border border-white/10 p-4 sm:grid-cols-2"><legend className="px-1 text-sm font-medium text-white">声音与字幕</legend><label className="flex items-start gap-2 text-sm text-slate-200"><input aria-label="视频自带声音" name="audio-mode" type="radio" checked={nativeAudio} onChange={() => setNativeAudio(true)} className="mt-1" /><span><span className="block">视频自带声音</span><span className="mt-0.5 block text-xs text-slate-500">适合支持原生音画直出的模型，无需再选配音模型。</span></span></label><label className="flex items-start gap-2 text-sm text-slate-200"><input aria-label="单独生成配音" name="audio-mode" type="radio" checked={!nativeAudio} onChange={() => setNativeAudio(false)} className="mt-1" /><span><span className="block">单独生成配音</span><span className="mt-0.5 block text-xs text-slate-500">视频和配音分开生成，便于替换声音和字幕。</span></span></label><label className="text-xs text-slate-400">字幕来源<select aria-label="字幕来源" value={subtitleSource} disabled className="model-center-input mt-1 w-full"><option value="video_dialogue_timeline">跟随视频声音自动生成</option><option value="tts_timeline">跟随独立配音自动生成</option></select></label>{!nativeAudio && !bindingIds.audio && <p className="text-xs text-amber-200">请在下方为“独立配音”选择模型后再保存。</p>}</fieldset><div className="mt-5"><h3 className="mb-2 text-sm font-medium text-white">生产步骤与模型</h3><RecipePipeline bindings={bindings} values={bindingIds} nativeAudio={nativeAudio} onChange={updateBinding} /></div>{error && <p className="mt-4 flex gap-2 rounded-md bg-rose-500/10 p-3 text-sm text-rose-100"><AlertCircle className="h-4 w-4 shrink-0" />{error}</p>}<footer className="mt-5 flex justify-end gap-2"><button type="button" onClick={onClose} className="model-center-quiet">取消</button><button type="submit" disabled={pending || requiredMissing || !name.trim() || !recipeKey.trim()} className="model-center-primary">{pending ? '保存中' : '保存为草稿版本'}</button></footer></form></div>;
}
