'use client';

import { FormEvent, useEffect, useState } from 'react';
import { X } from 'lucide-react';

import { promptUsageApi } from '../prompt-usage-api';
import type { PromptUsageAssignmentResult, PromptUsageCandidate, PromptUsageStage } from '../prompt-usage-types';

export function PromptUsageAssignmentDialog({
  stage,
  onClose,
  onCreated,
}: {
  stage: PromptUsageStage;
  onClose: () => void;
  onCreated: (result: PromptUsageAssignmentResult) => void;
}) {
  const [items, setItems] = useState<PromptUsageCandidate[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    void promptUsageApi.listCandidates(stage.id).then((candidates) => {
      if (!active) return;
      setItems(candidates);
      setSelectedId(candidates[0]?.id || '');
    }).catch((reason) => {
      if (active) setError(reason instanceof Error ? reason.message : '无法读取已发布模板');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [stage.id]);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedId) return;
    try {
      setPending(true);
      setError(null);
      const result = await promptUsageApi.createAssignmentDraft(stage.id, {
        prompt_version_id: selectedId,
        reason: `用于当前默认${stage.name}模型`,
      });
      onCreated(result);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '模型专用草稿创建失败');
    } finally {
      setPending(false);
    }
  };
  return <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/80 p-4 sm:p-8">
    <form role="dialog" aria-modal="true" aria-label={`更换${stage.name}模板`} onSubmit={submit} className="mx-auto max-w-xl rounded-2xl border border-white/15 bg-slate-900 p-5 shadow-2xl">
      <header className="flex items-start justify-between gap-4"><div><h2 className="text-lg font-semibold text-white">更换{stage.name}模板</h2><p className="mt-2 text-sm leading-6 text-slate-400">将基于所选已发布模板创建当前模型专用草稿。生产任务不会改变，直到你预览并发布该草稿。</p></div><button type="button" aria-label="关闭更换模板" onClick={onClose} className="model-center-quiet"><X className="h-4 w-4" /></button></header>
      <label className="mt-5 block text-xs text-slate-400">选择已发布模板<select aria-label="选择已发布模板" value={selectedId} onChange={(event) => setSelectedId(event.target.value)} disabled={loading} className="model-center-input mt-2 w-full"><option value="">{loading ? '正在读取…' : '请选择模板'}</option>{items.map((item) => <option key={item.id} value={item.id}>{item.name} · v{item.version} · {item.source_label}</option>)}</select></label>
      {!loading && !items.length && !error && <p className="mt-3 text-xs text-amber-300">这个环节还没有可选择的已发布模板。</p>}
      {error && <p className="mt-3 rounded-lg border border-rose-400/20 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">{error}</p>}
      <footer className="mt-6 flex justify-end gap-2"><button type="button" onClick={onClose} className="model-center-quiet">取消</button><button type="submit" disabled={pending || !selectedId} className="model-center-primary">{pending ? '正在创建…' : '创建模型专用草稿'}</button></footer>
    </form>
  </div>;
}
