'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { 
  ChevronLeft, 
  Loader2,
  Save,
  Trash2
} from 'lucide-react';
import { novelApi } from '@/lib/api';

export default function ChapterDetailPage() {
  const router = useRouter();
  const params = useParams();
  const novelId = params.id as string;
  const chapterId = params.chapterId as string;
  
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);
  const [error, setError] = useState('');
  
  const [formData, setFormData] = useState({
    title: '',
    content: '',
    chapter_number: 1,
  });

  useEffect(() => {
    const fetchChapter = async () => {
      try {
        const response = await novelApi.getChapter(novelId, chapterId);
        const chapter = response.data;
        
        setFormData({
          title: chapter.title || '',
          content: chapter.content || '',
          chapter_number: chapter.chapter_number || 1,
        });
      } catch (err) {
        console.error('获取章节失败', err);
        setError('加载失败，请稍后重试');
      } finally {
        setIsFetching(false);
      }
    };

    if (novelId && chapterId) {
      fetchChapter();
    }
  }, [novelId, chapterId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    if (!formData.title.trim()) {
      setError('请输入章节标题');
      return;
    }
    
    setIsLoading(true);
    
    try {
      await novelApi.updateChapter(novelId, chapterId, {
        title: formData.title,
        content: formData.content,
        chapter_number: formData.chapter_number,
      });
      
      router.push(`/novels/${novelId}`);
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: unknown } } };
      const detail = axiosError.response?.data?.detail;
      
      if (Array.isArray(detail)) {
        setError(detail[0]?.msg || '保存失败，请稍后重试');
      } else if (typeof detail === 'string') {
        setError(detail);
      } else {
        setError('保存失败，请稍后重试');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('确定要删除这个章节吗？')) return;
    
    setIsLoading(true);
    
    try {
      await novelApi.deleteChapter(novelId, chapterId);
      router.push(`/novels/${novelId}`);
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: unknown } } };
      const detail = axiosError.response?.data?.detail;
      
      if (typeof detail === 'string') {
        setError(detail);
      } else {
        setError('删除失败，请稍后重试');
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (isFetching) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-violet-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900">
      <header className="glass sticky top-0 z-50 border-b border-white/5">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Link href={`/novels/${novelId}`} className="p-2 rounded-lg hover:bg-white/5 transition-colors">
                <ChevronLeft className="w-5 h-5 text-white/60" />
              </Link>
              <h1 className="text-xl font-bold text-white">编辑章节</h1>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="glass rounded-2xl p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                {error}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                章节标题
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:border-violet-500"
                placeholder="输入章节标题"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                章节序号
              </label>
              <input
                type="number"
                value={formData.chapter_number}
                onChange={(e) => setFormData({ ...formData, chapter_number: parseInt(e.target.value) || 1 })}
                min={1}
                className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:border-violet-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                章节内容
              </label>
              <textarea
                value={formData.content}
                onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                rows={15}
                className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:border-violet-500 resize-none font-mono text-sm"
                placeholder="输入章节内容"
              />
            </div>

            <div className="flex gap-4 pt-4">
              <button
                type="submit"
                disabled={isLoading}
                className="flex-1 flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-violet-600 text-white font-medium hover:bg-violet-700 transition-colors disabled:opacity-50"
              >
                {isLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Save className="w-5 h-5" />
                )}
                保存修改
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={isLoading}
                className="flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-red-600/20 text-red-400 hover:bg-red-600/30 transition-colors disabled:opacity-50"
              >
                <Trash2 className="w-5 h-5" />
                删除
              </button>
              <Link
                href={`/novels/${novelId}`}
                className="px-6 py-3 rounded-lg bg-white/10 text-white font-medium hover:bg-white/20 transition-colors"
              >
                取消
              </Link>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
