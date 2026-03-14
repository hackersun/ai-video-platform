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
  Sparkles
} from 'lucide-react';

const menuItems = [
  { label: '控制台', path: '/dashboard', icon: Home },
  { label: '作品', path: '/novels', icon: BookOpen },
  { label: '剧本', path: '/scripts', icon: FileText },
  { label: '角色', path: '/characters', icon: Users },
  { label: '视频', path: '/videos', icon: Video },
  { label: '语音合成', path: '/tts', icon: Mic },
  { label: '分镜', path: '/storyboards', icon: LayoutGrid },
  { label: '任务队列', path: '/jobs', icon: ListTodo },
  { label: '模板', path: '/templates/market', icon: LayoutTemplate },
  { label: 'AI模型', path: '/ai-models', icon: Cpu },
  { label: '分析', path: '/analytics', icon: BarChart3 },
  { label: '团队', path: '/teams', icon: Users },
  { label: '设置', path: '/settings', icon: Settings },
];

export function TopNavigation() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-white/5 bg-[#0f172a]/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link href="/dashboard" className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <span className="text-xl font-bold text-white">AI视频平台</span>
        </Link>

        {/* Navigation */}
        <nav className="flex items-center gap-1">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.path || pathname.startsWith(item.path + '/');
            
            return (
              <Link
                key={item.path}
                href={item.path}
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2
                  ${isActive 
                    ? 'text-white bg-white/10' 
                    : 'text-white/60 hover:text-white hover:bg-white/5'
                  }`}
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* User Menu */}
        <div className="flex items-center gap-3">
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
