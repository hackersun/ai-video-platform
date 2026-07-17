'use client';

import { CheckCircle2, PlayCircle } from 'lucide-react';

import { useModelCatalog } from '../hooks/use-model-catalog';
import type { ModelCapability } from '../types';
import { ModelCenterEmpty, ModelCenterError, ModelCenterLoading } from './model-center-state';

const labels: Record<ModelCapability, string> = {
  text_generation: '文本', vision_analysis: '视觉理解', image_generation: '图像', speech_generation: '语音',
  video_generation: '视频', subtitle_generation: '字幕', media_render: '渲染', object_storage: '存储',
};

export function ModelCenterCatalogPanel({ capability }: { capability?: ModelCapability }) {
  const { data, error, loading, reload } = useModelCatalog();
  if (loading && !data) return <ModelCenterLoading label="正在读取模型目录…" />;
  if (error && !data) return <ModelCenterError error={error} onRetry={() => void reload()} />;
  const models = (data?.items || []).filter((item) => !capability || item.profile.capabilities.includes(capability));
  return (
    <div className="p-4">
      {!models.length ? <ModelCenterEmpty title="没有匹配的模型版本" description="请先在连接中保存凭证，或切换查看全部能力。" /> : <div className="overflow-x-auto rounded-lg border border-white/10"><table className="min-w-full text-left text-sm"><thead className="bg-white/[0.035] text-xs text-slate-500"><tr><th>模型名称</th><th>提供方</th><th>能力</th><th>版本</th><th>认证</th><th className="text-right">操作</th></tr></thead><tbody>{models.map(({ provider, profile, certification_level }) => <tr key={profile.id} className="border-t border-white/[0.07] text-slate-300"><td><p className="font-medium text-white">{profile.api_model_id}</p><p className="mt-0.5 text-[11px] text-slate-500">{profile.driver_key}</p></td><td>{provider.display_name}</td><td><div className="flex flex-wrap gap-1">{profile.capabilities.map((item) => <span key={item} className="rounded border border-violet-400/25 bg-violet-500/10 px-1.5 py-0.5 text-[11px] text-violet-200">{labels[item]}</span>)}</div></td><td>v{profile.version}</td><td><span className={certification_level === 'none' ? 'text-amber-200' : 'inline-flex items-center gap-1 text-emerald-300'}>{certification_level !== 'none' && <CheckCircle2 className="h-3.5 w-3.5" />}{certification_level === 'none' ? '待认证' : certification_level}</span></td><td className="text-right"><span className="inline-flex items-center gap-1 text-xs text-slate-500"><PlayCircle className="h-3.5 w-3.5" />查看</span></td></tr>)}</tbody></table></div>}
      <div className="mt-3 flex justify-between text-xs text-slate-500"><span>共 {models.length}/{data?.meta.total || 0} 个模型版本</span><button type="button" onClick={() => void reload()} className="hover:text-white">刷新目录</button></div>
    </div>
  );
}
