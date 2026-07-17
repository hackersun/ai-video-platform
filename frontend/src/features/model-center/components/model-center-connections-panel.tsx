'use client';

import { FormEvent, useState } from 'react';
import { CheckCircle2, KeyRound, Loader2, Plus, TestTube } from 'lucide-react';
import { useRouter } from 'next/navigation';

import { useModelConnections } from '../hooks/use-model-connections';
import { modelCenterHref, type ModelCenterLocation } from '../navigation';
import { ModelCenterEmpty, ModelCenterError, ModelCenterLoading } from './model-center-state';

const blankForm = { providerId: '', name: '', baseUrl: '', apiKey: '' };

export function ModelCenterConnectionsPanel({ location }: { location: ModelCenterLocation }) {
  const router = useRouter();
  const { data, error, loading, reload, createConnection, testConnection } = useModelConnections();
  const [form, setForm] = useState(blankForm);
  const [creating, setCreating] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCreating(true);
    setMessage(null);
    try {
      await createConnection({ provider_id: form.providerId.trim(), name: form.name.trim(), base_url: form.baseUrl.trim() || undefined, api_key: form.apiKey });
      setForm(blankForm);
      setMessage('连接已保存。请使用“测试连接”完成认证。');
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : '连接保存失败');
    } finally {
      setCreating(false);
    }
  };

  const runTest = async (connectionId: string) => {
    setTestingId(connectionId);
    setMessage(null);
    try {
      const run = await testConnection(connectionId);
      router.push(modelCenterHref({ ...location, section: 'test-lab', runId: run.id }));
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : '测试请求未能提交');
    } finally {
      setTestingId(null);
    }
  };

  if (loading && !data) return <ModelCenterLoading label="正在读取模型连接…" />;
  if (error && !data) return <ModelCenterError error={error} onRetry={() => void reload()} />;
  return (
    <div className="space-y-4 p-4">
      <form onSubmit={submit} className="grid gap-2 rounded-lg border border-white/10 bg-slate-950/30 p-3 md:grid-cols-[1fr_1fr_1fr_1fr_auto]">
        <input aria-label="提供方 ID" required value={form.providerId} onChange={(event) => setForm({ ...form, providerId: event.target.value })} placeholder="提供方 ID" className="model-center-input" />
        <input aria-label="连接名称" required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="连接名称" className="model-center-input" />
        <input aria-label="自定义 API 地址" value={form.baseUrl} onChange={(event) => setForm({ ...form, baseUrl: event.target.value })} placeholder="自定义 API 地址（可选）" className="model-center-input" />
        <input aria-label="API Key" required type="password" autoComplete="off" value={form.apiKey} onChange={(event) => setForm({ ...form, apiKey: event.target.value })} placeholder="API Key" className="model-center-input" />
        <button disabled={creating} type="submit" className="model-center-primary"><Plus className="h-4 w-4" />{creating ? '保存中' : '新增连接'}</button>
      </form>
      <p className="flex items-center gap-2 px-1 text-xs text-slate-500"><KeyRound className="h-3.5 w-3.5" />密钥仅提交到服务端保存；界面只显示脱敏状态。</p>
      {message && <p className={`rounded-md px-3 py-2 text-xs ${message.includes('失败') || message.includes('未能') ? 'bg-rose-500/10 text-rose-200' : 'bg-emerald-500/10 text-emerald-200'}`}>{message}</p>}
      {!data?.items.length ? <ModelCenterEmpty title="还没有模型连接" description="新增连接后，按任务能力绑定到生产方案。" /> : (
        <div className="overflow-x-auto rounded-lg border border-white/10">
          <table className="min-w-full text-left text-sm"><thead className="bg-white/[0.035] text-xs text-slate-500"><tr><th>连接名称</th><th>提供方</th><th>凭证</th><th>地址</th><th className="text-right">操作</th></tr></thead>
            <tbody>{data.items.map((connection) => <tr key={connection.id} className="border-t border-white/[0.07] text-slate-300"><td className="font-medium text-white">{connection.name}</td><td>{connection.provider_id}</td><td><span className={connection.has_secret ? 'text-emerald-300' : 'text-amber-300'}>{connection.has_secret ? '已保存 · 已脱敏' : '未设置'}</span></td><td className="max-w-44 truncate text-slate-500">{connection.base_url || '默认地址'}</td><td className="text-right"><button type="button" disabled={testingId === connection.id || !connection.enabled} onClick={() => void runTest(connection.id)} className="model-center-quiet"><TestTube className="h-3.5 w-3.5" />{testingId === connection.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : '测试连接'}</button></td></tr>)}</tbody>
          </table>
        </div>
      )}
      <div className="flex items-center justify-between text-xs text-slate-500"><span>共 {data?.meta.total || 0} 条连接</span><button type="button" onClick={() => void reload()} className="hover:text-white">刷新连接列表</button></div>
    </div>
  );
}
