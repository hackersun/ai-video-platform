'use client';

import Link from 'next/link';
import { Cable, CheckCircle2, FlaskConical, Settings2, X } from 'lucide-react';
import { useState } from 'react';

import { modelCenterApi } from '../api';
import { capabilityLabels, certificationLabel, driverLabel } from '../model-center-labels';
import { modelCenterHref, type ModelCenterLocation } from '../navigation';
import type { ModelCatalogView } from '../types';
import { VideoContractSummary } from './video-contract-summary';

export function ModelCatalogDetail({
  model, location, onClose,
}: {
  model: ModelCatalogView;
  location: ModelCenterLocation;
  onClose: () => void;
}) {
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const capability = model.capabilities[0] || location.capability;
  const canValidate = Boolean(model.profile_version_id);

  const validate = async () => {
    if (!model.profile_version_id) return;
    setPending(true);
    setMessage(null);
    setError(null);
    try {
      const result = await modelCenterApi.validateProfileVersion(model.profile_version_id);
      if (!result.valid) throw new Error('配置检查未通过，请检查 Model ID、用途和适配器。');
      setMessage('配置检查通过，可继续测试供应商账号或设为默认模型。');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '配置检查失败，请检查模型设置后重试。');
    } finally {
      setPending(false);
    }
  };

  return <div role="dialog" aria-modal="true" aria-label={`${model.model_name} 模型详情`} className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/80 p-4 sm:p-8">
    <section className="mx-auto max-w-2xl rounded-xl border border-white/15 bg-slate-900 p-5 shadow-2xl">
      <header className="flex items-start justify-between gap-4"><div><h2 className="text-xl font-semibold text-white">{model.model_name}</h2><p className="mt-1 text-sm text-slate-400">{model.provider_name} · {model.api_model_id}</p></div><button type="button" aria-label="关闭模型详情" onClick={onClose} className="model-center-quiet"><X className="h-4 w-4" /></button></header>
      <dl className="mt-5 grid gap-3 rounded-lg border border-white/10 bg-black/15 p-4 text-sm sm:grid-cols-2"><div><dt>配置版本</dt><dd className="mt-1 text-white">{model.profile_version ? `v${model.profile_version}` : '旧版兼容配置'}</dd></div><div><dt>接口适配器</dt><dd className="mt-1 text-white">{model.driver_key ? driverLabel(model.driver_key) : '旧版适配'}</dd></div><div><dt>验证状态</dt><dd className="mt-1 text-white">{certificationLabel(model.certification_status)}</dd></div><div><dt>模型用途</dt><dd className="mt-1 text-white">{model.capabilities.map((item) => capabilityLabels[item] || item).join('、')}</dd></div></dl>
      <VideoContractSummary model={model} />
      <div className="mt-4 rounded-lg border border-white/10 px-3 py-2 text-xs leading-5 text-slate-400"><p className="font-medium text-slate-200">要变更什么？</p><p>换 API Key：进入“供应商账号”；切换生产使用模型：进入“默认模型”；更换 Model ID 或接口适配器：新增模型配置，验证通过后再切换默认，已发布版本不会被直接覆盖。</p></div>
      {!canValidate && <p className="mt-4 rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-100">这是旧版兼容目录项，需先用“新增模型”建立版本化配置后才能运行检查。</p>}
      <div className="mt-5 grid gap-2 sm:grid-cols-2">
        <button type="button" disabled={!canValidate || pending} onClick={() => void validate()} className="model-center-primary"><CheckCircle2 className="h-4 w-4" />{pending ? '检查中…' : '免费检查配置'}</button>
        <Link href={modelCenterHref({ ...location, section: 'test-lab', capability, level: 'contract', profileVersionId: model.profile_version_id || undefined, runId: undefined })} className={`model-center-quiet ${canValidate ? '' : 'pointer-events-none opacity-40'}`}><FlaskConical className="h-4 w-4" />进入测试实验室</Link>
        <Link href={modelCenterHref({ ...location, section: 'connections', capability, runId: undefined })} className="model-center-quiet"><Cable className="h-4 w-4" />配置供应商账号</Link>
        <Link href={modelCenterHref({ ...location, section: 'bindings', capability, runId: undefined })} className="model-center-quiet"><Settings2 className="h-4 w-4" />设为默认模型</Link>
      </div>
      {message && <p className="mt-4 rounded-md bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">{message}</p>}
      {error && <p className="mt-4 rounded-md bg-rose-500/10 px-3 py-2 text-xs text-rose-200">{error}</p>}
    </section>
  </div>;
}
