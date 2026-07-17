'use client';

import { AlertCircle, CheckCircle2, Clock3, Loader2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import type { StudioActionResult } from '@/lib/studio-types';
import type { StudioGuidance } from '@/lib/studio-types';

function statusCopy(status?: string) {
  if (status === 'succeeded') return '执行完成';
  if (status === 'failed') return '执行失败';
  if (status === 'skipped') return '已记录跳过';
  if (status === 'running') return '执行中';
  return '最近动作';
}

function StatusIcon({ status, loading }: { status?: string; loading?: boolean }) {
  if (loading || status === 'running') return <Loader2 className="h-4 w-4 animate-spin text-cyan-300" aria-hidden />;
  if (status === 'failed') return <AlertCircle className="h-4 w-4 text-red-300" aria-hidden />;
  if (status === 'succeeded' || status === 'skipped') return <CheckCircle2 className="h-4 w-4 text-emerald-300" aria-hidden />;
  return <Clock3 className="h-4 w-4 text-white/45" aria-hidden />;
}

export function StudioActionProgress({
  action,
  loading,
  retryMessage,
  resume,
}: {
  action: StudioActionResult | null;
  loading?: boolean;
  retryMessage?: string;
  resume?: StudioGuidance['orchestration_resume'];
}) {
  if (!action && !loading && !retryMessage && !resume?.task_id) return null;

  return (
    <Card className="border-white/10 bg-white/[0.04]">
      <CardContent className="flex flex-col gap-2 p-3 text-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-start gap-2">
          <StatusIcon status={action?.status} loading={loading && !action} />
          <div className="min-w-0">
            <div className="font-medium text-white">{retryMessage || statusCopy(action?.status)}</div>
            {action ? (
              <div className="mt-0.5 min-w-0 break-words text-xs leading-5 text-white/55">
                {action.label || action.code}
                {action.source_issue_code ? ` · 来源 ${action.source_issue_code}` : ''}
                {action.error_message ? ` · ${action.error_message}` : ''}
              </div>
            ) : resume?.task_id ? (
              <div className="mt-0.5 min-w-0 break-words text-xs leading-5 text-white/55">
                任务 {resume.task_id} · 已完成 {(resume.completed_stages || []).join('、') || '无'}
                {resume.safe_retry ? ' · 可安全重试当前阶段' : ''}
              </div>
            ) : (
              <div className="mt-0.5 text-xs text-white/45">正在刷新工作台状态</div>
            )}
          </div>
        </div>
        {action?.updated_at || action?.created_at ? (
          <div className="shrink-0 text-xs text-white/40">{action.updated_at || action.created_at}</div>
        ) : null}
      </CardContent>
    </Card>
  );
}
