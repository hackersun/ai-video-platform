'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton, DashboardSkeleton } from '@/components/ui/skeleton';
import { MainLayout } from '@/components/layout/main-layout';
import { NextStepGuide } from '@/components/production/next-step-guide';
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
  Loader,
  FolderOpen,
  PlugZap,
  ShieldCheck,
  Workflow,
  Captions,
  Images,
  Wand2,
  ChevronDown
} from 'lucide-react';

// API基础URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const API_ORIGIN = API_BASE_URL.replace(/\/api\/v1\/?$/, '');

const toMediaUrl = (url?: string | null) => {
  if (!url) return '';
  return url.startsWith('/') ? `${API_ORIGIN}${url}` : url;
};

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
  const [showAdvancedTools, setShowAdvancedTools] = useState(false);
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
      const token = localStorage.getItem('auth_token');
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
        <div className="space-y-8 px-4 max-w-7xl mx-auto">
          <DashboardSkeleton />
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
            <p className="text-white/60">从小说开始，把角色、世界观、声音和镜头统一成连续动漫</p>
          </div>
          <Button asChild className="bg-violet-600 hover:bg-violet-700">
            <Link href="/quick-start">
              <Sparkles className="w-4 h-4 mr-2" />
              开始连续动漫向导
            </Link>
          </Button>
        </div>

        <NextStepGuide
          current={novels.length ? `已有 ${novels.length} 个作品，可继续制作下一集` : '还没有作品，适合先用一段小说跑通首集'}
          next={novels.length ? '进入连续动漫向导或工作台，选择作品继续生成分集' : '粘贴小说梗概和第一章，让 AI 生成首集工程'}
          reason="先锁定设定本，后续多集才能保持人物、场景、道具和声线一致。"
          href="/quick-start"
          actionLabel="打开连续动漫向导"
          checklist={['AI自动生成动漫设定本', 'AI自动生成剧本分镜', '可一键产出首集草片']}
        />

        {/* 创作流程引导 - 时间线样式 */}
        <Card className="bg-gradient-to-r from-violet-600/10 to-indigo-600/10 border-violet-500/20">
          <CardContent className="p-6">
            <h2 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-violet-400" />
              推荐制作路径
            </h2>
            <div className="relative">
              {/* 时间线连接线 */}
              <div className="absolute top-6 left-0 right-0 h-0.5 bg-gradient-to-r from-violet-500 via-purple-500 to-blue-500 hidden md:block" />
              
              <div className="flex flex-wrap md:flex-nowrap items-center justify-between gap-4">
                {[
                  { step: 1, label: '开始连续动漫', href: '/quick-start', icon: Wand2, color: 'from-violet-500 to-violet-600' },
                  { step: 2, label: '完善角色设定', href: '/characters', icon: Users, color: 'from-purple-500 to-purple-600' },
                  { step: 3, label: '生成分集计划', href: '/novels', icon: BookOpen, color: 'from-blue-500 to-blue-600' },
                  { step: 4, label: '一键制作首集', href: '/producer', icon: Sparkles, color: 'from-cyan-500 to-cyan-600' },
                  { step: 5, label: '审核分镜声音', href: '/storyboards', icon: LayoutGrid, color: 'from-emerald-500 to-emerald-600' },
                  { step: 6, label: '连续成片', href: '/studio', icon: Workflow, color: 'from-pink-500 to-pink-600' },
                ].map((item, index) => (
                  <div key={item.step} className="flex flex-col items-center relative z-10">
                    <Link
                      href={item.href}
                      className={`w-12 h-12 rounded-full bg-gradient-to-br ${item.color} flex items-center justify-center text-white shadow-lg transition-transform duration-200 hover:scale-110`}
                    >
                      <item.icon className="w-5 h-5" />
                    </Link>
                    <span className="text-xs text-white/60 mt-2 whitespace-nowrap">{item.label}</span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <div>
            <h2 className="mb-3 text-lg font-semibold text-white">常用入口</h2>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <Link href="/quick-start">
                <Card className="h-full border-cyan-400/30 bg-cyan-500/10 transition-colors hover:border-cyan-300/60">
                  <CardContent className="p-5">
                    <Wand2 className="mb-3 h-6 w-6 text-cyan-300" />
                    <div className="font-medium text-white">连续动漫向导</div>
                    <div className="mt-1 text-sm text-white/55">从小说开始，一次生成设定本、分镜和第一集草片</div>
                  </CardContent>
                </Card>
              </Link>
              <Link href="/novels">
                <Card className="h-full border-white/10 bg-white/5 transition-colors hover:border-violet-400/40">
                  <CardContent className="p-5">
                    <BookOpen className="mb-3 h-6 w-6 text-violet-300" />
                    <div className="font-medium text-white">我的作品</div>
                    <div className="mt-1 text-sm text-white/55">查看小说、章节、分集计划和已有制作进度</div>
                  </CardContent>
                </Card>
              </Link>
              <Link href="/studio">
                <Card className="h-full border-white/10 bg-white/5 transition-colors hover:border-emerald-400/40">
                  <CardContent className="p-5">
                    <Workflow className="mb-3 h-6 w-6 text-emerald-300" />
                    <div className="font-medium text-white">继续制作</div>
                    <div className="mt-1 text-sm text-white/55">进入工作台，继续审核镜头、声音、字幕和成片质量</div>
                  </CardContent>
                </Card>
              </Link>
            </div>
          </div>

          <Card className="border-white/10 bg-white/5">
            <button
              type="button"
              onClick={() => setShowAdvancedTools((value) => !value)}
              className="flex w-full items-center justify-between gap-3 p-5 text-left"
              aria-expanded={showAdvancedTools}
            >
              <div>
                <div className="font-medium text-white">高级制作工具</div>
                <div className="mt-1 text-sm text-white/50">资产、字幕、生产适配、镜头上下文和质量巡检，首集跑通后再用。</div>
              </div>
              <ChevronDown className={`h-5 w-5 text-white/50 transition-transform ${showAdvancedTools ? 'rotate-180' : ''}`} />
            </button>
            {showAdvancedTools && (
              <CardContent className="grid grid-cols-1 gap-4 border-t border-white/10 p-5 md:grid-cols-2 xl:grid-cols-4">
                <Link href="/assets">
                  <Card className="bg-white/5 border-white/10 hover:border-amber-400/40 transition-colors h-full">
                    <CardContent className="p-5">
                      <Images className="w-6 h-6 text-amber-300 mb-3" />
                      <div className="text-white font-medium">资产库</div>
                      <div className="text-white/50 text-sm mt-1">管理角色、场景、道具、关键帧、音效和参考资产</div>
                    </CardContent>
                  </Card>
                </Link>
                <Link href="/entities">
                  <Card className="bg-white/5 border-white/10 hover:border-violet-400/40 transition-colors h-full">
                    <CardContent className="p-5">
                      <Users className="w-6 h-6 text-violet-300 mb-3" />
                      <div className="text-white font-medium">实体审阅台</div>
                      <div className="text-white/50 text-sm mt-1">角色、场景、道具、事件实体的统一管理和审阅</div>
                    </CardContent>
                  </Card>
                </Link>
                <Link href="/production-adapters">
                  <Card className="bg-white/5 border-white/10 hover:border-cyan-400/40 transition-colors h-full">
                    <CardContent className="p-5">
                      <PlugZap className="w-6 h-6 text-cyan-300 mb-3" />
                      <div className="text-white font-medium">生产适配</div>
                      <div className="text-white/50 text-sm mt-1">配置视频模型、云渲染、口型和音视频合成服务</div>
                    </CardContent>
                  </Card>
                </Link>
                <Link href="/subtitles">
                  <Card className="bg-white/5 border-white/10 hover:border-blue-400/40 transition-colors h-full">
                    <CardContent className="p-5">
                      <Captions className="w-6 h-6 text-blue-300 mb-3" />
                      <div className="text-white font-medium">字幕工作台</div>
                      <div className="text-white/50 text-sm mt-1">编辑字幕段、审阅对白时间码并导出 SRT/VTT/ASS</div>
                    </CardContent>
                  </Card>
                </Link>
                <Link href="/shots">
                  <Card className="bg-white/5 border-white/10 hover:border-emerald-400/40 transition-colors h-full">
                    <CardContent className="p-5">
                      <ShieldCheck className="w-6 h-6 text-emerald-300 mb-3" />
                      <div className="text-white font-medium">镜头生产上下文</div>
                      <div className="text-white/50 text-sm mt-1">维护资产锁、关键帧、多视图参考、口型和审核状态</div>
                    </CardContent>
                  </Card>
                </Link>
                <Link href="/workflow">
                  <Card className="bg-white/5 border-white/10 hover:border-violet-400/40 transition-colors h-full">
                    <CardContent className="p-5">
                      <Workflow className="w-6 h-6 text-violet-300 mb-3" />
                      <div className="text-white font-medium">批量直生与云渲染</div>
                      <div className="text-white/50 text-sm mt-1">在制作流程中批量生成音视频、字幕轨和渲染包</div>
                    </CardContent>
                  </Card>
                </Link>
                <Link href="/producer">
                  <Card className="bg-white/5 border-white/10 hover:border-cyan-400/40 transition-colors h-full">
                    <CardContent className="p-5">
                      <Sparkles className="w-6 h-6 text-cyan-300 mb-3" />
                      <div className="text-white font-medium">一键成片中心</div>
                      <div className="text-white/50 text-sm mt-1">查看状态机、定稿包、媒体巡检、质量检查和安全补齐</div>
                    </CardContent>
                  </Card>
                </Link>
              </CardContent>
            )}
          </Card>
        </div>

        {/* 我的作品 */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-violet-400" />
              我的作品
            </h2>
            <Button asChild variant="ghost" size="sm" className="text-white/60 hover:text-white">
              <Link href="/novels">
                查看全部
                <ArrowRight className="w-4 h-4 ml-1" />
              </Link>
            </Button>
          </div>
          
          {novels.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {novels.map((novel) => {
                const progress = getNovelProgress(novel);
                const totalProgress = progress.chapters + progress.characters + progress.scripts;
                const progressPercent = Math.min(100, (totalProgress / 9) * 100); // 假设总共9个步骤
                return (
                  <Link key={novel.id} href={`/novels/${novel.id}`}>
                    <Card className="bg-white/5 border-white/10 transition-colors duration-300 hover:border-violet-500/50 cursor-pointer h-full overflow-hidden group">
                      <CardContent className="p-0">
                        {/* 封面图区域 */}
                        <div className="relative h-32 bg-gradient-to-br from-violet-600/30 to-purple-600/30 overflow-hidden">
                          {novel.cover_url ? (
                            <img 
                              src={toMediaUrl(novel.cover_url)}
                              alt="" 
                              width={384}
                              height={128}
                              loading="lazy"
                              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" 
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center">
                              <BookOpen className="w-12 h-12 text-violet-400/50" />
                            </div>
                          )}
                          {/* 状态标签 */}
                          <div className="absolute top-2 right-2">
                            <span className={`px-2 py-0.5 rounded text-xs backdrop-blur-sm ${
                              novel.status === 'completed' ? 'bg-green-500/80 text-green-100' :
                              novel.status === 'writing' ? 'bg-blue-500/80 text-blue-100' :
                              'bg-yellow-500/80 text-yellow-100'
                            }`}>
                              {novel.status === 'completed' ? '已完成' : 
                               novel.status === 'writing' ? '连载中' : '草稿'}
                            </span>
                          </div>
                        </div>
                        
                        {/* 内容区域 */}
                        <div className="p-4">
                          <h3 className="text-white font-medium mb-1 truncate group-hover:text-violet-300 transition-colors">{novel.title}</h3>
                          {novel.genre && (
                            <p className="text-white/40 text-sm mb-3">{novel.genre}</p>
                          )}
                          
                          {/* 统计信息 */}
                          <div className="flex items-center justify-between text-xs text-white/50 mb-2">
                            <span className="flex items-center gap-1">
                              <FileText className="w-3 h-3" /> {progress.chapters}
                            </span>
                            <span className="flex items-center gap-1">
                              <Users className="w-3 h-3" /> {progress.characters}
                            </span>
                            <span className="flex items-center gap-1">
                              <Video className="w-3 h-3" /> {progress.scripts}
                            </span>
                          </div>
                          
                          {/* 进度条 */}
                          <div className="relative h-1.5 bg-white/10 rounded-full overflow-hidden">
                            <div 
                              className="absolute top-0 left-0 h-full bg-gradient-to-r from-violet-500 to-purple-500 rounded-full transition-[width] duration-500"
                              style={{ width: `${progressPercent}%` }}
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
            <Card className="bg-gradient-to-br from-violet-600/10 to-indigo-600/10 border-violet-500/20">
              <CardContent className="p-12 text-center">
                <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-violet-500/20 to-purple-500/20 flex items-center justify-center">
                  <FolderOpen className="w-10 h-10 text-violet-400" />
                </div>
                <h3 className="text-xl font-semibold text-white mb-2">开始您的创作之旅</h3>
                <p className="text-white/60 mb-6 max-w-md mx-auto">
                  从连续动漫向导开始，AI会帮您把小说整理成设定本、分镜和首集草片
                </p>
                <div className="flex flex-col sm:flex-row gap-4 justify-center">
                  <Button asChild className="bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 text-white px-8">
                    <Link href="/quick-start">
                      <Sparkles className="w-4 h-4 mr-2" />
                      开始向导
                    </Link>
                  </Button>
                  <Button asChild variant="outline" className="border-violet-500/50 text-violet-300 hover:bg-violet-600/20 px-8">
                    <Link href="/novels">
                      查看作品
                    </Link>
                  </Button>
                </div>
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
              <Button asChild variant="ghost" size="sm" className="text-white/60 hover:text-white">
                <Link href="/video-generation">
                  <Plus className="w-4 h-4 mr-1" />
                  生成
                </Link>
              </Button>
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
                          <video src={toMediaUrl(video.video_url)} className="w-full h-full object-cover" />
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
                      <Button asChild variant="ghost" size="sm">
                        <Link href="/video-generation" aria-label="查看视频生成">
                          <Play className="w-4 h-4" />
                        </Link>
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 px-4">
                  <div className="w-14 h-14 mx-auto mb-3 rounded-full bg-pink-500/10 flex items-center justify-center">
                    <Video className="w-7 h-7 text-pink-400/50" />
                  </div>
                  <p className="text-white/60 text-sm mb-3">还没有生成的视频</p>
                  <Button asChild size="sm" className="bg-pink-600 hover:bg-pink-700 text-white">
                    <Link href="/video-generation">
                      <Sparkles className="w-4 h-4 mr-1" />
                      生成视频
                    </Link>
                  </Button>
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
              <Button asChild variant="ghost" size="sm" className="text-white/60 hover:text-white">
                <Link href="/tts">
                  <Plus className="w-4 h-4 mr-1" />
                  生成
                </Link>
              </Button>
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
                <div className="text-center py-8 px-4">
                  <div className="w-14 h-14 mx-auto mb-3 rounded-full bg-blue-500/10 flex items-center justify-center">
                    <Volume2 className="w-7 h-7 text-blue-400/50" />
                  </div>
                  <p className="text-white/60 text-sm mb-3">还没有生成的音频</p>
                  <Button asChild size="sm" className="bg-blue-600 hover:bg-blue-700 text-white">
                    <Link href="/tts">
                      <Sparkles className="w-4 h-4 mr-1" />
                      生成语音
                    </Link>
                  </Button>
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
                    transition-transform duration-200 hover:scale-105
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
