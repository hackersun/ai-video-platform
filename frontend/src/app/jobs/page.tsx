'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MainLayout } from '@/components/layout/main-layout';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  ListTodo, 
  RefreshCw,
  Clock,
  Video,
  Mic,
  Image as ImageIcon,
  CheckCircle,
  AlertCircle,
  Loader2,
  Trash2,
  Download,
  Eye
} from 'lucide-react';

// 任务数据类型
interface Job {
  id: string;
  name: string;
  type: 'video' | 'tts' | 'image' | 'script';
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  duration?: number;
  output?: string;
  error?: string;
}

// 模拟任务数据
const MOCK_JOBS: Job[] = [
  {
    id: '1',
    name: '第一章视频生成',
    type: 'video',
    status: 'completed',
    progress: 100,
    createdAt: '2024-03-15 14:30:00',
    startedAt: '2024-03-15 14:30:05',
    completedAt: '2024-03-15 14:35:20',
    duration: 315,
    output: '/output/video_001.mp4'
  },
  {
    id: '2',
    name: '角色配音生成',
    type: 'tts',
    status: 'running',
    progress: 65,
    createdAt: '2024-03-15 14:35:00',
    startedAt: '2024-03-15 14:35:10',
  },
  {
    id: '3',
    name: '场景图片生成',
    type: 'image',
    status: 'pending',
    progress: 0,
    createdAt: '2024-03-15 14:40:00',
  },
  {
    id: '4',
    name: '剧本优化',
    type: 'script',
    status: 'failed',
    progress: 45,
    createdAt: '2024-03-15 14:25:00',
    startedAt: '2024-03-15 14:25:05',
    completedAt: '2024-03-15 14:26:30',
    error: 'API 调用超时'
  },
  {
    id: '5',
    name: '第二章视频生成',
    type: 'video',
    status: 'cancelled',
    progress: 30,
    createdAt: '2024-03-15 14:20:00',
    startedAt: '2024-03-15 14:20:10',
    completedAt: '2024-03-15 14:22:00',
  }
];

const TYPE_ICONS = {
  video: Video,
  tts: Mic,
  image: ImageIcon,
  script: ListTodo
};

const TYPE_LABELS = {
  video: '视频生成',
  tts: '语音合成',
  image: '图片生成',
  script: '剧本处理'
};

const STATUS_LABELS = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消'
};

const STATUS_COLORS = {
  pending: 'bg-yellow-500/20 text-yellow-400',
  running: 'bg-blue-500/20 text-blue-400',
  completed: 'bg-green-500/20 text-green-400',
  failed: 'bg-red-500/20 text-red-400',
  cancelled: 'bg-gray-500/20 text-gray-400'
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>(MOCK_JOBS);
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // 筛选任务
  const filteredJobs = jobs.filter(job => {
    const matchesSearch = job.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = activeTab === 'all' || job.status === activeTab;
    return matchesSearch && matchesStatus;
  });

  // 统计
  const stats = {
    total: jobs.length,
    pending: jobs.filter(j => j.status === 'pending').length,
    running: jobs.filter(j => j.status === 'running').length,
    completed: jobs.filter(j => j.status === 'completed').length,
    failed: jobs.filter(j => j.status === 'failed').length
  };

  // 格式化时间
  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}分${secs}秒`;
  };

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div>
          <h1 className="text-3xl font-bold text-white">任务队列</h1>
          <p className="text-white/60 mt-1">查看和管理生成任务</p>
        </div>

        {/* 统计卡片 */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-white">{stats.total}</div>
              <div className="text-sm text-white/60">全部任务</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-yellow-400">{stats.pending}</div>
              <div className="text-sm text-white/60">等待中</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-blue-400">{stats.running}</div>
              <div className="text-sm text-white/60">运行中</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-green-400">{stats.completed}</div>
              <div className="text-sm text-white/60">已完成</div>
            </CardContent>
          </Card>
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-red-400">{stats.failed}</div>
              <div className="text-sm text-white/60">失败</div>
            </CardContent>
          </Card>
        </div>

        {/* 搜索栏 */}
        <Card className="bg-white/5 border-white/10">
          <CardContent className="p-4">
            <div className="flex gap-4">
              <div className="flex-1 relative">
                <Input
                  placeholder="搜索任务..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
              </div>
              <Button variant="outline" className="border-white/20 text-white">
                <RefreshCw className="w-4 h-4 mr-2" />
                刷新
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* 状态标签页 */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-white/5">
            <TabsTrigger value="all" className="data-[state=active]:bg-teal-600">全部</TabsTrigger>
            <TabsTrigger value="pending" className="data-[state=active]:bg-teal-600">等待中</TabsTrigger>
            <TabsTrigger value="running" className="data-[state=active]:bg-teal-600">运行中</TabsTrigger>
            <TabsTrigger value="completed" className="data-[state=active]:bg-teal-600">已完成</TabsTrigger>
            <TabsTrigger value="failed" className="data-[state=active]:bg-teal-600">失败</TabsTrigger>
          </TabsList>

          <TabsContent value={activeTab} className="mt-4">
            {filteredJobs.length > 0 ? (
              <div className="space-y-3">
                {filteredJobs.map((job) => {
                  const Icon = TYPE_ICONS[job.type];
                  return (
                    <Card key={job.id} className="bg-white/5 border-white/10">
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-3">
                              <Icon className="w-5 h-5 text-teal-400" />
                              <span className="text-white font-medium">{job.name}</span>
                              <span className={`px-2 py-0.5 rounded text-xs ${STATUS_COLORS[job.status]}`}>
                                {STATUS_LABELS[job.status]}
                              </span>
                            </div>
                            <div className="flex items-center gap-4 mt-2 text-sm text-white/40">
                              <span>{TYPE_LABELS[job.type]}</span>
                              <span>·</span>
                              <span>创建于 {job.createdAt}</span>
                              {job.duration && (
                                <>
                                  <span>·</span>
                                  <span>耗时 {formatDuration(job.duration)}</span>
                                </>
                              )}
                            </div>
                            {job.status === 'running' && (
                              <div className="mt-3">
                                <div className="w-full bg-white/10 rounded-full h-2">
                                  <div 
                                    className="bg-teal-500 h-2 rounded-full transition-all"
                                    style={{ width: `${job.progress}%` }}
                                  />
                                </div>
                                <span className="text-sm text-teal-400 mt-1">{job.progress}%</span>
                              </div>
                            )}
                            {job.error && (
                              <div className="mt-2 text-sm text-red-400">
                                <AlertCircle className="w-4 h-4 inline mr-1" />
                                {job.error}
                              </div>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            {job.status === 'completed' && job.output && (
                              <Button variant="ghost" size="icon" className="text-white/60">
                                <Download className="w-4 h-4" />
                              </Button>
                            )}
                            <Button variant="ghost" size="icon" className="text-white/60">
                              <Eye className="w-4 h-4" />
                            </Button>
                            <Button variant="ghost" size="icon" className="text-white/60 hover:text-red-400">
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-12">
                <ListTodo className="w-12 h-12 mx-auto text-white/20" />
                <p className="text-white/40 mt-4">暂无任务</p>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </MainLayout>
  );
}