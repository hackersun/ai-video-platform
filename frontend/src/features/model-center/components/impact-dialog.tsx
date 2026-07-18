'use client';

import type { ResourceImpact } from '../types';

type ImpactDialogProps = {
  title: string;
  description: string;
  impact: ResourceImpact;
  reason: string;
  confirmLabel: string;
  onReasonChange: (value: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
  pending?: boolean;
};

export function ImpactDialog({ title, description, impact, reason, confirmLabel, onReasonChange, onCancel, onConfirm, pending }: ImpactDialogProps) {
  const profiles = impact.affected_profiles ?? impact.affected_bindings;
  return <div role="dialog" aria-modal="true" aria-label={title} className="fixed inset-0 z-50 grid place-items-center bg-slate-950/75 p-4"><section className="w-full max-w-lg rounded-xl border border-white/15 bg-slate-900 p-5 shadow-2xl"><h2 className="text-lg font-semibold text-white">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-400">{description}</p><dl className="mt-5 grid grid-cols-2 gap-3 rounded-lg border border-white/10 bg-black/15 p-4 text-sm"><div><dt className="text-xs text-slate-500">受影响模型版本</dt><dd className="mt-1 font-medium text-white">{profiles} 个模型版本</dd></div><div><dt className="text-xs text-slate-500">受影响生产方案</dt><dd className="mt-1 font-medium text-white">{impact.affected_recipes} 个生产方案</dd></div></dl><label className="mt-5 block text-sm text-slate-300">发布原因<textarea aria-label="发布原因" required value={reason} onChange={(event) => onReasonChange(event.target.value)} className="model-center-input mt-2 h-20 w-full py-2" placeholder="说明这次变更的原因" /></label><div className="mt-5 flex justify-end gap-2"><button type="button" onClick={onCancel} className="model-center-quiet">取消</button><button type="button" disabled={pending || reason.trim().length < 2} onClick={onConfirm} className="model-center-primary">{pending ? '提交中' : confirmLabel}</button></div></section></div>;
}
