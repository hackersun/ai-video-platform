'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { 
  Home, 
  BookOpen, 
  FileText, 
  Users, 
  Video, 
  Mic, 
  Clapperboard,
  Captions,
  LayoutGrid, 
  ListTodo,
  Cpu,
  BarChart3,
  Settings,
  Sparkles,
  Bot,
  Boxes,
  Images,
  ChevronDown,
  Wand2,
  PlugZap,
  Workflow,
  MonitorPlay
} from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

// 主导航菜单 - 核心功能
const mainMenuItems = [
  { label: '控制台', path: '/dashboard', icon: Home },
  { label: '极速向导', path: '/quick-start', icon: Wand2 },
  { label: '作品', path: '/novels', icon: BookOpen },
  { label: '剧本', path: '/scripts', icon: FileText },
  { label: '角色', path: '/characters', icon: Users },
  { label: '分镜', path: '/storyboards', icon: LayoutGrid },
  { label: '创作工作台', path: '/studio', icon: MonitorPlay },
  { label: '工作流', path: '/workflow', icon: Workflow },
  { label: 'AI制片', path: '/producer', icon: Bot },
  { label: '视频生成', path: '/video-generation', icon: Video },
  { label: '生产适配', path: '/production-adapters', icon: PlugZap },
];

// 工具菜单
const toolMenuItems = [
  { label: '语音合成', path: '/tts', icon: Mic },
  { label: '音视频合成', path: '/synthesis', icon: Video },
  { label: '字幕工作台', path: '/subtitles', icon: Captions },
  { label: '时间线编辑', path: '/timelines', icon: Clapperboard },
  { label: '资产库', path: '/assets', icon: Images },
  { label: '实体库', path: '/entities', icon: Boxes },
  { label: '模板库', path: '/templates', icon: LayoutGrid },
  { label: 'AI模型', path: '/llm-config', icon: Cpu },
  { label: '任务队列', path: '/jobs', icon: ListTodo },
];

// 更多菜单
const moreMenuItems = [
  { label: '数据分析', path: '/analytics', icon: BarChart3 },
  { label: '团队', path: '/teams', icon: Users },
  { label: '设置', path: '/settings', icon: Settings },
];

const mobileMainMenuItems = mainMenuItems.filter((item) =>
  ['/dashboard', '/quick-start', '/novels'].includes(item.path)
);

const mobileMoreMenuItems = [
  ...mainMenuItems.filter((item) =>
    !mobileMainMenuItems.some((mobileItem) => mobileItem.path === item.path)
  ),
  ...moreMenuItems,
];

export function TopNavigation() {
  const pathname = usePathname();
  const router = useRouter();

  const isActive = (path: string) => {
    return pathname === path || pathname.startsWith(path + '/');
  };

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
          {mainMenuItems.map((item) => {
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

          {/* 工具下拉 */}
          <DropdownMenu modal={false}>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label="打开工具菜单"
                title="工具"
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950
                  ${toolMenuItems.some(item => isActive(item.path))
                    ? 'text-white bg-white/10'
                    : 'text-white/60 hover:text-white hover:bg-white/5'
                  }`}
              >
                <Cpu className="w-4 h-4" />
                <span className="hidden md:inline">工具</span>
                <ChevronDown className="w-3 h-3" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              sideOffset={8}
              className="z-[60] w-52 border-white/10 bg-[#0f172a]/98 text-white backdrop-blur-md"
            >
              {toolMenuItems.map((item) => {
                const Icon = item.icon;
                return (
                  <DropdownMenuItem
                    key={item.path}
                    className={`flex items-center gap-2 px-3 py-2 text-sm transition-colors focus-visible:bg-white/10 focus-visible:text-white
                      ${isActive(item.path)
                        ? 'text-white bg-white/10'
                        : 'text-white/70 hover:text-white hover:bg-white/5'
                      }`}
                    onSelect={() => router.push(item.path)}
                  >
                    <>
                      <Icon className="w-4 h-4" />
                      {item.label}
                    </>
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>

          {/* 更多下拉 */}
          <DropdownMenu modal={false}>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label="打开更多菜单"
                title="更多"
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950
                  ${moreMenuItems.some(item => isActive(item.path))
                    ? 'text-white bg-white/10'
                    : 'text-white/60 hover:text-white hover:bg-white/5'
                  }`}
              >
                <Settings className="w-4 h-4" />
                <span className="hidden md:inline">更多</span>
                <ChevronDown className="w-3 h-3" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              sideOffset={8}
              className="z-[60] w-52 border-white/10 bg-[#0f172a]/98 text-white backdrop-blur-md"
            >
              {moreMenuItems.map((item) => {
                const Icon = item.icon;
                return (
                  <DropdownMenuItem
                    key={item.path}
                    className={`flex items-center gap-2 px-3 py-2 text-sm transition-colors focus-visible:bg-white/10 focus-visible:text-white
                      ${isActive(item.path)
                        ? 'text-white bg-white/10'
                        : 'text-white/70 hover:text-white hover:bg-white/5'
                      }`}
                    onSelect={() => router.push(item.path)}
                  >
                    <>
                      <Icon className="w-4 h-4" />
                      {item.label}
                    </>
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </nav>

        <nav className="flex min-w-0 flex-1 items-center justify-end gap-1 md:hidden">
          {mobileMainMenuItems.map((item) => {
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
                aria-label="工具"
                title="工具"
                className={`flex h-9 shrink-0 items-center gap-1 rounded-lg px-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950
                  ${toolMenuItems.some(item => isActive(item.path))
                    ? 'bg-white/10 text-white'
                    : 'text-white/60 hover:bg-white/5 hover:text-white'
                  }`}
              >
                <Cpu className="h-4 w-4" />
                <ChevronDown className="h-3 w-3" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              sideOffset={8}
              className="z-[60] w-52 max-w-[calc(100vw-1rem)] border-white/10 bg-[#0f172a]/98 text-white backdrop-blur-md"
            >
              {toolMenuItems.map((item) => {
                const Icon = item.icon;
                return (
                  <DropdownMenuItem
                    key={item.path}
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
              })}
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu modal={false}>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label="更多"
                title="更多"
                className={`flex h-9 shrink-0 items-center gap-1 rounded-lg px-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950
                  ${mobileMoreMenuItems.some(item => isActive(item.path))
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
              {mobileMoreMenuItems.map((item) => {
                const Icon = item.icon;
                return (
                  <DropdownMenuItem
                    key={item.path}
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
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </nav>
      </div>
    </header>
  );
}
