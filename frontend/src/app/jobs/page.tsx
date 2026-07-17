'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { MainLayout } from '@/components/layout/main-layout';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock,
  ExternalLink,
  FileText,
  ListTodo, 
  RefreshCw,
  Video,
  Mic,
  Image as ImageIcon,
  AlertCircle,
  Loader2,
  Trash2,
  Download,
  Eye,
  Link2,
  Layers,
  XCircle
} from 'lucide-react';
import apiClient from '@/lib/api-client';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, '');

const toMediaUrl = (url?: string | null) => {
  if (!url) return '';
  return url.startsWith('/') ? `${API_ORIGIN}${url}` : url;
};

// 任务数据类型
interface Job {
  id: string;
  name: string;
  type: 'video' | 'tts' | 'image' | 'synthesis' | 'media' | 'batch';
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  createdAt: string;
  createdAtTime: number;
  startedAt?: string;
  completedAt?: string;
  duration?: number;
  output?: string;
  error?: string;
}

const TYPE_ICONS = {
  video: Video,
  tts: Mic,
  image: ImageIcon,
  synthesis: ListTodo,
  media: Video,
  batch: Layers
};

const TYPE_LABELS = {
  video: '视频生成',
  tts: '语音合成',
  image: '图片生成',
  synthesis: '音视频合成',
  media: '直生媒体',
  batch: '批量任务'
};

const STATUS_LABELS = {
  pending: '等待中',
  running: '运行中',
  paused: '已暂停',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消'
};

const STATUS_COLORS = {
  pending: 'bg-yellow-500/20 text-yellow-400',
  running: 'bg-blue-500/20 text-blue-400',
  paused: 'bg-amber-500/20 text-amber-400',
  completed: 'bg-green-500/20 text-green-400',
  failed: 'bg-red-500/20 text-red-400',
  cancelled: 'bg-gray-500/20 text-gray-400'
};

type JobTypeFilter = 'all' | Job['type'];
type OutputFilter = 'all' | 'withOutput' | 'withoutOutput' | 'withError';
type TimeRangeFilter = 'all' | 'today' | '7d' | '30d' | 'custom';
type SortMode = 'newest' | 'oldest' | 'progress' | 'duration';

const typeOptions = [
  { value: 'all', label: '全部类型' },
  { value: 'video', label: TYPE_LABELS.video },
  { value: 'tts', label: TYPE_LABELS.tts },
  { value: 'image', label: TYPE_LABELS.image },
  { value: 'synthesis', label: TYPE_LABELS.synthesis },
  { value: 'media', label: TYPE_LABELS.media },
  { value: 'batch', label: TYPE_LABELS.batch },
];

const timeRangeOptions = [
  { value: 'all', label: '全部时间' },
  { value: 'today', label: '今天' },
  { value: '7d', label: '近 7 天' },
  { value: '30d', label: '近 30 天' },
  { value: 'custom', label: '自定义日期' },
];

const outputOptions = [
  { value: 'all', label: '全部产物' },
  { value: 'withOutput', label: '有产物' },
  { value: 'withoutOutput', label: '无产物' },
  { value: 'withError', label: '有错误信息' },
];

const sortOptions = [
  { value: 'newest', label: '最新创建优先' },
  { value: 'oldest', label: '最早创建优先' },
  { value: 'progress', label: '进度高优先' },
  { value: 'duration', label: '耗时长优先' },
];

const pageSizeOptions = [
  { value: '12', label: '每页 12 条' },
  { value: '24', label: '每页 24 条' },
  { value: '48', label: '每页 48 条' },
];

const getOutputKind = (job?: Job | null) => {
  if (!job?.output) return 'empty';
  const output = job.output.toLowerCase();
  if (job.type === 'image' || /\.(png|jpe?g|webp|gif)(\?|$)/.test(output)) return 'image';
  if (job.type === 'tts' || /\.(mp3|wav|m4a|aac|ogg)(\?|$)/.test(output)) return 'audio';
  return 'video';
};

function JobOutputPreview({ job }: { job?: Job | null }) {
  const outputUrl = toMediaUrl(job?.output);
  const outputKind = getOutputKind(job);

  if (!job || !outputUrl) {
    return (
      <div className="flex aspect-video items-center justify-center rounded-md border border-dashed border-white/10 bg-black/20 text-sm text-white/40">
        暂无可预览产物
      </div>
    );
  }

  if (outputKind === 'image') {
    return (
      <div className="overflow-hidden rounded-md border border-white/10 bg-black/20">
        <img src={outputUrl} alt={`${job.name}输出预览`} className="aspect-video w-full object-contain" loading="lazy" />
      </div>
    );
  }

  if (outputKind === 'audio') {
    return (
      <div className="rounded-md border border-white/10 bg-black/20 p-3">
        <audio controls preload="none" src={outputUrl} className="w-full" />
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-md border border-white/10 bg-black/20">
      <video controls preload="none" src={outputUrl} className="aspect-video w-full bg-black object-contain" />
    </div>
  );
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<JobTypeFilter>('all');
  const [timeRange, setTimeRange] = useState<TimeRangeFilter>('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [outputFilter, setOutputFilter] = useState<OutputFilter>('all');
  const [sortMode, setSortMode] = useState<SortMode>('newest');
  const [pageSize, setPageSize] = useState(12);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionJobId, setActionJobId] = useState<string | null>(null);

  const normalizeStatus = (status?: string): Job['status'] => {
    if (status === 'succeeded' || status === 'completed') return 'completed';
    if (status === 'running' || status === 'generating' || status === 'processing') return 'running';
    if (status === 'paused') return 'paused';
    if (status === 'failed') return 'failed';
    if (status === 'cancelled') return 'cancelled';
    return 'pending';
  };

  const toDateText = (value?: string) => {
    if (!value) return '-';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN');
  };

  const toDateTime = (value?: string) => {
    if (!value) return 0;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 0 : date.getTime();
  };

  const mapJob = (raw: any, type: Job['type']): Job => ({
    id: raw.id || raw.job_id || raw.task_id,
    name: raw.title || raw.prompt || raw.text || `${TYPE_LABELS[type]}任务`,
    type,
    status: normalizeStatus(raw.status),
    progress: raw.progress_percent ?? raw.progress ?? (raw.status === 'succeeded' || raw.status === 'completed' ? 100 : 0),
    createdAt: toDateText(raw.created_at),
    createdAtTime: toDateTime(raw.created_at),
    startedAt: raw.started_at ? toDateText(raw.started_at) : undefined,
    completedAt: raw.completed_at ? toDateText(raw.completed_at) : undefined,
    duration: Math.round(raw.duration_seconds || raw.duration || 0) || undefined,
    output: raw.output_url || raw.video_url || raw.audio_url || raw.output_video_url || raw.output_audio_url || raw.output_manifest_url || raw.image_urls?.[0],
    error: raw.error_message || raw.message,
  });

  const loadJobs = async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const [videos, ttsJobs, images, synthesis, media, batchJobs] = await Promise.all([
        apiClient.getVideoJobs(),
        apiClient.getTTSJobs(),
        apiClient.getImageJobs({ limit: 100 }),
        apiClient.getSynthesisJobs(),
        apiClient.getMediaJobs(),
        apiClient.getBatchJobs({ limit: 100 }),
      ]);
      const batchJobItems = Array.isArray(batchJobs) ? batchJobs : batchJobs.jobs || [];

      const mergedJobs = [
        ...videos.map((job: any) => mapJob(job, 'video')),
        ...ttsJobs.map((job: any) => mapJob(job, 'tts')),
        ...images.map((job: any) => mapJob(job, 'image')),
        ...synthesis.map((job: any) => mapJob(job, 'synthesis')),
        ...media.map((job: any) => mapJob(job, 'media')),
        ...batchJobItems.map((job: any) => mapJob(job, 'batch')),
      ].sort((a, b) => b.createdAtTime - a.createdAtTime);

      setJobs(mergedJobs);
    } catch (err: any) {
      setLoadError(err.message || '任务加载失败');
      setJobs([]);
    } finally {
      setIsLoading(false);
    }
  };

  const canCancel = (job: Job) => (
    (job.type === 'video' || job.type === 'media') && ['pending', 'running', 'failed'].includes(job.status)
  );

  const handleCancel = async (job: Job) => {
    setActionJobId(job.id);
    setLoadError(null);
    try {
      const updated = job.type === 'media'
        ? await apiClient.cancelMediaJob(job.id)
        : await apiClient.cancelVideoJob(job.id);
      setJobs(prev => prev.map(item => (
        item.id === job.id ? mapJob(updated, job.type) : item
      )));
    } catch (err: any) {
      setLoadError(err.message || '取消任务失败');
    } finally {
      setActionJobId(null);
    }
  };

  const handleDelete = async (job: Job) => {
    setActionJobId(job.id);
    setLoadError(null);
    try {
      if (job.type === 'video') {
        await apiClient.deleteVideoJob(job.id);
      } else if (job.type === 'tts') {
        await apiClient.deleteTTSJob(job.id);
      } else if (job.type === 'image') {
        await apiClient.deleteImageJob(job.id);
      } else if (job.type === 'synthesis') {
        await apiClient.deleteSynthesisJob(job.id);
      } else if (job.type === 'media') {
        await apiClient.deleteMediaJob(job.id);
      } else {
        await apiClient.deleteBatchJob(job.id);
      }
      setJobs(prev => prev.filter(item => item.id !== job.id));
      if (selectedJobId === job.id) setSelectedJobId(null);
    } catch (err: any) {
      setLoadError(err.message || '删除任务失败');
    } finally {
      setActionJobId(null);
    }
  };

  const handleOpenOutput = (job: Job) => {
    const output = toMediaUrl(job.output);
    if (output) {
      window.open(output, '_blank');
    }
  };

  const handleDownloadOutput = (job: Job) => {
    const output = toMediaUrl(job.output);
    if (!output) return;
    const link = document.createElement('a');
    link.href = output;
    link.download = `${job.name || job.id}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  useEffect(() => {
    loadJobs();
  }, []);

  const getTimeBounds = () => {
    const now = new Date();
    if (timeRange === 'today') {
      const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
      return { start, end: now.getTime() };
    }
    if (timeRange === '7d') {
      return { start: now.getTime() - 7 * 24 * 60 * 60 * 1000, end: now.getTime() };
    }
    if (timeRange === '30d') {
      return { start: now.getTime() - 30 * 24 * 60 * 60 * 1000, end: now.getTime() };
    }
    if (timeRange === 'custom') {
      const start = startDate ? new Date(`${startDate}T00:00:00`).getTime() : 0;
      const end = endDate ? new Date(`${endDate}T23:59:59`).getTime() : 0;
      return {
        start: Number.isNaN(start) ? 0 : start,
        end: Number.isNaN(end) ? 0 : end,
      };
    }
    return { start: 0, end: 0 };
  };

  const resetFilters = () => {
    setSearchQuery('');
    setActiveTab('all');
    setTypeFilter('all');
    setTimeRange('all');
    setStartDate('');
    setEndDate('');
    setOutputFilter('all');
    setSortMode('newest');
    setCurrentPage(1);
    setSelectedJobId(null);
  };

  const hasActiveFilters = Boolean(
    searchQuery.trim() ||
    activeTab !== 'all' ||
    typeFilter !== 'all' ||
    timeRange !== 'all' ||
    outputFilter !== 'all' ||
    sortMode !== 'newest'
  );

  // 筛选任务
  const timeBounds = getTimeBounds();
  const filteredJobs = jobs.filter(job => {
    const normalizedSearch = searchQuery.trim().toLowerCase();
    const searchableText = [
      job.name,
      job.id,
      TYPE_LABELS[job.type],
      STATUS_LABELS[job.status],
      job.error,
    ].filter(Boolean).join(' ').toLowerCase();
    const matchesSearch = !normalizedSearch || searchableText.includes(normalizedSearch);
    const matchesStatus = activeTab === 'all' || job.status === activeTab;
    const matchesType = typeFilter === 'all' || job.type === typeFilter;
    const matchesOutput =
      outputFilter === 'all' ||
      (outputFilter === 'withOutput' && Boolean(job.output)) ||
      (outputFilter === 'withoutOutput' && !job.output) ||
      (outputFilter === 'withError' && Boolean(job.error));
    const matchesTime =
      timeRange === 'all' ||
      Boolean(job.createdAtTime) &&
        (!timeBounds.start || job.createdAtTime >= timeBounds.start) &&
        (!timeBounds.end || job.createdAtTime <= timeBounds.end);
    return matchesSearch && matchesStatus && matchesType && matchesOutput && matchesTime;
  }).sort((a, b) => {
    if (sortMode === 'oldest') return a.createdAtTime - b.createdAtTime;
    if (sortMode === 'progress') return b.progress - a.progress;
    if (sortMode === 'duration') return (b.duration || 0) - (a.duration || 0);
    return b.createdAtTime - a.createdAtTime;
  });

  const totalPages = Math.max(1, Math.ceil(filteredJobs.length / pageSize));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const pageStartIndex = (safeCurrentPage - 1) * pageSize;
  const pagedJobs = filteredJobs.slice(pageStartIndex, pageStartIndex + pageSize);
  const pageStartText = filteredJobs.length > 0 ? pageStartIndex + 1 : 0;
  const pageEndText = Math.min(pageStartIndex + pageSize, filteredJobs.length);
  const selectedJob = pagedJobs.find(job => job.id === selectedJobId) || pagedJobs[0] || null;

  useEffect(() => {
    setCurrentPage(1);
    setSelectedJobId(null);
  }, [activeTab, searchQuery, typeFilter, timeRange, startDate, endDate, outputFilter, sortMode, pageSize]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  // 统计
  const stats = {
    total: jobs.length,
    pending: jobs.filter(j => j.status === 'pending').length,
    running: jobs.filter(j => j.status === 'running').length,
    paused: jobs.filter(j => j.status === 'paused').length,
    completed: jobs.filter(j => j.status === 'completed').length,
    failed: jobs.filter(j => j.status === 'failed').length,
    cancelled: jobs.filter(j => j.status === 'cancelled').length
  };

  // 格式化时间
  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}分${secs}秒`;
  };

  const goToPage = (page: number) => {
    setCurrentPage(Math.min(Math.max(page, 1), totalPages));
    setSelectedJobId(null);
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
        <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-4">
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
              <div className="text-2xl font-bold text-amber-400">{stats.paused}</div>
              <div className="text-sm text-white/60">已暂停</div>
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
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-gray-400">{stats.cancelled}</div>
              <div className="text-sm text-white/60">已取消</div>
            </CardContent>
          </Card>
        </div>

        {/* 查询过滤 */}
        <Card className="bg-white/5 border-white/10">
          <CardHeader className="pb-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <CardTitle className="text-base text-white">查询过滤</CardTitle>
              <p className="text-sm text-white/50">
                当前显示 {filteredJobs.length} / {jobs.length} 个任务
              </p>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 p-4 pt-0">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
              <label className="space-y-2 xl:col-span-2">
                <span className="text-xs font-medium text-white/60">关键字</span>
                <Input
                  name="job-search"
                  autoComplete="off"
                  placeholder="搜索名称、ID、错误信息…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="bg-white/5 border-white/10 text-white placeholder:text-white/40"
                />
              </label>
              <label className="space-y-2">
                <span className="text-xs font-medium text-white/60">任务类型</span>
                <Select
                  name="job-type-filter"
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value as JobTypeFilter)}
                  options={typeOptions}
                  aria-label="按任务类型筛选"
                />
              </label>
              <label className="space-y-2">
                <span className="text-xs font-medium text-white/60">时间范围</span>
                <Select
                  name="job-time-filter"
                  value={timeRange}
                  onChange={(e) => setTimeRange(e.target.value as TimeRangeFilter)}
                  options={timeRangeOptions}
                  aria-label="按创建时间筛选"
                />
              </label>
              <label className="space-y-2">
                <span className="text-xs font-medium text-white/60">产物状态</span>
                <Select
                  name="job-output-filter"
                  value={outputFilter}
                  onChange={(e) => setOutputFilter(e.target.value as OutputFilter)}
                  options={outputOptions}
                  aria-label="按产物状态筛选"
                />
              </label>
              <label className="space-y-2">
                <span className="text-xs font-medium text-white/60">排序</span>
                <Select
                  name="job-sort"
                  value={sortMode}
                  onChange={(e) => setSortMode(e.target.value as SortMode)}
                  options={sortOptions}
                  aria-label="任务排序方式"
                />
              </label>
            </div>

            {timeRange === 'custom' && (
              <div className="grid gap-3 rounded-lg border border-white/10 bg-black/20 p-3 sm:grid-cols-2">
                <label className="space-y-2">
                  <span className="text-xs font-medium text-white/60">开始日期</span>
                  <Input
                    type="date"
                    name="job-start-date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="bg-white/5 border-white/10 text-white"
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-xs font-medium text-white/60">结束日期</span>
                  <Input
                    type="date"
                    name="job-end-date"
                    value={endDate}
                    min={startDate || undefined}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="bg-white/5 border-white/10 text-white"
                  />
                </label>
              </div>
            )}

            <div className="flex flex-col gap-3 border-t border-white/10 pt-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-white/45">
                可组合状态、类型、时间和产物条件；操作按钮不会受筛选状态影响。
              </p>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  className="text-white/70 hover:text-white"
                  onClick={resetFilters}
                  disabled={!hasActiveFilters}
                >
                  重置筛选
                </Button>
                <Button variant="outline" className="border-white/20 text-white" onClick={loadJobs} disabled={isLoading}>
                {isLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
                刷新
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 状态标签页 */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-white/5">
            <TabsTrigger value="all" className="data-[state=active]:bg-teal-600">全部</TabsTrigger>
            <TabsTrigger value="pending" className="data-[state=active]:bg-teal-600">等待中</TabsTrigger>
            <TabsTrigger value="running" className="data-[state=active]:bg-teal-600">运行中</TabsTrigger>
            <TabsTrigger value="paused" className="data-[state=active]:bg-teal-600">已暂停</TabsTrigger>
            <TabsTrigger value="completed" className="data-[state=active]:bg-teal-600">已完成</TabsTrigger>
            <TabsTrigger value="failed" className="data-[state=active]:bg-teal-600">失败</TabsTrigger>
            <TabsTrigger value="cancelled" className="data-[state=active]:bg-teal-600">已取消</TabsTrigger>
          </TabsList>

          <TabsContent value={activeTab} className="mt-4">
            {loadError && (
              <div className="mb-4 rounded border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
                {loadError}
              </div>
            )}
            {isLoading ? (
              <div className="text-center py-12">
                <Loader2 className="w-10 h-10 mx-auto text-teal-400 animate-spin" />
                <p className="text-white/40 mt-4">正在加载任务</p>
              </div>
            ) : filteredJobs.length > 0 ? (
              <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
                <Card className="overflow-hidden bg-white/5 border-white/10">
                  <CardHeader className="border-b border-white/10 p-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                      <div>
                        <CardTitle className="text-base text-white">任务列表</CardTitle>
                        <p className="mt-1 text-sm text-white/45">显示 {pageStartText}-{pageEndText} / {filteredJobs.length}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Select
                          value={String(pageSize)}
                          onChange={(e) => setPageSize(Number(e.target.value))}
                          options={pageSizeOptions}
                          aria-label="每页任务数量"
                          className="h-9 w-32"
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-9 w-9 text-white/70 hover:text-white"
                          onClick={() => goToPage(safeCurrentPage - 1)}
                          disabled={safeCurrentPage <= 1}
                          aria-label="向前翻页"
                          title="上一页"
                        >
                          <ChevronLeft className="h-4 w-4" />
                        </Button>
                        <span className="min-w-16 text-center text-sm text-white/55">
                          {safeCurrentPage}/{totalPages}
                        </span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-9 w-9 text-white/70 hover:text-white"
                          onClick={() => goToPage(safeCurrentPage + 1)}
                          disabled={safeCurrentPage >= totalPages}
                          aria-label="向后翻页"
                          title="下一页"
                        >
                          <ChevronRight className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="p-0">
                    <div className="hidden grid-cols-[minmax(220px,1.8fr)_120px_150px_96px_140px] gap-3 border-b border-white/10 px-4 py-2 text-xs font-medium text-white/40 lg:grid">
                      <span>任务</span>
                      <span>状态</span>
                      <span>创建时间</span>
                      <span>进度</span>
                      <span className="text-right">操作</span>
                    </div>
                    <div className="divide-y divide-white/10">
                      {pagedJobs.map((job) => {
                        const Icon = TYPE_ICONS[job.type];
                        const isActing = actionJobId === job.id;
                        const isSelected = selectedJob?.id === job.id;
                        const progress = Math.max(0, Math.min(job.progress || 0, 100));
                        return (
                          <div
                            key={job.id}
                            className={`flex flex-col gap-2 px-3 py-3 transition-colors lg:flex-row lg:items-center lg:gap-3 lg:px-4 ${isSelected ? 'bg-teal-500/10' : 'hover:bg-white/[0.04]'}`}
                          >
                            <button
                              type="button"
                              onClick={() => setSelectedJobId(job.id)}
                              aria-label={`查看${job.name}详情`}
                              className="grid min-w-0 flex-1 gap-3 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 lg:grid-cols-[minmax(220px,1.8fr)_120px_150px_96px]"
                            >
                              <div className="flex min-w-0 items-start gap-3">
                                <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-white/10 bg-black/20 text-teal-300">
                                  <Icon className="h-4 w-4" />
                                </div>
                                <div className="min-w-0">
                                  <div className="truncate text-sm font-medium text-white">{job.name}</div>
                                  <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-white/40">
                                    <span>{TYPE_LABELS[job.type]}</span>
                                    <span className="max-w-[160px] truncate font-mono">{job.id}</span>
                                    {job.output && (
                                      <span className="inline-flex items-center gap-1 text-teal-300/80">
                                        <Link2 className="h-3 w-3" />产物
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>
                              <div className="flex items-center lg:justify-start">
                                <span className={`inline-flex h-6 items-center rounded px-2 text-xs ${STATUS_COLORS[job.status]}`}>
                                  {STATUS_LABELS[job.status]}
                                </span>
                              </div>
                              <div className="flex items-center gap-2 text-xs text-white/45">
                                <CalendarDays className="h-3.5 w-3.5 text-white/30" />
                                <span className="truncate">{job.createdAt}</span>
                              </div>
                              <div className="min-w-0">
                                <div className="flex items-center justify-between text-xs text-white/45">
                                  <span>{progress}%</span>
                                  <span>{formatDuration(job.duration)}</span>
                                </div>
                                <div className="mt-1 h-1.5 w-full rounded-full bg-white/10">
                                  <div className="h-1.5 rounded-full bg-teal-500 transition-[width]" style={{ width: `${progress}%` }} />
                                </div>
                              </div>
                            </button>
                            <div className="flex shrink-0 items-center justify-end gap-1 lg:w-[140px]">
                              {job.status === 'completed' && job.output && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-9 w-9 text-white/60 hover:text-white"
                                  onClick={() => handleDownloadOutput(job)}
                                  aria-label={`下载${job.name}输出`}
                                  title="下载输出"
                                >
                                  <Download className="w-4 h-4" />
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-9 w-9 text-white/60 hover:text-white"
                                onClick={() => handleOpenOutput(job)}
                                disabled={!job.output}
                                aria-label={`打开${job.name}输出`}
                                title="打开输出"
                              >
                                <ExternalLink className="w-4 h-4" />
                              </Button>
                              {canCancel(job) && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-9 w-9 text-white/60 hover:text-yellow-400"
                                  onClick={() => handleCancel(job)}
                                  disabled={isActing}
                                  aria-label={`取消${job.name}`}
                                  title="取消任务"
                                >
                                  {isActing ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-9 w-9 text-white/60 hover:text-red-400"
                                onClick={() => handleDelete(job)}
                                disabled={isActing}
                                aria-label={`删除归档${job.name}`}
                                title="删除归档"
                              >
                                {isActing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                              </Button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <div className="flex flex-col gap-3 border-t border-white/10 px-4 py-3 text-sm text-white/50 sm:flex-row sm:items-center sm:justify-between">
                      <span>显示 {pageStartText}-{pageEndText} / {filteredJobs.length}</span>
                      <div className="flex items-center gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="border-white/20 text-white"
                          onClick={() => goToPage(safeCurrentPage - 1)}
                          disabled={safeCurrentPage <= 1}
                        >
                          <ChevronLeft className="mr-1 h-4 w-4" />上一页
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="border-white/20 text-white"
                          onClick={() => goToPage(safeCurrentPage + 1)}
                          disabled={safeCurrentPage >= totalPages}
                        >
                          下一页<ChevronRight className="ml-1 h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-white/5 border-white/10 xl:sticky xl:top-24 xl:self-start">
                  <CardHeader className="border-b border-white/10 p-4">
                    <CardTitle className="text-base text-white">任务预览</CardTitle>
                    <p className="text-sm text-white/45">点选左侧任务查看详情、产物和错误信息</p>
                  </CardHeader>
                  <CardContent className="space-y-4 p-4">
                    {selectedJob ? (
                      <>
                        <div className="space-y-3">
                          <div className="flex items-start gap-3">
                            {(() => {
                              const Icon = TYPE_ICONS[selectedJob.type];
                              return (
                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-white/10 bg-black/20 text-teal-300">
                                  <Icon className="h-5 w-5" />
                                </div>
                              );
                            })()}
                            <div className="min-w-0 flex-1">
                              <h2 className="truncate text-lg font-semibold text-white">{selectedJob.name}</h2>
                              <p className="mt-1 truncate font-mono text-xs text-white/40">{selectedJob.id}</p>
                            </div>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <span className={`inline-flex h-6 items-center rounded px-2 text-xs ${STATUS_COLORS[selectedJob.status]}`}>
                              {STATUS_LABELS[selectedJob.status]}
                            </span>
                            <span className="inline-flex h-6 items-center rounded bg-white/10 px-2 text-xs text-white/70">
                              {TYPE_LABELS[selectedJob.type]}
                            </span>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3 text-sm">
                          <div className="rounded-md border border-white/10 bg-black/20 p-3">
                            <div className="flex items-center gap-2 text-white/40">
                              <Clock className="h-4 w-4" />耗时
                            </div>
                            <div className="mt-2 text-white">{formatDuration(selectedJob.duration)}</div>
                          </div>
                          <div className="rounded-md border border-white/10 bg-black/20 p-3">
                            <div className="flex items-center gap-2 text-white/40">
                              <FileText className="h-4 w-4" />进度
                            </div>
                            <div className="mt-2 text-white">{Math.max(0, Math.min(selectedJob.progress || 0, 100))}%</div>
                          </div>
                        </div>

                        <div className="space-y-2 rounded-md border border-white/10 bg-black/20 p-3 text-sm">
                          <div className="flex justify-between gap-3 text-white/45">
                            <span>创建</span>
                            <span className="text-right text-white/70">{selectedJob.createdAt}</span>
                          </div>
                          {selectedJob.startedAt && (
                            <div className="flex justify-between gap-3 text-white/45">
                              <span>开始</span>
                              <span className="text-right text-white/70">{selectedJob.startedAt}</span>
                            </div>
                          )}
                          {selectedJob.completedAt && (
                            <div className="flex justify-between gap-3 text-white/45">
                              <span>完成</span>
                              <span className="text-right text-white/70">{selectedJob.completedAt}</span>
                            </div>
                          )}
                        </div>

                        <div className="space-y-2">
                          <div className="flex items-center justify-between gap-3">
                            <h3 className="text-sm font-medium text-white">输出预览</h3>
                            <div className="flex gap-1">
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-white/60 hover:text-white"
                                onClick={() => handleOpenOutput(selectedJob)}
                                disabled={!selectedJob.output}
                                aria-label="打开当前任务输出"
                                title="打开输出"
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-white/60 hover:text-white"
                                onClick={() => handleDownloadOutput(selectedJob)}
                                disabled={!selectedJob.output}
                                aria-label="下载当前任务输出"
                                title="下载输出"
                              >
                                <Download className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                          <JobOutputPreview job={selectedJob} />
                          {selectedJob.output && (
                            <p className="truncate font-mono text-xs text-white/35">{toMediaUrl(selectedJob.output)}</p>
                          )}
                        </div>

                        {selectedJob.error && (
                          <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
                            <div className="mb-2 flex items-center gap-2 font-medium">
                              <AlertCircle className="h-4 w-4" />错误信息
                            </div>
                            <p className="whitespace-pre-wrap break-words text-red-100/85">{selectedJob.error}</p>
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="flex aspect-video items-center justify-center rounded-md border border-dashed border-white/10 bg-black/20 text-sm text-white/40">
                        选择任务后预览详情
                      </div>
                    )}
                  </CardContent>
                </Card>
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
