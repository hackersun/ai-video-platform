'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
  AlertCircle
} from 'lucide-react';
import Link from 'next/link';

// 剧本数据类型
interface Script {
  id: string;
  title: string;
  novelTitle: string;
  chapter: string;
  duration: number;
  status: 'draft' | 'review' | 'approved' | 'generated';
  scenes: number;
  createdAt: string;
  updatedAt: string;
}

// 模拟剧本数据
const MOCK_SCRIPTS: Script[] = [
  {
    id: '1',
    title: '第一章：下山',
    novelTitle: '仙侠世界',
    chapter: '第一章',
    duration: 180,
    status: 'approved',
    scenes: 12,
    createdAt: '2024-03-01',
    updatedAt: '2024-03-15'
  },
  {
    id: '2',
    title: '第二章：初入江湖',
    novelTitle: '仙侠世界',
    chapter: '第二章',
    duration: 210,
    status: 'generated',
    scenes: 15,
    createdAt: '2024-03-05',
    updatedAt: '2024-03-12'
  },
  {
    id: '3',
    title: '第三章：历练',
    novelTitle: '仙侠世界',
    chapter: '第三章',
    duration: 150,
    status: 'review',
    scenes: 8,
    createdAt: '2024-03-10',
    updatedAt: '2024-03-14'
  },
  {
    id: '4',
    title: '第一集：危机',
    novelTitle: '都市纵横',
    chapter: '第一集',
    duration: 240,
    status: 'draft',
    scenes: 18,
    createdAt: '2024-03-11',
    updatedAt: '2024-03-13'
  }
];

const STATUS_LABELS = {
  draft: '草稿',
  review: '审核中',
  approved: '已通过',
  generated: '已生成视频'
};

const STATUS_COLORS = {
  draft: 'bg-yellow-500/20 text-yellow-400',
  review: 'bg-blue-500/20 text-blue-400',
  approved: 'bg-green-500/20 text-green-400',
  generated: 'bg-violet-500/20 text-violet-400'
};

export default function ScriptsPage() {
  const [scripts, setScripts] = useState<Script[]>(MOCK_SCRIPTS);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('all');

  // 筛选剧本
  const filteredScripts = scripts.filter(script => {
    const matchesSearch = script.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          script.novelTitle.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = activeTab === 'all' || script.status === activeTab;
    return matchesSearch && matchesStatus;
  });

  // 删除剧本
  const handleDelete = (id: string) => {
    if (confirm('确定要删除这个剧本吗？')) {
      setScripts(scripts.filter(s => s.id !== id));
    }
  };

  // 格式化时长
  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // 统计
  const stats = {
    total: scripts.length,
    draft: scripts.filter(s => s.status === 'draft').length,
    review: scripts.filter(s => s.status === 'review').length,
    approved: scripts.filter(s => s.status === 'approved').length,
    generated: scripts.filter(s => s.status === 'generated').length
  };

  return (
    <MainLayout>
    
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">剧本管理</h1>
            <p className="text-white/60 mt-1">管理视频剧本和分镜脚本</p>
          </div>
          <Button className="bg-blue-600 hover:bg-blue-700">
            <Plus className="w-4 h-4 mr-2" />
            创建剧本
          </Button>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
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
              <div className="text-2xl font-bold text-blue-400">{stats.review}</div>
              <div className="text-sm text-white/60">审核中</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-green-400">{stats.approved}</div>
              <div className="text-sm text-white/60">已通过</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-violet-400">{stats.generated}</div>
              <div className="text-sm text-white/60">已生成视频</div>
            </CardContent>
          </Card>
        </div>

        {/* 搜索栏 */}
        <Card className="bg-white/5 border-white/10">
          <CardContent className="p-4">
            <div className="flex gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <Input
                  placeholder="搜索剧本标题或所属小说..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 状态标签页 */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-white/5">
            <TabsTrigger value="all" className="data-[state=active]:bg-blue-600">全部</TabsTrigger>
            <TabsTrigger value="draft" className="data-[state=active]:bg-blue-600">草稿</TabsTrigger>
            <TabsTrigger value="review" className="data-[state=active]:bg-blue-600">审核中</TabsTrigger>
            <TabsTrigger value="approved" className="data-[state=active]:bg-blue-600">已通过</TabsTrigger>
            <TabsTrigger value="generated" className="data-[state=active]:bg-blue-600">已生成</TabsTrigger>
          </TabsList>

          <TabsContent value={activeTab} className="mt-4">
            {filteredScripts.length > 0 ? (
              <div className="grid gap-4">
                {filteredScripts.map((script) => (
                  <Card key={script.id} className="bg-white/5 border-white/10 hover:border-blue-500/30 transition-colors">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-3">
                            <FileText className="w-5 h-5 text-blue-400" />
                            <h3 className="text-lg font-semibold text-white">{script.title}</h3>
                            <span className={`px-2 py-0.5 rounded text-xs ${STATUS_COLORS[script.status]}`}>
                              {STATUS_LABELS[script.status]}
                            </span>
                          </div>
                          <div className="flex items-center gap-4 mt-2 text-sm text-white/60">
                            <span>{script.novelTitle} · {script.chapter}</span>
                          </div>
                          <div className="flex items-center gap-4 mt-3 text-sm text-white/40">
                            <span className="flex items-center gap-1">
                              <Video className="w-4 h-4" />
                              {script.scenes} 个分镜
                            </span>
                            <span className="flex items-center gap-1">
                              <Clock className="w-4 h-4" />
                              {formatDuration(script.duration)}
                            </span>
                            <span>更新于 {script.updatedAt}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {script.status === 'approved' && (
                            <Link href={`/video-generation?script=${script.id}`}>
                              <Button variant="ghost" size="sm" className="text-violet-400 hover:text-violet-300">
                                <Play className="w-4 h-4 mr-1" />
                                生成视频
                              </Button>
                            </Link>
                          )}
                          <Button variant="ghost" size="icon" className="text-white/60 hover:text-white">
                            <Eye className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="icon" className="text-white/60 hover:text-white">
                            <Edit2 className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="icon" className="text-white/60 hover:text-white">
                            <Copy className="w-4 h-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="icon" 
                            className="text-white/60 hover:text-red-400"
                            onClick={() => handleDelete(script.id)}
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
                <Button className="mt-4 bg-blue-600 hover:bg-blue-700">
                  创建第一个剧本
                </Button>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </MainLayout>
  );
}