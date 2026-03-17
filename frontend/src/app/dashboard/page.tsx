'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { MainLayout } from '@/components/layout/main-layout';
import Link from 'next/link';
import { 
  BookOpen, 
  Users, 
  FileText, 
  Video, 
  Mic, 
  LayoutGrid, 
  ListTodo,
  LayoutTemplate,
  Cpu,
  BarChart3,
  Sparkles,
  Plus,
  TrendingUp,
  Clock,
  CheckCircle,
  Loader2
} from 'lucide-react';

// 统计数据
const STATS_CONFIG = [
  { label: '作品数量', key: 'novels_count', icon: BookOpen, color: 'from-violet-600 to-indigo-600' },
  { label: '剧本数量', key: 'scripts_count', icon: FileText, color: 'from-blue-600 to-cyan-600' },
  { label: '角色数量', key: 'characters_count', icon: Users, color: 'from-green-600 to-emerald-600' },
  { label: '视频数量', key: 'videos_count', icon: Video, color: 'from-pink-600 to-rose-600' },
];

// 快捷操作
const QUICK_ACTIONS = [
  { label: '创建小说', href: '/novels/new', icon: BookOpen, color: 'from-violet-600 to-indigo-600', desc: '开始新的创作' },
  { label: '创建剧本', href: '/scripts', icon: FileText, color: 'from-blue-600 to-cyan-600', desc: '编写视频剧本' },
  { label: '管理角色', href: '/characters', icon: Users, color: 'from-green-600 to-emerald-600', desc: '管理角色库' },
  { label: '生成视频', href: '/video-generation', icon: Video, color: 'from-pink-600 to-rose-600', desc: 'AI生成视频' },
  { label: '语音合成', href: '/tts', icon: Mic, color: 'from-amber-600 to-orange-600', desc: '文本转语音' },
  { label: '分镜设计', href: '/storyboards', icon: LayoutGrid, color: 'from-purple-600 to-fuchsia-600', desc: '设计视频分镜' },
  { label: '任务队列', href: '/jobs', icon: ListTodo, color: 'from-teal-600 to-cyan-600', desc: '查看生成任务' },
  { label: 'AI模型', href: '/llm-config', icon: Cpu, color: 'from-indigo-600 to-violet-600', desc: '配置AI模型' },
  { label: '数据分析', href: '/analytics', icon: BarChart3, color: 'from-cyan-600 to-blue-600', desc: '查看统计数据' },
  { label: '模板市场', href: '/templates', icon: LayoutTemplate, color: 'from-gray-600 to-slate-600', desc: '浏览模板' },
];

// API 基础URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface DashboardStats {
  novels_count: number;
  scripts_count: number;
  characters_count: number;
  videos_count: number;
  recent_activities: Array<{
    id: string;
    type: string;
    title: string;
    description: string;
    timestamp: string;
  }>;
}

async function fetchDashboardStats(): Promise<DashboardStats> {
  try {
    const response = await fetch(`${API_BASE_URL}/dashboard/stats`);
    if (!response.ok) {
      throw new Error('Failed to fetch stats');
    }
    return response.json();
  } catch (error) {
    console.error('Error fetching dashboard stats:', error);
    // 返回默认值
    return {
      novels_count: 0,
      scripts_count: 0,
      characters_count: 0,
      videos_count: 0,
      recent_activities: []
    };
  }
}

export default function DashboardPage() {
  const [user, setUser] = useState({ username: '用户' });
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats>({
    novels_count: 0,
    scripts_count: 0,
    characters_count: 0,
    videos_count: 0,
    recent_activities: []
  });

  useEffect(() => {
    // 加载统计数据
    const loadStats = async () => {
      try {
        const data = await fetchDashboardStats();
        setStats(data);
      } catch (error) {
        console.error('Failed to load stats:', error);
      } finally {
        setLoading(false);
      }
    };

    loadStats();
  }, []);

  if (loading) {
    return (
      <MainLayout>
        <div className="min-h-screen flex items-center justify-center">
          <div className="w-12 h-12 rounded-full border-3 border-violet-500 border-t-transparent animate-spin" />
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-8">
        {/* 欢迎区域 */}
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            欢迎回来，{user.username}
          </h1>
          <p className="text-white/60">开始您的AI视频创作之旅</p>
        </div>

        {/* 创作流程引导 */}
        <Card className="bg-gradient-to-r from-violet-600/20 to-indigo-600/20 border-violet-500/30">
          <CardContent className="p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-violet-400" />
              创作流程
            </h2>
            <div className="flex flex-wrap items-center gap-2">
              {[
                { step: 1, label: '创建小说', href: '/novels/new' },
                { step: 2, label: '添加章节', href: '/novels' },
                { step: 3, label: '创建角色', href: '/characters' },
                { step: 4, label: '编写剧本', href: '/scripts' },
                { step: 5, label: '设计分镜', href: '/storyboards' },
                { step: 6, label: '生成视频', href: '/video-generation' },
              ].map((item, index) => (
                <div key={item.step} className="flex items-center gap-2">
                  <Link
                    href={item.href}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-all"
                  >
                    <span className="w-5 h-5 rounded-full bg-white/20 flex items-center justify-center text-xs">
                      {item.step}
                    </span>
                    {item.label}
                  </Link>
                  {index < 5 && (
                    <span className="text-white/40">→</span>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* 快捷操作 */}
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">快捷操作</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {QUICK_ACTIONS.map((action) => {
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
                  <span className="text-xs text-white/70">{action.desc}</span>
                </Link>
              );
            })}
          </div>
        </div>

        {/* 统计数据 - 从API加载 */}
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">数据统计</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {STATS_CONFIG.map((stat) => {
              const Icon = stat.icon;
              const value = stats[stat.key as keyof Omit<DashboardStats, 'recent_activities'>] || 0;
              return (
                <Card key={stat.label} className="bg-white/5 border-white/10">
                  <CardContent className="p-6">
                    <div className="text-3xl font-bold text-white mb-1">{value}</div>
                    <div className="text-white/60">{stat.label}</div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>

        {/* 最近活动 - 从API加载 */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Clock className="w-5 h-5" />
              最近活动
            </CardTitle>
          </CardHeader>
          <CardContent>
            {stats.recent_activities && stats.recent_activities.length > 0 ? (
              <div className="space-y-3">
                {stats.recent_activities.map((activity) => (
                  <div key={activity.id} className="flex items-center gap-3 p-3 rounded-lg bg-white/5">
                    <CheckCircle className="w-5 h-5 text-green-400" />
                    <div>
                      <div className="text-white font-medium">{activity.title}</div>
                      <div className="text-white/60 text-sm">{activity.description}</div>
                    </div>
                    <div className="ml-auto text-white/40 text-sm">
                      {new Date(activity.timestamp).toLocaleDateString()}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-white/40">
                <CheckCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>暂无最近活动</p>
                <p className="text-sm mt-2">开始创作您的第一个作品吧！</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}