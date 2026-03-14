'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { MainLayout } from '@/components/layout/main-layout';
import { 
  ChevronLeft,
  ChevronRight,
  Edit3, 
  Plus,
  BookOpen,
  FileText,
  Film,
  Clock,
  Trash2,
  Sparkles,
  Loader2
} from 'lucide-react';
import { novelApi, scriptApi } from '@/lib/api';

interface Novel {
  id: string;
  title: string;
  description: string;
  genre: string;
  status: string;
  word_count: number;
  cover?: string;
  created_at: string;
  updated_at: string;
}

interface Chapter {
  id: string;
  title: string;
  chapter_number: number;
  word_count: number;
  status: string;
  created_at: string;
}

interface Script {
  id: string;
  title: string;
  status: string;
  scene_count?: number;
  created_at: string;
}

export default function NovelDetailPage() {
  const router = useRouter();
  const params = useParams();
  const novelId = params.id as string;
  
  const [novel, setNovel] = useState<Novel | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [scripts, setScripts] = useState<Script[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'chapters' | 'scripts'>('chapters');

  useEffect(() => {
    if (novelId) {
      loadData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [novelId]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [novelRes, chaptersRes] = await Promise.all([
        novelApi.getById(novelId),
        novelApi.getChapters(novelId)
      ]);
      
      setNovel(novelRes.data);
      setChapters(chaptersRes.data.items || []);
      
      // 加载剧本
      const scriptsRes = await scriptApi.getList({ novel_id: novelId });
      setScripts(scriptsRes.data.items || []);
    } catch (error) {
      console.error('加载数据失败', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('确定要删除这部小说吗？所有章节和剧本也将被删除。')) {
      return;
    }
    
    try {
      await novelApi.delete(novelId);
      router.push('/novels');
    } catch (error) {
      console.error('删除失败', error);
      alert('删除失败，请稍后重试');
    }
  };

  const handlePublish = async () => {
    try {
      await novelApi.publish(novelId);
      loadData();
    } catch (error) {
      console.error('发布失败', error);
      alert('发布失败，请稍后重试');
    }
  };

  const getStatusBadge = (status: string) => {
    const styles = {
      draft: 'bg-yellow-500/20 text-yellow-400',
      published: 'bg-green-500/20 text-green-400',
      archived: 'bg-gray-500/20 text-gray-400',
    };
    const labels = {
      draft: '草稿',
      published: '已发布',
      archived: '已归档',
    };
    return (
      <span className={`px-3 py-1 rounded-full text-xs font-medium ${styles[status as keyof typeof styles] || styles.draft}`}>
        {labels[status as keyof typeof labels] || status}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  if (!novel) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <p className="text-white/60">小说不存在</p>
          <Link href="/novels" className="text-violet-400 hover:underline mt-2">
            返回作品列表
          </Link>
        </div>
      </div>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/novels" className="p-2 rounded-lg hover:bg-white/5 transition-colors">
              <ChevronLeft className="w-5 h-5 text-white/60" />
            </Link>
            <h1 className="text-2xl font-bold text-white line-clamp-1">{novel.title}</h1>
          </div>
            <div className="flex items-center gap-2">
              <Link
                href={`/novels/${novelId}/edit`}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 text-white/80 hover:bg-white/10 transition-colors"
              >
                <Edit3 className="w-4 h-4" />
                编辑
              </Link>
              {novel.status === 'draft' && (
                <button
                  onClick={handlePublish}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-colors"
                >
                  <Sparkles className="w-4 h-4" />
                  发布
                </button>
              )}
              <button
                onClick={handleDelete}
                className="p-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* 主内容 */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* 小说信息卡片 */}
        <div className="glass rounded-2xl p-6 mb-8">
          <div className="flex gap-6">
            {/* 封面 */}
            <div className="w-40 h-56 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden flex-shrink-0">
              {novel.cover ? (
                <img 
                  src={novel.cover} 
                  alt={novel.title}
                  className="w-full h-full object-cover"
                />
              ) : (
                <BookOpen className="w-12 h-12 text-white/20" />
              )}
            </div>
            
            {/* 信息 */}
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-3">
                {getStatusBadge(novel.status)}
                <span className="text-white/40 text-sm">{novel.genre || '未分类'}</span>
              </div>
              
              <h2 className="text-2xl font-bold text-white mb-3">{novel.title}</h2>
              
              <p className="text-white/60 mb-4 line-clamp-3">
                {novel.description || '暂无简介'}
              </p>
              
              <div className="flex items-center gap-6 text-sm text-white/40">
                <span className="flex items-center gap-1">
                  <BookOpen className="w-4 h-4" />
                  {chapters.length} 章节
                </span>
                <span>{novel.word_count || 0} 字</span>
                <span className="flex items-center gap-1">
                  <Clock className="w-4 h-4" />
                  更新于 {new Date(novel.updated_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* 标签切换 */}
        <div className="flex items-center gap-1 mb-6 border-b border-white/10">
          <button
            onClick={() => setActiveTab('chapters')}
            className={`px-4 py-3 text-sm font-medium transition-colors relative ${
              activeTab === 'chapters' ? 'text-white' : 'text-white/40 hover:text-white/60'
            }`}
          >
            <span className="flex items-center gap-2">
              <FileText className="w-4 h-4" />
              章节 ({chapters.length})
            </span>
            {activeTab === 'chapters' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-violet-500" />
            )}
          </button>
          <button
            onClick={() => setActiveTab('scripts')}
            className={`px-4 py-3 text-sm font-medium transition-colors relative ${
              activeTab === 'scripts' ? 'text-white' : 'text-white/40 hover:text-white/60'
            }`}
          >
            <span className="flex items-center gap-2">
              <Film className="w-4 h-4" />
              剧本 ({scripts.length})
            </span>
            {activeTab === 'scripts' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-violet-500" />
            )}
          </button>
        </div>

        {/* 章节列表 */}
        {activeTab === 'chapters' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-white">章节列表</h3>
              <Link
                href={`/novels/${novelId}/chapters/new`}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-colors text-sm"
              >
                <Plus className="w-4 h-4" />
                添加章节
              </Link>
            </div>
            
            {chapters.length > 0 ? (
              <div className="space-y-2">
                {chapters.map((chapter) => (
                  <Link
                    key={chapter.id}
                    href={`/novels/${novelId}/chapters/${chapter.id}`}
                    className="flex items-center gap-4 p-4 rounded-xl bg-white/5 border border-white/10 hover:border-violet-500/50 transition-all group"
                  >
                    <div className="w-10 h-10 rounded-lg bg-violet-600/20 flex items-center justify-center text-violet-400 font-medium">
                      {chapter.chapter_number}
                    </div>
                    <div className="flex-1">
                      <h4 className="text-white font-medium group-hover:text-violet-400 transition-colors">
                        {chapter.title}
                      </h4>
                      <p className="text-white/40 text-sm">
                        {chapter.word_count} 字 · {new Date(chapter.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <ChevronRight className="w-5 h-5 text-white/20 group-hover:text-violet-400 transition-colors" />
                  </Link>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 glass rounded-2xl">
                <FileText className="w-12 h-12 text-white/20 mx-auto mb-4" />
                <p className="text-white/40 mb-4">还没有章节</p>
                <Link
                  href={`/novels/${novelId}/chapters/new`}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  添加第一章
                </Link>
              </div>
            )}
          </div>
        )}

        {/* 剧本列表 */}
        {activeTab === 'scripts' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-white">剧本列表</h3>
              <Link
                href={`/scripts/new?novel_id=${novelId}`}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-colors text-sm"
              >
                <Plus className="w-4 h-4" />
                创建剧本
              </Link>
            </div>
            
            {scripts.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {scripts.map((script) => (
                  <Link
                    key={script.id}
                    href={`/scripts/${script.id}`}
                    className="p-4 rounded-xl bg-white/5 border border-white/10 hover:border-violet-500/50 transition-all group"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h4 className="text-white font-medium group-hover:text-violet-400 transition-colors">
                        {script.title}
                      </h4>
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        script.status === 'published' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'
                      }`}>
                        {script.status === 'published' ? '已发布' : '草稿'}
                      </span>
                    </div>
                    <p className="text-white/40 text-sm">
                      {script.scene_count || 0} 场景 · {new Date(script.created_at).toLocaleDateString()}
                    </p>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 glass rounded-2xl">
                <Film className="w-12 h-12 text-white/20 mx-auto mb-4" />
                <p className="text-white/40 mb-4">还没有剧本</p>
                <Link
                  href={`/scripts/new?novel_id=${novelId}`}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-colors"
                >
                  <Sparkles className="w-4 h-4" />
                  AI生成剧本
                </Link>
              </div>
            )}
          </div>
        )}
      </div>
    </MainLayout>
  );
}