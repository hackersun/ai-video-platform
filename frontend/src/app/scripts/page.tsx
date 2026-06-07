'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { 
  FileText, 
  Plus, 
  Edit2, 
  Trash2,
  Search,
  Video,
  Clock,
  ChevronRight,
  MoreVertical,
  Copy,
  Download,
  Eye,
  Play,
  CheckCircle,
  AlertCircle,
  Save,
  Loader2,
  Sparkles,
  Wand2,
  BookOpen,
  LayoutGrid,
  RefreshCw
} from 'lucide-react';
import Link from 'next/link';
import { fetchWithAuth } from '@/lib/fetch-with-auth';
import { apiClient } from '@/lib/api-client';
import { ModelCapabilitySelector } from '@/components/model-capability-selector';
import {
  getDefaultConfigForCapability,
  SavedModelConfig,
} from '@/lib/model-configs';
import { useToast } from '@/components/ui/toast';

// 剧本数据类型
interface Script {
  id: string;
  title: string;
  description?: string;
  content?: string;
  genre?: string;
  style?: string;
  duration?: number;
  status: 'draft' | 'writing' | 'completed';
  novel_id?: string;
  chapter_id?: string;
  created_at: string;
  updated_at: string;
}

// 小说数据类型
interface Novel {
  id: string;
  title: string;
  description?: string;
  genre?: string;
}

interface Chapter {
  id: string;
  novel_id?: string;
  title: string;
  chapter_number?: number;
}

interface GeneratedScriptDraft {
  title: string;
  description: string;
  content: string;
  genre?: string;
  style?: string;
  novel_id?: string;
  chapter_id?: string;
}

const STATUS_LABELS = {
  draft: '草稿',
  writing: '连载中',
  completed: '已完成'
};

const STATUS_COLORS = {
  draft: 'bg-yellow-500/20 text-yellow-400',
  writing: 'bg-blue-500/20 text-blue-400',
  completed: 'bg-green-500/20 text-green-400'
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export default function ScriptsPage() {
  const { toast } = useToast();
  const [scripts, setScripts] = useState<Script[]>([]);
  const [novels, setNovels] = useState<Novel[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFilterNovelId, setSelectedFilterNovelId] = useState('');
  const [selectedFilterChapterId, setSelectedFilterChapterId] = useState('');
  const [filtersInitialized, setFiltersInitialized] = useState(false);
  const [aiChapters, setAiChapters] = useState<Chapter[]>([]);
  const [activeTab, setActiveTab] = useState('all');
  const [showModal, setShowModal] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editingScript, setEditingScript] = useState<Script | null>(null);
  const [modelConfigs, setModelConfigs] = useState<SavedModelConfig[]>([]);
  const [textModelConfigId, setTextModelConfigId] = useState('');
  
  // AI生成相关状态
  const [showAIGenerateModal, setShowAIGenerateModal] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [aiGenerateType, setAiGenerateType] = useState<'from_novel' | 'custom'>('custom');
  const [selectedNovelId, setSelectedNovelId] = useState('');
  const [selectedChapterId, setSelectedChapterId] = useState('');
  const [customPrompt, setCustomPrompt] = useState('');
  const [generationResult, setGenerationResult] = useState<string | null>(null);
  const [generatedScriptDraft, setGeneratedScriptDraft] = useState<GeneratedScriptDraft | null>(null);
  const [generationContext, setGenerationContext] = useState<any | null>(null);
  const [loadingGenerationContext, setLoadingGenerationContext] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Script | null>(null);
  const [deletingScript, setDeletingScript] = useState(false);
  const [storyboardTarget, setStoryboardTarget] = useState<Script | null>(null);
  const [creatingStoryboard, setCreatingStoryboard] = useState(false);

  const loadChapters = async (novelId: string) => {
    const list = await fetchChaptersForNovel(novelId);
    setChapters(list);
    return list;
  };

  const fetchChaptersForNovel = async (novelId: string) => {
    if (!novelId) {
      return [];
    }
    try {
      const response = await fetchWithAuth(`${API_BASE}/chapters/novel/${novelId}`);
      if (response.ok) {
        const data = await response.json();
        const list = Array.isArray(data) ? data : [];
        return list;
      }
    } catch (err) {
      console.error('加载章节失败:', err);
    }
    return [];
  };
  
  // 表单数据
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    genre: '',
    style: ''
  });

  // 加载剧本数据
  const loadScripts = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchWithAuth(`${API_BASE}/scripts`);
      if (!response.ok) {
        throw new Error('加载失败');
      }
      const data = await response.json();
      setScripts(data || []);
    } catch (err) {
      console.error('加载剧本失败:', err);
      setError('加载失败，请检查后端服务');
      setScripts([]);
    } finally {
      setLoading(false);
    }
  };

  // 加载小说列表
  const loadNovels = async () => {
    try {
      const response = await fetchWithAuth(`${API_BASE}/novels`);
      if (response.ok) {
        const data = await response.json();
        setNovels(data || []);
      }
    } catch (err) {
      console.error('加载小说失败:', err);
    }
  };

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

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const novelId = params.get('novel_id') || '';
    const chapterId = params.get('chapter_id') || '';
    if (novelId) setSelectedFilterNovelId(novelId);
    if (chapterId) setSelectedFilterChapterId(chapterId);
    setFiltersInitialized(true);
    loadScripts();
    loadNovels();
    loadModelConfigs();
  }, []);

  useEffect(() => {
    if (!filtersInitialized) return;
    if (selectedFilterNovelId) {
      loadChapters(selectedFilterNovelId);
    } else {
      setChapters([]);
      setSelectedFilterChapterId('');
    }
  }, [filtersInitialized, selectedFilterNovelId]);

  // 筛选剧本
  const filteredScripts = scripts.filter(script => {
    const matchesSearch = script.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          script.description?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesNovel = !selectedFilterNovelId || script.novel_id === selectedFilterNovelId;
    const matchesChapter = !selectedFilterChapterId || script.chapter_id === selectedFilterChapterId;
    const matchesStatus = activeTab === 'all' || script.status === activeTab;
    return matchesSearch && matchesNovel && matchesChapter && matchesStatus;
  });

  // 打开创建弹窗
  const handleCreate = () => {
    setEditingScript(null);
    setFormData({
      title: '',
      description: '',
      genre: '',
      style: ''
    });
    setShowModal(true);
  };

  // 打开AI生成弹窗
  const handleOpenAIGenerate = () => {
    setAiGenerateType('from_novel');
    const defaultNovelId = selectedFilterNovelId || (novels.length > 0 ? novels[0].id : '');
    setSelectedNovelId(defaultNovelId);
    setSelectedChapterId(selectedFilterChapterId || '');
    if (defaultNovelId) {
      fetchChaptersForNovel(defaultNovelId).then((list) => {
        setAiChapters(list);
        if (!selectedFilterChapterId && list.length > 0) {
          setSelectedChapterId(list[0].id);
        }
      });
    } else {
      setAiChapters([]);
    }
    setCustomPrompt('');
    setGenerationResult(null);
    setGeneratedScriptDraft(null);
    setGenerationContext(null);
    setShowAIGenerateModal(true);
  };

  const loadGenerationContext = async (chapterId: string, style?: string, genre?: string) => {
    if (!chapterId) {
      setGenerationContext(null);
      return;
    }
    setLoadingGenerationContext(true);
    try {
      const context = await apiClient.getScriptGenerateContext(chapterId, {
        style: style || formData.style || 'anime',
        genre: genre || formData.genre || undefined,
      });
      setGenerationContext(context);
    } catch (err: any) {
      setGenerationContext({ error: err?.message || '上下文加载失败' });
    } finally {
      setLoadingGenerationContext(false);
    }
  };

  useEffect(() => {
    if (showAIGenerateModal && aiGenerateType === 'from_novel' && selectedChapterId) {
      loadGenerationContext(selectedChapterId);
    }
  }, [showAIGenerateModal, aiGenerateType, selectedChapterId]);

  // AI生成剧本
  const handleAIGenerate = async () => {
    if (aiGenerateType === 'from_novel' && !selectedChapterId) {
      toast({ title: '请选择章节', description: '需要先选择要改编的章节。', type: 'error' });
      return;
    }
    if (aiGenerateType === 'custom' && !customPrompt.trim()) {
      toast({ title: '请输入剧本描述', description: '补充描述后再开始生成。', type: 'error' });
      return;
    }

    setIsGenerating(true);
    setGenerationResult(null);
    setGeneratedScriptDraft(null);

    try {
      if (aiGenerateType === 'from_novel') {
        const response = await fetchWithAuth(`${API_BASE}/scripts/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            chapter_id: selectedChapterId,
            style: formData.style || 'anime',
            genre: formData.genre || undefined,
            model_config_id: textModelConfigId || undefined,
          }),
        });
        if (!response.ok) {
          const error = await response.json().catch(() => ({}));
          throw new Error(error.detail || error.message || `AI 生成失败：HTTP ${response.status}`);
        }
        const script = await response.json();
        setGenerationResult(script.content || script.description || '生成成功');
        const check = await apiClient.checkScriptConsistency(script.id).catch(() => null);
        if (check) {
          setGenerationContext((prev: any) => ({
            ...(prev || {}),
            latest_check: check,
            generated_script_id: script.id,
          }));
        }
        await loadScripts();
        return;
      }

      const contextNovelId = selectedFilterNovelId || selectedNovelId || undefined;
      const contextChapterId = selectedFilterChapterId || selectedChapterId || undefined;
      const contextNovel = novels.find((item) => item.id === contextNovelId);
      const contextChapter = [...aiChapters, ...chapters].find((item) => item.id === contextChapterId);
      const chapterTitle = contextChapter?.title?.trim();
      const draftTitle = chapterTitle ? `${chapterTitle} 剧本` : '自定义剧本';
      const draftGenre = formData.genre || contextNovel?.genre || '';
      const draftStyle = formData.style || 'anime';

      const result = await apiClient.assistScriptEdit({
        title: draftTitle,
        description: customPrompt.trim(),
        content: customPrompt.trim(),
        genre: draftGenre || undefined,
        style: draftStyle,
        mode: 'short_drama',
        model_config_id: textModelConfigId || undefined,
      });

      const content = (result.content || customPrompt.trim()).trim();
      const title = (result.title || draftTitle).trim();
      const description = (result.description || customPrompt.trim()).trim().slice(0, 500);
      setGenerationResult(content || `${title}\n${description}`);
      setGeneratedScriptDraft({
        title,
        description,
        content: content || description,
        genre: draftGenre || undefined,
        style: draftStyle,
        novel_id: contextNovelId,
        chapter_id: contextChapterId,
      });
    } catch (err) {
      console.error('AI生成失败:', err);
      const message = err instanceof Error ? err.message : 'AI 生成失败';
      toast({ title: 'AI 生成失败', description: message, type: 'error' });
    } finally {
      setIsGenerating(false);
    }
  };

  // 应用生成的剧本
  const handleApplyGenerated = async () => {
    if (!generationResult) return;
    if (aiGenerateType === 'from_novel') {
      setShowAIGenerateModal(false);
      return;
    }

    // 解析生成的剧本内容，创建新剧本
    const title = generatedScriptDraft?.title || generationResult.match(/^#\s+(.+)$/m)?.[1] || 'AI生成剧本';
    const description = generatedScriptDraft?.description || generationResult.split('---')[0].replace(/^#.*$/mg, '').trim().slice(0, 200);

    setIsSaving(true);
    try {
      const response = await fetchWithAuth(`${API_BASE}/scripts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          novel_id: generatedScriptDraft?.novel_id,
          chapter_id: generatedScriptDraft?.chapter_id,
          title,
          description,
          content: generatedScriptDraft?.content || generationResult,
          genre: generatedScriptDraft?.genre || undefined,
          style: generatedScriptDraft?.style || undefined
        })
      });

      if (response.ok) {
        await loadScripts();
        setShowAIGenerateModal(false);
        toast({ title: '剧本已创建', description: title, type: 'success' });
      } else {
        throw new Error('保存失败');
      }
    } catch (err) {
      console.error('保存失败:', err);
      toast({ title: '保存失败', description: '请重试。', type: 'error' });
    } finally {
      setIsSaving(false);
    }
  };

  // 打开编辑弹窗
  const handleEdit = (script: Script) => {
    setEditingScript(script);
    setFormData({
      title: script.title,
      description: script.description || '',
      genre: script.genre || '',
      style: script.style || ''
    });
    setShowModal(true);
  };

  // 保存剧本
  const handleSave = async () => {
    if (!formData.title.trim()) {
      toast({ title: '请输入剧本标题', description: '标题是保存剧本的必填项。', type: 'error' });
      return;
    }

    setIsSaving(true);
    try {
      const payload = {
        title: formData.title,
        description: formData.description,
        genre: formData.genre || undefined,
        style: formData.style || undefined
      };

      const response = editingScript
        ? await fetchWithAuth(`${API_BASE}/scripts/${editingScript.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...payload, status: editingScript.status })
          })
        : await fetchWithAuth(`${API_BASE}/scripts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });

      if (response.ok) {
        await loadScripts();
        setShowModal(false);
        toast({
          title: editingScript ? '剧本已更新' : '剧本已创建',
          description: formData.title,
          type: 'success',
        });
      } else {
        throw new Error('保存失败');
      }
    } catch (err) {
      console.error('保存失败:', err);
      toast({ title: '保存失败', description: '请重试。', type: 'error' });
    } finally {
      setIsSaving(false);
    }
  };

  // 删除剧本
  const handleDelete = async (id: string) => {
    try {
      const response = await fetchWithAuth(`${API_BASE}/scripts/${id}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        setScripts(scripts.filter(s => s.id !== id));
        toast({ title: '剧本已删除', description: '列表已更新。', type: 'success' });
      } else {
        throw new Error('删除失败');
      }
    } catch (err) {
      console.error('删除失败:', err);
      toast({ title: '删除失败', description: '请重试。', type: 'error' });
    }
  };

  // 复制剧本
  const handleDuplicate = async (script: Script) => {
    try {
      const response = await fetchWithAuth(`${API_BASE}/scripts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: `${script.title} (副本)`,
          description: script.description,
          genre: script.genre,
          style: script.style
        })
      });
      
      if (response.ok) {
        await loadScripts();
        toast({ title: '剧本已复制', description: `${script.title} (副本)`, type: 'success' });
      } else {
        throw new Error('复制失败');
      }
    } catch (err) {
      console.error('复制失败:', err);
      toast({ title: '复制失败', description: '请重试。', type: 'error' });
    }
  };

  // 生成分镜
  const handleGenerateStoryboard = async (script: Script) => {
    try {
      // 调用AI生成storyboard
      const response = await fetchWithAuth(`${API_BASE}/storyboards`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: `${script.title} - 分镜`,
          description: script.description,
          script_id: script.id
        })
      });

      if (response.ok) {
        await response.json();
        toast({ title: '分镜已创建', description: '正在跳转到分镜页面。', type: 'success' });
        window.location.href = '/storyboards';
      } else {
        throw new Error('创建失败');
      }
    } catch (err) {
      console.error('生成分镜失败:', err);
      toast({ title: '生成分镜失败', description: '请重试。', type: 'error' });
    }
  };

  // 格式化时长
  const formatDuration = (minutes?: number) => {
    if (!minutes) return '0:00';
    const mins = Math.floor(minutes);
    const secs = Math.round((minutes - mins) * 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // 统计
  const stats = {
    total: scripts.length,
    draft: scripts.filter(s => s.status === 'draft').length,
    writing: scripts.filter(s => s.status === 'writing').length,
    completed: scripts.filter(s => s.status === 'completed').length
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">剧本管理</h1>
            <p className="text-white/60 mt-1">管理视频剧本和分镜脚本</p>
          </div>
          <div className="flex flex-wrap gap-3 sm:justify-end">
            <Button 
              variant="outline"
              className="border-violet-500/50 text-violet-400 hover:bg-violet-600/20"
              onClick={handleOpenAIGenerate}
            >
              <Sparkles className="w-4 h-4 mr-2" />
              AI生成剧本
            </Button>
            <Button className="bg-blue-600 hover:bg-blue-700" onClick={handleCreate}>
              <Plus className="w-4 h-4 mr-2" />
              创建剧本
            </Button>
          </div>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-white">{stats.total}</div>
              <div className="text-sm text-white/60">全部剧本</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-yellow-400">{stats.draft}</div>
              <div className="text-sm text-white/60">草稿</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-blue-400">{stats.writing}</div>
              <div className="text-sm text-white/60">连载中</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-green-400">{stats.completed}</div>
              <div className="text-sm text-white/60">已完成</div>
            </CardContent>
          </Card>
        </div>

        {/* 搜索栏 */}
        <Card className="bg-white/5 border-white/10">
          <CardContent className="p-4">
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_13rem_13rem]">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <Input
                  placeholder="搜索剧本标题或描述…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
              </div>
              <select
                value={selectedFilterNovelId}
                onChange={(e) => {
                  setSelectedFilterNovelId(e.target.value);
                  setSelectedFilterChapterId('');
                }}
                className="w-full min-w-0 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
              >
                <option value="">全部小说</option>
                {novels.map((novel) => (
                  <option key={novel.id} value={novel.id}>{novel.title}</option>
                ))}
              </select>
              <select
                value={selectedFilterChapterId}
                onChange={(e) => setSelectedFilterChapterId(e.target.value)}
                disabled={!selectedFilterNovelId}
                className="w-full min-w-0 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white disabled:opacity-50"
              >
                <option value="">全部章节</option>
                {chapters.map((chapter) => (
                  <option key={chapter.id} value={chapter.id}>
                    {chapter.chapter_number ? `第${chapter.chapter_number}章 ` : ''}{chapter.title}
                  </option>
                ))}
              </select>
            </div>
          </CardContent>
        </Card>

        {/* 加载状态 */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
            <span className="ml-3 text-white/60">加载中…</span>
          </div>
        )}

        {/* 错误提示 */}
        {error && (
          <Card className="bg-red-500/10 border-red-500/30">
            <CardContent className="p-4 flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-400" />
              <span className="text-red-300">{error}</span>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={loadScripts}
                className="ml-auto border-red-500/50 text-red-400"
              >
                重试
              </Button>
            </CardContent>
          </Card>
        )}

        {/* 状态标签页 */}
        {!loading && !error && (
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="h-auto max-w-full flex-wrap justify-start bg-white/5">
              <TabsTrigger value="all" className="data-[state=active]:bg-blue-600">全部</TabsTrigger>
              <TabsTrigger value="draft" className="data-[state=active]:bg-blue-600">草稿</TabsTrigger>
              <TabsTrigger value="writing" className="data-[state=active]:bg-blue-600">连载中</TabsTrigger>
              <TabsTrigger value="completed" className="data-[state=active]:bg-blue-600">已完成</TabsTrigger>
            </TabsList>

            <TabsContent value={activeTab} className="mt-4">
              {filteredScripts.length > 0 ? (
                <div className="grid gap-4">
                  {filteredScripts.map((script) => (
                    <Card key={script.id} className="bg-white/5 border-white/10 hover:border-blue-500/30 transition-colors">
                      <CardContent className="p-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <Link href={`/scripts/${script.id}`} className="min-w-0 flex-1 block">
                            <div className="flex flex-wrap items-center gap-3">
                              <FileText className="h-5 w-5 shrink-0 text-blue-400" />
                              <h3 className="min-w-0 break-words text-lg font-semibold text-white transition-colors hover:text-blue-400">{script.title}</h3>
                              <span className={`px-2 py-0.5 rounded text-xs ${STATUS_COLORS[script.status]}`}>
                                {STATUS_LABELS[script.status]}
                              </span>
                            </div>
                            {script.description && (
                              <p className="mt-1 break-words text-sm text-white/40">{script.description}</p>
                            )}
                            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-white/40">
                              {script.genre && <span>{script.genre}</span>}
                              {script.style && <span>{script.style}</span>}
                              {script.novel_id && (
                                <span>{novels.find((novel) => novel.id === script.novel_id)?.title || '已绑定小说'}</span>
                              )}
                              {script.chapter_id && (
                                <span>
                                  {chapters.find((chapter) => chapter.id === script.chapter_id)?.title || '已绑定章节'}
                                </span>
                              )}
                              {script.chapter_id && (
                                <Link
                                  href={`/storyboards?script_id=${script.id}&novel_id=${script.novel_id || ''}&chapter_id=${script.chapter_id}`}
                                  className="text-blue-300 hover:text-blue-200"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  生成分镜
                                </Link>
                              )}
                              <span className="flex items-center gap-1">
                                <Clock className="w-4 h-4" />
                                {formatDuration(script.duration)}
                              </span>
                              <span>更新于 {new Date(script.updated_at).toLocaleDateString()}</span>
                            </div>
                          </Link>
                          <div className="flex flex-wrap items-center gap-2 sm:justify-end" onClick={(e) => e.stopPropagation()}>
                            {script.status === 'completed' && (
                              <Button 
                                variant="ghost" 
                                size="sm"
                                className="text-violet-400 hover:text-violet-300"
                                onClick={() => setStoryboardTarget(script)}
                              >
                                <LayoutGrid className="w-4 h-4 mr-1" />
                                生成分镜
                              </Button>
                            )}
                            {script.status === 'completed' && (
                              <Button asChild variant="ghost" size="sm" className="text-violet-400 hover:text-violet-300">
                                <Link href={`/video-generation?script=${script.id}`}>
                                  <Play className="w-4 h-4 mr-1" />
                                  生成视频
                                </Link>
                              </Button>
                            )}
                            <Button asChild variant="ghost" size="icon" className="text-white/60 hover:text-white" aria-label={`查看《${script.title}》`} title="查看">
                              <Link href={`/scripts/${script.id}`}>
                                <Eye className="w-4 h-4" />
                              </Link>
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              aria-label={`编辑《${script.title}》`}
                              title="编辑"
                              className="text-white/60 hover:text-white"
                              onClick={() => handleEdit(script)}
                            >
                              <Edit2 className="w-4 h-4" />
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              aria-label={`复制《${script.title}》`}
                              title="复制"
                              className="text-white/60 hover:text-white"
                              onClick={() => handleDuplicate(script)}
                            >
                              <Copy className="w-4 h-4" />
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              aria-label={`删除《${script.title}》`}
                              title="删除"
                              className="text-white/60 hover:text-red-400"
                              onClick={() => setDeleteTarget(script)}
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
                <div className="text-center py-12">
                  <FileText className="w-12 h-12 mx-auto text-white/20" />
                  <p className="text-white/40 mt-4">没有找到剧本</p>
                  <div className="flex gap-2 justify-center mt-4">
                    <Button 
                      variant="outline"
                      className="border-violet-500/50 text-violet-400"
                      onClick={handleOpenAIGenerate}
                    >
                      <Sparkles className="w-4 h-4 mr-2" />
                      AI生成
                    </Button>
                    <Button className="bg-blue-600 hover:bg-blue-700" onClick={handleCreate}>
                      创建剧本
                    </Button>
                  </div>
                </div>
              )}
            </TabsContent>
          </Tabs>
        )}
        <ConfirmDialog
          open={Boolean(deleteTarget)}
          title="删除剧本"
          description={`确定要删除「${deleteTarget?.title || ''}」吗？此操作无法撤销。`}
          confirmText="删除"
          destructive
          loading={deletingScript}
          onOpenChange={(open) => {
            if (!open) setDeleteTarget(null);
          }}
          onConfirm={async () => {
            if (!deleteTarget) return;
            setDeletingScript(true);
            try {
              await handleDelete(deleteTarget.id);
              setDeleteTarget(null);
            } finally {
              setDeletingScript(false);
            }
          }}
        />
        <ConfirmDialog
          open={Boolean(storyboardTarget)}
          title="生成分镜"
          description={`是否为「${storyboardTarget?.title || ''}」创建分镜？创建后会跳转到分镜页面。`}
          confirmText="生成分镜"
          loading={creatingStoryboard}
          onOpenChange={(open) => {
            if (!open) setStoryboardTarget(null);
          }}
          onConfirm={async () => {
            if (!storyboardTarget) return;
            setCreatingStoryboard(true);
            try {
              await handleGenerateStoryboard(storyboardTarget);
              setStoryboardTarget(null);
            } finally {
              setCreatingStoryboard(false);
            }
          }}
        />
      </div>

      {/* 创建/编辑剧本弹窗 */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-w-lg border-white/20 bg-slate-950/95">
            <DialogHeader className="pr-10">
              <DialogTitle>
                {editingScript ? '编辑剧本' : '创建剧本'}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-white/60 mb-2 block">剧本标题 *</label>
                <Input
                  placeholder="例如：第一章：星际启航"
                  value={formData.title}
                  onChange={(e) => setFormData({...formData, title: e.target.value})}
                  className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
              </div>
              
              <div>
                <label className="text-sm text-white/60 mb-2 block">剧本描述</label>
                <Textarea
                  placeholder="简要描述剧本内容…"
                  value={formData.description}
                  onChange={(e) => setFormData({...formData, description: e.target.value})}
                  rows={3}
                  className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-white/60 mb-2 block">题材</label>
                  <Input
                    placeholder="例如：仙侠"
                    value={formData.genre}
                    onChange={(e) => setFormData({...formData, genre: e.target.value})}
                    className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                  />
                </div>
                <div>
                  <label className="text-sm text-white/60 mb-2 block">风格</label>
                  <Input
                    placeholder="例如：热血"
                    value={formData.style}
                    onChange={(e) => setFormData({...formData, style: e.target.value})}
                    className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                  />
                </div>
              </div>
              
              <div className="flex gap-3 pt-4">
                <Button 
                  variant="outline" 
                  onClick={() => setShowModal(false)}
                  className="flex-1 border-white/20 text-white"
                >
                  取消
                </Button>
                <Button 
                  onClick={handleSave}
                  disabled={isSaving}
                  className="flex-1 bg-blue-600 hover:bg-blue-700"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      保存中…
                    </>
                  ) : (
                    <>
                      <Save className="w-4 h-4 mr-2" />
                      保存剧本
                    </>
                  )}
                </Button>
              </div>
            </div>
        </DialogContent>
      </Dialog>

      {/* AI生成剧本弹窗 */}
      <Dialog open={showAIGenerateModal} onOpenChange={setShowAIGenerateModal}>
        <DialogContent className="max-w-2xl border-white/20 bg-slate-950/95">
            <DialogHeader className="pr-10">
              <DialogTitle className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-violet-400" />
                AI生成剧本
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              {/* 生成方式选择 */}
              <div>
                <label className="text-sm text-white/60 mb-2 block">生成方式</label>
                <div className="flex gap-2">
                  <Button
                    variant={aiGenerateType === 'from_novel' ? 'default' : 'outline'}
                    onClick={() => setAiGenerateType('from_novel')}
                    className={aiGenerateType === 'from_novel' ? 'bg-violet-600' : 'border-white/20'}
                  >
                    <BookOpen className="w-4 h-4 mr-2" />
                    基于小说
                  </Button>
                  <Button
                    variant={aiGenerateType === 'custom' ? 'default' : 'outline'}
                    onClick={() => setAiGenerateType('custom')}
                    className={aiGenerateType === 'custom' ? 'bg-violet-600' : 'border-white/20'}
                  >
                    <Wand2 className="w-4 h-4 mr-2" />
                    自定义描述
                  </Button>
                </div>
              </div>

              <ModelCapabilitySelector
                capability="text"
                configs={modelConfigs}
                value={textModelConfigId}
                onChange={setTextModelConfigId}
                disabled={isGenerating}
                title="剧本生成模型"
                description="从章节改编剧本或根据自定义描述生成剧本草稿时，都会使用这里选择的文本模型配置。"
              />

              {/* 选择小说 */}
              {aiGenerateType === 'from_novel' && (
                <div className="space-y-3">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div>
                      <label className="text-sm text-white/60 mb-2 block">选择小说</label>
                      <select
                        value={selectedNovelId}
                        onChange={(e) => {
                          const nextNovelId = e.target.value;
                          setSelectedNovelId(nextNovelId);
                          setSelectedChapterId('');
                          setGenerationContext(null);
                          if (nextNovelId) {
                            fetchChaptersForNovel(nextNovelId).then((list) => {
                              setAiChapters(list);
                              if (list.length > 0) setSelectedChapterId(list[0].id);
                            });
                          } else {
                            setAiChapters([]);
                          }
                        }}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white"
                      >
                        <option value="">选择小说…</option>
                        {novels.map(novel => (
                          <option key={novel.id} value={novel.id}>{novel.title}</option>
                        ))}
                      </select>
                      {novels.length === 0 && (
                        <p className="text-white/40 text-sm mt-1">暂无可用小说，请先创建小说</p>
                      )}
                    </div>
                    <div>
                      <label className="text-sm text-white/60 mb-2 block">选择章节</label>
                      <select
                        value={selectedChapterId}
                        onChange={(e) => setSelectedChapterId(e.target.value)}
                        disabled={!selectedNovelId}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white disabled:opacity-50"
                      >
                        <option value="">选择章节…</option>
                        {aiChapters.map((chapter) => (
                          <option key={chapter.id} value={chapter.id}>
                            {chapter.chapter_number ? `第${chapter.chapter_number}章 ` : ''}{chapter.title}
                          </option>
                        ))}
                      </select>
                      {selectedNovelId && aiChapters.length === 0 && (
                        <p className="text-white/40 text-sm mt-1">该小说暂无章节，请先创建章节内容</p>
                      )}
                    </div>
                  </div>

                  <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <div className="text-sm font-medium text-white/80">生成上下文预览</div>
                      {loadingGenerationContext && <Loader2 className="h-4 w-4 animate-spin text-violet-300" />}
                    </div>
                    {generationContext?.error ? (
                      <div className="text-sm text-red-300">{generationContext.error}</div>
                    ) : generationContext ? (
                      <div className="space-y-2 text-sm text-white/60">
                        <div className="flex flex-wrap gap-2">
                          <span className="rounded bg-white/10 px-2 py-1">人物 {generationContext.summary?.counts?.characters || 0}</span>
                          <span className="rounded bg-white/10 px-2 py-1">场景 {generationContext.summary?.counts?.scenes || 0}</span>
                          <span className="rounded bg-white/10 px-2 py-1">道具 {generationContext.summary?.counts?.props || 0}</span>
                          <span className="rounded bg-white/10 px-2 py-1">事件 {generationContext.summary?.counts?.events || 0}</span>
                          <span className="rounded bg-white/10 px-2 py-1">关系 {generationContext.summary?.counts?.relationships || 0}</span>
                        </div>
                        <div>前情：{generationContext.previous_chapter?.title || '无'}；后续约束：{generationContext.next_chapter?.title || '无'}</div>
                        <div className="line-clamp-2">人物：{(generationContext.summary?.characters || []).join('、') || '未提取'}</div>
                        <div className="line-clamp-2">场景/道具/事件：{[
                          ...(generationContext.summary?.scenes || []),
                          ...(generationContext.summary?.props || []),
                          ...(generationContext.summary?.events || []),
                        ].slice(0, 8).join('、') || '未提取'}</div>
                        {generationContext.latest_check && (
                          <div className={generationContext.latest_check.issue_count ? 'text-yellow-200' : 'text-green-300'}>
                            生成后一致性检查：{generationContext.latest_check.issue_count || 0} 个提示
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-sm text-white/40">选择章节后会自动加载 Story Bible、人物关系、事件线和章节承接信息。</div>
                    )}
                  </div>
                </div>
              )}

              {/* 自定义描述 */}
              {aiGenerateType === 'custom' && (
                <div>
                  <label className="text-sm text-white/60 mb-2 block">剧本描述</label>
                  <Textarea
                    placeholder="描述你想要生成的剧本内容…\n例如：\n- 仙侠风格\n- 主人公离开山门\n- 遇到神秘老者\n- 获得传承"
                    value={customPrompt}
                    onChange={(e) => setCustomPrompt(e.target.value)}
                    rows={6}
                    className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                  />
                </div>
              )}

              {/* 生成按钮 */}
              <Button
                onClick={handleAIGenerate}
                disabled={isGenerating || (aiGenerateType === 'from_novel' && !selectedChapterId) || (aiGenerateType === 'custom' && !customPrompt.trim())}
                className="w-full bg-violet-600 hover:bg-violet-700"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    AI生成中…
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    开始生成
                  </>
                )}
              </Button>

              {/* 生成结果 */}
              {generationResult && (
                <div className="mt-4">
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm text-white/60">生成结果</label>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => navigator.clipboard.writeText(generationResult)}
                      className="text-white/60 hover:text-white"
                    >
                      <Copy className="w-4 h-4 mr-1" />
                      复制
                    </Button>
                  </div>
                  <div className="bg-white/5 border border-white/10 rounded-lg p-4 max-h-80 overflow-y-auto">
                    <pre className="text-white/80 text-sm whitespace-pre-wrap font-sans">
                      {generationResult}
                    </pre>
                  </div>
                  
                  <div className="flex gap-3 mt-4">
                    <Button
                      onClick={handleAIGenerate}
                      disabled={isGenerating}
                      variant="outline"
                      className="flex-1 border-white/20"
                    >
                      <RefreshCw className="w-4 h-4 mr-2" />
                      重新生成
                    </Button>
                    <Button
                      onClick={handleApplyGenerated}
                      disabled={isSaving}
                      className="flex-1 bg-green-600 hover:bg-green-700"
                    >
                      {isSaving ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <CheckCircle className="w-4 h-4 mr-2" />
                      )}
                      {aiGenerateType === 'from_novel' ? '已创建，关闭' : '创建剧本'}
                    </Button>
                  </div>
                </div>
              )}
            </div>
        </DialogContent>
      </Dialog>
    </MainLayout>
  );
}
