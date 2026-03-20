'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { MainLayout } from '@/components/layout/main-layout';
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
  FileTextIcon
} from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';

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

// 类型统计
const STATUS_LABELS = {
  draft: '草稿',
  writing: '连载中',
  completed: '已完成'
};

const GENRE_OPTIONS = ['全部', '仙侠', '都市', '科幻', '历史', '言情', '悬疑'];

// 内嵌组件使用 useSearchParams
function NovelsContent() {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedGenre, setSelectedGenre] = useState('全部');
  const [activeTab, setActiveTab] = useState('all');
  const router = useRouter();
  const searchParams = useSearchParams();
  const highlightId = searchParams.get('highlight');

  // 从后端API加载小说
  const loadNovelsFromAPI = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/novels`);
      if (!response.ok) {
        throw new Error('加载失败');
      }
      const data: ApiNovel[] = await response.json();
      
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
    } catch (err) {
      console.error('加载小说失败:', err);
      setError('加载失败，请检查后端服务是否启动');
      setNovels([]);
    } finally {
      setLoading(false);
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
    if (!confirm('确定要删除这本小说吗？')) return;
    
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/novels/${id}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        setNovels(novels.filter(n => n.id !== id));
      } else {
        throw new Error('删除失败');
      }
    } catch (err) {
      console.error('删除失败:', err);
      alert('删除失败，请重试');
    }
  };

  // 复制小说
  const handleDuplicate = async (novel: Novel) => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/novels`, {
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
      alert('复制失败，请重试');
    }
  };

  // 查看小说
  const handleView = (id: string) => {
    router.push(`/novels/${id}`);
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">小说管理</h1>
            <p className="text-white/60 mt-1">管理您的作品和章节</p>
          </div>
          <Link href="/novels/new">
            <Button className="bg-violet-600 hover:bg-violet-700">
              <Plus className="w-4 h-4 mr-2" />
              创建小说
            </Button>
          </Link>
        </div>

        {/* 搜索和筛选 */}
        <Card className="bg-white/5 border-white/10">
          <CardContent className="p-4">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <Input
                  placeholder="搜索小说标题或描述..."
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
            <span className="ml-3 text-white/60">加载中...</span>
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
            <TabsList className="bg-white/5">
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
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-3">
                              <BookOpen className="w-5 h-5 text-violet-400" />
                              <h3 className="text-lg font-semibold text-white">{novel.title}</h3>
                              <span className={`px-2 py-0.5 rounded text-xs ${
                                novel.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                                novel.status === 'writing' ? 'bg-blue-500/20 text-blue-400' :
                                'bg-yellow-500/20 text-yellow-400'
                              }`}>
                                {STATUS_LABELS[novel.status]}
                              </span>
                            </div>
                            <p className="text-white/60 mt-2">{novel.description}</p>
                            <div className="flex items-center gap-4 mt-3 text-sm text-white/40">
                              <span className="flex items-center gap-1">
                                <FileText className="w-4 h-4" />
                                {novel.chapters} 章
                              </span>
                              <span className="flex items-center gap-1">
                                <Users className="w-4 h-4" />
                                {novel.characters} 角色
                              </span>
                              <span className="flex items-center gap-1">
                                <Clock className="w-4 h-4" />
                                更新于 {novel.updatedAt}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Link href={`/scripts?novel_id=${novel.id}`}>
                              <Button variant="ghost" size="sm" className="text-blue-400 hover:text-blue-300">
                                <FileTextIcon className="w-4 h-4 mr-1" />
                                剧本
                              </Button>
                            </Link>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              className="text-white/60 hover:text-white"
                              onClick={() => handleView(novel.id)}
                            >
                              <Eye className="w-4 h-4" />
                            </Button>
                            <Link href={`/novels/${novel.id}`}>
                              <Button variant="ghost" size="icon" className="text-white/60 hover:text-white">
                                <Edit2 className="w-4 h-4" />
                              </Button>
                            </Link>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              className="text-white/60 hover:text-white"
                              onClick={() => handleDuplicate(novel)}
                            >
                              <Copy className="w-4 h-4" />
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              className="text-white/60 hover:text-red-400"
                              onClick={() => handleDelete(novel.id)}
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
                  <Link href="/novels/new">
                    <Button className="mt-4 bg-violet-600 hover:bg-violet-700">
                      创建第一本小说
                    </Button>
                  </Link>
                </div>
              )}
            </TabsContent>
          </Tabs>
        )}
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
          <span className="ml-3 text-white/60">加载中...</span>
        </div>
      </MainLayout>
    }>
      <NovelsContent />
    </Suspense>
  );
}
