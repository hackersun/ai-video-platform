'use client';

import Link from 'next/link';
import { ArrowRight, CheckCircle2, ShieldAlert } from 'lucide-react';

import { modelCenterSectionHref, type ModelCenterLocation } from '../navigation';
import { useModelCenterOverview } from '../hooks/use-model-center-overview';
import { ModelCenterError, ModelCenterLoading } from './model-center-state';
import { ReadinessChecklist } from './readiness-checklist';

export function ModelCenterOverviewPanel({ location }: { location: ModelCenterLocation }) {
  const { data, error, loading, reload } = useModelCenterOverview();
  if (loading && !data) return <ModelCenterLoading />;
  if (error && !data) return <ModelCenterError error={error} onRetry={() => void reload()} />;
  const issues = data?.blocking_issues || [];
  return <div className="grid gap-4 p-4 lg:grid-cols-2"><section className="rounded-lg border border-white/10 bg-slate-950/30 p-5"><div className="flex items-center gap-2"><ShieldAlert className="h-5 w-5 text-amber-300" /><h2 className="font-semibold text-white">生产阻塞项</h2></div><ReadinessChecklist issues={issues} location={location} /></section><section className="rounded-lg border border-white/10 bg-slate-950/30 p-5"><div className="flex items-center gap-2"><CheckCircle2 className="h-5 w-5 text-emerald-300" /><h2 className="font-semibold text-white">配置覆盖</h2></div><dl className="mt-5 grid grid-cols-2 gap-3"><div><dt>已保存连接</dt><dd className="mt-1 text-2xl font-semibold text-white">{data?.connections.length || 0}</dd></div><div><dt>生产组合</dt><dd className="mt-1 text-2xl font-semibold text-white">{data?.recipes.length || 0}</dd></div></dl><Link href={modelCenterSectionHref('recipes', location)} className="mt-7 inline-flex items-center gap-1 text-sm text-violet-300 hover:text-violet-200">维护组合预设 <ArrowRight className="h-4 w-4" /></Link></section></div>;
}
