'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { MainLayout } from '@/components/layout/main-layout';
import { apiClient } from '@/lib/api-client';
import {
  ArrowLeft,
  Save,
  Loader2,
  Clock,
  FileText,
  Sparkles,
  RefreshCw
} from 'lucide-react';
import Link from 'next/link';
import { useRouter, useParams } from 'next/navigation';

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

export default function ChapterEditPage() {
  const params = useParams();
  const novelId = params.id as string;
  const chapterId = params.chapter_id as string;
  const router = useRouter();

  const [novel, setNovel] = useState<Novel | null>(null);
  const [chapter, setChapter] = useState<Chapter | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  const [formData, setFormData] = useState({
    title: '',
    content: ''
  });

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
      setFormData({
        title: chapterData.title || '',
        content: chapterData.content || ''
      });
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

  // 保存章节
  const handleSave = async () => {
    if (!formData.title.trim()) {
      alert('请输入章节标题');
      return;
    }

    setSaving(true);
    try {
      await apiClient.updateChapter(chapterId, {
        title: formData.title,
        content: formData.content,
        status: formData.content.length > 100 ? 'completed' : 'draft'
      });
      alert('保存成功');
      router.push(`/novels/${novelId}`);
    } catch (err) {
      console.error('保存失败:', err);
      alert('保存失败');
    } finally {
      setSaving(false);
    }
  };

  // AI生成内容
  const handleAIGenerate = async () => {
    if (!novel?.title) {
      alert('请先加载小说信息');
      return;
    }
    setIsGenerating(true);
    try {
      const result = await apiClient.autoGenerate(
        `请为小说《${novel.title}》生成一章节内容，包括标题和正文。`,
        'novel',
        ''
      );
      // API返回 result.result
      const content = result?.result || result?.content || result?.plan;
      if (content) {
        // 如果返回的是包含标题和内容的格式，尝试解析
        const titleMatch = content.match(/^第[一二三四五六七八九十百千零\d]+章[^\n]*/);
        const chapterTitle = titleMatch ? titleMatch[0].replace(/^第[一二三四五六七八九十百千零\d]+章/, '').trim() : '';
        const bodyContent = content.replace(/^第[一二三四五六七八九十百千零\d]+章[^\n]*\n?/, '');

        setFormData(prev => ({
          ...prev,
          title: chapterTitle || prev.title,
          content: bodyContent || content
        }));
        alert('内容已生成');
      } else {
        alert(result?.result || 'AI生成功能暂不可用，请配置LLM');
      }
    } catch (err: any) {
      console.error('AI生成失败:', err);
      alert(err?.message || 'AI生成失败');
    } finally {
      setIsGenerating(false);
    }
  };

  // AI续写
  const handleAIExtend = async () => {
    if (!formData.content.trim()) {
      alert('请先编写一些内容');
      return;
    }

    setIsGenerating(true);
    try {
      const result = await apiClient.autoGenerate(
        `请续写以下内容：\n\n${formData.content}`,
        'novel',
        ''
      );
      const newContent = result?.result || result?.content;
      if (newContent) {
        setFormData(prev => ({ ...prev, content: prev.content + '\n\n' + newContent }));
        alert('续写完成');
      } else {
        alert(result?.result || 'AI续写功能暂不可用，请配置LLM');
      }
    } catch (err: any) {
      console.error('AI续写失败:', err);
      alert(err?.message || 'AI续写失败');
    } finally {
      setIsGenerating(false);
    }
  };

  // AI润色
  const handleAIPolish = async () => {
    if (!formData.content.trim()) {
      alert('请先编写内容');
      return;
    }

    setIsGenerating(true);
    try {
      const result = await apiClient.autoGenerate(
        `请润色以下内容，使其更加流畅生动：\n\n${formData.content}`,
        'novel',
        ''
      );
      const polishedContent = result?.result || result?.content;
      if (polishedContent) {
        setFormData(prev => ({ ...prev, content: polishedContent }));
        alert('润色完成');
      } else {
        alert(result?.result || 'AI润色功能暂不可用，请配置LLM');
      }
    } catch (err: any) {
      console.error('AI润色失败:', err);
      alert(err?.message || 'AI润色失败');
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

  const wordCount = formData.content.replace(/\s/g, '').length;

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 顶部导航 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href={`/novels/${novelId}/chapters/${chapterId}`}>
              <Button variant="ghost" className="text-white/60 hover:text-white">
                <ArrowLeft className="w-4 h-4 mr-2" />
                返回
              </Button>
            </Link>
            <div>
              <p className="text-white/40 text-sm">{novel.title}</p>
              <h1 className="text-xl font-bold text-white">编辑章节</h1>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              onClick={handleSave}
              disabled={saving}
              className="bg-violet-600 hover:bg-violet-700"
            >
              {saving ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Save className="w-4 h-4 mr-2" />
              )}
              保存
            </Button>
          </div>
        </div>

        {/* AI辅助 */}
        <Card className="bg-violet-500/5 border-violet-500/20">
          <CardHeader className="pb-3">
            <CardTitle className="text-violet-400 text-base flex items-center gap-2">
              <Sparkles className="w-4 h-4" />
              AI辅助写作
              {isGenerating && <Loader2 className="w-4 h-4 animate-spin ml-2" />}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              className="border-violet-500/50 text-violet-400 hover:bg-violet-500/10"
              onClick={handleAIGenerate}
              disabled={isGenerating}
            >
              {isGenerating ? (
                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4 mr-1" />
              )}
              重新生成
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="border-blue-500/50 text-blue-400 hover:bg-blue-500/10"
              onClick={handleAIExtend}
              disabled={isGenerating}
            >
              {isGenerating ? (
                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4 mr-1" />
              )}
              续写内容
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="border-green-500/50 text-green-400 hover:bg-green-500/10"
              onClick={handleAIPolish}
              disabled={isGenerating}
            >
              {isGenerating ? (
                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4 mr-1" />
              )}
              润色内容
            </Button>
          </CardContent>
        </Card>

        {/* 章节标题 */}
        <Card className="bg-white/5 border-white/10">
          <CardContent className="p-4">
            <label className="text-white/60 text-sm mb-2 block">章节标题</label>
            <Input
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="bg-white/5 border-white/10 text-white text-lg"
              placeholder="输入章节标题"
            />
          </CardContent>
        </Card>

        {/* 章节内容 */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-white">章节正文</CardTitle>
            <div className="flex items-center gap-4 text-sm text-white/40">
              <span className="flex items-center gap-1">
                <FileText className="w-4 h-4" />
                {wordCount} 字
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <Textarea
              value={formData.content}
              onChange={(e) => setFormData({ ...formData, content: e.target.value })}
              className="bg-white/5 border-white/10 text-white min-h-[500px]"
              placeholder="开始编写章节内容..."
            />
          </CardContent>
        </Card>

        {/* 保存按钮 */}
        <div className="flex justify-center">
          <Button
            onClick={handleSave}
            disabled={saving}
            size="lg"
            className="bg-violet-600 hover:bg-violet-700 px-8"
          >
            {saving ? (
              <Loader2 className="w-5 h-5 mr-2 animate-spin" />
            ) : (
              <Save className="w-5 h-5 mr-2" />
            )}
            保存章节
          </Button>
        </div>
      </div>
    </MainLayout>
  );
}
