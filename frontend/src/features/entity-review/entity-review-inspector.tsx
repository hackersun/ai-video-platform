'use client';

import { Loader2, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import type { ReanalysisResult, ReviewEntity } from './types';
import { EntityEditForm } from './entity-edit-form';

type Props = {
  entity: ReviewEntity | null;
  preview: ReanalysisResult | null;
  onSave: (patch: Partial<ReviewEntity>) => Promise<void>;
  onPreview: () => Promise<void>;
  onApply: () => Promise<void>;
};

export function EntityReviewInspector({ entity, preview, onSave, onPreview, onApply }: Props) {
  if (!entity) return <aside className="rounded-lg border border-white/10 p-6 text-sm text-white/50">请选择一个实体</aside>;
  const [reanalyzing, setReanalyzing] = useAsyncFlag();
  return <aside className="sticky top-4 max-h-[82vh] space-y-4 overflow-y-auto rounded-lg border border-white/10 bg-slate-950/80 p-4">
    <div><div className="text-xs text-white/45">当前实体 · {entity.review_status}</div><h2 className="mt-1 text-xl font-semibold text-white">{entity.name}</h2></div>
    <div className="rounded border border-white/10 bg-black/20 p-3 text-sm"><div className="text-xs text-white/40">原文证据</div><p className="mt-2 whitespace-pre-wrap leading-6 text-white/70">{entity.evidence || '缺少证据，请补充后再定稿'}</p></div>
    <section><h3 className="mb-3 font-medium text-white">修改识别结果</h3><EntityEditForm entity={entity} onSave={onSave} /></section>
    <section className="rounded border border-cyan-500/20 bg-cyan-500/[0.05] p-3">
      <div className="flex items-center justify-between gap-2"><div><h3 className="font-medium text-white">AI 重新分析此项</h3><p className="mt-1 text-xs text-white/45">先预览差异，不会直接覆盖。</p></div><Button size="sm" variant="outline" disabled={reanalyzing} onClick={() => setReanalyzing(onPreview)}>{reanalyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}</Button></div>
      {preview?.current.id === entity.id ? <div className="mt-3 space-y-2"><div className="text-xs text-cyan-100">模型：{String(preview.model_execution.provider || '-')} / {String(preview.model_execution.model_id || '-')}</div>{Object.entries(preview.differences).map(([field, diff]) => <div key={field} className="rounded border border-white/10 p-2 text-xs"><div className="text-white/45">{field}</div><div className="mt-1 text-rose-200/75">原：{format(diff.before)}</div><div className="mt-1 text-emerald-200">新：{format(diff.after)}</div></div>)}<Button className="w-full bg-cyan-600" onClick={() => setReanalyzing(onApply)} disabled={reanalyzing}>确认应用模型建议</Button></div> : null}
    </section>
  </aside>;
}

function format(value: unknown) { return Array.isArray(value) ? value.join('、') : String(value ?? '-'); }
function useAsyncFlag(): [boolean, (operation: () => Promise<void>) => Promise<void>] {
  const [busy, setBusy] = useState(false);
  const run = async (operation: () => Promise<void>) => { setBusy(true); try { await operation(); } finally { setBusy(false); } };
  return [busy, run];
}
