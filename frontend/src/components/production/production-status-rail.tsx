'use client';

import { AlertCircle, CheckCircle2, CircleDashed } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PreflightIssueList } from './preflight-issue-list';

type StatusItem = {
  label: string;
  ok: boolean;
  detail: string;
};

type PreflightIssue = {
  code?: string;
  message?: string;
  severity?: string;
  field?: string;
};

interface ProductionStatusRailProps {
  title?: string;
  subtitle?: string;
  workflowId?: string | null;
  items: StatusItem[];
  issues?: PreflightIssue[];
}

export function ProductionStatusRail({
  title = '生产状态',
  subtitle = '确认链路、素材、字幕和渲染包是否满足生成条件。',
  workflowId,
  items,
  issues = [],
}: ProductionStatusRailProps) {
  const readyCount = items.filter((item) => item.ok).length;
  const blockingCount = issues.filter((issue) => issue.severity !== 'warning').length;

  return (
    <Card className="border-white/10 bg-white/5" data-testid="production-status-rail">
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-white">
              <CircleDashed className="h-4 w-4 text-cyan-300" />
              {title}
            </CardTitle>
            <div className="mt-1 text-sm leading-6 text-white/55">{subtitle}</div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className="border-cyan-500/25 text-cyan-200">
              {workflowId ? `工程 ${workflowId.slice(0, 8)}` : '未选择工程'}
            </Badge>
            <Badge variant="outline" className={blockingCount ? 'border-red-500/25 text-red-300' : 'border-emerald-500/25 text-emerald-300'}>
              {blockingCount ? `${blockingCount} 个阻断` : `${readyCount}/${items.length} 就绪`}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 md:grid-cols-3">
          {items.map((item) => (
            <div
              key={item.label}
              className={`rounded-lg border p-3 text-sm leading-5 ${
                item.ok
                  ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-50'
                  : 'border-white/10 bg-black/20 text-white/65'
              }`}
            >
              <div className="flex items-center gap-2 font-medium">
                {item.ok ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                {item.label}
              </div>
              <div className="mt-1 text-xs opacity-75">{item.detail}</div>
            </div>
          ))}
        </div>
        {issues.length > 0 && <PreflightIssueList issues={issues} />}
      </CardContent>
    </Card>
  );
}
