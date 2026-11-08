import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

import { modelCenterSectionHref, type ModelCenterLocation } from '../navigation';
import type { ReadinessIssue } from '../types';
import { ModelCenterEmpty } from './model-center-state';

export function ReadinessChecklist({ issues, location }: { issues: ReadinessIssue[]; location: ModelCenterLocation }) {
  if (!issues.length) return <ModelCenterEmpty title="当前没有生产阻塞项" description="连接、绑定、认证、提示词和发布方案均已就绪。" />;
  return <ul className="mt-4 space-y-2">{issues.map((issue) => <li key={`${issue.code}-${issue.resource_id}-${issue.capability || ''}`} className={`rounded-md border px-3 py-2 text-sm ${issue.severity === 'blocker' ? 'border-amber-400/15 bg-amber-400/5 text-amber-100' : 'border-white/10 bg-white/[0.03] text-slate-300'}`}><div className="flex items-start justify-between gap-3"><p>{issue.message}</p><span className="shrink-0 rounded bg-amber-300/10 px-1.5 py-0.5 text-[10px]">{issue.severity === 'blocker' ? '阻塞' : '建议'}</span></div><Link className="mt-2 inline-flex items-center gap-1 text-xs text-violet-300 hover:text-violet-200" href={modelCenterSectionHref(issue.section, { capability: issue.capability, returnTo: location.returnTo, runId: location.runId })}>{issue.action_label} <ArrowRight className="h-3 w-3" /></Link></li>)}</ul>;
}
