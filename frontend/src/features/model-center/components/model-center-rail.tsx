import Link from 'next/link';
import { AudioLines, BookText, Boxes, Cable, Clapperboard, Image as ImageIcon, PanelLeftClose, PlugZap, Sparkles, Workflow } from 'lucide-react';

import { modelCenterSectionHref, type ModelCenterLocation } from '../navigation';
import type { ModelCenterSection } from '../types';

type RailItem = { section: ModelCenterSection; label: string; description: string; icon: typeof BookText };

const items: RailItem[] = [
  { section: 'overview', label: '全局概览', description: '阻塞项与就绪度', icon: Boxes },
  { section: 'connections', label: '供应商账号', description: 'API 凭证与可用性', icon: Cable },
  { section: 'catalog', label: '模型目录', description: '文本、图像、视频、语音', icon: Clapperboard },
  { section: 'bindings', label: '默认模型', description: '生产任务使用哪个模型', icon: Workflow },
  { section: 'recipes', label: '组合预设', description: '生产方案版本', icon: PlugZap },
  { section: 'prompts', label: '提示词模板', description: '生产环节实际使用', icon: BookText },
  { section: 'test-lab', label: '测试实验室', description: '认证运行与证据', icon: Sparkles },
];

const capabilityItems = [
  { label: '文本模型', capability: 'text_generation' as const, icon: BookText },
  { label: '图像模型', capability: 'image_generation' as const, icon: ImageIcon },
  { label: '视频模型', capability: 'video_generation' as const, icon: Clapperboard },
  { label: '语音模型', capability: 'speech_generation' as const, icon: AudioLines },
];

interface ModelCenterRailProps {
  activeSection: ModelCenterSection;
  location: ModelCenterLocation;
}

export function ModelCenterCompactNav({ activeSection, location }: ModelCenterRailProps) {
  return <nav aria-label="模型中心功能" className="-mx-1 mb-5 flex gap-2 overflow-x-auto px-1 pb-1 xl:hidden">
    {items.map((item) => <Link key={item.section} href={modelCenterSectionHref(item.section, location)}
      className={`shrink-0 rounded-md border px-3 py-2 text-xs ${activeSection === item.section
        ? 'border-violet-400/60 bg-violet-500/15 text-violet-100' : 'border-white/10 text-slate-400'}`}>{item.label}</Link>)}
  </nav>;
}

export function ModelCenterRail({ activeSection, location }: ModelCenterRailProps) {
  return (
    <aside className="hidden min-h-[760px] border-r border-white/10 bg-slate-950/35 p-3 xl:block">
      <div className="mb-4 flex items-center justify-between border-b border-white/10 px-2 pb-3">
        <span className="text-sm font-semibold text-white">模型中心</span>
        <PanelLeftClose className="h-4 w-4 text-slate-500" />
      </div>
      <nav aria-label="模型中心功能" className="space-y-1">
        {items.map((item) => {
          const Icon = item.icon;
          const active = activeSection === item.section;
          return (
            <Link
              key={item.section}
              href={modelCenterSectionHref(item.section, location)}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors ${active
                ? 'border border-violet-400/60 bg-violet-500/15 text-white shadow-[inset_0_0_18px_rgba(124,58,237,0.15)]'
                : 'border border-transparent text-slate-300 hover:bg-white/5 hover:text-white'}`}
            >
              <Icon className={`h-5 w-5 ${active ? 'text-violet-300' : 'text-slate-400'}`} />
              <span className="min-w-0">
                <span className="block text-sm font-medium">{item.label}</span>
                <span className="block truncate text-[11px] text-slate-500">{item.description}</span>
              </span>
            </Link>
          );
        })}
      </nav>
      <div className="mt-8 border-t border-white/10 pt-4">
        <p className="px-2 text-[11px] font-medium tracking-wide text-slate-500">按能力查看</p>
        <div className="mt-2 space-y-1">
          {capabilityItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.capability} href={modelCenterSectionHref('catalog', { ...location, capability: item.capability })}
                className="flex items-center gap-2 rounded-md px-3 py-2 text-xs text-slate-400 hover:bg-white/5 hover:text-white">
                <Icon className="h-4 w-4" />{item.label}
              </Link>
            );
          })}
        </div>
      </div>
    </aside>
  );
}
