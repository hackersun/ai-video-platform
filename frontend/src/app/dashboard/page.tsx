'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { 
  Plus, 
  Mic, 
  LayoutTemplate, 
  BarChart3,
  FileText,
  Users,
  Video,
  LayoutGrid,
  ListTodo,
  Cpu
} from 'lucide-react';
import { MainLayout } from '@/components/layout/main-layout';

export default function DashboardPage() {
  const [user, setUser] = useState({ username: 'user' });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setTimeout(() => setLoading(false), 500);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0f172a] flex items-center justify-center">
        <div className="w-12 h-12 rounded-full border-3 border-violet-500 border-t-transparent animate-spin" />
      </div>
    );
  }

  const quickActions = [
    { label: '创建小说', href: '/novels/new', icon: Plus, color: 'from-violet-600 to-indigo-600' },
    { label: '创建剧本', href: '/scripts', icon: FileText, color: 'from-blue-600 to-cyan-600' },
    { label: '管理角色', href: '/characters', icon: Users, color: 'from-green-600 to-emerald-600' },
    { label: '生成视频', href: '/videos', icon: Video, color: 'from-pink-600 to-rose-600' },
    { label: '语音合成', href: '/tts', icon: Mic, color: 'from-amber-600 to-orange-600' },
    { label: '分镜设计', href: '/storyboards', icon: LayoutGrid, color: 'from-purple-600 to-fuchsia-600' },
    { label: '模板市场', href: '/templates/market', icon: LayoutTemplate, color: 'from-gray-600 to-slate-600' },
    { label: '任务队列', href: '/jobs', icon: ListTodo, color: 'from-teal-600 to-cyan-600' },
    { label: 'AI模型', href: '/ai-models', icon: Cpu, color: 'from-indigo-600 to-violet-600' },
    { label: '数据分析', href: '/analytics', icon: BarChart3, color: 'from-cyan-600 to-blue-600' },
  ];

  return (
    <MainLayout>
      <div className="space-y-8">
        {/* Welcome Section */}
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            欢迎回来，{user.username}
          </h1>
          <p className="text-white/60">管理您的创作项目</p>
        </div>

        {/* 创作流程引导 */}
        <div className="glass rounded-2xl p-6">
          <h2 className="text-lg font-semibold text-white mb-4">创作流程</h2>
          <div className="flex flex-wrap items-center gap-2">
            {[
              { step: 1, label: '创建小说', href: '/novels/new', color: 'bg-violet-600' },
              { step: 2, label: '添加章节', href: '/novels', color: 'bg-blue-600' },
              { step: 3, label: '创建角色', href: '/characters', color: 'bg-green-600' },
              { step: 4, label: '编写剧本', href: '/scripts', color: 'bg-yellow-600' },
              { step: 5, label: '设计分镜', href: '/storyboards', color: 'bg-purple-600' },
              { step: 6, label: '生成视频', href: '/videos', color: 'bg-pink-600' },
            ].map((item, index) => (
              <div key={item.step} className="flex items-center gap-2">
                <Link
                  href={item.href}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg ${item.color} text-white font-medium hover:opacity-90 transition-opacity`}
                >
                  <span className="w-5 h-5 rounded-full bg-white/20 flex items-center justify-center text-xs">
                    {item.step}
                  </span>
                  {item.label}
                </Link>
                {index < 5 && (
                  <div className="text-white/40">→</div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Quick Actions Grid */}
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">快速操作</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {quickActions.map((action) => {
              const Icon = action.icon;
              return (
                <Link
                  key={action.href}
                  href={action.href}
                  className={`group p-6 rounded-xl bg-gradient-to-br ${action.color} 
                    hover:scale-105 transition-all duration-200
                    flex flex-col items-center gap-3 text-white`}
                >
                  <Icon className="w-8 h-8" />
                  <span className="font-medium">{action.label}</span>
                </Link>
              );
            })}
          </div>
        </div>

        {/* Stats Section */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-6 rounded-xl bg-white/5 border border-white/10">
            <div className="text-3xl font-bold text-white mb-1">0</div>
            <div className="text-white/60">作品数量</div>
          </div>
          <div className="p-6 rounded-xl bg-white/5 border border-white/10">
            <div className="text-3xl font-bold text-white mb-1">0</div>
            <div className="text-white/60">剧本数量</div>
          </div>
          <div className="p-6 rounded-xl bg-white/5 border border-white/10">
            <div className="text-3xl font-bold text-white mb-1">0</div>
            <div className="text-white/60">视频数量</div>
          </div>
          <div className="p-6 rounded-xl bg-white/5 border border-white/10">
            <div className="text-3xl font-bold text-white mb-1">0</div>
            <div className="text-white/60">角色数量</div>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
