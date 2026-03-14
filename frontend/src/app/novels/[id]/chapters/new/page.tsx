'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { MainLayout } from '@/components/layout/main-layout';
import { 
  ChevronLeft, 
  Loader2,
  Save
} from 'lucide-react';
import { novelApi } from '@/lib/api';

export default function NewChapterPage() {
  const router = useRouter();
  const params = useParams();
  const novelId = params.id as string;
  
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  
  const [formData, setFormData] = useState({
    title: '',
    content: '',
    chapter_number: 1,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    if (!formData.title.trim()) {
      setError('请输入章节标题');
      return;
    }
    
    setIsLoading(true);
    
    try {
      await novelApi.createChapter(novelId, {
        title: formData.title,
        content: formData.content,
        chapter_number: formData.chapter_number,
      });
      
      router.push(`/novels/${novelId}`);
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: unknown } } };
      const detail = axiosError.response?.data?.detail;
      
      if (Array.isArray(detail)) {
        setError(detail[0]?.msg || '创建失败，请稍后重试');
      } else if (typeof detail === 'string') {
        setError(detail);
      } else {
        setError('创建失败，请稍后重试');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <MainLayout>
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Page Header */}
        <div className="flex items-center gap-4">
          <Link href={`/novels/${novelId}`} className="p-2 rounded-lg hover:bg-white/5 transition-colors">
            <ChevronLeft className="w-5 h-5 text-white/60" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-white">添加章节</h1>
            <p className="text-white/60 mt-1">为小说添加新章节</p>
          </div>
        </div>

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
                创建章节
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
      </div>
    </MainLayout>
  );
}
