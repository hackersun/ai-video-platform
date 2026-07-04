'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { AlertCircle, ArrowUpRight, CheckCircle2, RefreshCcw } from 'lucide-react';
import { MainLayout } from '@/components/layout/main-layout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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

function ContinuityTaskCard({
  task,
  resolving,
  onResolve,
}: {
  task: ContinuityReviewTask;
  resolving: boolean;
  onResolve: (task: ContinuityReviewTask) => void;
}) {
  return (
    <Card className="border-white/10 bg-white/[0.04] text-white shadow-none">
      <CardHeader className="space-y-4 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Badge variant="warning">{reviewStateLabel(task.review_state)}</Badge>
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
              {task.storyboard_title ? ` · ${task.storyboard_title}` : ''}
              {task.novel_title ? ` · ${task.novel_title}` : ''}
            </p>
          </div>
          <Button asChild size="sm" variant="secondary" className="shrink-0">
            <Link href="/studio/shot-review">
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
          <Button type="button" size="sm" onClick={() => onResolve(task)} disabled={resolving}>
            <CheckCircle2 className="mr-2 h-4 w-4" aria-hidden="true" />
            {resolving ? '处理中' : '标记已复审'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ContinuityReviewContent() {
  const [data, setData] = useState<ContinuityReviewTasksResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [resolvingShotId, setResolvingShotId] = useState('');
  const [error, setError] = useState('');

  const loadTasks = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await apiClient.getContinuityReviewTasks({ limit: 200 });
      setData(response);
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
  const groupedCount = useMemo(() => {
    return new Set(tasks.map((task) => task.entity_id || task.entity_name || task.shot_id)).size;
  }, [tasks]);

  const resolveTask = async (task: ContinuityReviewTask) => {
    setResolvingShotId(task.shot_id);
    setError('');
    try {
      await apiClient.resolveContinuityReviewTask(task.shot_id);
      setData((current) => {
        if (!current) return current;
        const nextTasks = current.tasks.filter((item) => item.shot_id !== task.shot_id);
        return { ...current, tasks: nextTasks, total: nextTasks.length };
      });
    } catch (err: any) {
      setError(err?.message || '标记复审完成失败');
    } finally {
      setResolvingShotId('');
    }
  };

  return (
    <MainLayout>
      <div className="space-y-6 text-white">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-normal">连续性复审</h1>
            <div className="mt-3 flex flex-wrap gap-2 text-sm text-white/70">
              <span className="rounded-md bg-white/[0.06] px-3 py-2">{data?.total ?? tasks.length} 个待复审镜头</span>
              <span className="rounded-md bg-white/[0.06] px-3 py-2">{groupedCount} 个受影响实体</span>
            </div>
          </div>
          <Button type="button" variant="secondary" onClick={loadTasks} disabled={loading}>
            <RefreshCcw className="mr-2 h-4 w-4" aria-hidden="true" />
            刷新
          </Button>
        </div>

        {error ? (
          <div className="flex items-center gap-2 rounded-lg border border-red-300/20 bg-red-500/10 px-4 py-3 text-sm text-red-50">
            <AlertCircle className="h-4 w-4" aria-hidden="true" />
            {error}
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
                resolving={resolvingShotId === task.shot_id}
                onResolve={resolveTask}
              />
            ))}
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
