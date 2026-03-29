'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import { fetchWithAuth } from '@/lib/fetch-with-auth';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
import {
  BookOpen,
  Plus,
  Loader2,
  AlertCircle,
  Layers,
  FileText,
  Edit2,
  Trash2,
  Sparkles,
  ArrowLeft,
  Search,
  Clock
} from 'lucide-react';
import Link from 'next/link';
import { Suspense } from 'react';

interface Chapter {
  id: string;
  title: string;
  content?: string;
  word_count?: number;
  status: string;
  created_at: string;
  updated_at: string;
}

const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  writing: '创作中',
  completed: '已完成'
};

function ChaptersContent() {
  const params = useParams();
  const novelId = params.id as string;

  const [novel, setNovel] = useState<{ title: string } | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [generatingChapter, setGeneratingChapter] = useState(false);
  const [creatingChapterId, setCreatingChapterId] = useState<string | null>(null);

  // 加载小说信息
  const loadNovel = async () => {
    try {
      const response = await fetchWithAuth(`${API_BASE}/novels/${novelId}`);
      if (response.ok) {
        const data = await response.json();
        setNovel(data);
      }
    } catch (err) {
      console.error('加载小说失败:', err);
    }
  };

  // 加载章节列表
  const loadChapters = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchWithAuth(`${API_BASE}/chapters/novel/${novelId}`);
      if (!response.ok) {
        throw new Error('加载章节失败');
      }
      const data: Chapter[] = await response.json();
      setChapters(data || []);
    } catch (err: any) {
      console.error('加载章节失败:', err);
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (novelId) {
      loadNovel();
      loadChapters();
    }
  }, [novelId]);

  // AI 生成章节
  const handleGenerateChapter = async () => {
    if (!confirm('确定要使用AI自动生成章节大纲吗？')) return;
    setGeneratingChapter(true);
    try {
      const response = await fetchWithAuth(`${API_BASE}/chapters/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ novel_id: novelId })
      });
      if (response.ok) {
        await loadChapters();
        alert('章节生成成功！');
      } else {
        const errData = await response.json();
        const msg = typeof errData.detail === 'string'
          ? errData.detail
          : Array.isArray(errData.detail)
            ? errData.detail.map((e: any) => e.msg || JSON.stringify(e)).join('; ')
            : '生成失败';
        throw new Error(msg);
      }
    } catch (err: any) {
      console.error('生成章节失败:', err);
      alert(err.message || '生成章节失败');
    } finally {
      setGeneratingChapter(false);
    }
  };

  // 创建新章节
  const handleCreateChapter = async () => {
    setCreatingChapterId('new');
    try {
      const response = await fetchWithAuth(`${API_BASE}/chapters`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          novel_id: novelId,
          title: `第 ${chapters.length + 1} 章`,
          content: '',
          status: 'draft'
        })
      });
      if (response.ok) {
        await loadChapters();
      } else {
        throw new Error('创建失败');
      }
    } catch (err) {
      console.error('创建章节失败:', err);
      alert('创建章节失败');
    } finally {
      setCreatingChapterId(null);
    }
  };

  // 删除章节
  const handleDeleteChapter = async (chapterId: string) => {
    if (!confirm('确定要删除这个章节吗？')) return;
    try {
      const response = await fetchWithAuth(`${API_BASE}/chapters/${chapterId}`, {
        method: 'DELETE'
      });
      if (response.ok) {
        setChapters(chapters.filter(c => c.id !== chapterId));
      }
    } catch (err) {
      console.error('删除章节失败:', err);
      alert('删除失败');
    }
  };

  // 筛选章节
  const filteredChapters = chapters.filter(chapter =>
    chapter.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href={`/novels/${novelId}`}>
              <Button variant="ghost" size="icon" className="text-white/60 hover:text-white">
                <ArrowLeft className="w-5 h-5" />
              </Button>
            </Link>
            <div>
              <div className="flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-violet-400" />
                <h1 className="text-2xl font-bold text-white">
                  {novel?.title ? `${novel.title} - 章节管理` : '章节管理'}
                </h1>
              </div>
              <p className="text-white/60 mt-1 ml-7">{chapters.length} 个章节</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleGenerateChapter}
              disabled={generatingChapter}
              className="border-violet-500/50 text-violet-400 hover:bg-violet-500/10"
            >
              {generatingChapter ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1" />}
              AI 生成章节
            </Button>
            <Button
              size="sm"
              onClick={handleCreateChapter}
              disabled={creatingChapterId !== null}
              className="bg-violet-600 hover:bg-violet-700"
            >
              {creatingChapterId !== null ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Plus className="w-4 h-4 mr-1" />}
              创建章节
            </Button>
          </div>
        </div>

        {/* 搜索 */}
        <Card className="bg-white/5 border-white/10">
          <CardContent className="p-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
              <Input
                placeholder="搜索章节标题..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/40"
              />
            </div>
          </CardContent>
        </Card>

        {/* 加载状态 */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
            <span className="ml-3 text-white/60">加载中...</span>
          </div>
        )}

        {/* 错误提示 */}
        {error && (
          <Card className="bg-red-500/10 border-red-500/30">
            <CardContent className="p-4 flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-400" />
              <span className="text-red-300">{error}</span>
              <Button variant="outline" size="sm" onClick={loadChapters} className="ml-auto border-red-500/50 text-red-400">
                重试
              </Button>
            </CardContent>
          </Card>
        )}

        {/* 章节列表 */}
        {!loading && !error && (
          filteredChapters.length > 0 ? (
            <div className="grid gap-4">
              {filteredChapters.map((chapter, index) => (
                <Card
                  key={chapter.id}
                  className="bg-white/5 border-white/10 hover:border-violet-500/30 transition-colors"
                >
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-4 flex-1 min-w-0">
                        <div className="w-10 h-10 rounded-lg bg-violet-500/20 flex items-center justify-center flex-shrink-0">
                          <span className="text-violet-300 font-bold">{index + 1}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-3">
                            <h3 className="text-white font-medium truncate">{chapter.title}</h3>
                            <span className={`px-2 py-0.5 rounded text-xs flex-shrink-0 ${
                              chapter.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                              chapter.status === 'writing' ? 'bg-blue-500/20 text-blue-400' :
                              'bg-yellow-500/20 text-yellow-400'
                            }`}>
                              {STATUS_LABELS[chapter.status] || chapter.status}
                            </span>
                          </div>
                          <div className="flex items-center gap-4 mt-1 text-sm text-white/40">
                            {chapter.word_count && (
                              <span className="flex items-center gap-1">
                                <FileText className="w-3 h-3" />
                                {chapter.word_count.toLocaleString()} 字
                              </span>
                            )}
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {chapter.updated_at?.split('T')[0]}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <Link href={`/novels/${novelId}/chapters/${chapter.id}`}>
                          <Button variant="ghost" size="icon" className="text-white/60 hover:text-white">
                            <Edit2 className="w-4 h-4" />
                          </Button>
                        </Link>
                        <Link href={`/scripts?chapter_id=${chapter.id}`}>
                          <Button variant="ghost" size="sm" className="text-blue-400 hover:text-blue-300">
                            <FileText className="w-4 h-4 mr-1" />
                            剧本
                          </Button>
                        </Link>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteChapter(chapter.id)}
                          className="text-red-400/60 hover:text-red-400"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <Card className="bg-white/5 border-white/10">
              <CardContent className="p-12 text-center">
                <Layers className="w-12 h-12 mx-auto text-white/20" />
                <p className="text-white/40 mt-4">
                  {searchQuery ? '没有找到匹配的章节' : '暂无章节'}
                </p>
                {!searchQuery && (
                  <Button
                    onClick={handleCreateChapter}
                    disabled={creatingChapterId !== null}
                    className="mt-4 bg-violet-600 hover:bg-violet-700"
                  >
                    {creatingChapterId !== null ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Plus className="w-4 h-4 mr-1" />}
                    创建第一章
                  </Button>
                )}
              </CardContent>
            </Card>
          )
        )}

        {/* 统计信息 */}
        {!loading && !error && chapters.length > 0 && (
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-2xl font-bold text-white">{chapters.length}</div>
                  <div className="text-sm text-white/60">总章节数</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-green-400">
                    {chapters.filter(c => c.status === 'completed').length}
                  </div>
                  <div className="text-sm text-white/60">已完成</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-violet-400">
                    {chapters.reduce((sum, c) => sum + (c.word_count || 0), 0).toLocaleString()}
                  </div>
                  <div className="text-sm text-white/60">总字数</div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </MainLayout>
  );
}

export default function NovelChaptersPage() {
  return (
    <Suspense fallback={
      <MainLayout>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
          <span className="ml-3 text-white/60">加载中...</span>
        </div>
      </MainLayout>
    }>
      <ChaptersContent />
    </Suspense>
  );
}
