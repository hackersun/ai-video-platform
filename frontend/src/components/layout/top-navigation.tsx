'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  Home, 
  BookOpen, 
  FileText, 
  Users, 
  Video, 
  Mic, 
  LayoutGrid, 
  ListTodo,
  LayoutTemplate,
  Cpu,
  BarChart3,
  Settings,
  Sparkles,
  ChevronDown
} from 'lucide-react';
import { useState } from 'react';

// 菜单分组配置
const menuGroups = [
  {
    id: 'create',
    label: '创作',
    items: [
      { label: '作品', path: '/novels', icon: BookOpen },
      { label: '剧本', path: '/scripts', icon: FileText },
      { label: '角色', path: '/characters', icon: Users },
      { label: '分镜', path: '/storyboards', icon: LayoutGrid },
    ]
  },
  {
    id: 'generate',
    label: '生成',
    items: [
      { label: '视频', path: '/videos', icon: Video },
      { label: '语音', path: '/tts', icon: Mic },
      { label: 'AI模型', path: '/ai-models', icon: Cpu },
    ]
  },
  {
    id: 'manage',
    label: '管理',
    items: [
      { label: '任务', path: '/jobs', icon: ListTodo },
      { label: '模板', path: '/templates/market', icon: LayoutTemplate },
      { label: '分析', path: '/analytics', icon: BarChart3 },
    ]
  },
];

const systemItems = [
  { label: '团队', path: '/teams', icon: Users },
  { label: '设置', path: '/settings', icon: Settings },
];

function NavItem({ item, isActive }: { item: any; isActive: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.path}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap
        ${isActive 
          ? 'text-white bg-white/10' 
          : 'text-white/60 hover:text-white hover:bg-white/5'
        }`}
    >
      <Icon className="w-4 h-4" />
      <span>{item.label}</span>
    </Link>
  );
}

function MenuGroup({ group }: { group: typeof menuGroups[0] }) {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname();
  const isActive = group.items.some(item => pathname === item.path || pathname.startsWith(item.path + '/'));

  return (
    <div className="relative group">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-1 px-3 py-2 rounded-lg text-sm font-medium transition-all
          ${isActive ? 'text-white bg-white/10' : 'text-white/60 hover:text-white hover:bg-white/5'}`}
      >
        <span>{group.label}</span>
        <ChevronDown className="w-3 h-3 opacity-60" />
      </button>
      
      {/* Dropdown */}
      <div className="absolute top-full left-0 mt-1 w-40 py-2 bg-[#1a1f2e] border border-white/10 rounded-xl shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
        {group.items.map((item) => (
          <NavItem 
            key={item.path} 
            item={item} 
            isActive={pathname === item.path || pathname.startsWith(item.path + '/')} 
          />
        ))}
      </div>
    </div>
  );
}

export function TopNavigation() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-white/5 bg-[#0f172a]/95 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link href="/dashboard" className="flex items-center gap-3 shrink-0">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <span className="text-lg font-bold text-white hidden sm:block">AI视频平台</span>
        </Link>

        {/* Navigation */}
        <nav className="flex items-center gap-1">
          {/* 控制台 */}
          <Link
            href="/dashboard"
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all
              ${pathname === '/dashboard'
                ? 'text-white bg-white/10' 
                : 'text-white/60 hover:text-white hover:bg-white/5'
              }`}
          >
            <Home className="w-4 h-4" />
            <span className="hidden sm:inline">控制台</span>
          </Link>

          {/* 分隔线 */}
          <div className="w-px h-5 bg-white/10 mx-1" />

          {/* 分组菜单 */}
          {menuGroups.map((group) => (
            <MenuGroup key={group.id} group={group} />
          ))}

          {/* 分隔线 */}
          <div className="w-px h-5 bg-white/10 mx-1" />

          {/* 系统菜单 */}
          {systemItems.map((item) => (
            <NavItem 
              key={item.path}
              item={item}
              isActive={pathname === item.path || pathname.startsWith(item.path + '/')}
            />
          ))}
        </nav>

        {/* User Menu */}
        <div className="flex items-center gap-2 shrink-0">
          <Link 
            href="/settings"
            className="p-2 rounded-lg text-white/60 hover:text-white hover:bg-white/5 transition-all"
          >
            <Settings className="w-5 h-5" />
          </Link>
        </div>
      </div>
    </header>
  );
}
