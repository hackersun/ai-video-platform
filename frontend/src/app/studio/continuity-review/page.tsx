'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertCircle,
  ArrowUpRight,
  CheckCircle2,
  ClipboardCheck,
  Film,
  Gauge,
  RefreshCcw,
  Wand2,
} from 'lucide-react';
import { MainLayout } from '@/components/layout/main-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import apiClient, { ContinuityReviewTask, ContinuityReviewTasksResponse } from '@/lib/api-client';

const ENTITY_LABELS: Record<string, string> = {
  character: '角色',
  scene: '场景',
  prop: '道具',
  event: '事件',
};

const REVIEW_STATE_LABELS: Record<string, string> = {
  changes_requested: '需复审',
  pending_review: '待审核',
  approved: '已通过',
  locked: '已锁定',
};

type FilterOption = {
  value: string;
  label: string;
};

function episodeLabel(index?: number | null) {
  return index ? `第 ${index} 集` : '未绑定集数';
}

function reviewStateLabel(value?: string | null) {
  if (!value) return '待复审';
  return REVIEW_STATE_LABELS[value] || value;
}

function entityTypeLabel(value?: string | null) {
  if (!value) return '实体';
  return ENTITY_LABELS[value] || value;
}

function taskKey(task: ContinuityReviewTask) {
  return `${task.shot_id}-${task.entity_id || 'entity'}-${task.episode_index || 'episode'}`;
}

function taskReviewUrl(task: ContinuityReviewTask) {
  if (task.shot_review_url) return task.shot_review_url;
  if (task.workflow_id) {
    return `/studio/shot-review?workflow_id=${encodeURIComponent(task.workflow_id)}&shot_id=${encodeURIComponent(task.shot_id)}`;
  }
  return '/studio/shot-review';
}

function isResolvedTask(task: ContinuityReviewTask) {
  return task.status === 'resolved' || task.review_state === 'approved';
}

function ContinuityTaskCard({
  task,
  selected,
  resolving,
  onSelect,
  onResolve,
}: {
  task: ContinuityReviewTask;
  selected: boolean;
  resolving: boolean;
  onSelect: (task: ContinuityReviewTask, selected: boolean) => void;
  onResolve: (task: ContinuityReviewTask) => void;
}) {
  const resolved = isResolvedTask(task);

  return (
    <Card className="border-white/10 bg-white/[0.04] text-white shadow-none">
      <CardHeader className="space-y-4 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex min-w-0 gap-3">
            <Checkbox
              aria-label={`选择镜头 ${task.shot_number}`}
              checked={selected}
              onCheckedChange={(checked) => onSelect(task, checked === true)}
              className="mt-1"
            />
            <div className="min-w-0">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Badge variant="warning">{reviewStateLabel(task.review_state)}</Badge>
                {task.status ? (
                  <span className="rounded-full bg-white/[0.06] px-2.5 py-1 text-xs text-white/70">
                    {task.status === 'resolved' ? '已完成' : '待处理'}
                  </span>
                ) : null}
                <span className="rounded-full bg-white/[0.06] px-2.5 py-1 text-xs text-white/70">
                  {episodeLabel(task.episode_index)}
                </span>
                <span className="rounded-full bg-white/[0.06] px-2.5 py-1 text-xs text-white/70">
                  镜头 {task.shot_number}
                </span>
              </div>
              <CardTitle className="text-lg leading-6">
                {task.entity_name || '未命名实体'}
              </CardTitle>
              <p className="mt-1 text-sm text-white/55">
                {entityTypeLabel(task.entity_type)}
                {task.workflow_title ? ` · ${task.workflow_title}` : ''}
                {task.storyboard_title ? ` · ${task.storyboard_title}` : ''}
                {task.novel_title ? ` · ${task.novel_title}` : ''}
              </p>
            </div>
          </div>
          <Button asChild size="sm" variant="secondary" className="shrink-0">
            <Link href={taskReviewUrl(task)}>
              打开镜头审阅
              <ArrowUpRight className="ml-1.5 h-4 w-4" aria-hidden="true" />
            </Link>
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 p-4 pt-0">
        {task.change_note ? (
          <div className="rounded-md bg-amber-400/10 px-3 py-2 text-sm text-amber-50">
            {task.change_note}
          </div>
        ) : null}
        <p className="text-sm leading-6 text-white/70">
          {task.review_reason || task.review_notes || '连续性变更需要复审'}
        </p>
        {task.shot_summary ? (
          <p className="rounded-md bg-white/[0.05] px-3 py-2 text-sm leading-6 text-white/60">
            {task.shot_summary}
          </p>
        ) : null}
        <div className="flex justify-end">
          {resolved ? (
            <span className="inline-flex h-9 items-center rounded-md bg-emerald-400/10 px-3 text-sm text-emerald-50">
              <CheckCircle2 className="mr-2 h-4 w-4" aria-hidden="true" />
              已复审完成
            </span>
          ) : (
            <Button type="button" size="sm" onClick={() => onResolve(task)} disabled={resolving}>
              <CheckCircle2 className="mr-2 h-4 w-4" aria-hidden="true" />
              {resolving ? '处理中' : '标记已复审'}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function ContinuityReviewContent() {
  const [data, setData] = useState<ContinuityReviewTasksResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [resolvingShotId, setResolvingShotId] = useState('');
  const [bulkResolving, setBulkResolving] = useState(false);
  const [actionWorking, setActionWorking] = useState('');
  const [error, setError] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [novelFilter, setNovelFilter] = useState('');
  const [entityFilter, setEntityFilter] = useState('');
  const [episodeFilter, setEpisodeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('open');
  const [sort, setSort] = useState('updated_desc');
  const [selectedShotIds, setSelectedShotIds] = useState<Set<string>>(() => new Set());
  const [novelOptionCatalog, setNovelOptionCatalog] = useState<FilterOption[]>([]);
  const [entityOptionCatalog, setEntityOptionCatalog] = useState<FilterOption[]>([]);

  const mergeFilterOptions = (responseTasks: ContinuityReviewTask[]) => {
    const novelOptions = new Map(novelOptionCatalog.map((option) => [option.value, option.label]));
    const entityOptions = new Map(entityOptionCatalog.map((option) => [option.value, option.label]));
    responseTasks.forEach((task) => {
      if (task.novel_id) novelOptions.set(task.novel_id, task.novel_title || task.novel_id);
      if (task.entity_id) {
        const label = task.entity_name
          ? `${task.entity_name} (${entityTypeLabel(task.entity_type)})`
          : task.entity_id;
        entityOptions.set(task.entity_id, label);
      }
    });
    setNovelOptionCatalog(Array.from(novelOptions.entries()).map(([value, label]) => ({ value, label })));
    setEntityOptionCatalog(Array.from(entityOptions.entries()).map(([value, label]) => ({ value, label })));
  };

  const loadTasks = async () => {
    setLoading(true);
    setError('');
    setActionMessage('');
    try {
      const response = await apiClient.getContinuityReviewTasks({
        novel_id: novelFilter || undefined,
        entity_id: entityFilter || undefined,
        episode_index: episodeFilter.trim() ? Number(episodeFilter) : undefined,
        status: statusFilter || undefined,
        sort: sort || undefined,
        limit: 200,
      });
      setData(response);
      mergeFilterOptions(response.tasks);
      setSelectedShotIds((current) => {
        const availableShotIds = new Set(response.tasks.map((task) => task.shot_id));
        return new Set(Array.from(current).filter((shotId) => availableShotIds.has(shotId)));
      });
    } catch (err: any) {
      setError(err?.message || '连续性复审任务加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTasks();
  }, []);

  const tasks = data?.tasks || [];
  const selectedTasks = useMemo(() => {
    return tasks.filter((task) => selectedShotIds.has(task.shot_id));
  }, [selectedShotIds, tasks]);
  const groupedCount = useMemo(() => {
    return new Set(tasks.map((task) => task.entity_id || task.entity_name || task.shot_id)).size;
  }, [tasks]);
  const countLabel = statusFilter === 'open' ? '待复审镜头' : '复审镜头';

  const applyResolvedState = (task: ContinuityReviewTask): ContinuityReviewTask => ({
    ...task,
    status: 'resolved',
    review_state: 'approved',
  });

  const toggleTaskSelection = (task: ContinuityReviewTask, nextSelected: boolean) => {
    setSelectedShotIds((current) => {
      const next = new Set(current);
      if (nextSelected) {
        next.add(task.shot_id);
      } else {
        next.delete(task.shot_id);
      }
      return next;
    });
  };

  const resolveTask = async (task: ContinuityReviewTask) => {
    setResolvingShotId(task.shot_id);
    setError('');
    setActionMessage('');
    try {
      await apiClient.resolveContinuityReviewTask(task.shot_id);
      setData((current) => {
        if (!current) return current;
        if (statusFilter === 'all') {
          const nextTasks = current.tasks.map((item) => (
            item.shot_id === task.shot_id ? applyResolvedState(item) : item
          ));
          return { ...current, tasks: nextTasks };
        }
        const nextTasks = current.tasks.filter((item) => item.shot_id !== task.shot_id);
        return { ...current, tasks: nextTasks, total: Math.max((current.total || 0) - 1, 0) };
      });
      setSelectedShotIds((current) => {
        const next = new Set(current);
        next.delete(task.shot_id);
        return next;
      });
    } catch (err: any) {
      setError(err?.message || '标记复审完成失败');
    } finally {
      setResolvingShotId('');
    }
  };

  const resolveSelectedTasks = async () => {
    const shotIds = selectedTasks.filter((task) => !isResolvedTask(task)).map((task) => task.shot_id);
    if (!shotIds.length) return;
    setBulkResolving(true);
    setError('');
    setActionMessage('');
    try {
      await apiClient.resolveContinuityReviewTasks(shotIds);
      setData((current) => {
        if (!current) return current;
        const completed = new Set(shotIds);
        if (statusFilter === 'all') {
          const nextTasks = current.tasks.map((task) => (
            completed.has(task.shot_id) ? applyResolvedState(task) : task
          ));
          return { ...current, tasks: nextTasks };
        }
        const nextTasks = current.tasks.filter((task) => !completed.has(task.shot_id));
        return { ...current, tasks: nextTasks, total: Math.max((current.total || 0) - completed.size, 0) };
      });
      setSelectedShotIds(new Set());
      setActionMessage('已批量标记完成');
    } catch (err: any) {
      setError(err?.message || '批量标记复审完成失败');
    } finally {
      setBulkResolving(false);
    }
  };

  const regenerateSelectedShots = async () => {
    const workflowGroups = new Map<string, string[]>();
    selectedTasks.forEach((task) => {
      if (!task.workflow_id) return;
      const shotIds = workflowGroups.get(task.workflow_id) || [];
      shotIds.push(task.shot_id);
      workflowGroups.set(task.workflow_id, shotIds);
    });
    if (!workflowGroups.size) {
      setError('选中的镜头缺少工作流，无法提交重生任务');
      return;
    }
    setActionWorking('regenerate');
    setError('');
    setActionMessage('');
    try {
      await Promise.all(
        Array.from(workflowGroups.entries()).map(([workflowId, shotIds]) => (
          apiClient.regenerateWorkflowShots(workflowId, { shot_ids: shotIds })
        ))
      );
      setActionMessage('已提交重生任务');
    } catch (err: any) {
      setError(err?.message || '提交重生任务失败');
    } finally {
      setActionWorking('');
    }
  };

  const refreshSelectedQuality = async () => {
    const shotIds = selectedTasks.map((task) => task.shot_id);
    if (!shotIds.length) return;
    setActionWorking('quality');
    setError('');
    setActionMessage('');
    try {
      await apiClient.refreshShotsQuality(shotIds);
      setActionMessage('质量检查已刷新');
    } catch (err: any) {
      setError(err?.message || '质量检查刷新失败');
    } finally {
      setActionWorking('');
    }
  };

  const preflightSelectedWorkflow = async () => {
    const workflowIds = Array.from(new Set(selectedTasks.map((task) => task.workflow_id).filter(Boolean)));
    if (!workflowIds.length) {
      setError('选中的镜头缺少工作流，无法执行成片预检');
      return;
    }
    if (workflowIds.length > 1) {
      setError('请选择同一工作流的镜头执行成片预检');
      return;
    }
    const workflowId = workflowIds[0] as string;
    setActionWorking('preflight');
    setError('');
    setActionMessage('');
    try {
      await apiClient.preflightWorkflowRender(workflowId);
      setActionMessage('成片预检通过');
    } catch (err: any) {
      setError(err?.message || '成片预检失败');
    } finally {
      setActionWorking('');
    }
  };

  return (
    <MainLayout>
      <div className="space-y-6 text-white">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-normal">连续性复审</h1>
            <div className="mt-3 flex flex-wrap gap-2 text-sm text-white/70">
              <span className="rounded-md bg-white/[0.06] px-3 py-2">{data?.total ?? tasks.length} 个{countLabel}</span>
              <span className="rounded-md bg-white/[0.06] px-3 py-2">{groupedCount} 个受影响实体</span>
            </div>
          </div>
          <Button type="button" variant="secondary" onClick={loadTasks} disabled={loading}>
            <RefreshCcw className="mr-2 h-4 w-4" aria-hidden="true" />
            刷新
          </Button>
        </div>

        <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
          <div className="grid gap-3 md:grid-cols-5">
            <label className="space-y-1.5 text-sm text-white/70">
              <span>小说筛选</span>
              <Select
                aria-label="小说筛选"
                value={novelFilter}
                onValueChange={setNovelFilter}
                options={[
                  { value: '', label: '全部小说' },
                  ...novelOptionCatalog,
                ]}
              />
            </label>
            <label className="space-y-1.5 text-sm text-white/70">
              <span>实体筛选</span>
              <Select
                aria-label="实体筛选"
                value={entityFilter}
                onValueChange={setEntityFilter}
                options={[
                  { value: '', label: '全部实体' },
                  ...entityOptionCatalog,
                ]}
              />
            </label>
            <label className="space-y-1.5 text-sm text-white/70">
              <span>集数筛选</span>
              <Input
                aria-label="集数筛选"
                type="number"
                min={1}
                value={episodeFilter}
                onChange={(event) => setEpisodeFilter(event.target.value)}
                placeholder="全部集数"
                className="border-white/10 bg-white/5 text-white placeholder:text-white/40"
              />
            </label>
            <label className="space-y-1.5 text-sm text-white/70">
              <span>状态筛选</span>
              <Select
                aria-label="状态筛选"
                value={statusFilter}
                onValueChange={setStatusFilter}
                options={[
                  { value: 'open', label: '待处理' },
                  { value: 'resolved', label: '已完成' },
                  { value: 'all', label: '全部状态' },
                ]}
              />
            </label>
            <label className="space-y-1.5 text-sm text-white/70">
              <span>排序方式</span>
              <Select
                aria-label="排序方式"
                value={sort}
                onValueChange={setSort}
                options={[
                  { value: 'updated_desc', label: '最近更新优先' },
                  { value: 'updated_asc', label: '最早更新优先' },
                  { value: 'episode_desc', label: '集数从高到低' },
                  { value: 'episode_asc', label: '集数从低到高' },
                  { value: 'entity_desc', label: '实体倒序' },
                  { value: 'entity_asc', label: '实体正序' },
                ]}
              />
            </label>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button type="button" onClick={loadTasks} disabled={loading}>
              应用筛选
            </Button>
          </div>
        </div>

        {error ? (
          <div
            role="alert"
            className="flex items-center gap-2 rounded-lg border border-red-300/20 bg-red-500/10 px-4 py-3 text-sm text-red-50"
          >
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            {error}
          </div>
        ) : null}

        {actionMessage ? (
          <div
            role="status"
            aria-live="polite"
            className="flex items-center gap-2 rounded-lg border border-emerald-300/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-50"
          >
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            {actionMessage}
          </div>
        ) : null}

        {loading ? (
          <div className="rounded-lg border border-white/10 bg-white/[0.04] p-6 text-sm text-white/60">
            正在加载复审任务
          </div>
        ) : tasks.length ? (
          <div className="grid gap-3">
            {tasks.map((task) => (
              <ContinuityTaskCard
                key={taskKey(task)}
                task={task}
                selected={selectedShotIds.has(task.shot_id)}
                resolving={resolvingShotId === task.shot_id}
                onSelect={toggleTaskSelection}
                onResolve={resolveTask}
              />
            ))}
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] p-4">
              <Button
                type="button"
                variant="secondary"
                onClick={resolveSelectedTasks}
                disabled={!selectedTasks.length || bulkResolving}
              >
                <ClipboardCheck className="mr-2 h-4 w-4" aria-hidden="true" />
                {bulkResolving ? '处理中' : '批量标记已复审'}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={regenerateSelectedShots}
                disabled={!selectedTasks.length || Boolean(actionWorking)}
              >
                <Wand2 className="mr-2 h-4 w-4" aria-hidden="true" />
                重生选中镜头
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={refreshSelectedQuality}
                disabled={!selectedTasks.length || Boolean(actionWorking)}
              >
                <Gauge className="mr-2 h-4 w-4" aria-hidden="true" />
                刷新质量检查
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={preflightSelectedWorkflow}
                disabled={!selectedTasks.length || Boolean(actionWorking)}
              >
                <Film className="mr-2 h-4 w-4" aria-hidden="true" />
                成片预检
              </Button>
              <span className="ml-auto text-sm text-white/55">
                已选择 {selectedTasks.length} 个镜头
              </span>
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-white/10 bg-white/[0.04] p-6 text-sm text-white/60">
            暂无待复审镜头
          </div>
        )}
      </div>
    </MainLayout>
  );
}

export default function ContinuityReviewPage() {
  return <ContinuityReviewContent />;
}
