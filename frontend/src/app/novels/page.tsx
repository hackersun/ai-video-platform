'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { 
  Plus, 
  Search, 
  BookOpen,
  Edit3,
  Trash2,
  Eye,
  ChevronLeft,
  ChevronRight,
  Sparkles
} from 'lucide-react';
import { novelApi } from '@/lib/api';

interface Novel {
  id: string;
  title: string;
  description: string;
  genre: string;
  status: string;
  word_count: number;
  chapter_count?: number;
  cover?: string;
  created_at: string;
  updated_at: string;
}

export default function NovelsPage() {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    loadNovels();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, statusFilter]);

  const loadNovels = async () => {
    try {
      setLoading(true);
      const params: { page: number; limit: number; status?: string } = { page, limit: 12 };
      if (statusFilter !== 'all') {
        params.status = statusFilter;
      }
      
      const response = await novelApi.getMyList(params);
      setNovels(response.data.items);
      setTotalPages(response.data.pages);
    } catch (error) {
      console.error('加载小说失败', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('确定要删除这部小说吗？此操作不可恢复。')) {
      return;
    }
    
    try {
      await novelApi.delete(id);
      setNovels(novels.filter(n => n.id !== id));
    } catch (error) {
      console.error('删除失败', error);
      alert('删除失败，请稍后重试');
    }
  };

  const handlePublish = async (id: string) => {
    try {
      await novelApi.publish(id);
      loadNovels();
    } catch (error) {
      console.error('发布失败', error);
      alert('发布失败，请稍后重试');
    }
  };

  const filteredNovels = novels.filter(novel => 
    novel.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    novel.description?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getStatusBadge = (status: string) => {
    const styles = {
      draft: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      published: 'bg-green-500/20 text-green-400 border-green-500/30',
      archived: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    };
    const labels = {
      draft: '草稿',
      published: '已发布',
      archived: '已归档',
    };
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium border ${styles[status as keyof typeof styles] || styles.draft}`}>
        {labels[status as keyof typeof labels] || status}
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-slate-900">
      {/* 顶部导航 */}
      <header className="glass sticky top-0 z-50 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Link href="/dashboard" className="p-2 rounded-lg hover:bg-white/5 transition-colors">
                <ChevronLeft className="w-5 h-5 text-white/60" />
              </Link>
              <h1 className="text-xl font-bold text-white">我的作品</h1>
            </div>
            <Link 
              href="/novels/new"
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-colors"
            >
              <Plus className="w-4 h-4" />
              创建小说
            </Link>
          </div>
        </div>
      </header>

      {/* 主内容 */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* 筛选栏 */}
        <div className="flex flex-col sm:flex-row gap-4 mb-8">
          {/* 搜索 */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
            <input
              type="text"
              placeholder="搜索作品..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent"
            />
          </div>
          
          {/* 状态筛选 */}
          <div className="flex gap-2">
            {['all', 'draft', 'published'].map((status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  statusFilter === status
                    ? 'bg-violet-600 text-white'
                    : 'bg-white/5 text-white/60 hover:bg-white/10'
                }`}
              >
                {status === 'all' ? '全部' : status === 'draft' ? '草稿' : '已发布'}
              </button>
            ))}
          </div>
        </div>

        {/* 小说列表 */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-violet-500"></div>
          </div>
        ) : filteredNovels.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredNovels.map((novel) => (
              <div
                key={novel.id}
                className="glass rounded-2xl overflow-hidden hover:border-violet-500/50 transition-all group"
              >
                {/* 封面 */}
                <div className="relative h-40 bg-gradient-to-br from-violet-600/20 to-indigo-600/20 flex items-center justify-center">
                  {novel.cover ? (
                    <img 
                      src={novel.cover} 
                      alt={novel.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <BookOpen className="w-12 h-12 text-white/20" />
                  )}
                  <div className="absolute top-3 left-3">
                    {getStatusBadge(novel.status)}
                  </div>
                </div>
                
                {/* 内容 */}
                <div className="p-5">
                  <h3 className="text-lg font-semibold text-white mb-2 line-clamp-1 group-hover:text-violet-400 transition-colors">
                    {novel.title}
                  </h3>
                  <p className="text-white/40 text-sm line-clamp-2 mb-4">
                    {novel.description || '暂无描述'}
                  </p>
                  
                  {/* 统计 */}
                  <div className="flex items-center gap-4 text-sm text-white/40 mb-4">
                    <span className="flex items-center gap-1">
                      <BookOpen className="w-4 h-4" />
                      {novel.chapter_count || 0} 章
                    </span>
                    <span>{novel.word_count || 0} 字</span>
                  </div>
                  
                  {/* 操作按钮 */}
                  <div className="flex items-center gap-2">
                    <Link
                      href={`/novels/${novel.id}`}
                      className="flex-1 flex items-center justify-center gap-1 px-3 py-2 rounded-lg bg-violet-600/20 text-violet-400 hover:bg-violet-600/30 transition-colors text-sm"
                    >
                      <Eye className="w-4 h-4" />
                      查看
                    </Link>
                    <Link
                      href={`/novels/${novel.id}/edit`}
                      className="flex items-center justify-center p-2 rounded-lg bg-white/5 text-white/60 hover:bg-white/10 transition-colors"
                    >
                      <Edit3 className="w-4 h-4" />
                    </Link>
                    {novel.status === 'draft' && (
                      <button
                        onClick={() => handlePublish(novel.id)}
                        className="flex items-center justify-center p-2 rounded-lg bg-green-500/20 text-green-400 hover:bg-green-500/30 transition-colors"
                      >
                        <Sparkles className="w-4 h-4" />
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(novel.id)}
                      className="flex items-center justify-center p-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-20">
            <BookOpen className="w-20 h-20 text-white/20 mx-auto mb-6" />
            <h3 className="text-xl font-medium text-white mb-2">还没有作品</h3>
            <p className="text-white/40 mb-6">创建你的第一部小说，开始AI创作之旅</p>
            <Link 
              href="/novels/new"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-violet-600 text-white hover:bg-violet-700 transition-colors"
            >
              <Plus className="w-5 h-5" />
              创建小说
            </Link>
          </div>
        )}

        {/* 分页 */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-8">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-2 rounded-lg bg-white/5 text-white/60 hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <span className="text-white/60">
              第 {page} / {totalPages} 页
            </span>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="p-2 rounded-lg bg-white/5 text-white/60 hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        )}
      </main>
    </div>
  );
}