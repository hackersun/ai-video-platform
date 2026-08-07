import { AlertTriangle, CheckCircle2, Layers3 } from 'lucide-react';

import type { PromptUsageMap } from '../prompt-usage-types';

export function PromptUsageSummary({
  summary,
  problemsOnly,
  onToggleProblems,
}: {
  summary: PromptUsageMap['summary'];
  problemsOnly: boolean;
  onToggleProblems: () => void;
}) {
  const healthy = (summary.counts.effective || 0) + (summary.counts.overridden || 0);
  const issues = (summary.counts.internal_fallback || 0) + (summary.counts.invalid_binding || 0);
  return <div data-testid="prompt-usage-summary" className="grid gap-3 border-b border-white/10 p-4 sm:grid-cols-3">
    <div className="rounded-xl border border-violet-400/20 bg-violet-500/[0.07] p-4">
      <div className="flex items-center gap-2 text-xs text-violet-300"><Layers3 className="h-4 w-4" />生产流程</div>
      <p className="mt-2 text-2xl font-semibold text-white">{summary.total} <span className="text-sm font-normal text-slate-400">个环节</span></p>
    </div>
    <div className="rounded-xl border border-emerald-400/20 bg-emerald-500/[0.06] p-4">
      <div className="flex items-center gap-2 text-xs text-emerald-300"><CheckCircle2 className="h-4 w-4" />模板已就绪</div>
      <p className="mt-2 text-2xl font-semibold text-white">{healthy}</p>
    </div>
    <button type="button" onClick={onToggleProblems} className={`rounded-xl border p-4 text-left transition-colors ${problemsOnly ? 'border-amber-400/60 bg-amber-500/15' : 'border-amber-400/20 bg-amber-500/[0.06] hover:bg-amber-500/10'}`}>
      <div className="flex items-center justify-between gap-2 text-xs text-amber-300"><span className="flex items-center gap-2"><AlertTriangle className="h-4 w-4" />需要关注</span><span>{problemsOnly ? '查看全部环节' : '只看问题环节'}</span></div>
      <p className="mt-2 text-2xl font-semibold text-white">{issues}</p>
    </button>
  </div>;
}
