'use client';

import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { MainLayout } from '@/components/layout/main-layout';
import { StoryWorkbenchPanel, getStoryExcerpt } from '@/components/novels/story-workbench-panel';
import { useToast } from '@/components/ui/toast';
import { apiClient } from '@/lib/api-client';
import {
  ArrowLeft,
  Save,
  Loader2,
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
  const { toast } = useToast();
  const params = useParams();
  const novelId = params.id as string;
  const chapterId = params.chapter_id as string;
  const router = useRouter();

  const [novel, setNovel] = useState<Novel | null>(null);
  const [chapter, setChapter] = useState<Chapter | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [showRewriteConfirm, setShowRewriteConfirm] = useState(false);
  const [aiInstruction, setAiInstruction] = useState('');
  const [targetWordCount, setTargetWordCount] = useState(1800);
  const autoSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSavedRef = useRef({ title: '', content: '' });

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
      lastSavedRef.current = {
        title: chapterData.title || '',
        content: chapterData.content || ''
      };
    } catch (err) {
      console.error('加载失败:', err);
      toast({ title: '加载失败', description: '将返回小说详情页。', type: 'error' });
      router.push(`/novels/${novelId}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [novelId, chapterId]);

  const persistChapter = async (
    nextData = formData,
    options: { navigate?: boolean; silent?: boolean } = {}
  ) => {
    if (!nextData.title.trim()) {
      if (!options.silent) {
        toast({ title: '请输入章节标题', type: 'info' });
      }
      return null;
    }

    if (
      nextData.title === lastSavedRef.current.title &&
      nextData.content === lastSavedRef.current.content
    ) {
      if (options.navigate) {
        router.push(`/novels/${novelId}/chapters/${chapterId}`);
      }
      return chapter;
    }

    setSaving(true);
    setSaveState('saving');
    try {
      const updated = await apiClient.updateChapter(chapterId, {
        title: nextData.title,
        content: nextData.content,
        status: nextData.content.length > 100 ? 'completed' : 'draft'
      });
      setChapter(updated);
      lastSavedRef.current = {
        title: updated.title || '',
        content: updated.content || ''
      };
      setSaveState('saved');
      if (!options.silent) {
        toast({ title: '保存成功', type: 'success' });
      }
      if (options.navigate) {
        router.push(`/novels/${novelId}/chapters/${chapterId}`);
      }
      return updated;
    } catch (err) {
      console.error('保存失败:', err);
      setSaveState('error');
      if (!options.silent) {
        toast({ title: '保存失败', type: 'error' });
      }
      return null;
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    if (loading || !chapter) return;
    if (
      formData.title === lastSavedRef.current.title &&
      formData.content === lastSavedRef.current.content
    ) {
      return;
    }

    if (autoSaveTimer.current) {
      clearTimeout(autoSaveTimer.current);
    }
    autoSaveTimer.current = setTimeout(() => {
      persistChapter(formData, { silent: true });
    }, 1200);

    return () => {
      if (autoSaveTimer.current) {
        clearTimeout(autoSaveTimer.current);
      }
    };
  }, [formData.title, formData.content, loading, chapterId]);

  // 保存章节
  const handleSave = async () => {
    if (!formData.title.trim()) {
      toast({ title: '请输入章节标题', type: 'info' });
      return;
    }
    await persistChapter(formData, { navigate: true });
  };

  const applyGeneratedChapter = (updated: Chapter, message: string) => {
    setChapter(updated);
    const nextForm = {
      title: updated.title || formData.title,
      content: updated.content || ''
    };
    setFormData(nextForm);
    lastSavedRef.current = nextForm;
    setSaveState('saved');
    toast({ title: message, type: 'success' });
  };

  const runChapterAI = async (mode: 'rewrite' | 'extend' | 'polish') => {
    if (!chapter?.id) {
      toast({ title: '请先加载章节信息', type: 'info' });
      return;
    }
    if (mode === 'polish' && !formData.content.trim()) {
      toast({ title: '请先编写一些内容', description: '润色需要已有正文；空章节可以直接点击生成本章内容。', type: 'info' });
      return;
    }

    await persistChapter(formData, { silent: true });
    setIsGenerating(true);
    try {
      const updated = await apiClient.aiAssistChapter(chapterId, {
        mode,
        instruction: aiInstruction.trim() || undefined,
        target_word_count: targetWordCount,
        sync_story_bible: true
      });
      const message = mode === 'rewrite'
        ? '章节已重新生成并保存'
        : mode === 'extend'
          ? '章节已续写并保存'
          : '章节已润色并保存';
      applyGeneratedChapter(updated, message);
    } catch (err: any) {
      console.error('AI处理失败:', err);
      toast({ title: 'AI 处理失败', description: err?.message || '请稍后重试。', type: 'error' });
    } finally {
      setIsGenerating(false);
    }
  };

  // AI生成内容
  const handleAIGenerate = async () => {
    if (!novel?.title) {
      toast({ title: '请先加载小说信息', type: 'info' });
      return;
    }
    setShowRewriteConfirm(true);
  };

  // AI续写
  const handleAIExtend = async () => {
    await runChapterAI('extend');
  };

  // AI润色
  const handleAIPolish = async () => {
    await runChapterAI('polish');
  };

  if (loading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
          <span className="ml-3 text-white/60">加载中…</span>
        </div>
      </MainLayout>
    );
  }

  if (!novel || !chapter) {
    return (
      <MainLayout>
        <div className="text-center py-20">
          <p className="text-white/60">章节不存在</p>
          <Button asChild className="mt-4 bg-violet-600">
            <Link href={`/novels/${novelId}`}>返回小说</Link>
          </Button>
        </div>
      </MainLayout>
    );
  }

  const wordCount = formData.content.replace(/\s/g, '').length;
  const canContinueFromContext = wordCount === 0;
  const contentPreview = getStoryExcerpt(
    formData.content,
    '这个章节还没有正文，适合让 AI 根据前文、Story Bible 和实体上下文生成本章内容。',
    260
  );

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 顶部导航 */}
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex min-w-0 items-start gap-3 sm:gap-4">
            <Button asChild variant="ghost" className="text-white/60 hover:text-white">
              <Link href={`/novels/${novelId}/chapters/${chapterId}`}>
                <ArrowLeft className="w-4 h-4 mr-2" />
                返回
              </Link>
            </Button>
            <div className="min-w-0">
              <p className="text-white/40 text-sm">{novel.title}</p>
              <h1 className="break-words text-xl font-bold text-white">编辑章节</h1>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 lg:justify-end">
            <span className={`text-xs ${
              saveState === 'error' ? 'text-red-400' :
              saveState === 'saving' ? 'text-yellow-400' :
              saveState === 'saved' ? 'text-green-400' :
              'text-white/40'
            }`}>
              {saveState === 'saving' ? '自动保存中…' :
                saveState === 'saved' ? '已自动保存' :
                  saveState === 'error' ? '自动保存失败' : '编辑会自动保存'}
            </span>
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

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px] xl:items-start">
          <div className="space-y-4">
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
              <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
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
                  className="min-h-[clamp(460px,62vh,820px)] resize-y bg-white/5 border-white/10 text-base leading-7 text-white"
                  placeholder="开始编写章节内容…"
                />
                <p className="mt-2 text-xs text-white/40">
                  长章节可直接滚动页面编辑，也可以拖动正文框右下角调整写作区高度。
                </p>
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

          <StoryWorkbenchPanel
            heading="章节写作助手"
            description="边写边看正文摘要、保存状态和 AI 辅助动作，减少在页面里来回寻找按钮。"
            title={formData.title || chapter.title || '未命名章节'}
            subtitle={`《${novel.title}》 · 第 ${chapter.chapter_number} 章`}
            excerptLabel="当前正文预览"
            excerpt={contentPreview}
            metrics={[
              { label: '字数', value: `${wordCount} 字` },
              {
                label: '保存',
                value: saveState === 'saving' ? '自动保存中' : saveState === 'saved' ? '已保存' : saveState === 'error' ? '失败' : '待编辑',
              },
            ]}
            actions={
              <>
                <Input
                  value={aiInstruction}
                  onChange={(e) => setAiInstruction(e.target.value)}
                  placeholder="补充要求，例如：强化女主视角、保留雨夜场景、结尾接下一章追击"
                  className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
                <Input
                  type="number"
                  min={300}
                  max={8000}
                  value={targetWordCount}
                  onChange={(e) => setTargetWordCount(Math.max(300, Math.min(8000, parseInt(e.target.value) || 1800)))}
                  className="bg-white/5 border-white/10 text-white"
                  title="目标字数"
                />
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 xl:grid-cols-1">
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-violet-500/50 text-violet-300 hover:bg-violet-500/10"
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
                    className="border-blue-500/50 text-blue-300 hover:bg-blue-500/10"
                    onClick={handleAIExtend}
                    disabled={isGenerating}
                  >
                    {isGenerating ? (
                      <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                    ) : (
                      <RefreshCw className="w-4 h-4 mr-1" />
                    )}
                    {canContinueFromContext ? '生成本章内容' : '续写内容'}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-green-500/50 text-green-300 hover:bg-green-500/10"
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
                </div>
              </>
            }
            footer={
              <p className="text-xs leading-5 text-white/40">
                AI 会读取小说简介、前后章节、Story Bible 及已抽取的人物/场景/道具/事件，生成后立即保存并同步一致性上下文。
              </p>
            }
          />
        </div>
      </div>
      <ConfirmDialog
        open={showRewriteConfirm}
        title="重新生成本章"
        description="确定要根据小说整体设定、前后章节和 Story Bible 重新生成本章吗？当前正文会被替换。"
        confirmText="重新生成"
        loading={isGenerating}
        onOpenChange={setShowRewriteConfirm}
        onConfirm={async () => {
          await runChapterAI('rewrite');
          setShowRewriteConfirm(false);
        }}
      />
    </MainLayout>
  );
}
