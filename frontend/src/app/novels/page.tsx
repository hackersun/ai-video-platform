'use client';

import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { MainLayout } from '@/components/layout/main-layout';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { 
  BookOpen, 
  Plus, 
  Edit2, 
  Trash2,
  Search,
  FileText,
  Users,
  Clock,
  Copy,
  Eye,
  Loader2,
  AlertCircle,
  FileTextIcon,
  Upload,
  CheckCircle
} from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { fetchWithAuth } from '@/lib/fetch-with-auth';
import { apiClient } from '@/lib/api-client';
import { useToast } from '@/components/ui/toast';
import { NovelProductionEntryCard } from '@/components/novels/novel-production-entry-card';
import type { NovelProductionEntry } from '@/lib/studio-types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// 小说数据类型
interface Novel {
  id: string;
  title: string;
  description: string;
  genre: string;
  status: 'draft' | 'writing' | 'completed';
  chapters: number;
  characters: number;
  createdAt: string;
  updatedAt: string;
}

// 后端API返回的小说格式
interface ApiNovel {
  id: string;
  title: string;
  description?: string;
  content?: string;
  genre?: string;
  status: 'draft' | 'writing' | 'completed';
  word_count?: number;
  created_at: string;
  updated_at: string;
}

interface ImportChapter {
  title: string;
  chapter_number: number;
  word_count: number;
  preview: string;
}

// 类型统计
const STATUS_LABELS = {
  draft: '草稿',
  writing: '连载中',
  completed: '已完成'
};

const GENRE_OPTIONS = ['全部', '仙侠', '都市', '科幻', '历史', '言情', '悬疑'];

// 内嵌组件使用 useSearchParams
function NovelsContent() {
  const { toast } = useToast();
  const [novels, setNovels] = useState<Novel[]>([]);
  const [productionEntries, setProductionEntries] = useState<Record<string, NovelProductionEntry>>({});
  const [productionEntriesLoaded, setProductionEntriesLoaded] = useState(false);
  const [productionEntriesFailed, setProductionEntriesFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedGenre, setSelectedGenre] = useState('全部');
  const [activeTab, setActiveTab] = useState('all');
  const [importTitle, setImportTitle] = useState('');
  const [importGenre, setImportGenre] = useState('');
  const [importJobId, setImportJobId] = useState('');
  const [importChapters, setImportChapters] = useState<ImportChapter[]>([]);
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Novel | null>(null);
  const [deleting, setDeleting] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();
  const highlightId = searchParams.get('highlight');
  const productionEntriesRequestRef = useRef(0);

  // 从后端API加载小说
  const loadNovelsFromAPI = async () => {
    const requestId = productionEntriesRequestRef.current + 1;
    productionEntriesRequestRef.current = requestId;
    setLoading(true);
    setError(null);
    setProductionEntriesLoaded(false);
    setProductionEntriesFailed(false);
    try {
      const response = await fetchWithAuth(`${API_BASE}/novels`);
      if (!response.ok) {
        throw new Error('加载失败');
      }
      const data: ApiNovel[] = await response.json();
      if (productionEntriesRequestRef.current !== requestId) return;
      
      // 转换API数据为前端格式
      const convertedNovels: Novel[] = data.map(n => ({
        id: n.id,
        title: n.title,
        description: n.description || n.content?.substring(0, 100) || '',
        genre: n.genre || '其他',
        status: n.status,
        chapters: 0,
        characters: n.word_count || 0,
        createdAt: n.created_at?.split('T')[0] || new Date().toISOString().split('T')[0],
        updatedAt: n.updated_at?.split('T')[0] || new Date().toISOString().split('T')[0]
      }));
      
      setNovels(convertedNovels);
      const ids = convertedNovels.map((item) => item.id);
      if (ids.length) {
        apiClient.getNovelProductionEntries(ids)
          .then((response) => {
            if (productionEntriesRequestRef.current !== requestId) return;
            setProductionEntries(response.entries || {});
            setProductionEntriesFailed(false);
            setProductionEntriesLoaded(true);
          })
          .catch(() => {
            if (productionEntriesRequestRef.current !== requestId) return;
            setProductionEntries({});
            setProductionEntriesFailed(true);
            setProductionEntriesLoaded(true);
          });
      } else {
        setProductionEntries({});
        setProductionEntriesFailed(false);
        setProductionEntriesLoaded(true);
      }
    } catch (err) {
      if (productionEntriesRequestRef.current !== requestId) return;
      console.error('加载小说失败:', err);
      setError('加载失败，请检查后端服务是否启动');
      setNovels([]);
      setProductionEntries({});
      setProductionEntriesFailed(false);
      setProductionEntriesLoaded(true);
    } finally {
      if (productionEntriesRequestRef.current === requestId) {
        setLoading(false);
      }
    }
  };

  // 初始化加载数据
  useEffect(() => {
    loadNovelsFromAPI();
  }, []);

  // 筛选小说
  const filteredNovels = novels.filter(novel => {
    const matchesSearch = novel.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          novel.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesGenre = selectedGenre === '全部' || novel.genre === selectedGenre;
    const matchesStatus = activeTab === 'all' || novel.status === activeTab;
    return matchesSearch && matchesGenre && matchesStatus;
  });

  // 删除小说
  const handleDelete = async (id: string) => {
    try {
      const response = await fetchWithAuth(`${API_BASE}/novels/${id}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        setNovels(novels.filter(n => n.id !== id));
        toast({ title: '删除成功', description: '小说已移除', type: 'success' });
      } else {
        throw new Error('删除失败');
      }
    } catch (err) {
      console.error('删除失败:', err);
      toast({ title: '删除失败', description: '请重试', type: 'error' });
    }
  };

  // 复制小说
  const handleDuplicate = async (novel: Novel) => {
    try {
      const response = await fetchWithAuth(`${API_BASE}/novels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: `${novel.title} (副本)`,
          description: novel.description,
          genre: novel.genre
        })
      });
      
      if (response.ok) {
        await loadNovelsFromAPI();
      } else {
        throw new Error('复制失败');
      }
    } catch (err) {
      console.error('复制失败:', err);
      toast({ title: '复制失败', description: '请重试', type: 'error' });
    }
  };

  // 查看小说
  const handleView = (id: string) => {
    router.push(`/novels/${id}`);
  };

  const handleImportFile = async (file?: File) => {
    if (!file) return;
    if (!/\.(txt|md|markdown)$/i.test(file.name)) {
      setImportMessage('仅支持 .txt、.md 或 .markdown 文件');
      return;
    }

    setImporting(true);
    setImportMessage(null);
    try {
      const preview = await apiClient.previewNovelImport(file);
      setImportJobId(preview.id);
      setImportTitle(preview.title || file.name.replace(/\.(txt|md|markdown)$/i, ''));
      setImportChapters(preview.chapters || []);
      setImportMessage(`已解析 ${preview.chapter_count || 0} 章，请确认后导入`);
    } catch (err: any) {
      setImportMessage(err?.message || '导入预览失败，请检查文件格式');
    } finally {
      setImporting(false);
    }
  };

  const confirmImport = async () => {
    if (!importJobId || !importTitle.trim() || importChapters.length === 0) return;

    setImporting(true);
    setImportMessage(null);
    try {
      const novel = await apiClient.confirmNovelImport({
        job_id: importJobId,
        title: importTitle.trim(),
        genre: importGenre.trim() || undefined,
        tags: importGenre.trim() ? [importGenre.trim()] : [],
      });

      setImportMessage(`导入成功：${importTitle}`);
      toast({ title: '导入成功', description: importTitle, type: 'success' });
      setImportJobId('');
      setImportTitle('');
      setImportGenre('');
      setImportChapters([]);
      await loadNovelsFromAPI();
      router.push(`/novels/${novel.id}`);
    } catch (err: any) {
      setImportMessage(err?.message || '导入失败，请检查后端服务');
      toast({ title: '导入失败', description: err?.message || '请检查后端服务', type: 'error' });
    } finally {
      setImporting(false);
    }
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">小说管理</h1>
            <p className="text-white/60 mt-1">管理您的作品和章节</p>
          </div>
          <Button asChild className="w-full bg-violet-600 hover:bg-violet-700 sm:w-auto">
            <Link href="/novels/new">
              <Plus className="w-4 h-4 mr-2" />
              创建小说
            </Link>
          </Button>
        </div>

        <Card className="bg-white/5 border-white/10">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Upload className="w-5 h-5 text-violet-400" />
              文本导入
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-[1fr_180px_auto] gap-3">
              <Input
                value={importTitle}
                onChange={(e) => setImportTitle(e.target.value)}
                placeholder="导入后小说标题"
                className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
              />
              <Input
                value={importGenre}
                onChange={(e) => setImportGenre(e.target.value)}
                placeholder="类型（可选）"
                className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
              />
              <label className="inline-flex items-center justify-center rounded-md bg-white/10 px-4 py-2 text-sm text-white hover:bg-white/15 cursor-pointer">
                <Upload className="w-4 h-4 mr-2" />
                选择 txt/md
                <input
                  type="file"
                  accept=".txt,.md,text/plain,text/markdown"
                  className="hidden"
                  onChange={(event) => handleImportFile(event.target.files?.[0])}
                />
              </label>
            </div>

            {importChapters.length > 0 && (
              <div className="rounded-lg bg-white/5 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm text-white/70">
                    预览：{importChapters.length} 章 · 首章《{importChapters[0]?.title}》
                  </div>
                  <Button
                    size="sm"
                    onClick={confirmImport}
                    disabled={importing || !importTitle.trim()}
                    className="bg-violet-600 hover:bg-violet-700"
                  >
                    {importing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle className="w-4 h-4 mr-2" />}
                    确认导入
                  </Button>
                </div>
                <div className="mt-2 max-h-24 overflow-y-auto text-xs text-white/50">
                      {importChapters.slice(0, 5).map((chapter) => (
                        <div key={`${chapter.chapter_number}-${chapter.title}`}>
                          {chapter.chapter_number}. {chapter.title} · {chapter.word_count || 0} 字 · {chapter.preview}
                        </div>
                      ))}
                </div>
              </div>
            )}

            {importMessage && (
              <div className="text-sm text-white/60">{importMessage}</div>
            )}
          </CardContent>
        </Card>

        {/* 搜索和筛选 */}
        <Card className="bg-white/5 border-white/10">
          <CardContent className="p-4">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <Input
                  placeholder="搜索小说标题或描述…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
              </div>
              <div className="flex gap-2 flex-wrap">
                {GENRE_OPTIONS.map(genre => (
                  <Button
                    key={genre}
                    variant={selectedGenre === genre ? 'default' : 'outline'}
                    onClick={() => setSelectedGenre(genre)}
                    className={selectedGenre === genre ? 'bg-violet-600' : 'border-white/20 text-white'}
                  >
                    {genre}
                  </Button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 加载状态 */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
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
                onClick={loadNovelsFromAPI}
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
              <TabsTrigger value="all" className="data-[state=active]:bg-violet-600">全部</TabsTrigger>
              <TabsTrigger value="draft" className="data-[state=active]:bg-violet-600">草稿</TabsTrigger>
              <TabsTrigger value="writing" className="data-[state=active]:bg-violet-600">连载中</TabsTrigger>
              <TabsTrigger value="completed" className="data-[state=active]:bg-violet-600">已完成</TabsTrigger>
            </TabsList>

            <TabsContent value={activeTab} className="mt-4">
              {filteredNovels.length > 0 ? (
                <div className="grid gap-4">
                  {filteredNovels.map((novel) => (
                    <Card 
                      key={novel.id} 
                      className={`bg-white/5 border-white/10 hover:border-violet-500/30 transition-colors ${
                        highlightId === novel.id ? 'ring-2 ring-violet-500' : ''
                      }`}
                    >
                      <CardContent className="p-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-3">
                              <BookOpen className="w-5 h-5 shrink-0 text-violet-400" />
                              <h3 className="min-w-0 break-words text-lg font-semibold text-white">{novel.title}</h3>
                              <span className={`px-2 py-0.5 rounded text-xs ${
                                novel.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                                novel.status === 'writing' ? 'bg-blue-500/20 text-blue-400' :
                                'bg-yellow-500/20 text-yellow-400'
                              }`}>
                                {STATUS_LABELS[novel.status]}
                              </span>
                            </div>
                            <p className="mt-2 break-words text-white/60">{novel.description}</p>
                            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-white/40">
                              <span className="flex items-center gap-1">
                                <FileText className="w-4 h-4" />
                                {novel.chapters} 章
                              </span>
                              <span className="flex items-center gap-1">
                                <Users className="w-4 h-4" />
                                {novel.characters} 字
                              </span>
                              <span className="flex items-center gap-1">
                                <Clock className="w-4 h-4" />
                                更新于 {novel.updatedAt}
                              </span>
                            </div>
                            <div className="mt-3">
                              <NovelProductionEntryCard
                                entry={productionEntries[novel.id] || (productionEntriesLoaded ? null : undefined)}
                                failed={productionEntriesFailed}
                                novelId={novel.id}
                              />
                            </div>
                          </div>
                          <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                            <Button asChild variant="ghost" size="sm" className="text-blue-400 hover:text-blue-300">
                              <Link href={`/scripts?novel_id=${novel.id}`}>
                                <FileTextIcon className="w-4 h-4 mr-1" />
                                剧本
                              </Link>
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              aria-label={`查看《${novel.title}》`}
                              title="查看"
                              className="text-white/60 hover:text-white"
                              onClick={() => handleView(novel.id)}
                            >
                              <Eye className="w-4 h-4" />
                            </Button>
                            <Button asChild variant="ghost" size="icon" className="text-white/60 hover:text-white" aria-label={`编辑《${novel.title}》`} title="编辑">
                              <Link href={`/novels/${novel.id}`}>
                                <Edit2 className="w-4 h-4" />
                              </Link>
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              aria-label={`复制《${novel.title}》`}
                              title="复制"
                              className="text-white/60 hover:text-white"
                              onClick={() => handleDuplicate(novel)}
                            >
                              <Copy className="w-4 h-4" />
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              aria-label={`删除《${novel.title}》`}
                              title="删除"
                              className="text-white/60 hover:text-red-400"
                              onClick={() => setDeleteTarget(novel)}
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
                  <BookOpen className="w-12 h-12 mx-auto text-white/20" />
                  <p className="text-white/40 mt-4">没有找到小说</p>
                  <Button asChild className="mt-4 bg-violet-600 hover:bg-violet-700">
                    <Link href="/novels/new">
                      创建第一本小说
                    </Link>
                  </Button>
                </div>
              )}
            </TabsContent>
          </Tabs>
        )}
        <ConfirmDialog
          open={Boolean(deleteTarget)}
          title="删除小说"
          description={`确定要删除「${deleteTarget?.title || ''}」吗？此操作无法撤销。`}
          confirmText="删除"
          destructive
          loading={deleting}
          onOpenChange={(open) => {
            if (!open) setDeleteTarget(null);
          }}
          onConfirm={async () => {
            if (!deleteTarget) return;
            setDeleting(true);
            try {
              await handleDelete(deleteTarget.id);
              setDeleteTarget(null);
            } finally {
              setDeleting(false);
            }
          }}
        />
      </div>
    </MainLayout>
  );
}

// 包装组件，提供 Suspense 边界
export default function NovelsPage() {
  return (
    <Suspense fallback={
      <MainLayout>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-violet-400" />
          <span className="ml-3 text-white/60">加载中…</span>
        </div>
      </MainLayout>
    }>
      <NovelsContent />
    </Suspense>
  );
}
