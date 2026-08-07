import { AlertCircle, Check, Code2, Minus } from 'lucide-react';

import type { PromptUsageGroup, PromptUsageStage, PromptUsageStatus } from '../prompt-usage-types';

const statusStyle: Record<PromptUsageStatus, string> = {
  effective: 'border-emerald-400/25 bg-emerald-500/10 text-emerald-300',
  overridden: 'border-violet-400/30 bg-violet-500/12 text-violet-300',
  internal_fallback: 'border-amber-400/30 bg-amber-500/10 text-amber-300',
  invalid_binding: 'border-rose-400/30 bg-rose-500/10 text-rose-300',
  not_applicable: 'border-white/10 bg-white/[0.04] text-slate-400',
};

function StatusIcon({ status }: { status: PromptUsageStatus }) {
  if (status === 'internal_fallback' || status === 'invalid_binding') return <AlertCircle className="h-3.5 w-3.5" />;
  if (status === 'not_applicable') return <Minus className="h-3.5 w-3.5" />;
  if (status === 'overridden') return <Code2 className="h-3.5 w-3.5" />;
  return <Check className="h-3.5 w-3.5" />;
}

export function PromptUsageStageList({
  groups,
  selectedStageId,
  onSelect,
}: {
  groups: PromptUsageGroup[];
  selectedStageId: string | null;
  onSelect: (stageId: string) => void;
}) {
  return <nav aria-label="生产环节提示词" className="space-y-5 p-4">
    {groups.map((group) => <section key={group.id}>
      <h3 className="mb-2 px-1 text-[11px] font-semibold tracking-[0.14em] text-slate-500">{group.name}</h3>
      <div className="space-y-2">{group.stages.map((stage: PromptUsageStage) => {
        const active = stage.id === selectedStageId;
        return <button key={stage.id} type="button" onClick={() => onSelect(stage.id)}
          className={`w-full rounded-xl border p-3 text-left transition-all ${active ? 'border-violet-400/60 bg-violet-500/12 shadow-[0_8px_24px_rgba(76,29,149,0.12)]' : 'border-white/10 bg-slate-950/20 hover:border-white/20 hover:bg-white/[0.04]'}`}>
          <div className="flex items-start justify-between gap-3"><span className="text-sm font-medium text-white">{stage.name}</span><span className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-1 text-[10px] ${statusStyle[stage.status]}`}><StatusIcon status={stage.status} />{stage.routing.source_label}</span></div>
          <p className="mt-2 truncate text-xs text-slate-500">{stage.template ? `${stage.template.name} · v${stage.template.version}` : stage.message}</p>
        </button>;
      })}</div>
    </section>)}
  </nav>;
}
