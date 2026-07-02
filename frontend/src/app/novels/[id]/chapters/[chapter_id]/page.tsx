'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { MainLayout } from '@/components/layout/main-layout';
import { ModelCapabilitySelector } from '@/components/model-capability-selector';
import { useToast } from '@/components/ui/toast';
import {
  BookOpen,
  ArrowLeft,
  Save,
  Loader2,
  AlertCircle,
  FileText,
  Users,
  Sparkles,
  Film,
  Clock,
  RefreshCw
} from 'lucide-react';
import Link from 'next/link';

import { fetchWithAuth } from '@/lib/fetch-with-auth';
import {
  getDefaultConfigForCapability,
  SavedModelConfig,
} from '@/lib/model-configs';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface Chapter {
  id: string;
  novel_id: string;
  title: string;
  content: string;
  chapter_number: number;
  word_count: number;
  status: string;
  created_at: string;
  updated_at: string;
}

interface Novel {
  id: string;
  title: string;
  description?: string;
}

export default function ChapterDetailPage() {
  const { toast } = useToast();
  const params = useParams();
  const router = useRouter();
  const novelId = params.id as string;
  const chapterId = params.chapter_id as string;

  const [chapter, setChapter] = useState<Chapter | null>(null);
  const [novel, setNovel] = useState<Novel | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRewriteConfirm, setShowRewriteConfirm] = useState(false);

  // 编辑状态
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [hasChanges, setHasChanges] = useState(false);
  const [aiInstruction, setAiInstruction] = useState('');
  const [targetWordCount, setTargetWordCount] = useState(1800);
  const [modelConfigs, setModelConfigs] = useState<SavedModelConfig[]>([]);
  const [textModelConfigId, setTextModelConfigId] = useState('');

  useEffect(() => {
    if (novelId && chapterId) {
      loadChapter();
      loadModelConfigs();
    }
  }, [novelId, chapterId]);

  const loadModelConfigs = async () => {
    try {
      const response = await fetchWithAuth(`${API_BASE}/llm/configs`);
      if (!response.ok) return;
      const configs = await response.json();
      const list = Array.isArray(configs) ? configs : [];
      setModelConfigs(list);
      const textDefault = getDefaultConfigForCapability(list, 'text');
      if (textDefault) setTextModelConfigId(textDefault.id);
    } catch (err) {
      console.error('加载模型配置失败:', err);
    }
  };

  const loadChapter = async () => {
    setLoading(true);
    try {
      const [chapterRes, novelRes] = await Promise.all([
        fetchWithAuth(`${API_BASE}/chapters/${chapterId}`),
        fetchWithAuth(`${API_BASE}/novels/${novelId}`)
      ]);

      if (chapterRes.ok) {
        const data = await chapterRes.json();
        setChapter(data);
        setTitle(data.title);
        setContent(data.content || '');
        setHasChanges(false);
      } else {
        throw new Error('章节不存在');
      }

      if (novelRes.ok) {
        setNovel(await novelRes.json());
      }
    } catch (err: any) {
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const saveChapter = async (options: { silent?: boolean } = {}) => {
    if (!title.trim()) {
      if (!options.silent) {
        toast({ title: '请输入章节标题', type: 'info' });
      }
      return null;
    }

    setSaving(true);
    try {
      const response = await fetchWithAuth(`${API_BASE}/chapters/${chapterId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          content
        })
      });

      if (response.ok) {
        const updated = await response.json();
        setChapter(updated);
        setTitle(updated.title || title);
        setContent(updated.content || '');
        setHasChanges(false);
        if (!options.silent) {
          toast({ title: '保存成功', type: 'success' });
        }
        return updated;
      } else {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || '保存失败');
      }
    } catch (err: any) {
      if (!options.silent) {
        toast({ title: '保存失败', description: err.message || '请稍后重试。', type: 'error' });
      }
      return null;
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    await saveChapter();
  };

  const applyGeneratedChapter = (updated: Chapter, message: string) => {
    setChapter(updated);
    setTitle(updated.title || title);
    setContent(updated.content || '');
    setHasChanges(false);
    toast({ title: message, type: 'success' });
  };

  const runChapterAI = async (mode: 'rewrite' | 'extend' | 'polish') => {
    if (!chapter?.id) {
      toast({ title: '请先加载章节信息', type: 'info' });
      return;
    }
    if (mode !== 'rewrite' && !content.trim()) {
      toast({ title: '请先编写一些内容', description: '续写或润色需要已有正文。', type: 'info' });
      return;
    }

    if (hasChanges) {
      const saved = await saveChapter({ silent: true });
      if (!saved) return;
    }

    setIsGenerating(true);
    try {
      const response = await fetchWithAuth(`${API_BASE}/chapters/${chapterId}/ai-assist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode,
          instruction: aiInstruction.trim() || undefined,
          target_word_count: targetWordCount,
          sync_story_bible: true,
          model_config_id: textModelConfigId || undefined,
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || 'AI处理失败');
      }

      const updated = await response.json();
      const message = mode === 'rewrite'
        ? '章节已智能编写并保存'
        : mode === 'extend'
          ? '章节已续写并保存'
          : '章节已润色并保存';
      applyGeneratedChapter(updated, message);
    } catch (err: any) {
      toast({ title: 'AI 处理失败', description: err.message || '请稍后重试。', type: 'error' });
    } finally {
      setIsGenerating(false);
    }
  };

  // 监听内容变化
  useEffect(() => {
    if (chapter) {
      setHasChanges(title !== chapter.title || content !== (chapter.content || ''));
    }
  }, [title, content, chapter]);

  if (loading) {
    return (
      <MainLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-violet-500" />
        </div>
      </MainLayout>
    );
  }

  if (error || !chapter) {
    return (
      <MainLayout>
        <div className="text-center py-12">
          <AlertCircle className="w-12 h-12 mx-auto mb-4 text-red-500" />
          <h2 className="text-xl font-bold text-white mb-2">{error || '章节不存在'}</h2>
          <Button onClick={() => router.push(`/novels/${novelId}`)}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            返回小说
          </Button>
        </div>
      </MainLayout>
    );
  }

  const wordCount = content.replace(/\s/g, '').length;

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 顶部导航 */}
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex min-w-0 items-start gap-3 sm:gap-4">
            <Button variant="ghost" onClick={() => router.push(`/novels/${novelId}`)}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              返回
            </Button>
            <div className="min-w-0">
              <h1 className="flex items-center gap-2 break-words text-2xl font-bold text-white">
                <FileText className="w-6 h-6 shrink-0" />
                {chapter.novel_id ? `第${chapter.chapter_number}章` : '章节编辑'}
              </h1>
              {novel && (
                <p className="text-white/60 text-sm mt-1">
                  《{novel.title}》
                </p>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 lg:justify-end">
            <Badge variant="outline" className="text-white/60 border-white/20">
              <Clock className="w-3 h-3 mr-1" />
              {wordCount} 字
            </Badge>
            {hasChanges && (
              <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
                未保存
              </Badge>
            )}
            <Button
              onClick={handleSave}
              disabled={saving || !hasChanges}
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

        {/* AI辅助写作 */}
        <Card className="bg-violet-500/5 border-violet-500/20">
          <CardHeader className="pb-3">
            <CardTitle className="text-violet-300 text-base flex items-center gap-2">
              <Sparkles className="w-4 h-4" />
              AI智能编写
              {isGenerating && <Loader2 className="w-4 h-4 animate-spin ml-2" />}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-[1fr_160px] gap-3">
              <Input
                value={aiInstruction}
                onChange={(e) => setAiInstruction(e.target.value)}
                placeholder="补充要求，例如：强化主角动机、保持雨夜场景、结尾承接下一章"
                className="bg-white/10 border-white/20 text-white placeholder:text-white/40"
              />
              <Input
                type="number"
                min={300}
                max={8000}
                value={targetWordCount}
                onChange={(e) => setTargetWordCount(Math.max(300, Math.min(8000, parseInt(e.target.value) || 1800)))}
                className="bg-white/10 border-white/20 text-white"
                title="目标字数"
              />
            </div>
            <ModelCapabilitySelector
              capability="text"
              configs={modelConfigs}
              value={textModelConfigId}
              onChange={setTextModelConfigId}
              disabled={isGenerating || saving}
              title="章节写作模型"
              description="智能编写、续写和润色会使用文本生成能力，并自动承接全书设定、前后章节和实体上下文。"
              compact
            />
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                className="border-violet-500/50 text-violet-300 hover:bg-violet-500/10"
                onClick={() => setShowRewriteConfirm(true)}
                disabled={isGenerating || saving}
              >
                {isGenerating ? (
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4 mr-1" />
                )}
                智能编写
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="border-blue-500/50 text-blue-300 hover:bg-blue-500/10"
                onClick={() => runChapterAI('extend')}
                disabled={isGenerating || saving}
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
                className="border-green-500/50 text-green-300 hover:bg-green-500/10"
                onClick={() => runChapterAI('polish')}
                disabled={isGenerating || saving}
              >
                {isGenerating ? (
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4 mr-1" />
                )}
                润色内容
              </Button>
            </div>
            <p className="text-xs text-white/40">
              AI 会读取小说简介、前后章节、Story Bible 以及已抽取的人物、场景、道具、事件；生成后立即保存并同步一致性上下文。
            </p>
          </CardContent>
        </Card>

        {/* 章节内容编辑 */}
        <Card className="bg-white/5 border-white/10">
          <CardContent className="space-y-4 p-4 sm:p-6">
            <div>
              <label className="text-white/80 mb-2 block">章节标题</label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="输入章节标题"
                className="bg-white/10 border-white/20 text-white text-lg"
              />
            </div>

            <div>
              <label className="text-white/80 mb-2 block">章节内容</label>
              <Textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="开始创作您的章节内容…"
                className="min-h-[clamp(420px,58vh,760px)] resize-y bg-white/10 border-white/20 text-base leading-7 text-white"
              />
              <p className="mt-2 text-xs text-white/40">
                长章节可直接在页面滚动，也可以拖动正文框右下角调整写作区高度。
              </p>
            </div>
          </CardContent>
        </Card>

        {/* 底部快捷操作 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="bg-gradient-to-br from-violet-600/20 to-purple-600/20 border-violet-500/30 cursor-pointer hover:border-violet-500/50 transition-colors">
            <Link href={`/novels/${novelId}`}>
              <CardContent className="p-4 text-center">
                <BookOpen className="w-8 h-8 mx-auto mb-2 text-violet-400" />
                <div className="text-white font-medium">返回小说</div>
                <div className="text-white/60 text-sm">查看小说详情</div>
              </CardContent>
            </Link>
          </Card>
          <Card className="bg-gradient-to-br from-blue-600/20 to-cyan-600/20 border-blue-500/30 cursor-pointer hover:border-blue-500/50 transition-colors">
            <Link href={`/characters?novel_id=${novelId}`}>
              <CardContent className="p-4 text-center">
                <Users className="w-8 h-8 mx-auto mb-2 text-blue-400" />
                <div className="text-white font-medium">角色管理</div>
                <div className="text-white/60 text-sm">管理小说角色</div>
              </CardContent>
            </Link>
          </Card>
          <Card className="bg-gradient-to-br from-green-600/20 to-emerald-600/20 border-green-500/30 cursor-pointer hover:border-green-500/50 transition-colors">
            <Link href={`/scripts?novel_id=${novelId}&chapter_id=${chapterId}`}>
              <CardContent className="p-4 text-center">
                <Film className="w-8 h-8 mx-auto mb-2 text-green-400" />
                <div className="text-white font-medium">基于本章创作</div>
                <div className="text-white/60 text-sm">生成分镜剧本</div>
              </CardContent>
            </Link>
          </Card>
        </div>
      </div>
      <ConfirmDialog
        open={showRewriteConfirm}
        title="智能编写本章"
        description="确定要根据小说整体设定、前后章节和 Story Bible 智能编写本章吗？当前正文会被替换。"
        confirmText="智能编写"
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
