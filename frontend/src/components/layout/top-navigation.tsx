'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { 
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
  MonitorPlay,
  MessageSquare
} from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

type NavigationItem = {
  label: string;
  path: string;
  icon: typeof BookOpen;
};

type NavigationGroup = {
  label: string;
  ariaLabel: string;
  icon: typeof BookOpen;
  items: NavigationItem[];
};

// 高频入口：按个人/小团队最快创作路径保留在顶部
const mainMenuItems = [
  { label: '工作台', path: '/studio', icon: MonitorPlay },
  { label: '连续动漫向导', path: '/quick-start', icon: Wand2 },
  { label: '作品', path: '/novels', icon: BookOpen },
] satisfies NavigationItem[];

const contentMenuItems = [
  { label: '小说/作品', path: '/novels', icon: BookOpen },
  { label: '章节', path: '/novels', icon: FileText },
  { label: '剧本', path: '/scripts', icon: FileText },
  { label: '分镜', path: '/storyboards', icon: LayoutGrid },
  { label: '镜头', path: '/shots', icon: Clapperboard },
] satisfies NavigationItem[];

const assetMenuItems = [
  { label: '动漫设定本', path: '/story-bibles', icon: Sparkles },
  { label: '角色', path: '/characters', icon: Users },
  { label: '实体库', path: '/entities', icon: Boxes },
  { label: '资产库', path: '/assets', icon: Images },
  { label: '模板库', path: '/templates', icon: LayoutGrid },
] satisfies NavigationItem[];

const productionMenuItems = [
  { label: '制作流程', path: '/workflow', icon: Workflow },
  { label: '一键成片', path: '/producer', icon: Bot },
  { label: '视频生成', path: '/video-generation', icon: Video },
  { label: '语音合成', path: '/tts', icon: Mic },
  { label: '字幕工作台', path: '/subtitles', icon: Captions },
  { label: '时间线编辑', path: '/timelines', icon: Clapperboard },
  { label: '音视频合成', path: '/synthesis', icon: Video },
  { label: '任务队列', path: '/jobs', icon: ListTodo },
] satisfies NavigationItem[];

const configMenuItems = [
  { label: 'AI提示词模板', path: '/prompt-skills', icon: MessageSquare },
  { label: '模型与密钥', path: '/llm-config', icon: Cpu },
  { label: '生产适配', path: '/production-adapters', icon: PlugZap },
  { label: '设置', path: '/settings', icon: Settings },
  { label: '数据分析', path: '/analytics', icon: BarChart3 },
] satisfies NavigationItem[];

const groupedMenuItems: NavigationGroup[] = [
  { label: '故事创作', ariaLabel: '打开故事创作菜单', icon: FileText, items: contentMenuItems },
  { label: '角色与世界观', ariaLabel: '打开角色与世界观菜单', icon: Boxes, items: assetMenuItems },
  { label: '生成与成片', ariaLabel: '打开生成与成片菜单', icon: Video, items: productionMenuItems },
  { label: '高级工具', ariaLabel: '打开高级工具菜单', icon: Cpu, items: configMenuItems },
];

const teamMenuItem = { label: '团队', path: '/teams', icon: Users } satisfies NavigationItem;

const mobileMainMenuItems = mainMenuItems.filter((item) =>
  ['/studio', '/quick-start', '/novels'].includes(item.path)
);

const mobileMoreMenuItems = [
  ...groupedMenuItems.flatMap((group) => group.items),
  teamMenuItem,
];

const EXPERT_NAV_KEY = 'ai-video-platform:expert-nav';

export function TopNavigation() {
  const pathname = usePathname();
  const router = useRouter();
  const [expertMode, setExpertMode] = useState(false);

  const isActive = (path: string) => {
    return pathname === path || pathname.startsWith(path + '/');
  };

  const isGroupActive = (group: NavigationGroup) => group.items.some((item) => isActive(item.path));
  const isExpertRoute = useMemo(
    () => groupedMenuItems.some((group) => isGroupActive(group)) || isActive(teamMenuItem.path),
    [pathname]
  );
  const showExpertNav = expertMode || isExpertRoute;

  useEffect(() => {
    setExpertMode(localStorage.getItem(EXPERT_NAV_KEY) === '1');
  }, []);

  const toggleExpertMode = () => {
    setExpertMode((current) => {
      const next = !current;
      localStorage.setItem(EXPERT_NAV_KEY, next ? '1' : '0');
      return next;
    });
  };

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

          {showExpertNav && groupedMenuItems.map((group) => {
            const Icon = group.icon;
            return (
              <DropdownMenu key={group.label} modal={false}>
                <DropdownMenuTrigger asChild>
                  <button
                    type="button"
                    aria-label={group.ariaLabel}
                    title={group.label}
                    className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950
                      ${isGroupActive(group)
                        ? 'text-white bg-white/10'
                        : 'text-white/60 hover:text-white hover:bg-white/5'
                      }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="hidden md:inline">{group.label}</span>
                    <ChevronDown className="w-3 h-3" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  align="end"
                  sideOffset={8}
                  className="z-[60] w-52 border-white/10 bg-[#0f172a]/98 text-white backdrop-blur-md"
                >
                  {renderDropdownItems(group.items)}
                </DropdownMenuContent>
              </DropdownMenu>
            );
          })}

          {showExpertNav && (
            <Link
              href={teamMenuItem.path}
              aria-label={teamMenuItem.label}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950
                ${isActive(teamMenuItem.path)
                  ? 'text-white bg-white/10'
                  : 'text-white/60 hover:text-white hover:bg-white/5'
                }`}
            >
              <Users className="w-4 h-4" />
              <span className="hidden md:inline">{teamMenuItem.label}</span>
            </Link>
          )}

          <button
            type="button"
            onClick={toggleExpertMode}
            aria-pressed={expertMode}
            className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950
              ${showExpertNav
                ? 'text-cyan-100 bg-cyan-500/10'
                : 'text-white/60 hover:text-white hover:bg-white/5'
              }`}
          >
            <Settings className="w-4 h-4" />
            <span className="hidden lg:inline">{showExpertNav ? '收起专家工具' : '专家工具'}</span>
          </button>
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

          {showExpertNav && (
            <DropdownMenu modal={false}>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  aria-label="流程菜单"
                  title="流程菜单"
                  className={`flex h-9 shrink-0 items-center gap-1 rounded-lg px-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950
                    ${groupedMenuItems.some((group) => isGroupActive(group))
                      ? 'bg-white/10 text-white'
                      : 'text-white/60 hover:bg-white/5 hover:text-white'
                    }`}
                >
                  <Workflow className="h-4 w-4" />
                  <ChevronDown className="h-3 w-3" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                sideOffset={8}
                className="z-[60] w-52 max-w-[calc(100vw-1rem)] border-white/10 bg-[#0f172a]/98 text-white backdrop-blur-md"
              >
                {groupedMenuItems.flatMap((group) => renderDropdownItems(group.items))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}

          {showExpertNav ? (
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
          ) : (
            <button
              type="button"
              onClick={toggleExpertMode}
              aria-label="显示专家工具"
              title="显示专家工具"
              className="flex h-9 shrink-0 items-center gap-1 rounded-lg px-2 text-sm font-medium text-white/60 transition-colors hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
            >
              <Settings className="h-4 w-4" />
            </button>
          )}
        </nav>
      </div>
    </header>
  );
}
