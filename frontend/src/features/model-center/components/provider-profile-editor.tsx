'use client';

import { X } from 'lucide-react';
import { useEffect, useState } from 'react';

import { modelCenterApi } from '../api';
import { useModelDrivers } from '../hooks/use-model-drivers';
import { useModelProviders } from '../hooks/use-model-providers';
import type { ModelProfileVersionView } from '../types';

export function ProviderProfileEditor({
  onClose,
  onPublished,
}: {
  onClose: () => void;
  onPublished: () => Promise<void>;
}) {
  const providers = useModelProviders();
  const drivers = useModelDrivers();
  const [providerId, setProviderId] = useState('');
  const [newProvider, setNewProvider] = useState(false);
  const [providerCode, setProviderCode] = useState('');
  const [providerName, setProviderName] = useState('');
  const [providerFamily, setProviderFamily] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [profileKey, setProfileKey] = useState('');
  const [apiModelId, setApiModelId] = useState('');
  const [driverKey, setDriverKey] = useState('');
  const [version, setVersion] = useState<ModelProfileVersionView | null>(null);
  const [validated, setValidated] = useState(false);
  const [reason, setReason] = useState('');
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!providerId && providers.data?.items[0]) setProviderId(providers.data.items[0].id);
    if (!driverKey && drivers.data?.items[0]) setDriverKey(drivers.data.items[0].key);
  }, [driverKey, drivers.data, providerId, providers.data]);
  const selectedDriver = drivers.data?.items.find((driver) => driver.key === driverKey);
  const run = async (operation: () => Promise<void>) => {
    try { setPending(true); setError(null); await operation(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : '模型档案操作失败'); }
    finally { setPending(false); }
  };
  const save = () => run(async () => {
    let selectedProviderId = providerId;
    if (newProvider) {
      const provider = await modelCenterApi.createProvider({ code: providerCode, display_name: providerName, provider_family: providerFamily });
      selectedProviderId = provider.id;
      setProviderId(provider.id);
    }
    const profile = await modelCenterApi.createProfile({ provider_id: selectedProviderId, profile_key: profileKey, display_name: displayName, enabled: true });
    const draft = await modelCenterApi.createProfileVersion(profile.id, {
      expected_revision: profile.revision, api_model_id: apiModelId, driver_key: driverKey,
      capabilities: selectedDriver?.capabilities || [], contract_version: selectedDriver?.contract_version || 'driver-v1',
    });
    setVersion(draft); setMessage(`草稿 v${draft.version} 已保存`);
  });
  const validate = () => version && run(async () => {
    const result = await modelCenterApi.validateProfileVersion(version.id);
    setValidated(result.valid); setMessage(result.valid ? '契约校验通过' : '契约校验未通过');
  });
  const publish = () => version && run(async () => {
    await modelCenterApi.publishProfileVersion(version.id, { expected_revision: version.revision, reason });
    setMessage('模型版本已发布'); await onPublished();
  });
  return <div role="dialog" aria-modal="true" aria-label="新增模型档案" className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/80 p-4 sm:p-8"><div className="mx-auto max-w-3xl rounded-xl border border-white/15 bg-slate-900 p-5 shadow-2xl"><header className="flex items-start justify-between"><div><h2 className="text-xl font-semibold text-white">新增模型档案</h2><p className="mt-1 text-sm text-slate-400">保存草稿 → 本地契约校验 → 发布；不会自动发起付费请求。</p></div><button type="button" aria-label="关闭模型向导" onClick={onClose} className="model-center-quiet"><X className="h-4 w-4" /></button></header>{!version ? <div className="mt-5 space-y-4"><label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={newProvider} onChange={(event) => setNewProvider(event.target.checked)} />新建提供方</label>{newProvider ? <div className="grid gap-2 sm:grid-cols-3"><input aria-label="提供方代码" value={providerCode} onChange={(event) => setProviderCode(event.target.value)} placeholder="提供方代码" className="model-center-input" /><input aria-label="提供方名称" value={providerName} onChange={(event) => setProviderName(event.target.value)} placeholder="提供方名称" className="model-center-input" /><input aria-label="提供方家族" value={providerFamily} onChange={(event) => setProviderFamily(event.target.value)} placeholder="例如 volcano" className="model-center-input" /></div> : <select aria-label="模型提供方" value={providerId} onChange={(event) => setProviderId(event.target.value)} className="model-center-input w-full">{providers.data?.items.map((provider) => <option key={provider.id} value={provider.id}>{provider.display_name}（{provider.code}）</option>)}</select>}<div className="grid gap-2 sm:grid-cols-2"><input aria-label="模型档案名称" value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="使用人员可读名称" className="model-center-input" /><input aria-label="档案键" value={profileKey} onChange={(event) => setProfileKey(event.target.value)} placeholder="稳定档案键" className="model-center-input" /><input aria-label="API 模型标识" value={apiModelId} onChange={(event) => setApiModelId(event.target.value)} placeholder="供应商 API model ID" className="model-center-input" /><select aria-label="模型驱动" value={driverKey} onChange={(event) => setDriverKey(event.target.value)} className="model-center-input">{drivers.data?.items.map((driver) => <option key={driver.key} value={driver.key}>{driver.key}</option>)}</select></div><p className="text-xs text-slate-500">能力：{selectedDriver?.capabilities.join('、') || '请先选择已安装驱动'}</p><button type="button" disabled={pending || !displayName || !profileKey || !apiModelId || !driverKey || (!providerId && !newProvider)} onClick={() => void save()} className="model-center-primary">保存模型草稿</button></div> : <div className="mt-5 space-y-4"><div className="rounded-lg border border-white/10 bg-black/10 p-4 text-sm text-slate-300"><p>{displayName} · v{version.version} · {version.status}</p><p className="mt-1 text-xs text-slate-500">{version.api_model_id} · {version.driver_key}</p></div><button type="button" disabled={pending || validated} onClick={() => void validate()} className="model-center-quiet">运行契约校验</button>{validated && <div className="grid gap-2 sm:grid-cols-[1fr_auto]"><input aria-label="发布说明" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="说明本次发布原因" className="model-center-input" /><button type="button" disabled={pending || reason.trim().length < 2} onClick={() => void publish()} className="model-center-primary">发布模型版本</button></div>}</div>}{message && <p className="mt-4 rounded-md bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">{message}</p>}{error && <p className="mt-4 rounded-md bg-rose-500/10 px-3 py-2 text-xs text-rose-200">{error}</p>}</div></div>;
}
