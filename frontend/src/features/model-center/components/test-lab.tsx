'use client';

import { FormEvent, useState } from 'react';

import { useCertificationRun } from '../hooks/use-certification-run';
import { useModelCatalog } from '../hooks/use-model-catalog';
import { useModelConnections } from '../hooks/use-model-connections';
import { type ModelCenterLocation } from '../navigation';
import type { CertificationLevel } from '../types';
import { AdvancedParametersDrawer, type LiveCertificationContext } from './advanced-parameters-drawer';
import { CertificationRunPanel } from './certification-run-panel';
import { ModelCenterEmpty, ModelCenterError, ModelCenterLoading } from './model-center-state';

const emptyLiveContext: LiveCertificationContext = { userScope: '', recipeVersion: '', chapterContext: '', selectedShots: '', budgetCeiling: '', retryPolicy: 'no_retry', storagePolicy: 'public_qiniu' };

function LiveConfirmation({ canSubmit, onClose, onSubmit }: { canSubmit: boolean; onClose: () => void; onSubmit: () => void }) {
  const [confirmed, setConfirmed] = useState(false);
  return <div role="dialog" aria-modal="true" aria-label="真实费用确认" className="fixed inset-0 z-50 grid place-items-center bg-slate-950/75 p-4"><section className="w-full max-w-lg rounded-xl border border-amber-300/25 bg-slate-900 p-5 shadow-2xl"><h2 className="text-lg font-semibold text-white">真实费用确认</h2><p className="mt-2 text-sm leading-6 text-slate-300">真实验证会调用已选模型并产生费用。系统将遵守预算上限和失败不重试策略。</p><label className="mt-5 flex items-start gap-2 text-sm text-amber-100"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />本次会产生真实费用</label>{!canSubmit && <p className="mt-3 text-xs text-amber-100">请先完整填写模型、连接、运行上下文、镜头、预算、重试与存储策略。</p>}<div className="mt-5 flex justify-end gap-2"><button type="button" onClick={onClose} className="model-center-quiet">取消</button><button type="button" disabled={!confirmed || !canSubmit} onClick={onSubmit} className="model-center-primary">提交真实验证</button></div></section></div>;
}

export function TestLab({ runId, location }: { runId?: string; location: ModelCenterLocation }) {
  const run = useCertificationRun(runId);
  const catalog = useModelCatalog();
  const connections = useModelConnections();
  const [level, setLevel] = useState<Exclude<CertificationLevel, 'none'>>('contract');
  const [profileVersionId, setProfileVersionId] = useState('');
  const [connectionId, setConnectionId] = useState('');
  const [reason, setReason] = useState('');
  const [liveContext, setLiveContext] = useState(emptyLiveContext);
  const [showLiveConfirmation, setShowLiveConfirmation] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (level === 'live') return setShowLiveConfirmation(true);
    try {
      const created = await run.createCertification({ profile_version_id: profileVersionId, connection_id: connectionId, level, reason });
      setMessage(`认证请求已提交：${created.id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '认证请求失败');
    }
  };
  const submitLive = async () => {
    setShowLiveConfirmation(false);
    try {
      const created = await run.createCertification({ profile_version_id: profileVersionId, connection_id: connectionId, level: 'live', reason });
      setMessage(`真实验证请求已提交：${created.id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '真实验证请求失败');
    }
  };
  const profiles = catalog.data?.items || [];
  const savedConnections = connections.data?.items || [];
  const liveReady = [liveContext.userScope, liveContext.recipeVersion, liveContext.chapterContext, liveContext.selectedShots, liveContext.budgetCeiling].every((value) => value.trim().length > 0);
  return <div className="space-y-4 p-4">{runId && (run.loading && !run.data ? <ModelCenterLoading label="正在读取认证证据…" /> : run.error && !run.data ? <ModelCenterError error={run.error} onRetry={() => void run.reload()} /> : run.data ? <CertificationRunPanel run={run.data} location={location} /> : <ModelCenterEmpty title="未找到认证运行" description="请从连接或模型版本的认证入口重新进入。" />)}<section className="rounded-lg border border-white/10 bg-slate-950/20 p-4"><header className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-sm font-semibold text-white">分级认证</h2><p className="mt-1 text-xs text-slate-500">连接认证用于启用连接；契约认证用于发布模型；真实验证用于生产方案验收。</p></div><button type="button" onClick={() => setLevel('live')} className="model-center-quiet">发起真实验证</button></header><form onSubmit={submit} className="mt-4 grid gap-3 sm:grid-cols-2"><label className="text-xs text-slate-400">认证等级<select aria-label="认证等级" value={level} onChange={(event) => setLevel(event.target.value as Exclude<CertificationLevel, 'none'>)} className="model-center-input mt-1 w-full"><option value="connection">连接认证（最小健康请求）</option><option value="contract">契约认证（低成本或模拟）</option><option value="live">真实验证（费用确认）</option></select></label><label className="text-xs text-slate-400">模型版本<select aria-label="模型版本" required value={profileVersionId} onChange={(event) => setProfileVersionId(event.target.value)} className="model-center-input mt-1 w-full"><option value="">选择目录中的模型版本</option>{profiles.map((entry) => <option key={entry.profile.id} value={entry.profile.id}>{entry.profile.api_model_id} · v{entry.profile.version}</option>)}</select></label><label className="text-xs text-slate-400">模型连接<select aria-label="模型连接" required value={connectionId} onChange={(event) => setConnectionId(event.target.value)} className="model-center-input mt-1 w-full"><option value="">选择已保存连接</option>{savedConnections.map((connection) => <option key={connection.id} value={connection.id}>{connection.name} · {connection.has_secret ? '已脱敏凭证' : '未设置凭证'}</option>)}</select></label><label className="text-xs text-slate-400">操作原因<input aria-label="操作原因" required value={reason} onChange={(event) => setReason(event.target.value)} className="model-center-input mt-1 w-full" /></label>{level === 'live' && <div className="sm:col-span-2"><AdvancedParametersDrawer value={liveContext} onChange={setLiveContext} /></div>}<div className="sm:col-span-2 flex justify-end"><button type="submit" disabled={!profileVersionId || !connectionId || reason.trim().length < 2 || (level === 'live' && !liveReady)} className="model-center-primary">提交{level === 'live' ? '真实验证' : '认证'}</button></div></form>{message && <p className="mt-3 rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-100">{message}</p>}</section>{showLiveConfirmation && <LiveConfirmation canSubmit={Boolean(profileVersionId && connectionId && reason.trim().length >= 2 && liveReady)} onClose={() => setShowLiveConfirmation(false)} onSubmit={() => void submitLive()} />}</div>;
}
