import Link from 'next/link';
import { ArrowRight } from 'lucide-react';

import { modelCenterSectionHref, type ModelCenterLocation } from '../navigation';
import type { ReadinessIssue } from '../types';
import { ModelCenterEmpty } from './model-center-state';

export function ReadinessChecklist({ issues, location }: { issues: ReadinessIssue[]; location: ModelCenterLocation }) {
  if (!issues.length) return <ModelCenterEmpty title="当前没有生产阻塞项" description="连接、绑定、认证、提示词和发布方案均已就绪。" />;
  return <ul className="mt-4 space-y-2">{issues.map((issue) => <li key={`${issue.code}-${issue.resource_id}-${issue.capability || ''}`} className="rounded-md border border-amber-400/15 bg-amber-400/5 px-3 py-2 text-sm text-amber-100"><div className="flex items-start justify-between gap-3"><p>{issue.message}</p><span className="shrink-0 rounded bg-amber-300/10 px-1.5 py-0.5 text-[10px]">{issue.severity === 'blocker' ? '阻塞' : '提醒'}</span></div><Link className="mt-2 inline-flex items-center gap-1 text-xs text-violet-300 hover:text-violet-200" href={modelCenterSectionHref(issue.section, { capability: issue.capability, returnTo: location.returnTo, runId: location.runId })}>{issue.action_label} <ArrowRight className="h-3 w-3" /></Link></li>)}</ul>;
}
