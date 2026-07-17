'use client';

import Link from 'next/link';
import { Plus, RefreshCw, SlidersHorizontal } from 'lucide-react';
import { useSearchParams } from 'next/navigation';

import { modelCenterHref, modelCenterSectionHref, readModelCenterLocation } from '../navigation';
import { ModelCenterCatalogPanel } from './model-center-catalog-panel';
import { ModelCenterConnectionsPanel } from './model-center-connections-panel';
import { ModelCenterInspector } from './model-center-inspector';
import { ModelCenterManagementPanel } from './model-center-management-panel';
import { ModelCenterOverviewPanel } from './model-center-overview-panel';
import { ModelCenterCompactNav, ModelCenterRail } from './model-center-rail';

const headingBySection = {
  overview: ['模型中心', '统一管理已接入模型、连接、任务组合和提示词版本。'],
  connections: ['模型连接', '保存脱敏凭证，完成认证后再投入生产使用。'],
  catalog: ['模型目录', '按能力查看已接入模型版本和认证等级。'],
  bindings: ['能力绑定', '将业务任务稳定路由到已认证模型版本。'],
  recipes: ['组合预设', '将文本、图像、视频、语音的生产组合版本化。'],
  prompts: ['提示词模板', '维护可追溯的提示词版本与发布状态。'],
  'test-lab': ['测试实验室', '查看连接认证运行和已脱敏测试证据。'],
} as const;

export function ModelCenterShell() {
  const searchParams = useSearchParams();
  const location = readModelCenterLocation(searchParams);
  const [title, description] = headingBySection[location.section];
  const currentHref = modelCenterHref(location);
  const content = location.section === 'overview' ? <ModelCenterOverviewPanel location={location} />
    : location.section === 'connections' ? <ModelCenterConnectionsPanel location={location} />
      : location.section === 'catalog' ? <ModelCenterCatalogPanel capability={location.capability} />
        : <ModelCenterManagementPanel section={location.section} runId={location.runId} />;

  return <div className="model-center-shell -mx-4 -mt-8 min-h-[calc(100vh-4rem)] border-y border-white/10 sm:-mx-8"><ModelCenterRail activeSection={location.section} location={location} /><main className="min-w-0 p-5 lg:p-6"><ModelCenterCompactNav activeSection={location.section} location={location} /><header className="mb-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div><h1 className="text-2xl font-bold tracking-tight text-white">{title}</h1><p className="mt-1 text-sm text-slate-400">{description}</p></div><div className="flex items-center gap-2"><Link href={currentHref} className="model-center-quiet"><RefreshCw className="h-4 w-4" />刷新</Link><Link href={modelCenterSectionHref('connections', location)} className="model-center-primary"><Plus className="h-4 w-4" />新增模型</Link></div></header><div className="mb-4 flex flex-wrap items-center gap-2 border-b border-white/10 pb-4"><Link href={modelCenterSectionHref('catalog', { ...location, capability: undefined })} className={`model-center-filter ${!location.capability ? 'model-center-filter-active' : ''}`}>全部模型</Link>{[['文本', 'text_generation'], ['图像', 'image_generation'], ['视频', 'video_generation'], ['语音', 'speech_generation']].map(([label, capability]) => <Link key={capability} href={modelCenterSectionHref('catalog', { ...location, capability: capability as never })} className={`model-center-filter ${location.capability === capability ? 'model-center-filter-active' : ''}`}>{label}</Link>)}<span className="ml-auto hidden items-center gap-1 text-xs text-slate-500 lg:inline-flex"><SlidersHorizontal className="h-3.5 w-3.5" />已应用服务端配置</span></div><section className="overflow-hidden rounded-xl border border-white/10 bg-slate-950/25 shadow-[0_16px_48px_rgba(0,0,0,0.12)]">{content}</section></main><ModelCenterInspector section={location.section} location={location} /></div>;
}
