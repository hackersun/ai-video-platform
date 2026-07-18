'use client';

import { CheckCircle2, PlayCircle } from 'lucide-react';

import { usePagedModelCatalog } from '../hooks/use-paged-model-catalog';
import { useModelProviders } from '../hooks/use-model-providers';
import type { ModelCapability } from '../types';
import { ModelCenterEmpty, ModelCenterError, ModelCenterLoading } from './model-center-state';
import { ModelCenterPagination } from './model-center-pagination';
import { ProviderModelLabel } from './provider-model-label';

const labels: Record<ModelCapability, string> = {
  text_generation: '文本', vision_analysis: '视觉理解', image_generation: '图像', speech_generation: '语音',
  video_generation: '视频', subtitle_generation: '字幕', media_render: '渲染', object_storage: '存储',
};

export function ModelCenterCatalogPanel({ capability }: { capability?: ModelCapability }) {
  const catalog = usePagedModelCatalog(capability);
  const providers = useModelProviders();
  const { data, error, loading, reload } = catalog;
  if (loading && !data) return <ModelCenterLoading label="正在读取模型目录…" />;
  if (error && !data) return <ModelCenterError error={error} onRetry={() => void reload()} />;
  const models = data?.items || [];
  return (
    <div className="p-4">
      <div className="mb-4 grid gap-2 md:grid-cols-[minmax(14rem,1fr)_12rem_11rem]"><input aria-label="搜索模型" value={catalog.query} onChange={(event) => catalog.setQuery(event.target.value)} placeholder="搜索模型名、API 标识或提供方" className="model-center-input" /><select aria-label="提供方筛选" value={catalog.providerId} onChange={(event) => catalog.setProviderId(event.target.value)} className="model-center-input"><option value="">全部提供方</option>{providers.data?.items.map((provider) => <option key={provider.id} value={provider.id}>{provider.display_name}</option>)}</select><select aria-label="认证状态" value={catalog.status} onChange={(event) => catalog.setStatus(event.target.value)} className="model-center-input"><option value="">全部认证状态</option><option value="unverified">待认证</option><option value="connection_verified">连接已认证</option><option value="contract_verified">契约已认证</option><option value="live_verified">实模已认证</option></select></div>
      {!models.length ? <ModelCenterEmpty title="没有匹配的模型版本" description="请先在连接中保存凭证，或切换查看全部能力。" /> : <div className="overflow-x-auto rounded-lg border border-white/10"><table className="min-w-full text-left text-sm"><thead className="bg-white/[0.035] text-xs text-slate-500"><tr><th>模型名称</th><th>提供方</th><th>能力</th><th>配置版本</th><th>认证</th><th className="text-right">操作</th></tr></thead><tbody>{models.map((model) => <tr key={`${model.profile_version_id || model.legacy_model_id || model.api_model_id}-${model.provider_id}`} className="border-t border-white/[0.07] text-slate-300"><td><p className="font-medium text-white">{model.model_name}</p><p className="mt-0.5 text-[11px] text-slate-500">{model.api_model_id}</p></td><td><ProviderModelLabel providerName={model.provider_name} providerCode={model.provider_code} /></td><td><div className="flex flex-wrap gap-1">{model.capabilities.map((item) => <span key={item} className="rounded border border-violet-400/25 bg-violet-500/10 px-1.5 py-0.5 text-[11px] text-violet-200">{labels[item]}</span>)}</div></td><td><span className="block">{model.profile_version ? `v${model.profile_version}` : '兼容配置'}</span><span className="text-[11px] text-slate-500">{model.driver_key || '旧版适配'}</span></td><td><span className={model.certification_status === 'unverified' ? 'text-amber-200' : 'inline-flex items-center gap-1 text-emerald-300'}>{model.certification_status !== 'unverified' && <CheckCircle2 className="h-3.5 w-3.5" />}{model.certification_status === 'unverified' ? '待认证' : model.certification_status}</span></td><td className="text-right"><span className="inline-flex items-center gap-1 text-xs text-slate-500"><PlayCircle className="h-3.5 w-3.5" />查看</span></td></tr>)}</tbody></table></div>}
      {!models.length ? null : <div className="mt-3"><ModelCenterPagination page={data?.meta.page || catalog.page} pageSize={data?.meta.page_size || catalog.pageSize} total={data?.meta.total || 0} onPageChange={catalog.setPage} /></div>}
    </div>
  );
}
