'use client';

import { FormEvent, Fragment, useEffect, useState } from 'react';
import { KeyRound, Plus, TestTube, Trash2 } from 'lucide-react';
import { useRouter } from 'next/navigation';

import { useModelConnections } from '../hooks/use-model-connections';
import { useModelProviders } from '../hooks/use-model-providers';
import { modelCenterHref, type ModelCenterLocation } from '../navigation';
import { connectionDisplayName } from '../model-center-labels';
import { ModelCenterEmpty, ModelCenterError, ModelCenterLoading } from './model-center-state';
import { ModelCenterPagination } from './model-center-pagination';
import { ProviderModelLabel } from './provider-model-label';
import { RemoveConnectionDialog } from './remove-connection-dialog';
import type { ModelConnectionView } from '../types';

const blankForm = { providerId: '', name: '', reason: '', baseUrl: '', apiKey: '' };

export function ModelCenterConnectionsPanel({ location }: { location: ModelCenterLocation }) {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const { data, error, loading, reload, createConnection, updateConnection, removeConnection } = useModelConnections(page, 20);
  const providers = useModelProviders();
  const [form, setForm] = useState(blankForm);
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [secretForm, setSecretForm] = useState({ apiKey: '', reason: '' });
  const [removing, setRemoving] = useState<ModelConnectionView | null>(null);
  useEffect(() => {
    const firstProvider = providers.data?.items[0];
    if (firstProvider && !form.providerId) setForm((current) => ({ ...current, providerId: firstProvider.id }));
  }, [form.providerId, providers.data]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCreating(true);
    setMessage(null);
    try {
      await createConnection({ provider_id: form.providerId.trim(), name: form.name.trim(), reason: form.reason.trim(), base_url: form.baseUrl.trim() || undefined, api_key: form.apiKey });
      setForm(blankForm);
      setMessage('供应商账号已保存。请使用“测试可用性”完成认证。');
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : '供应商账号保存失败');
    } finally {
      setCreating(false);
    }
  };

  const runTest = (connectionId: string) => {
    router.push(modelCenterHref({
      ...location, section: 'test-lab', level: 'connection', connectionId, runId: undefined,
    }));
  };

  const replaceSecret = async (event: FormEvent<HTMLFormElement>, connectionId: string, revision: number) => {
    event.preventDefault();
    setCreating(true);
    setMessage(null);
    try {
      await updateConnection(connectionId, {
        expected_revision: revision, api_key: secretForm.apiKey,
        reason: secretForm.reason.trim(),
      });
      setEditingId(null);
      setSecretForm({ apiKey: '', reason: '' });
      setMessage('凭证已更新并脱敏保存，请继续测试可用性。');
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : '凭证更新失败');
    } finally {
      setCreating(false);
    }
  };

  if (loading && !data) return <ModelCenterLoading label="正在读取供应商账号…" />;
  if (error && !data) return <ModelCenterError error={error} onRetry={() => void reload()} />;
  return (
    <div className="space-y-4 p-4">
      <form id="connection-form" onSubmit={submit} className="rounded-lg border border-white/10 bg-slate-950/30 p-4">
        <div><h2 className="text-sm font-semibold text-white">新增供应商账号</h2><p className="mt-1 text-xs leading-5 text-slate-400">账号名称用于区分同一供应商的不同账号、套餐或环境，不会发送给模型供应商。</p></div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <label className="text-xs text-slate-400">供应商<select aria-label="提供方" required value={form.providerId} onChange={(event) => setForm({ ...form, providerId: event.target.value })} className="model-center-input mt-1 w-full"><option value="" disabled>{providers.loading ? '正在读取供应商…' : '请选择供应商'}</option>{providers.data?.items.map((provider) => <option key={provider.id} value={provider.id}>{provider.display_name}（{provider.code}）</option>)}</select></label>
          <label className="text-xs text-slate-400">账号名称<input aria-label="账号名称" required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="例如：火山生产套餐" className="model-center-input mt-1 w-full" /></label>
          <label className="text-xs text-slate-400">API Key<input aria-label="API Key" required type="password" autoComplete="off" value={form.apiKey} onChange={(event) => setForm({ ...form, apiKey: event.target.value })} placeholder="仅加密保存到服务端" className="model-center-input mt-1 w-full" /></label>
          <label className="text-xs text-slate-400">保存说明<input aria-label="保存说明" required minLength={2} value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} placeholder="例如：新增生产账号" className="model-center-input mt-1 w-full" /></label>
          <label className="text-xs text-slate-400 md:col-span-2">自定义 API 地址（通常留空）<input aria-label="自定义 API 地址" value={form.baseUrl} onChange={(event) => setForm({ ...form, baseUrl: event.target.value })} placeholder="仅私有网关或兼容接口需要填写" className="model-center-input mt-1 w-full" /></label>
        </div>
        <div className="mt-4 flex justify-end"><button disabled={creating} type="submit" className="model-center-primary"><Plus className="h-4 w-4" />{creating ? '保存中' : '新增账号'}</button></div>
      </form>
      <p className="flex items-center gap-2 px-1 text-xs text-slate-500"><KeyRound className="h-3.5 w-3.5" />密钥仅提交到服务端保存；界面只显示脱敏状态。</p>
      {message && <p className={`rounded-md px-3 py-2 text-xs ${message.includes('失败') || message.includes('未能') ? 'bg-rose-500/10 text-rose-200' : 'bg-emerald-500/10 text-emerald-200'}`}>{message}</p>}
      {!data?.items.length ? <ModelCenterEmpty title="还没有供应商账号" description="先保存 API 凭证，再测试可用性并选择默认模型。" /> : (
        <div className="overflow-x-auto rounded-lg border border-white/10">
          <table className="w-full min-w-[900px] table-fixed text-left text-sm"><thead className="bg-white/[0.035] text-xs text-slate-500"><tr><th className="w-36">账号名称</th><th className="w-28">供应商</th><th className="w-32">凭证</th><th className="w-32">接口地址</th><th className="w-[22rem] text-right">操作</th></tr></thead>
            <tbody>{data.items.map((connection) => { const displayName = connectionDisplayName(connection.name, connection.provider_name); return <Fragment key={connection.id}><tr className="border-t border-white/[0.07] text-slate-300"><td><span className="font-medium text-white">{displayName}</span>{connection.name.startsWith('legacy:') && <span className="mt-0.5 block text-[11px] text-slate-500">历史迁移配置</span>}</td><td><ProviderModelLabel providerName={connection.provider_name} providerCode={connection.provider_code} /></td><td><span className={`whitespace-nowrap ${connection.has_secret ? 'text-emerald-300' : 'text-amber-300'}`}>{connection.has_secret ? '已保存 · 已脱敏' : '未设置'}</span></td><td className="max-w-44 truncate whitespace-nowrap text-slate-500">{connection.base_url || '供应商默认地址'}</td><td className="whitespace-nowrap text-right"><div className="flex flex-nowrap justify-end gap-2"><button type="button" onClick={() => { setEditingId(connection.id); setSecretForm({ apiKey: '', reason: '' }); }} className="model-center-quiet whitespace-nowrap"><KeyRound className="h-3.5 w-3.5 shrink-0" />{connection.has_secret ? '替换凭证' : '补录凭证'}</button><button type="button" disabled={!connection.has_secret} title={connection.has_secret ? '选择兼容模型并向供应商发起连接认证' : '请先保存 API Key'} onClick={() => runTest(connection.id)} className="model-center-quiet whitespace-nowrap"><TestTube className="h-3.5 w-3.5 shrink-0" />测试可用性</button><button type="button" aria-label={`移除${displayName}`} onClick={() => setRemoving(connection)} className="model-center-quiet whitespace-nowrap text-rose-200 hover:text-rose-100"><Trash2 className="h-3.5 w-3.5 shrink-0" />移除</button></div></td></tr>{editingId === connection.id && <tr className="border-t border-violet-400/15 bg-violet-500/5"><td colSpan={5}><form onSubmit={(event) => void replaceSecret(event, connection.id, connection.revision)} className="flex flex-wrap items-center gap-2 p-3"><input aria-label={`API Key ${connection.name}`} required type="password" autoComplete="off" value={secretForm.apiKey} onChange={(event) => setSecretForm({ ...secretForm, apiKey: event.target.value })} placeholder="输入新的 API Key" className="model-center-input min-w-64 flex-1" /><input aria-label={`凭证更新原因 ${connection.name}`} required minLength={2} value={secretForm.reason} onChange={(event) => setSecretForm({ ...secretForm, reason: event.target.value })} placeholder="更新原因（至少2字）" className="model-center-input min-w-52" /><button type="submit" disabled={creating} className="model-center-primary whitespace-nowrap">保存凭证</button><button type="button" onClick={() => setEditingId(null)} className="model-center-quiet whitespace-nowrap">取消</button></form></td></tr>}</Fragment>; })}</tbody>
          </table>
        </div>
      )}
      {data && <ModelCenterPagination page={data.meta.page} pageSize={data.meta.page_size} total={data.meta.total} onPageChange={setPage} />}
      {removing && <RemoveConnectionDialog connection={removing} onClose={() => setRemoving(null)} onConfirm={async (reason) => {
        await removeConnection(removing.id, { expected_revision: removing.revision, reason });
        setMessage('账号已移除，密钥已清除；历史测试和任务记录仍保留。');
      }} />}
    </div>
  );
}
