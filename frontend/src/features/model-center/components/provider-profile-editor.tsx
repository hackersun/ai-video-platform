'use client';

import Link from 'next/link';
import { X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { modelCenterApi } from '../api';
import { useModelDrivers } from '../hooks/use-model-drivers';
import { useModelProviders } from '../hooks/use-model-providers';
import { capabilityLabels, driverLabel, profileKeyFromModelId } from '../model-center-labels';
import { modelCenterSectionHref, type ModelCenterLocation } from '../navigation';
import type { ModelCapability, ModelProfileVersionView } from '../types';
import { emptyVideoCapabilityDraft, VideoCapabilityEditor, videoCapabilityPayload } from './video-capability-editor';

type ProviderProfileEditorProps = {
  location: ModelCenterLocation;
  onClose: () => void;
  onPublished: () => Promise<void>;
};

export function ProviderProfileEditor({ location, onClose, onPublished }: ProviderProfileEditorProps) {
  const providers = useModelProviders();
  const drivers = useModelDrivers();
  const [providerId, setProviderId] = useState('');
  const [newProvider, setNewProvider] = useState(false);
  const [providerCode, setProviderCode] = useState('');
  const [providerName, setProviderName] = useState('');
  const [providerFamily, setProviderFamily] = useState('');
  const [capability, setCapability] = useState<ModelCapability>(location.capability || 'text_generation');
  const [displayName, setDisplayName] = useState('');
  const [profileKey, setProfileKey] = useState('');
  const [profileKeyTouched, setProfileKeyTouched] = useState(false);
  const [apiModelId, setApiModelId] = useState('');
  const [driverKey, setDriverKey] = useState('');
  const [version, setVersion] = useState<ModelProfileVersionView | null>(null);
  const [validated, setValidated] = useState(false);
  const [published, setPublished] = useState(false);
  const [reason, setReason] = useState('');
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [videoCapability, setVideoCapability] = useState(emptyVideoCapabilityDraft);

  const compatibleDrivers = useMemo(
    () => drivers.data?.items.filter((driver) => driver.capabilities.includes(capability)) || [],
    [capability, drivers.data],
  );
  const selectedDriver = compatibleDrivers.find((driver) => driver.key === driverKey);

  useEffect(() => {
    if (!providerId && providers.data?.items[0]) setProviderId(providers.data.items[0].id);
  }, [providerId, providers.data]);
  useEffect(() => {
    if (!compatibleDrivers.some((driver) => driver.key === driverKey)) {
      setDriverKey(compatibleDrivers[0]?.key || '');
    }
  }, [compatibleDrivers, driverKey]);

  const run = async (operation: () => Promise<void>) => {
    try { setPending(true); setError(null); await operation(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : '模型操作失败'); }
    finally { setPending(false); }
  };
  const updateModelId = (value: string) => {
    setApiModelId(value);
    if (!profileKeyTouched) setProfileKey(profileKeyFromModelId(value));
  };
  const save = () => run(async () => {
    let selectedProviderId = providerId;
    if (newProvider) {
      const provider = await modelCenterApi.createProvider({
        code: providerCode, display_name: providerName, provider_family: providerFamily,
      });
      selectedProviderId = provider.id;
      setProviderId(provider.id);
    }
    const profile = await modelCenterApi.createProfile({
      provider_id: selectedProviderId, profile_key: profileKey, display_name: displayName, enabled: true,
    });
    const videoContract = capability === 'video_generation' ? videoCapabilityPayload(videoCapability) : null;
    const draft = await modelCenterApi.createProfileVersion(profile.id, {
      expected_revision: profile.revision, api_model_id: apiModelId, driver_key: driverKey,
      capabilities: [capability], input_contract: videoContract?.input_contract,
      limits: videoContract?.limits,
      contract_version: videoContract?.contract_version || selectedDriver?.contract_version || 'driver-v1',
    });
    setVersion(draft);
    setMessage(`草稿 v${draft.version} 已保存`);
  });
  const validate = () => version && run(async () => {
    const result = await modelCenterApi.validateProfileVersion(version.id);
    setValidated(result.valid);
    if (result.valid) {
      setMessage('配置校验通过，可以发布。');
      return;
    }
    const details = result.errors.map((item) => String(item.message || '')).filter(Boolean).join('；');
    setError(`配置校验未通过：${details || '请检查 Model ID、适配器和模型能力上限。'}`);
  });
  const publish = () => version && run(async () => {
    await modelCenterApi.publishProfileVersion(version.id, { expected_revision: version.revision, reason });
    setPublished(true);
    setMessage('模型已发布。下一步请配置供应商账号并设为默认模型。');
    await onPublished();
  });

  const providerFieldsReady = !newProvider || Boolean(providerCode && providerName && providerFamily);
  const draftReady = Boolean(providerId && displayName && profileKey && apiModelId && driverKey && providerFieldsReady);

  return <div role="dialog" aria-modal="true" aria-label="新增模型" className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/80 p-4 sm:p-8">
    <section className="mx-auto max-w-3xl rounded-xl border border-white/15 bg-slate-900 p-5 shadow-2xl">
      <header className="flex items-start justify-between gap-4"><div><h2 className="text-xl font-semibold text-white">新增模型</h2><p className="mt-1 text-sm text-slate-400">先建立模型配置并免费校验；只有实模测试才会调用供应商。</p></div><button type="button" aria-label="关闭模型向导" onClick={onClose} className="model-center-quiet"><X className="h-4 w-4" /></button></header>
      {!version ? <div className="mt-5 space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-slate-400">模型用途<select aria-label="模型用途" value={capability} onChange={(event) => setCapability(event.target.value as ModelCapability)} className="model-center-input mt-1 w-full">{Object.entries(capabilityLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          <label className="text-xs text-slate-400">供应商<select aria-label="模型提供方" disabled={newProvider} value={providerId} onChange={(event) => setProviderId(event.target.value)} className="model-center-input mt-1 w-full">{providers.data?.items.map((provider) => <option key={provider.id} value={provider.id}>{provider.display_name}（{provider.code}）</option>)}</select></label>
          <label className="text-xs text-slate-400">模型显示名称<input aria-label="模型显示名称" value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="例如：Qwen Plus" className="model-center-input mt-1 w-full" /></label>
          <label className="text-xs text-slate-400">供应商 Model ID<input aria-label="供应商 Model ID" value={apiModelId} onChange={(event) => updateModelId(event.target.value)} placeholder="复制供应商控制台中的模型 ID" className="model-center-input mt-1 w-full" /></label>
          <label className="text-xs text-slate-400 sm:col-span-2">兼容适配器<select aria-label="兼容适配器" value={driverKey} onChange={(event) => setDriverKey(event.target.value)} className="model-center-input mt-1 w-full"><option value="">请选择与用途匹配的接口</option>{compatibleDrivers.map((driver) => <option key={driver.key} value={driver.key}>{driverLabel(driver.key)} · {driver.key}</option>)}</select></label>
        </div>
        {capability === 'video_generation' && <VideoCapabilityEditor value={videoCapability} onChange={setVideoCapability} />}
        <p className="text-xs text-slate-500">配置标识会根据 Model ID 自动生成；一般不需要手工修改。</p>
        {!compatibleDrivers.length && !drivers.loading && <p className="rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-100">当前没有支持“{capabilityLabels[capability]}”的适配器，需要先由开发人员安装对应接口适配器。</p>}
        <details className="rounded-lg border border-white/10 px-3 py-2"><summary className="cursor-pointer text-xs text-slate-300">高级标识与新供应商</summary><div className="mt-3 space-y-3"><label className="block text-xs text-slate-400">配置标识<input aria-label="配置标识" value={profileKey} onChange={(event) => { setProfileKeyTouched(true); setProfileKey(event.target.value); }} className="model-center-input mt-1 w-full" /></label><label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={newProvider} onChange={(event) => setNewProvider(event.target.checked)} />供应商不在列表中，新建供应商</label>{newProvider && <div className="grid gap-2 sm:grid-cols-3"><input aria-label="提供方代码" value={providerCode} onChange={(event) => setProviderCode(event.target.value)} placeholder="唯一代码" className="model-center-input" /><input aria-label="提供方名称" value={providerName} onChange={(event) => setProviderName(event.target.value)} placeholder="显示名称" className="model-center-input" /><input aria-label="提供方家族" value={providerFamily} onChange={(event) => setProviderFamily(event.target.value)} placeholder="接口家族" className="model-center-input" /></div>}</div></details>
        <div className="flex justify-end"><button type="button" disabled={pending || !draftReady} onClick={() => void save()} className="model-center-primary">保存模型草稿</button></div>
      </div> : <div className="mt-5 space-y-4">
        <div className="rounded-lg border border-white/10 bg-black/10 p-4 text-sm text-slate-300"><p>{displayName} · v{version.version} · {version.status}</p><p className="mt-1 text-xs text-slate-500">{version.api_model_id} · {driverLabel(version.driver_key)}</p></div>
        {!published && <button type="button" disabled={pending || validated} onClick={() => void validate()} className="model-center-quiet">运行免费配置校验</button>}
        {validated && !published && <div className="grid gap-2 sm:grid-cols-[1fr_auto]"><input aria-label="发布说明" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="例如：新增文本模型" className="model-center-input" /><button type="button" disabled={pending || reason.trim().length < 2} onClick={() => void publish()} className="model-center-primary">发布模型</button></div>}
        {published && <div className="flex flex-wrap gap-2"><Link onClick={onClose} href={modelCenterSectionHref('connections', { ...location, capability })} className="model-center-quiet">配置供应商账号</Link><Link onClick={onClose} href={modelCenterSectionHref('bindings', { ...location, capability })} className="model-center-primary">设为默认模型</Link></div>}
      </div>}
      {message && <p className="mt-4 rounded-md bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">{message}</p>}
      {error && <p className="mt-4 rounded-md bg-rose-500/10 px-3 py-2 text-xs text-rose-200">{error}</p>}
    </section>
  </div>;
}
