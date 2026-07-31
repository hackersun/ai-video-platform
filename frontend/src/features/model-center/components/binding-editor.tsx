'use client';

import { X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { modelCenterApi } from '../api';
import { capabilityLabels, connectionDisplayName, modelTaskOptions, taskLabel } from '../model-center-labels';
import type {
  ModelBindingInput,
  ModelBindingView,
  ModelCapability,
  ModelCatalogView,
  ModelConnectionView,
} from '../types';

type BindingEditorProps = {
  binding?: ModelBindingView;
  onClose: () => void;
  onSave: (input: ModelBindingInput) => Promise<void>;
};

export function BindingEditor({ binding, onClose, onSave }: BindingEditorProps) {
  const initialTask = modelTaskOptions.find((item) => item.key === binding?.task) || modelTaskOptions[3];
  const [task, setTask] = useState(binding?.task || initialTask.key);
  const [capability, setCapability] = useState<ModelCapability>(binding?.capability || initialTask.capability);
  const [models, setModels] = useState<ModelCatalogView[]>([]);
  const [connections, setConnections] = useState<ModelConnectionView[]>([]);
  const [profileId, setProfileId] = useState(binding?.profile_version_id || '');
  const [connectionId, setConnectionId] = useState(binding?.connection_id || '');
  const [priority, setPriority] = useState(binding?.priority ?? 100);
  const [routePolicy, setRoutePolicy] = useState(binding?.route_policy || 'single');
  const [fallbackProfileId, setFallbackProfileId] = useState(binding?.fallback_profile_version_ids[0] || '');
  const [active, setActive] = useState(binding?.is_active ?? true);
  const [reason, setReason] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([
      modelCenterApi.listCatalog(1, 100, { capability }),
      modelCenterApi.listConnections(1, 100),
    ]).then(([catalog, connectionPage]) => {
      const candidates = catalog.items.filter((item) => item.profile_version_id);
      setModels(candidates);
      setConnections(connectionPage.items);
      setProfileId((current) => candidates.some((item) => item.profile_version_id === current)
        ? current : candidates[0]?.profile_version_id || '');
    }).catch((failure) => setError(failure instanceof Error ? failure.message : '无法读取兼容模型'));
  }, [capability]);

  const selectedModel = models.find((model) => model.profile_version_id === profileId);
  const matchingConnections = useMemo(() => connections.filter(
    (connection) => connection.enabled && connection.provider_id === selectedModel?.provider_id,
  ), [connections, selectedModel?.provider_id]);
  const fallbackModels = models.filter((model) => model.profile_version_id !== profileId);

  useEffect(() => {
    setConnectionId((current) => matchingConnections.some((item) => item.id === current)
      ? current : matchingConnections[0]?.id || '');
  }, [matchingConnections]);
  useEffect(() => {
    if (routePolicy !== 'pre_submit_fallback') setFallbackProfileId('');
  }, [routePolicy]);

  const changeTask = (value: string) => {
    const selected = modelTaskOptions.find((item) => item.key === value);
    setTask(value);
    if (selected) setCapability(selected.capability);
  };
  const save = async () => {
    try {
      setPending(true);
      setError(null);
      await onSave({
        scope_type: 'user', scope_id: binding?.scope_id || '', task, capability,
        profile_version_id: profileId, connection_id: connectionId, priority,
        route_policy: routePolicy,
        fallback_profile_version_ids: fallbackProfileId ? [fallbackProfileId] : [],
        is_active: active, reason,
      });
      onClose();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : '默认模型保存失败');
    } finally {
      setPending(false);
    }
  };
  const fallbackMissing = routePolicy === 'pre_submit_fallback' && !fallbackProfileId;

  return <div role="dialog" aria-modal="true" aria-label={binding ? '更换默认模型' : '设置默认模型'} className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/80 p-4 sm:p-8">
    <div className="mx-auto max-w-2xl rounded-xl border border-white/15 bg-slate-900 p-5">
      <header className="flex items-start justify-between">
        <div><h2 className="text-xl font-semibold text-white">{binding ? `更换${taskLabel(binding.task)}默认模型` : '设置默认模型'}</h2><p className="mt-1 text-sm text-slate-400">先选使用场景，系统只显示用途匹配的已发布模型和供应商账号。</p></div>
        <button type="button" aria-label="关闭绑定编辑器" onClick={onClose} className="model-center-quiet"><X className="h-4 w-4" /></button>
      </header>
      {binding && <p className="mt-4 rounded-lg border border-amber-300/20 bg-amber-500/[0.08] px-3 py-2 text-xs text-amber-100">更换后将影响 {binding.affected_recipes} 个生产组合；已生成的资产不受影响。</p>}
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-slate-400">使用场景<select aria-label="使用场景" value={task} onChange={(event) => changeTask(event.target.value)} className="model-center-input mt-1 w-full">{modelTaskOptions.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
        <div className="rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-400">模型用途<span className="mt-1 block text-sm text-white">{capabilityLabels[capability]}</span></div>
        <label className="text-xs text-slate-400">默认模型<select aria-label="默认模型" value={profileId} onChange={(event) => setProfileId(event.target.value)} className="model-center-input mt-1 w-full"><option value="">请选择模型</option>{models.map((model) => <option key={model.profile_version_id} value={model.profile_version_id || ''}>{model.model_name} · {model.api_model_id}</option>)}</select></label>
        <label className="text-xs text-slate-400">供应商账号<select aria-label="供应商账号" value={connectionId} onChange={(event) => setConnectionId(event.target.value)} className="model-center-input mt-1 w-full"><option value="">请选择账号</option>{matchingConnections.map((connection) => <option key={connection.id} value={connection.id}>{connectionDisplayName(connection.name, connection.provider_name)} · {connection.provider_name}</option>)}</select></label>
        <label className="flex items-center gap-2 text-sm text-slate-200 sm:col-span-2"><input aria-label="在生产中启用" type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} />在生产中启用</label>
      </div>
      <details className="mt-3 rounded-lg border border-white/10 px-3 py-2"><summary className="cursor-pointer text-xs text-slate-300">高级路由设置（可选）</summary><div className="mt-3 grid gap-3 sm:grid-cols-2"><label className="text-xs text-slate-400">优先级<input aria-label="优先级" type="number" min={0} max={10000} value={priority} onChange={(event) => setPriority(Number(event.target.value))} className="model-center-input mt-1 w-full" /></label><label className="text-xs text-slate-400">失败处理<select aria-label="路由策略" value={routePolicy} onChange={(event) => setRoutePolicy(event.target.value)} className="model-center-input mt-1 w-full"><option value="single">不自动切换模型</option><option value="pre_submit_fallback">提交前失败时切换备用模型</option><option value="status_poll_only">提交后只轮询状态</option></select></label>{routePolicy === 'pre_submit_fallback' && <label className="text-xs text-slate-400 sm:col-span-2">备用模型<select aria-label="备用模型" value={fallbackProfileId} onChange={(event) => setFallbackProfileId(event.target.value)} className="model-center-input mt-1 w-full"><option value="">请选择同用途的备用模型</option>{fallbackModels.map((model) => <option key={model.profile_version_id} value={model.profile_version_id || ''}>{model.model_name} · {model.api_model_id}</option>)}</select></label>}</div></details>
      <input aria-label="变更说明" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="说明设置或更换原因（至少2字）" className="model-center-input mt-3 w-full" />
      {!matchingConnections.length && <p className="mt-3 text-xs text-amber-200">该模型没有可用的供应商账号，请先到“供应商账号”保存并测试凭证。</p>}
      {error && <p className="mt-3 text-xs text-rose-200">{error}</p>}
      <div className="mt-5 flex justify-end"><button type="button" disabled={pending || !profileId || !connectionId || fallbackMissing || reason.trim().length < 2} onClick={() => void save()} className="model-center-primary">{binding ? '确认更换默认模型' : '保存默认模型'}</button></div>
    </div>
  </div>;
}
