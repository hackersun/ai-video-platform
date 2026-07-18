import Link from 'next/link';
import { AlertCircle, ArrowRight, Combine, ShieldCheck } from 'lucide-react';

import { modelCenterSectionHref, type ModelCenterLocation } from '../navigation';
import { useModelCenterOverview } from '../hooks/use-model-center-overview';
import type { ModelCenterSection } from '../types';

const titles: Record<ModelCenterSection, string> = {
  overview: '全局配置', connections: '模型连接', catalog: '模型详情', bindings: '能力绑定',
  recipes: '组合预设', prompts: '提示词模板', 'test-lab': '测试运行',
};

export function ModelCenterInspector({ section, location }: { section: ModelCenterSection; location: ModelCenterLocation }) {
  const { data, loading } = useModelCenterOverview();
  const blocked = data?.blocking_issues.length || 0;
  return <aside className="hidden min-h-[760px] border-l border-white/10 bg-slate-950/35 p-4 xl:block"><div className="flex items-center justify-between"><h2 className="text-sm font-semibold text-white">{titles[section]}</h2><span className="text-xs text-slate-500">{loading ? '同步中' : '实时状态'}</span></div><section className="mt-4 rounded-lg border border-white/10 bg-slate-900/55 p-4"><div className="flex items-center gap-2 text-sm font-medium text-white"><ShieldCheck className="h-4 w-4 text-emerald-300" />发布前检查</div><p className="mt-2 text-xs leading-5 text-slate-400">配置、连接认证、任务绑定和组合预设均由版本化服务端配置决定。</p><div className={`mt-3 flex items-center gap-2 text-sm ${blocked ? 'text-amber-200' : 'text-emerald-300'}`}>{blocked ? <AlertCircle className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}{blocked ? `${blocked} 项需要处理` : '没有阻塞项'}</div><Link href={modelCenterSectionHref('overview', location)} className="mt-3 inline-flex items-center gap-1 text-xs text-violet-300 hover:text-violet-200">查看检查项 <ArrowRight className="h-3.5 w-3.5" /></Link></section><section className="mt-4 rounded-lg border border-violet-400/20 bg-violet-500/[0.07] p-4"><div className="flex items-center gap-2 text-sm font-medium text-white"><Combine className="h-4 w-4 text-violet-300" />组合生产链</div><p className="mt-2 text-xs leading-5 text-slate-400">文本 → 图像 → 视频 → 语音；每一步从已发布绑定和提示词版本中解析。</p><Link href={modelCenterSectionHref('recipes', location)} className="mt-4 inline-flex w-full items-center justify-center gap-1 rounded-md bg-violet-500 px-3 py-2 text-xs font-medium text-white hover:bg-violet-400">维护组合预设 <ArrowRight className="h-3.5 w-3.5" /></Link></section>{location.returnTo && <Link href={location.returnTo} className="mt-5 block rounded-md border border-white/10 px-3 py-2 text-center text-xs text-slate-300 hover:bg-white/5 hover:text-white">返回原工作台</Link>}</aside>;
}
