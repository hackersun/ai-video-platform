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
  Cpu,
  BarChart3,
  Settings,
  Sparkles,
  ChevronDown
} from 'lucide-react';
import { useState } from 'react';

// 主导航菜单 - 核心功能
const mainMenuItems = [
  { label: '控制台', path: '/dashboard', icon: Home },
  { label: '作品', path: '/novels', icon: BookOpen },
  { label: '剧本', path: '/scripts', icon: FileText },
  { label: '角色', path: '/characters', icon: Users },
  { label: '分镜', path: '/storyboards', icon: LayoutGrid },
  { label: '视频生成', path: '/video-generation', icon: Video },
];

// 工具菜单
const toolMenuItems = [
  { label: '语音合成', path: '/tts', icon: Mic },
  { label: '音视频合成', path: '/synthesis', icon: Video },
  { label: 'AI模型', path: '/llm-config', icon: Cpu },
  { label: '任务队列', path: '/jobs', icon: ListTodo },
];

// 更多菜单
const moreMenuItems = [
  { label: '数据分析', path: '/analytics', icon: BarChart3 },
  { label: '团队', path: '/teams', icon: Users },
  { label: '设置', path: '/settings', icon: Settings },
];

export function TopNavigation() {
  const pathname = usePathname();
  const [showTools, setShowTools] = useState(false);
  const [showMore, setShowMore] = useState(false);

  const isActive = (path: string) => {
    return pathname === path || pathname.startsWith(path + '/');
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-16 bg-[#0f172a]/95 backdrop-blur-md border-b border-white/10">
      <div className="max-w-7xl mx-auto px-4 h-full flex items-center justify-between">
        {/* Logo */}
        <Link href="/dashboard" className="flex items-center gap-2 flex-shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <span className="text-lg font-bold text-white hidden sm:block">AI视频平台</span>
        </Link>

        {/* Navigation */}
        <nav className="flex items-center gap-1">
          {/* 主导航 */}
          {mainMenuItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                href={item.path}
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 whitespace-nowrap
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
          <div className="relative">
            <button
              onClick={() => setShowTools(!showTools)}
              onBlur={() => setTimeout(() => setShowTools(false), 200)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 whitespace-nowrap
                ${toolMenuItems.some(item => isActive(item.path))
                  ? 'text-white bg-white/10' 
                  : 'text-white/60 hover:text-white hover:bg-white/5'
                }`}
            >
              <Cpu className="w-4 h-4" />
              <span className="hidden md:inline">工具</span>
              <ChevronDown className="w-3 h-3" />
            </button>
            
            {showTools && (
              <div className="absolute top-full right-0 mt-1 w-48 bg-[#0f172a]/95 backdrop-blur-md border border-white/10 rounded-lg shadow-xl py-2">
                {toolMenuItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.path}
                      href={item.path}
                      className={`px-4 py-2 text-sm flex items-center gap-2 transition-colors
                        ${isActive(item.path)
                          ? 'text-white bg-white/10' 
                          : 'text-white/60 hover:text-white hover:bg-white/5'
                        }`}
                    >
                      <Icon className="w-4 h-4" />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>

          {/* 更多下拉 */}
          <div className="relative">
            <button
              onClick={() => setShowMore(!showMore)}
              onBlur={() => setTimeout(() => setShowMore(false), 200)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 whitespace-nowrap
                ${moreMenuItems.some(item => isActive(item.path))
                  ? 'text-white bg-white/10' 
                  : 'text-white/60 hover:text-white hover:bg-white/5'
                }`}
            >
              <Settings className="w-4 h-4" />
              <span className="hidden md:inline">更多</span>
              <ChevronDown className="w-3 h-3" />
            </button>
            
            {showMore && (
              <div className="absolute top-full right-0 mt-1 w-48 bg-[#0f172a]/95 backdrop-blur-md border border-white/10 rounded-lg shadow-xl py-2">
                {moreMenuItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.path}
                      href={item.path}
                      className={`px-4 py-2 text-sm flex items-center gap-2 transition-colors
                        ${isActive(item.path)
                          ? 'text-white bg-white/10' 
                          : 'text-white/60 hover:text-white hover:bg-white/5'
                        }`}
                    >
                      <Icon className="w-4 h-4" />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </nav>
      </div>
    </header>
  );
}
