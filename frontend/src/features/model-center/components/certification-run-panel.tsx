'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { modelCenterSectionHref, type ModelCenterLocation } from '../navigation';
import type { CertificationRun } from '../types';

const levelLabel = { connection: '连接认证', contract: '契约认证', live: '真实验证', none: '未认证' } as const;

function evidenceValue(evidence: Record<string, unknown>, key: string, fallback = '—') {
  const value = evidence[key];
  return typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? String(value) : fallback;
}

export function CertificationRunPanel({ run, location }: { run: CertificationRun; location: ModelCenterLocation }) {
  const router = useRouter();
  const evidence = run.sanitized_evidence || {};
  const retry = (section: 'connections' | 'bindings') => router.push(modelCenterSectionHref(section, location));
  return <section className="rounded-lg border border-white/10 bg-slate-950/25 p-4"><header className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-base font-semibold text-white">{levelLabel[run.level]}</h2><p className="mt-1 text-xs text-slate-500">运行 {run.id} · {run.status}</p></div><span className={run.status === 'passed' ? 'text-emerald-300' : 'text-rose-200'}>{run.status === 'passed' ? '已通过' : '需要处理'}</span></header><dl className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"><div><dt>失败阶段</dt><dd>{evidenceValue(evidence, 'failed_stage', '未失败')}</dd></div><div><dt>稳定错误码</dt><dd>{evidenceValue(evidence, 'error_code')}</dd></div><div><dt>已发生费用</dt><dd>¥{evidenceValue(evidence, 'cost_incurred_rmb', run.actual_cost_rmb)}</dd></div><div><dt>可否重试</dt><dd>{evidenceValue(evidence, 'retry_eligible', 'false') === 'true' ? '可重试' : '不可重试'}</dd></div><div><dt>预计费用</dt><dd>¥{run.estimated_cost_rmb}</dd></div><div><dt>完成时间</dt><dd>{run.completed_at || '进行中'}</dd></div></dl><div className="mt-4 rounded-lg border border-white/10 bg-black/15 p-3"><p className="text-xs text-slate-500">易读原因</p><p className="mt-1 text-sm text-slate-200">{evidenceValue(evidence, 'plain_reason', '尚无失败说明。')}</p></div><div className="mt-4 grid gap-3 lg:grid-cols-2"><details className="rounded-lg border border-white/10 p-3"><summary className="cursor-pointer text-xs text-slate-400">已脱敏请求摘要</summary><pre className="mt-3 overflow-auto text-xs text-slate-300">{JSON.stringify(evidence.request_summary ?? {}, null, 2)}</pre></details><details className="rounded-lg border border-white/10 p-3"><summary className="cursor-pointer text-xs text-slate-400">已脱敏响应证据</summary><pre className="mt-3 overflow-auto text-xs text-slate-300">{JSON.stringify(evidence.response_evidence ?? evidence, null, 2)}</pre></details></div>{run.status !== 'passed' && <div className="mt-4 flex flex-wrap gap-2"><button type="button" onClick={() => retry('connections')} className="model-center-quiet">修改连接后重试</button><button type="button" onClick={() => retry('bindings')} className="model-center-quiet">切换绑定后重试</button><button type="button" onClick={() => router.push(modelCenterSectionHref('recipes', location))} className="model-center-quiet">修改高级参数后重试</button>{location.returnTo && <Link href={location.returnTo} className="model-center-quiet">返回工作台</Link>}</div>}</section>;
}
