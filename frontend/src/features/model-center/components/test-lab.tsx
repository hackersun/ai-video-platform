'use client';

import { FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { useCertificationRun } from '../hooks/use-certification-run';
import { useCertificationCandidates, useCertificationHistory } from '../hooks/use-certification-history';
import { modelCenterHref, type ModelCenterLocation } from '../navigation';
import type { CertificationLevel, ModelCapability } from '../types';
import { AdvancedParametersDrawer, type LiveCertificationContext } from './advanced-parameters-drawer';
import { CertificationRunPanel } from './certification-run-panel';
import { ModelVersionPicker } from './model-version-picker';
import { ModelCenterEmpty, ModelCenterError, ModelCenterLoading } from './model-center-state';

const emptyLiveContext: LiveCertificationContext = { userScope: '', recipeVersion: '', chapterId: '', runId: '', selectedShots: '', budgetCeiling: '', retryPolicy: 'never', storagePolicy: 'qiniu_public' };
const capabilities: Array<{ value: ModelCapability; label: string }> = [
  { value: 'text_generation', label: '文本生成' },
  { value: 'vision_analysis', label: '视觉理解' },
  { value: 'image_generation', label: '图像生成' },
  { value: 'video_generation', label: '视频生成' },
  { value: 'speech_generation', label: '语音生成' },
  { value: 'subtitle_generation', label: '字幕生成' },
  { value: 'media_render', label: '成片合成' },
  { value: 'object_storage', label: '对象存储' },
];

function LiveConfirmation({ canSubmit, onClose, onSubmit }: { canSubmit: boolean; onClose: () => void; onSubmit: () => void }) {
  const [confirmed, setConfirmed] = useState(false);
  return <div role="dialog" aria-modal="true" aria-label="真实费用确认" className="fixed inset-0 z-50 grid place-items-center bg-slate-950/75 p-4"><section className="w-full max-w-lg rounded-xl border border-amber-300/25 bg-slate-900 p-5 shadow-2xl"><h2 className="text-lg font-semibold text-white">真实费用确认</h2><p className="mt-2 text-sm leading-6 text-slate-300">真实验证会按已确认的预算、镜头和策略提交安全执行意图；运行结束后需回到本页查看脱敏证据。</p><label className="mt-5 flex items-start gap-2 text-sm text-amber-100"><input aria-label="本次会产生真实费用" type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />本次会产生真实费用</label>{!canSubmit && <p className="mt-3 text-xs text-amber-100">请先完整填写兼容模型组合、运行上下文、镜头、预算、重试与存储策略。</p>}<div className="mt-5 flex justify-end gap-2"><button type="button" onClick={onClose} className="model-center-quiet">取消</button><button type="button" disabled={!confirmed || !canSubmit} onClick={onSubmit} className="model-center-primary">提交真实验证</button></div></section></div>;
}

export function TestLab({ runId, location }: { runId?: string; location: ModelCenterLocation }) {
  const router = useRouter();
  const run = useCertificationRun(runId);
  const [level, setLevel] = useState<Exclude<CertificationLevel, 'none'>>(location.level || 'contract');
  const [capability, setCapability] = useState<ModelCapability | undefined>(
    location.capability || (location.connectionId ? undefined : 'video_generation'),
  );
  const [query, setQuery] = useState('');
  const [profileFilter, setProfileFilter] = useState(location.profileVersionId);
  const [connectionFilter, setConnectionFilter] = useState(location.connectionId);
  const candidates = useCertificationCandidates(
    capability, query, 1, 100, level, profileFilter, connectionFilter,
  );
  const [candidateId, setCandidateId] = useState('');
  const [historyLevel, setHistoryLevel] = useState('');
  const [historyStatus, setHistoryStatus] = useState('');
  const history = useCertificationHistory(historyLevel, historyStatus);
  const [reason, setReason] = useState('');
  const [liveContext, setLiveContext] = useState(emptyLiveContext);
  const [showLiveConfirmation, setShowLiveConfirmation] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const candidateRows = candidates.data?.items || [];
  const selected = candidateRows.find((item) => item.id === candidateId);
  const profileVersionId = selected?.profile.id || '';
  const connectionId = selected?.connection.id || '';
  const liveReady = [liveContext.userScope, liveContext.recipeVersion, liveContext.chapterId, liveContext.runId, liveContext.selectedShots, liveContext.budgetCeiling].every((value) => value.trim().length > 0);
  useEffect(() => {
    if (candidateRows.length === 1 && !candidateId) setCandidateId(candidateRows[0].id);
  }, [candidateId, candidateRows]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (level === 'live') return setShowLiveConfirmation(true);
    try {
      const created = await run.createCertification({ profile_version_id: profileVersionId, connection_id: connectionId, level, reason });
      router.push(modelCenterHref({
        ...location, section: 'test-lab', runId: created.id,
        level: undefined, profileVersionId: undefined, connectionId: undefined,
      }));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '认证请求失败，请修改后重试。');
    }
  };
  const submitLive = async () => {
    setShowLiveConfirmation(false);
    try {
      const created = await run.createCertification({
        profile_version_id: profileVersionId, connection_id: connectionId, level: 'live', reason,
        user_scope: liveContext.userScope.trim(), recipe_version_id: liveContext.recipeVersion.trim(),
        chapter_id: liveContext.chapterId.trim(), run_id: liveContext.runId.trim(),
        selected_shot_ids: liveContext.selectedShots.split(',').map((item) => item.trim()).filter(Boolean),
        budget_ceiling_rmb: liveContext.budgetCeiling.trim(), retry_policy: liveContext.retryPolicy,
        storage_policy: liveContext.storagePolicy, real_cost_acknowledged: true,
      });
      router.push(modelCenterHref({
        ...location, section: 'test-lab', runId: created.id,
        level: undefined, profileVersionId: undefined, connectionId: undefined,
      }));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '真实验证请求失败，请修改后重试。');
    }
  };

  return <div className="space-y-4 p-4">
    {runId && (run.loading && !run.data ? <ModelCenterLoading label="正在读取认证证据…" /> : run.error && !run.data ? <ModelCenterError error={run.error} onRetry={() => void run.reload()} /> : run.data ? <CertificationRunPanel run={run.data} location={location} /> : <ModelCenterEmpty title="未找到认证运行" description="请从认证历史或兼容候选重新进入。" />)}
    <section className="rounded-lg border border-white/10 bg-slate-950/20 p-4">
      <header className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-sm font-semibold text-white">分级认证</h2><p className="mt-1 text-xs text-slate-500">候选由服务端按提供方、能力、发布状态和连接认证结果配对。</p></div><button type="button" onClick={() => setLevel('live')} className="model-center-quiet">发起真实验证</button></header>
      <form onSubmit={submit} className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-slate-400">认证等级<select aria-label="认证等级" value={level} onChange={(event) => { setLevel(event.target.value as Exclude<CertificationLevel, 'none'>); setCandidateId(''); }} className="model-center-input mt-1 w-full"><option value="connection">连接认证（会请求提供方）</option><option value="contract">契约认证（本地免费）</option><option value="live">真实验证（费用确认）</option></select></label>
        <label className="text-xs text-slate-400">模型能力<select aria-label="模型能力" value={capability || ''} onChange={(event) => { setCapability((event.target.value || undefined) as ModelCapability | undefined); setProfileFilter(undefined); setConnectionFilter(undefined); setCandidateId(''); }} className="model-center-input mt-1 w-full"><option value="">全部能力</option>{capabilities.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        <label className="text-xs text-slate-400">搜索兼容模型<input aria-label="搜索兼容模型" value={query} onChange={(event) => { setQuery(event.target.value); setProfileFilter(undefined); setConnectionFilter(undefined); setCandidateId(''); }} placeholder="模型、API 标识、提供方或连接" className="model-center-input mt-1 w-full" /></label>
        <ModelVersionPicker candidates={candidateRows} value={candidateId} loading={candidates.loading} onChange={setCandidateId} />
        <label className="text-xs text-slate-400 sm:col-span-2">操作原因<input aria-label="操作原因" required value={reason} onChange={(event) => setReason(event.target.value)} className="model-center-input mt-1 w-full" /></label>
        {level === 'live' && <div className="sm:col-span-2"><AdvancedParametersDrawer value={liveContext} onChange={setLiveContext} /></div>}
        <div className="sm:col-span-2 flex justify-end"><button type="submit" disabled={!selected || reason.trim().length < 2 || (level === 'live' && !liveReady)} className="model-center-primary">提交{level === 'live' ? '真实验证' : '认证'}</button></div>
      </form>
      {candidates.error && <p className="mt-3 rounded-md bg-rose-500/10 px-3 py-2 text-xs text-rose-100">{candidates.error.message} 请修改筛选或检查连接后重试。</p>}
      {candidates.data && !candidates.loading && !candidates.error && candidateRows.length === 0 && <p className="mt-3 rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-100">当前筛选没有可用的模型连接组合。<Link href={modelCenterHref({ ...location, section: 'connections', level: undefined, profileVersionId: undefined, connectionId: undefined, runId: undefined })} className="ml-1 font-medium text-violet-200 underline underline-offset-2">先配置模型连接</Link>，保存并测试凭证后再返回认证。</p>}
      {message && <p className="mt-3 rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-100">{message}</p>}
    </section>
    <section className="rounded-lg border border-white/10 bg-slate-950/20 p-4">
      <header><h2 className="text-sm font-semibold text-white">认证历史</h2><p className="mt-1 text-xs text-slate-500">仅展示脱敏证据，可按等级和状态筛选。</p></header>
      <div className="mt-3 grid gap-2 sm:grid-cols-2"><label className="text-xs text-slate-400">认证等级<select aria-label="历史认证等级" value={historyLevel} onChange={(event) => setHistoryLevel(event.target.value)} className="model-center-input mt-1 w-full"><option value="">全部等级</option><option value="connection">连接</option><option value="contract">契约</option><option value="live">真实</option></select></label><label className="text-xs text-slate-400">认证状态<select aria-label="历史认证状态" value={historyStatus} onChange={(event) => setHistoryStatus(event.target.value)} className="model-center-input mt-1 w-full"><option value="">全部状态</option><option value="queued">排队中</option><option value="success">成功</option><option value="failed">失败</option></select></label></div>
      {history.loading && !history.data ? <ModelCenterLoading label="正在读取认证历史…" /> : history.error && !history.data ? <ModelCenterError error={history.error} onRetry={() => void history.reload()} /> : history.data?.items.length ? <div className="mt-3 overflow-x-auto rounded-lg border border-white/10"><table className="min-w-full text-left text-sm"><thead className="bg-white/[0.035] text-xs text-slate-500"><tr><th>模型与连接</th><th>等级</th><th>状态</th><th>脱敏证据</th><th>时间</th></tr></thead><tbody>{history.data.items.map((item) => <tr key={item.id} className="border-t border-white/[0.07] text-slate-300"><td><span className="block text-white">{item.profile_name} · {item.connection_name}</span><span className="text-xs text-slate-500">{item.api_model_id} · {item.provider_name}</span></td><td>{item.level}</td><td>{item.status}</td><td>{String(item.sanitized_evidence.error_code || item.sanitized_evidence.failed_stage || '已脱敏')}</td><td>{new Date(item.created_at).toLocaleString('zh-CN')}</td></tr>)}</tbody></table></div> : <ModelCenterEmpty title="暂无匹配的认证历史" description="调整筛选条件或先提交一次无费用契约认证。" />}
    </section>
    {showLiveConfirmation && <LiveConfirmation canSubmit={Boolean(selected && reason.trim().length >= 2 && liveReady)} onClose={() => setShowLiveConfirmation(false)} onSubmit={() => void submitLive()} />}
  </div>;
}
