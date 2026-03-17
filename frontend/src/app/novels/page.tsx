'use client';

import { useState } from 'react';
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
  ChevronRight,
  MoreVertical,
  Copy,
  Download,
  Eye
} from 'lucide-react';
import Link from 'next/link';

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

// 模拟小说数据
const MOCK_NOVELS: Novel[] = [
  {
    id: '1',
    title: '仙侠世界',
    description: '一个关于修仙者与妖魔战斗的奇幻故事',
    genre: '仙侠',
    status: 'writing',
    chapters: 15,
    characters: 8,
    createdAt: '2024-03-01',
    updatedAt: '2024-03-15'
  },
  {
    id: '2',
    title: '都市纵横',
    description: '都市背景下的热血商战故事',
    genre: '都市',
    status: 'draft',
    chapters: 3,
    characters: 5,
    createdAt: '2024-03-10',
    updatedAt: '2024-03-12'
  },
  {
    id: '3',
    title: '星际探索',
    description: '人类探索宇宙深处的科幻冒险',
    genre: '科幻',
    status: 'completed',
    chapters: 20,
    characters: 12,
    createdAt: '2024-02-15',
    updatedAt: '2024-03-01'
  }
];

// 类型统计
const STATUS_LABELS = {
  draft: '草稿',
  writing: '连载中',
  completed: '已完成'
};

const GENRE_OPTIONS = ['全部', '仙侠', '都市', '科幻', '历史', '言情', '悬疑'];

export default function NovelsPage() {
  const [novels, setNovels] = useState<Novel[]>(MOCK_NOVELS);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedGenre, setSelectedGenre] = useState('全部');
  const [activeTab, setActiveTab] = useState('all');

  // 筛选小说
  const filteredNovels = novels.filter(novel => {
    const matchesSearch = novel.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          novel.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesGenre = selectedGenre === '全部' || novel.genre === selectedGenre;
    const matchesStatus = activeTab === 'all' || novel.status === activeTab;
    return matchesSearch && matchesGenre && matchesStatus;
  });

  // 删除小说
  const handleDelete = (id: string) => {
    if (confirm('确定要删除这本小说吗？')) {
      setNovels(novels.filter(n => n.id !== id));
    }
  };

  // 复制小说
  const handleDuplicate = (novel: Novel) => {
    const newNovel: Novel = {
      ...novel,
      id: Date.now().toString(),
      title: `${novel.title} (副本)`,
      createdAt: new Date().toISOString().split('T')[0],
      updatedAt: new Date().toISOString().split('T')[0]
    };
    setNovels([...novels, newNovel]);
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

        {/* 状态标签页 */}
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
                  <Card key={novel.id} className="bg-white/5 border-white/10 hover:border-violet-500/30 transition-colors">
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
                          <Button variant="ghost" size="icon" className="text-white/60 hover:text-white">
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
      </div>
    </MainLayout>
  );
}