'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { MainLayout } from '@/components/layout/main-layout';
import { apiClient } from '@/lib/api-client';
import { fetchWithAuth } from '@/lib/fetch-with-auth';
import {
  ArrowLeft,
  Loader2,
  Clock,
  FileText,
  Edit2,
  Trash2,
  Sparkles
} from 'lucide-react';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface Novel {
  id: string;
  title: string;
  description?: string;
  genre?: string;
  status: string;
}

interface Chapter {
  id: string;
  novel_id: string;
  title: string;
  content?: string;
  chapter_number: number;
  word_count: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export default function ChapterViewPage() {
  const params = useParams();
  const novelId = params.id as string;
  const chapterId = params.chapter_id as string;
  const router = useRouter();

  const [novel, setNovel] = useState<Novel | null>(null);
  const [chapter, setChapter] = useState<Chapter | null>(null);
  const [loading, setLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);

  // 加载小说和章节数据
  const loadData = async () => {
    setLoading(true);
    try {
      // 加载小说
      const novelData = await apiClient.getNovel(novelId);
      setNovel(novelData);

      // 加载章节
      const chapterData = await apiClient.getChapter(chapterId);
      setChapter(chapterData);
    } catch (err) {
      console.error('加载失败:', err);
      alert('加载失败');
      router.push(`/novels/${novelId}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [novelId, chapterId]);

  // 删除章节
  const handleDelete = async () => {
    if (!confirm('确定要删除这个章节吗？')) return;

    try {
      await apiClient.deleteChapter(chapterId);
      router.push(`/novels/${novelId}`);
    } catch (err) {
      console.error('删除失败:', err);
      alert('删除失败');
    }
  };

  // AI重生成章节内容
  const handleAIGenerate = async () => {
    if (!confirm('确定要使用AI重新生成章节内容吗？这将覆盖当前内容。')) return;

    setIsGenerating(true);
    try {
      const response = await fetchWithAuth(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/chapters/regenerate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chapter_id: chapterId,
          prompt: `请基于小说《${novel?.title}》的剧情，生成第${chapter?.chapter_number}章"${chapter?.title}"的完整内容。`
        })
      });

      if (response.ok) {
        await loadData();
        alert('AI生成完成！');
      } else {
        const errData = await response.json();
        const msg = typeof errData.detail === 'string'
          ? errData.detail
          : Array.isArray(errData.detail)
            ? errData.detail.map((e: any) => e.msg || JSON.stringify(e)).join('; ')
            : 'AI生成失败，请检查LLM配置';
        alert(msg);
      }
    } catch (err: any) {
      console.error('AI生成失败:', err);
      alert(err.message || 'AI生成失败');
    } finally {
      setIsGenerating(false);
    }
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
          <span className="ml-3 text-white/60">加载中...</span>
        </div>
      </MainLayout>
    );
  }

  if (!novel || !chapter) {
    return (
      <MainLayout>
        <div className="text-center py-20">
          <p className="text-white/60">章节不存在</p>
          <Link href={`/novels/${novelId}`}>
            <Button className="mt-4 bg-violet-600">返回小说</Button>
          </Link>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 顶部导航 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href={`/novels/${novelId}`}>
              <Button variant="ghost" className="text-white/60 hover:text-white">
                <ArrowLeft className="w-4 h-4 mr-2" />
                返回
              </Button>
            </Link>
            <div>
              <p className="text-white/40 text-sm">{novel.title}</p>
              <h1 className="text-xl font-bold text-white">第{chapter.chapter_number}章 {chapter.title}</h1>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link href={`/novels/${novelId}/chapters/${chapterId}/edit`}>
              <Button variant="outline" className="border-blue-500/50 text-blue-400">
                <Edit2 className="w-4 h-4 mr-2" />
                编辑
              </Button>
            </Link>
            <Button
              variant="outline"
              className="border-violet-500/50 text-violet-400"
              onClick={handleAIGenerate}
              disabled={isGenerating}
            >
              {isGenerating ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4 mr-2" />
              )}
              AI生成
            </Button>
            <Button
              variant="outline"
              className="border-red-500/50 text-red-400 hover:bg-red-500/10"
              onClick={handleDelete}
            >
              <Trash2 className="w-4 h-4 mr-2" />
              删除
            </Button>
          </div>
        </div>

        {/* 章节信息 */}
        <Card className="bg-white/5 border-white/10">
          <CardContent className="p-4">
            <div className="flex items-center gap-6 text-sm text-white/40">
              <span className="flex items-center gap-1">
                <FileText className="w-4 h-4" />
                第{chapter.chapter_number}章
              </span>
              <span className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                {chapter.word_count} 字
              </span>
              <span className={`px-2 py-0.5 rounded text-xs ${
                chapter.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                'bg-yellow-500/20 text-yellow-400'
              }`}>
                {chapter.status === 'completed' ? '已完成' : '草稿'}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* 章节内容 */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white">章节内容</CardTitle>
          </CardHeader>
          <CardContent>
            {chapter.content ? (
              <div className="prose prose-invert max-w-none">
                <div className="text-white/80 whitespace-pre-wrap leading-relaxed">
                  {chapter.content}
                </div>
              </div>
            ) : (
              <div className="text-center py-12">
                <FileText className="w-12 h-12 mx-auto text-white/20" />
                <p className="text-white/40 mt-4">暂无内容</p>
                <Link href={`/novels/${novelId}/chapters/${chapterId}/edit`}>
                  <Button className="mt-4 bg-violet-600 hover:bg-violet-700">
                    <Edit2 className="w-4 h-4 mr-2" />
                    编写章节
                  </Button>
                </Link>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
