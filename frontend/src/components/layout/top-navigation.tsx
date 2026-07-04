'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { 
  BookOpen, 
  Video, 
  Mic, 
  Cpu,
  Settings,
  Sparkles,
  Bot,
  Images,
  ChevronDown,
  Wand2,
  Workflow,
  MonitorPlay,
} from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

const primaryNav = [
  { href: '/studio', label: '工作室' },
  { href: '/quick-start', label: '快速开始' },
  { href: '/novels', label: '小说' },
  { href: '/assets', label: '资产' },
];

const expertNav = [
  { href: '/story-bibles', label: 'Story Bible' },
  { href: '/producer', label: 'AI 制片' },
  { href: '/workflow', label: '工作流' },
  { href: '/video-generation', label: '视频生成' },
  { href: '/tts', label: '配音' },
  { href: '/synthesis', label: '合成' },
  { href: '/llm-config', label: '模型配置' },
];

type NavigationItem = {
  label: string;
  path: string;
  icon: typeof BookOpen;
};

const iconByHref: Record<string, typeof BookOpen> = {
  '/studio': MonitorPlay,
  '/quick-start': Wand2,
  '/novels': BookOpen,
  '/assets': Images,
  '/story-bibles': Sparkles,
  '/producer': Bot,
  '/workflow': Workflow,
  '/video-generation': Video,
  '/tts': Mic,
  '/synthesis': Video,
  '/llm-config': Cpu,
};

const primaryNavItems = primaryNav.map((item) => ({
  label: item.label,
  path: item.href,
  icon: iconByHref[item.href],
})) satisfies NavigationItem[];

const expertNavItems = expertNav.map((item) => ({
  label: item.label,
  path: item.href,
  icon: iconByHref[item.href],
})) satisfies NavigationItem[];

export function TopNavigation() {
  const pathname = usePathname();
  const router = useRouter();

  const isActive = (path: string) => {
    return pathname === path || pathname.startsWith(path + '/');
  };

  const expertActive = expertNavItems.some((item) => isActive(item.path));

  const renderDropdownItems = (items: NavigationItem[]) =>
    items.map((item) => {
      const Icon = item.icon;
      return (
        <DropdownMenuItem
          key={`${item.label}-${item.path}`}
          className={`flex items-center gap-2 px-3 py-2 text-sm transition-colors focus-visible:bg-white/10 focus-visible:text-white
            ${isActive(item.path)
              ? 'text-white bg-white/10'
              : 'text-white/70 hover:text-white hover:bg-white/5'
            }`}
          onSelect={() => router.push(item.path)}
        >
          <Icon className="w-4 h-4" />
          {item.label}
        </DropdownMenuItem>
      );
    });

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-16 bg-[#0f172a]/95 backdrop-blur-md border-b border-white/10">
      <div className="max-w-7xl mx-auto px-4 h-full flex items-center justify-between gap-3 min-w-0">
        {/* Logo */}
        <Link href="/dashboard" className="flex items-center gap-2 flex-shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <span className="text-lg font-bold text-white hidden sm:block">AI视频平台</span>
        </Link>

        {/* Navigation */}
        <nav className="hidden min-w-0 flex-1 items-center justify-end gap-1 md:flex">
          {/* 主导航 */}
          {primaryNavItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                href={item.path}
                aria-label={item.label}
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950
                  ${isActive(item.path)
                    ? 'text-white bg-white/10' 
                    : 'text-white/60 hover:text-white hover:bg-white/5'
                  }`}
              >
                <Icon className="w-4 h-4" />
                <span className="hidden md:inline">{item.label}</span>
              </Link>
            );
          })}

          <DropdownMenu modal={false}>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label="专家工具"
                title="专家工具"
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950
                  ${expertActive
                    ? 'text-white bg-white/10'
                    : 'text-white/60 hover:text-white hover:bg-white/5'
                  }`}
              >
                <Settings className="w-4 h-4" />
                <span className="hidden md:inline">专家工具</span>
                <ChevronDown className="w-3 h-3" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              sideOffset={8}
              className="z-[60] w-52 border-white/10 bg-[#0f172a]/98 text-white backdrop-blur-md"
            >
              {renderDropdownItems(expertNavItems)}
            </DropdownMenuContent>
          </DropdownMenu>
        </nav>

        <nav className="flex min-w-0 flex-1 items-center justify-end gap-1 md:hidden">
          {primaryNavItems.slice(0, 4).map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                href={item.path}
                aria-label={item.label}
                title={item.label}
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950
                  ${isActive(item.path)
                    ? 'bg-white/10 text-white'
                    : 'text-white/60 hover:bg-white/5 hover:text-white'
                  }`}
              >
                <Icon className="h-4 w-4" />
              </Link>
            );
          })}

          <DropdownMenu modal={false}>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label="更多专家工具"
                title="更多"
                className={`flex h-9 shrink-0 items-center gap-1 rounded-lg px-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950
                  ${expertActive
                    ? 'bg-white/10 text-white'
                    : 'text-white/60 hover:bg-white/5 hover:text-white'
                  }`}
              >
                <Settings className="h-4 w-4" />
                <ChevronDown className="h-3 w-3" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              sideOffset={8}
              className="z-[60] w-52 max-w-[calc(100vw-1rem)] border-white/10 bg-[#0f172a]/98 text-white backdrop-blur-md"
            >
              {renderDropdownItems(expertNavItems)}
            </DropdownMenuContent>
          </DropdownMenu>
        </nav>
      </div>
    </header>
  );
}
