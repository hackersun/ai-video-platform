'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { 
  BookOpen, 
  FileVideo, 
  Users, 
  Settings, 
  Plus, 
  Search,
  ChevronRight,
  Sparkles,
  LogOut,
  User,
  Menu
} from 'lucide-react';
import { userApi, novelApi } from '@/lib/api';

interface Novel {
  id: string;
  title: string;
  description: string;
  genre: string;
  status: string;
  word_count: number;
  created_at: string;
}

export default function DashboardPage() {
  const router = useRouter();
  const [novels, setNovels] = useState<Novel[]>([]);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<{ username: string; nickname?: string } | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // 检查登录状态
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
      return;
    }

    // 加载数据
    loadData();
  }, [router]);

  const loadData = async () => {
    try {
      setError(null);
      const [userRes, novelsRes] = await Promise.all([
        userApi.getProfile(),
        novelApi.getMyList()
      ]);
      // 确保user数据是对象而不是数组或其他类型
      const userData = userRes.data;
      if (userData && typeof userData === 'object' && !Array.isArray(userData)) {
        setUser(userData);
      } else {
        console.error('User数据格式错误:', userData);
        setUser(null);
      }
      setNovels(novelsRes.data?.items || []);
    } catch (err: any) {
      console.error('加载数据失败', err);
      setError(err.response?.data?.detail || '加载数据失败，请稍后重试');
      // 如果是401错误，跳转到登录页
      if (err.response?.status === 401) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        router.push('/login');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    router.push('/login');
  };

  const filteredNovels = novels.filter(novel => 
    novel.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    novel.description?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'published': return 'bg-green-500/20 text-green-400';
      case 'draft': return 'bg-yellow-500/20 text-yellow-400';
      case 'archived': return 'bg-gray-500/20 text-gray-400';
      default: return 'bg-white/10 text-white/60';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-violet-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="text-center">
          <p className="text-red-400 mb-4">{error}</p>
          <button
            onClick={() => loadData()}
            className="px-4 py-2 bg-violet-600 text-white rounded hover:bg-violet-700"
          >
            重试
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900">
      {/* 顶部导航 */}
      <header className="glass sticky top-0 z-50 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link href="/dashboard" className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold gradient-text">AI视频平台</span>
            </Link>

            {/* 导航链接 */}
            <nav className="hidden md:flex items-center gap-6">
              <Link href="/dashboard" className="text-white/80 hover:text-white transition-colors">
                控制台
              </Link>
              <Link href="/novels" className="text-white/60 hover:text-white transition-colors">
                作品管理
              </Link>
              <Link href="/ai-generate" className="text-white/60 hover:text-white transition-colors">
                AI创作
              </Link>
              <Link href="/scripts" className="text-white/60 hover:text-white transition-colors">
                剧本库
              </Link>
              <Link href="/characters" className="text-white/60 hover:text-white transition-colors">
                角色库
              </Link>
              <Link href="/videos" className="text-white/60 hover:text-white transition-colors">
                视频生成
              </Link>
            </nav>

            {/* 用户菜单 */}
            <div className="flex items-center gap-4">
              <button className="p-2 rounded-lg hover:bg-white/5 transition-colors">
                <Settings className="w-5 h-5 text-white/60" />
              </button>
              <div className="flex items-center gap-3 pl-4 border-l border-white/10">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-indigo-500 flex items-center justify-center">
                  <User className="w-4 h-4 text-white" />
                </div>
                <span className="text-sm text-white/80 hidden sm:block">{user?.username}</span>
                <button 
                  onClick={handleLogout}
                  className="p-2 rounded-lg hover:bg-white/5 transition-colors"
                  title="退出登录"
                >
                  <LogOut className="w-5 h-5 text-white/60" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* 主内容 */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* 欢迎区域 */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">
            欢迎回来，{user?.nickname || user?.username}
          </h1>
          <p className="text-white/60">管理您的创作项目</p>
        </div>

        {/* 快捷操作 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <Link 
            href="/novels/new"
            className="p-6 rounded-2xl bg-gradient-to-br from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 transition-all group"
          >
            <Plus className="w-8 h-8 text-white mb-3" />
            <div className="text-white font-medium">创建小说</div>
            <div className="text-white/60 text-sm">开始新创作</div>
          </Link>
          
          <Link href="/ai-generate" className="p-6 rounded-2xl bg-white/5 border border-white/10 hover:border-white/20 transition-all cursor-pointer">
            <FileVideo className="w-8 h-8 text-cyan-400 mb-3" />
            <div className="text-white font-medium">AI生成</div>
            <div className="text-white/60 text-sm">智能创作</div>
          </Link>
          
          <Link href="/characters" className="p-6 rounded-2xl bg-white/5 border border-white/10 hover:border-white/20 transition-all cursor-pointer">
            <Users className="w-8 h-8 text-pink-400 mb-3" />
            <div className="text-white font-medium">角色库</div>
            <div className="text-white/60 text-sm">管理角色</div>
          </Link>
          
          <div className="p-6 rounded-2xl bg-white/5 border border-white/10 hover:border-white/20 transition-all cursor-pointer">
            <BookOpen className="w-8 h-8 text-amber-400 mb-3" />
            <div className="text-white font-medium">剧本库</div>
            <div className="text-white/60 text-sm">查看全部</div>
          </div>
        </div>

        {/* 小说列表 */}
        <div className="glass rounded-2xl p-6">
          {/* 标题和搜索 */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-white">我的作品</h2>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
              <input
                type="text"
                placeholder="搜索作品..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 pr-4 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-violet-500 w-64"
              />
            </div>
          </div>

          {/* 作品列表 */}
          {filteredNovels.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredNovels.map((novel) => (
                <Link
                  key={novel.id}
                  href={`/novels/${novel.id}`}
                  className="p-4 rounded-xl bg-white/5 border border-white/10 hover:border-violet-500/50 transition-all group"
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="text-white font-medium group-hover:text-violet-400 transition-colors line-clamp-1">
                      {novel.title}
                    </h3>
                    <span className={`px-2 py-0.5 rounded text-xs ${getStatusColor(novel.status)}`}>
                      {novel.status === 'published' ? '已发布' : novel.status === 'draft' ? '草稿' : '已归档'}
                    </span>
                  </div>
                  <p className="text-white/40 text-sm line-clamp-2 mb-3">
                    {novel.description || '暂无描述'}
                  </p>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-white/40">{novel.genre || '未分类'}</span>
                    <span className="text-white/40">{novel.word_count || 0} 字</span>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <BookOpen className="w-16 h-16 text-white/20 mx-auto mb-4" />
              <p className="text-white/40 mb-4">还没有任何作品</p>
              <Link 
                href="/novels/new"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-colors"
              >
                <Plus className="w-4 h-4" />
                创建第一个小说
              </Link>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}