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
  Loader2,
  Play,
  Volume2,
  ArrowRight,
  Loader
} from 'lucide-react';

// API基础URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// 统计数据
const STATS_CONFIG = [
  { label: '作品数量', key: 'novels_count', icon: BookOpen, color: 'from-violet-600 to-indigo-600' },
  { label: '剧本数量', key: 'scripts_count', icon: FileText, color: 'from-blue-600 to-cyan-600' },
  { label: '角色数量', key: 'characters_count', icon: Users, color: 'from-green-600 to-emerald-600' },
  { label: '视频数量', key: 'videos_count', icon: Video, color: 'from-pink-600 to-rose-600' },
];

// 小说数据类型
interface Novel {
  id: string;
  title: string;
  description?: string;
  genre?: string;
  status: string;
  cover_url?: string;
  chapters_count?: number;
  characters_count?: number;
  scripts_count?: number;
  videos_count?: number;
  created_at: string;
  updated_at: string;
}

// 视频任务类型
interface VideoJob {
  id: string;
  title?: string;
  prompt?: string;
  status: string;
  video_url?: string;
  duration?: number;
  created_at: string;
}

// TTS任务类型
interface TTSJob {
  id: string;
  title?: string;
  text_content?: string;
  status: string;
  audio_url?: string;
  duration?: number;
  created_at: string;
}

// 剧本类型
interface Script {
  id: string;
  title: string;
  status: string;
}

export default function DashboardPage() {
  const [user, setUser] = useState({ username: '用户' });
  const [loading, setLoading] = useState(true);
  const [novels, setNovels] = useState<Novel[]>([]);
  const [recentVideos, setRecentVideos] = useState<VideoJob[]>([]);
  const [recentAudios, setRecentAudios] = useState<TTSJob[]>([]);
  const [stats, setStats] = useState({
    novels_count: 0,
    scripts_count: 0,
    characters_count: 0,
    videos_count: 0
  });

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

      // 并行加载所有数据
      const [novelsRes, videosRes, ttsRes] = await Promise.allSettled([
        fetch(`${API_BASE_URL}/novels`, { headers }),
        fetch(`${API_BASE_URL}/video/jobs`, { headers }),
        fetch(`${API_BASE_URL}/tts/jobs`, { headers })
      ]);

      // 处理小说数据
      if (novelsRes.status === 'fulfilled' && novelsRes.value.ok) {
        const data = await novelsRes.value.json();
        const novelsList = Array.isArray(data) ? data : [];
        setNovels(novelsList.slice(0, 3)); // 只显示前3个
        
        // 统计
        setStats(prev => ({
          ...prev,
          novels_count: novelsList.length
        }));
      }

      // 处理视频数据
      if (videosRes.status === 'fulfilled' && videosRes.value.ok) {
        const data = await videosRes.value.json();
        const videosList = (Array.isArray(data) ? data : [])
          .filter((v: VideoJob) => v.status === 'succeeded' && v.video_url)
          .slice(0, 5);
        setRecentVideos(videosList);
        setStats(prev => ({ ...prev, videos_count: videosList.length }));
      }

      // 处理TTS数据
      if (ttsRes.status === 'fulfilled' && ttsRes.value.ok) {
        const data = await ttsRes.value.json();
        const audiosList = (Array.isArray(data) ? data : [])
          .filter((t: TTSJob) => t.status === 'succeeded' && t.audio_url)
          .slice(0, 5);
        setRecentAudios(audiosList);
      }

      // 加载剧本统计
      try {
        const scriptsRes = await fetch(`${API_BASE_URL}/scripts`, { headers });
        if (scriptsRes.ok) {
          const data = await scriptsRes.json();
          setStats(prev => ({ ...prev, scripts_count: Array.isArray(data) ? data.length : 0 }));
        }
      } catch (e) {
        console.error('加载剧本统计失败:', e);
      }

    } catch (error) {
      console.error('加载仪表盘数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 格式化时间
  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) return '今天';
    if (days === 1) return '昨天';
    if (days < 7) return `${days}天前`;
    return date.toLocaleDateString();
  };

  // 获取小说进度
  const getNovelProgress = (novel: Novel) => {
    const chapters = novel.chapters_count || 0;
    const characters = novel.characters_count || 0;
    const scripts = novel.scripts_count || 0;
    const videos = novel.videos_count || 0;
    return { chapters, characters, scripts, videos };
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <Loader2 className="w-12 h-12 mx-auto mb-4 text-violet-500 animate-spin" />
            <p className="text-white/60">加载中...</p>
          </div>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-8">
        {/* 欢迎区域 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">
              欢迎回来，{user.username} 👋
            </h1>
            <p className="text-white/60">开始您的AI视频创作之旅</p>
          </div>
          <Link href="/novels/new">
            <Button className="bg-violet-600 hover:bg-violet-700">
              <Plus className="w-4 h-4 mr-2" />
              创建小说
            </Button>
          </Link>
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
                { step: 1, label: '创建小说', href: '/novels/new', icon: BookOpen },
                { step: 2, label: '添加章节', href: '/novels', icon: FileText },
                { step: 3, label: '创建角色', href: '/characters', icon: Users },
                { step: 4, label: '编写剧本', href: '/scripts', icon: FileText },
                { step: 5, label: '设计分镜', href: '/storyboards', icon: LayoutGrid },
                { step: 6, label: '生成视频', href: '/video-generation', icon: Video },
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

        {/* 我的作品 */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-violet-400" />
              我的作品
            </h2>
            <Link href="/novels">
              <Button variant="ghost" size="sm" className="text-white/60 hover:text-white">
                查看全部
                <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </Link>
          </div>
          
          {novels.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {novels.map((novel) => {
                const progress = getNovelProgress(novel);
                return (
                  <Link key={novel.id} href={`/novels/${novel.id}`}>
                    <Card className="bg-white/5 border-white/10 hover:border-violet-500/30 transition-all cursor-pointer h-full">
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between mb-3">
                          <div className="w-12 h-16 rounded bg-gradient-to-br from-violet-500/30 to-purple-500/30 flex items-center justify-center">
                            {novel.cover_url ? (
                              <img src={novel.cover_url} alt="" className="w-full h-full object-cover rounded" />
                            ) : (
                              <BookOpen className="w-6 h-6 text-violet-400" />
                            )}
                          </div>
                          <span className={`px-2 py-0.5 rounded text-xs ${
                            novel.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                            novel.status === 'writing' ? 'bg-blue-500/20 text-blue-400' :
                            'bg-yellow-500/20 text-yellow-400'
                          }`}>
                            {novel.status === 'completed' ? '已完成' : 
                             novel.status === 'writing' ? '连载中' : '草稿'}
                          </span>
                        </div>
                        
                        <h3 className="text-white font-medium mb-1 truncate">{novel.title}</h3>
                        {novel.genre && (
                          <p className="text-white/40 text-sm mb-3">{novel.genre}</p>
                        )}
                        
                        {/* 进度条 */}
                        <div className="space-y-2">
                          <div className="flex justify-between text-xs text-white/40">
                            <span>章节 {progress.chapters}</span>
                            <span>角色 {progress.characters}</span>
                            <span>剧本 {progress.scripts}</span>
                          </div>
                          <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-gradient-to-r from-violet-500 to-purple-500 rounded-full"
                              style={{ width: `${Math.min(100, (progress.scripts / 3) * 100)}%` }}
                            />
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                );
              })}
            </div>
          ) : (
            <Card className="bg-white/5 border-white/10">
              <CardContent className="p-8 text-center">
                <BookOpen className="w-12 h-12 mx-auto mb-4 text-white/20" />
                <p className="text-white/60 mb-4">还没有任何作品</p>
                <Link href="/novels/new">
                  <Button className="bg-violet-600 hover:bg-violet-700">
                    <Plus className="w-4 h-4 mr-2" />
                    创建第一本小说
                  </Button>
                </Link>
              </CardContent>
            </Card>
          )}
        </div>

        {/* 统计数据 */}
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">数据统计</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {STATS_CONFIG.map((stat) => {
              const Icon = stat.icon;
              const value = stats[stat.key as keyof typeof stats] || 0;
              return (
                <Card key={stat.label} className="bg-white/5 border-white/10">
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between mb-2">
                      <Icon className="w-5 h-5 text-white/40" />
                      <span className="text-3xl font-bold text-white">{value}</span>
                    </div>
                    <div className="text-white/60">{stat.label}</div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>

        {/* 最近生成 - 视频和音频 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 最近视频 */}
          <Card className="bg-white/5 border-white/10">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-white flex items-center gap-2">
                <Video className="w-5 h-5 text-pink-400" />
                最近视频
              </CardTitle>
              <Link href="/video-generation">
                <Button variant="ghost" size="sm" className="text-white/60 hover:text-white">
                  <Plus className="w-4 h-4 mr-1" />
                  生成
                </Button>
              </Link>
            </CardHeader>
            <CardContent>
              {recentVideos.length > 0 ? (
                <div className="space-y-3">
                  {recentVideos.map((video) => (
                    <div
                      key={video.id}
                      className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5 transition-colors"
                    >
                      <div className="w-16 h-10 rounded bg-pink-500/20 flex items-center justify-center overflow-hidden">
                        {video.video_url ? (
                          <video src={video.video_url} className="w-full h-full object-cover" />
                        ) : (
                          <Video className="w-5 h-5 text-pink-400" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-white text-sm font-medium truncate">
                          {video.title || video.prompt?.slice(0, 20) || '视频'}
                        </div>
                        <div className="text-white/40 text-xs">
                          {formatTime(video.created_at)} · {video.duration || 0}秒
                        </div>
                      </div>
                      <Link href="/video-generation">
                        <Button variant="ghost" size="sm">
                          <Play className="w-4 h-4" />
                        </Button>
                      </Link>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <Video className="w-8 h-8 mx-auto mb-2 text-white/20" />
                  <p className="text-white/40 text-sm">暂无生成的视频</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* 最近音频 */}
          <Card className="bg-white/5 border-white/10">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-white flex items-center gap-2">
                <Volume2 className="w-5 h-5 text-blue-400" />
                最近音频
              </CardTitle>
              <Link href="/tts">
                <Button variant="ghost" size="sm" className="text-white/60 hover:text-white">
                  <Plus className="w-4 h-4 mr-1" />
                  生成
                </Button>
              </Link>
            </CardHeader>
            <CardContent>
              {recentAudios.length > 0 ? (
                <div className="space-y-3">
                  {recentAudios.map((audio) => (
                    <div
                      key={audio.id}
                      className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/5 transition-colors"
                    >
                      <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center">
                        <Volume2 className="w-5 h-5 text-blue-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-white text-sm font-medium truncate">
                          {audio.title || audio.text_content?.slice(0, 20) || '音频'}
                        </div>
                        <div className="text-white/40 text-xs">
                          {formatTime(audio.created_at)} · {audio.duration || 0}秒
                        </div>
                      </div>
                      <Button variant="ghost" size="sm">
                        <Play className="w-4 h-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <Volume2 className="w-8 h-8 mx-auto mb-2 text-white/20" />
                  <p className="text-white/40 text-sm">暂无生成的音频</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* 快捷操作 */}
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">快捷操作</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {[
              { label: '创建小说', href: '/novels/new', icon: BookOpen, color: 'from-violet-600 to-indigo-600' },
              { label: '管理剧本', href: '/scripts', icon: FileText, color: 'from-blue-600 to-cyan-600' },
              { label: '管理角色', href: '/characters', icon: Users, color: 'from-green-600 to-emerald-600' },
              { label: '生成视频', href: '/video-generation', icon: Video, color: 'from-pink-600 to-rose-600' },
              { label: '语音合成', href: '/tts', icon: Mic, color: 'from-amber-600 to-orange-600' },
              { label: '音视频合成', href: '/synthesis', icon: Play, color: 'from-purple-600 to-fuchsia-600' },
            ].map((action) => {
              const Icon = action.icon;
              return (
                <Link
                  key={action.href}
                  href={action.href}
                  className={`group p-4 rounded-xl bg-gradient-to-br ${action.color} 
                    hover:scale-105 transition-all duration-200
                    flex flex-col items-center gap-2 text-white`}
                >
                  <Icon className="w-6 h-6" />
                  <span className="font-medium text-sm">{action.label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
