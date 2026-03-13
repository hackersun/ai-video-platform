'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { 
  ChevronLeft, 
  Loader2,
  Image as ImageIcon,
  Sparkles,
  Save
} from 'lucide-react';
import { novelApi } from '@/lib/api';

const GENRES = [
  '玄幻', '仙侠', '都市', '科幻', '历史', 
  '游戏', '体育', '悬疑', '武侠', '军事',
  '现实', '轻小说', '古代言情', '现代言情'
];

export default function EditNovelPage() {
  const router = useRouter();
  const params = useParams();
  const novelId = params.id as string;
  
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);
  const [error, setError] = useState('');
  
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    genre: '',
    cover_image: '',
  });

  useEffect(() => {
    const fetchNovel = async () => {
      try {
        const response = await novelApi.getById(novelId);
        const novel = response.data;
        
        setFormData({
          title: novel.title || '',
          description: novel.description || '',
          genre: novel.genre || '',
          cover_image: (novel as any).cover_image || novel.cover || '',
        });
      } catch (err) {
        console.error('获取小说失败', err);
        setError('加载失败，请稍后重试');
      } finally {
        setIsFetching(false);
      }
    };

    if (novelId) {
      fetchNovel();
    }
  }, [novelId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    if (!formData.title.trim()) {
      setError('请输入小说标题');
      return;
    }
    
    setIsLoading(true);
    
    try {
      console.log('Updating novel:', novelId, formData);
      await novelApi.update(novelId, {
        title: formData.title,
        description: formData.description,
        genre: formData.genre,
        cover_image: formData.cover_image,
      });
      console.log('Update success');
      router.push(`/novels/${novelId}`);
    } catch (err: unknown) {
      console.error('Update failed:', err);
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

  const [isGeneratingCover, setIsGeneratingCover] = useState(false);

  const generateCover = async () => {
    if (!formData.title.trim()) {
      setError('请先输入小说标题');
      return;
    }
    
    setIsGeneratingCover(true);
    try {
      const response = await novelApi.generateCover({
        title: formData.title,
        description: formData.description,
        genre: formData.genre,
      });
      
      if (response.data.success && response.data.cover_url) {
        setFormData({ ...formData, cover_image: response.data.cover_url });
      } else {
        setError(response.data.message || '封面生成失败');
      }
    } catch (err) {
      console.error('生成封面失败', err);
      setError('封面生成失败，请稍后重试');
    } finally {
      setIsGeneratingCover(false);
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
              <h1 className="text-xl font-bold text-white">编辑小说</h1>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="glass rounded-2xl p-8">
          <form onSubmit={handleSubmit} className="space-y-8">
            {error && (
              <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                {error}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                小说标题
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:border-violet-500"
                placeholder="输入小说标题"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                小说简介
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={4}
                className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:border-violet-500 resize-none"
                placeholder="输入小说简介"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                分类
              </label>
              <select
                value={formData.genre}
                onChange={(e) => setFormData({ ...formData, genre: e.target.value })}
                className="w-full px-4 py-3 rounded-lg bg-white/5 border border-white/10 text-white focus:outline-none focus:border-violet-500"
              >
                <option value="">选择分类</option>
                {GENRES.map((genre) => (
                  <option key={genre} value={genre} className="bg-slate-800">
                    {genre}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                封面
              </label>
              <div className="flex items-center gap-4">
                <div className="w-32 h-44 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden">
                  {formData.cover_image ? (
                    <img 
                      src={formData.cover_image} 
                      alt="封面"
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <ImageIcon className="w-8 h-8 text-white/20" />
                  )}
                </div>
                <div className="flex flex-col gap-2">
                  <button
                    type="button"
                    onClick={generateCover}
                    disabled={isGeneratingCover}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600/20 text-violet-400 hover:bg-violet-600/30 transition-colors text-sm disabled:opacity-50"
                  >
                    {isGeneratingCover ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Sparkles className="w-4 h-4" />
                    )}
                    {isGeneratingCover ? '生成中...' : 'AI生成封面'}
                  </button>
                </div>
              </div>
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
