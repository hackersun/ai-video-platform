'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { 
  ChevronLeft, 
  Plus, 
  Loader2,
  Image as ImageIcon,
  Sparkles
} from 'lucide-react';
import { novelApi } from '@/lib/api';

const GENRES = [
  '玄幻', '仙侠', '都市', '科幻', '历史', 
  '游戏', '体育', '悬疑', '武侠', '军事',
  '现实', '轻小说', '古代言情', '现代言情'
];

export default function NewNovelPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    genre: '',
    cover_image: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    if (!formData.title.trim()) {
      setError('请输入小说标题');
      return;
    }
    
    setIsLoading(true);
    
    try {
      const response = await novelApi.create({
        title: formData.title,
        description: formData.description,
        genre: formData.genre,
        cover_image: formData.cover_image,
      });
      
      // 创建成功，跳转到小说详情页
      router.push(`/novels/${response.data.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建失败，请稍后重试');
    } finally {
      setIsLoading(false);
    }
  };

  const generateCover = async () => {
    // TODO: 调用AI生成封面
    setFormData({ ...formData, cover_image: '' });
  };

  return (
    <div className="min-h-screen bg-slate-900">
      {/* 顶部导航 */}
      <header className="glass sticky top-0 z-50 border-b border-white/5">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Link href="/novels" className="p-2 rounded-lg hover:bg-white/5 transition-colors">
                <ChevronLeft className="w-5 h-5 text-white/60" />
              </Link>
              <h1 className="text-xl font-bold text-white">创建新小说</h1>
            </div>
          </div>
        </div>
      </header>

      {/* 主内容 */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="glass rounded-2xl p-8">
          <form onSubmit={handleSubmit} className="space-y-8">
            {/* 错误提示 */}
            {error && (
              <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400">
                {error}
              </div>
            )}

            {/* 标题 */}
            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                小说标题 <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all"
                placeholder="给你的小说起个名字"
                maxLength={100}
                required
              />
            </div>

            {/* 分类 */}
            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                分类
              </label>
              <div className="flex flex-wrap gap-2">
                {GENRES.map((genre) => (
                  <button
                    key={genre}
                    type="button"
                    onClick={() => setFormData({ ...formData, genre })}
                    className={`px-4 py-2 rounded-lg text-sm transition-colors ${
                      formData.genre === genre
                        ? 'bg-violet-600 text-white'
                        : 'bg-white/5 text-white/60 hover:bg-white/10'
                    }`}
                  >
                    {genre}
                  </button>
                ))}
              </div>
            </div>

            {/* 简介 */}
            <div>
              <label className="block text-sm font-medium text-white/80 mb-2">
                简介
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all resize-none"
                placeholder="简单介绍一下你的小说..."
                rows={4}
                maxLength={500}
              />
              <p className="text-white/40 text-sm mt-1">
                {formData.description.length}/500
              </p>
            </div>

            {/* 封面 */}
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
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600/20 text-violet-400 hover:bg-violet-600/30 transition-colors text-sm"
                  >
                    <Sparkles className="w-4 h-4" />
                    AI生成封面
                  </button>
                  <p className="text-white/40 text-xs">
                    或使用默认封面
                  </p>
                </div>
              </div>
            </div>

            {/* 提交按钮 */}
            <div className="flex items-center justify-end gap-4 pt-4 border-t border-white/10">
              <Link
                href="/novels"
                className="px-6 py-3 rounded-xl text-white/60 hover:text-white transition-colors"
              >
                取消
              </Link>
              <button
                type="submit"
                disabled={isLoading}
                className="flex items-center gap-2 px-8 py-3 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-medium hover:from-violet-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    创建中...
                  </>
                ) : (
                  <>
                    <Plus className="w-5 h-5" />
                    创建小说
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}