'use client';

import { Bot, Loader2, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { StudioIssueCard } from './studio-issue-card';
import type { StudioIssue, StudioRunMode, StudioSnapshot } from '@/lib/studio-types';

export function StudioAgentPanel({
  snapshot,
  mode,
  loading,
  onRefresh,
  onAction,
}: {
  snapshot: StudioSnapshot | null;
  mode: StudioRunMode;
  loading?: boolean;
  onRefresh: () => void;
  onAction: (code: string) => void;
}) {
  const issues = snapshot?.issues || [];
  const nextIssue: StudioIssue | undefined = issues.find((item) => ['blocking', 'error', 'confirmable'].includes(String(item.severity))) || issues[0];
  return (
    <Card className="border-white/10 bg-white/5">
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-white">
              <Bot className="h-4 w-4 text-cyan-300" />
              Agent 监督返修
            </CardTitle>
            <div className="mt-1 text-sm text-white/55">
              {mode === 'production' ? '生产模式会阻断硬性缺失项，并给出修复入口。' : '测试模式可临时跳过部分限制，但会保留审计记录。'}
            </div>
          </div>
          <Button size="sm" variant="outline" className="border-white/20 text-white" onClick={onRefresh} disabled={loading}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            刷新检查
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {nextIssue ? (
          <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/10 p-3 text-sm leading-6 text-cyan-50">
            <div className="font-medium">下一步：{nextIssue.repair_action?.label || nextIssue.message || '继续完善生产条件'}</div>
            <div className="mt-1 text-white/70">{nextIssue.message}</div>
          </div>
        ) : (
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-sm text-emerald-50">
            当前工作流没有阻断项，可继续生成、合成或导出。
          </div>
        )}

        {issues.length ? (
          issues.map((issue, index) => (
            <StudioIssueCard key={`${issue.code || 'issue'}-${index}`} issue={issue} onAction={onAction} disabled={loading} />
          ))
        ) : (
          <div className="rounded-lg border border-white/10 bg-black/20 p-6 text-center text-sm text-white/50">
            暂无问题。选择工作流后可查看完整检查结果。
          </div>
        )}
      </CardContent>
    </Card>
  );
}
