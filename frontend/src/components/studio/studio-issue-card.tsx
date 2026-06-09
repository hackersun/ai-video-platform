'use client';

import Link from 'next/link';
import { AlertTriangle, ArrowRight, CheckCircle2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { severityLabel, severityTone } from '@/lib/studio-mode';
import type { StudioAction, StudioIssue, StudioRunMode } from '@/lib/studio-types';

export function StudioIssueCard({
  issue,
  mode,
  onAction,
  disabled,
}: {
  issue: StudioIssue;
  mode: StudioRunMode;
  onAction?: (action: StudioAction, issue: StudioIssue) => void;
  disabled?: boolean;
}) {
  const action = issue.repair_action || undefined;
  const blocking = issue.severity === 'blocking' || issue.severity === 'error';
  const canSkipInTest = mode === 'test' && (blocking || issue.severity === 'confirmable');
  return (
    <div className={`rounded-lg border p-3 text-sm leading-6 ${severityTone(issue.severity)}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {blocking ? <AlertTriangle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
            <span className="font-medium text-white">{issue.message || issue.code || '待处理事项'}</span>
            <Badge variant="outline" className="border-current text-current">
              {severityLabel(issue.severity)}
            </Badge>
          </div>
          <div className="mt-1 text-xs text-white/65">
            {blocking
              ? '生产出片前必须修复；测试验证模式下可填写原因后临时跳过。'
              : issue.severity === 'confirmable'
                ? '已按测试验证模式降级，生产出片仍需修复。'
                : '建议处理，可降低返工和跨镜头漂移风险。'}
          </div>
          {issue.bypass_error && <div className="mt-1 text-xs text-red-100">{issue.bypass_error}</div>}
        </div>
        {action?.href ? (
          <Button asChild size="sm" variant="outline" className="shrink-0 border-white/20 text-white">
            <Link href={action.href}>
              {action.label}
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        ) : action ? (
          <Button
            size="sm"
            className="shrink-0 bg-cyan-600 hover:bg-cyan-700"
            disabled={disabled}
            onClick={() => onAction?.(action, issue)}
          >
            {action.label}
          </Button>
        ) : null}
        {canSkipInTest && (
          <Button
            size="sm"
            variant="outline"
            className="shrink-0 border-amber-300/40 text-amber-50"
            disabled={disabled}
            onClick={() => onAction?.({ code: 'skip_issue', label: '确认跳过', risk: 'confirm' }, issue)}
          >
            确认临时跳过并继续验证
          </Button>
        )}
      </div>
    </div>
  );
}
