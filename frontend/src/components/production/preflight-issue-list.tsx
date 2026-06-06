'use client';

import { AlertCircle, CheckCircle2, Info } from 'lucide-react';

type PreflightIssue = {
  code?: string;
  message?: string;
  severity?: string;
  field?: string;
};

interface PreflightIssueListProps {
  issues?: PreflightIssue[];
  emptyText?: string;
}

export function PreflightIssueList({ issues = [], emptyText = '暂无阻断问题' }: PreflightIssueListProps) {
  if (!issues.length) {
    return (
      <div className="flex items-center gap-2 rounded border border-emerald-500/20 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100">
        <CheckCircle2 className="h-4 w-4" />
        {emptyText}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {issues.map((issue, index) => {
        const blocking = issue.severity !== 'warning';
        const Icon = blocking ? AlertCircle : Info;
        return (
          <div
            key={`${issue.code || 'issue'}-${index}`}
            className={`rounded border px-3 py-2 text-sm leading-5 ${
              blocking
                ? 'border-red-500/25 bg-red-500/10 text-red-50'
                : 'border-amber-500/25 bg-amber-500/10 text-amber-50'
            }`}
          >
            <div className="flex items-start gap-2">
              <Icon className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <div>
                <div>{issue.message || issue.code || '预检问题'}</div>
                {(issue.field || issue.code) && (
                  <div className="mt-1 text-xs opacity-65">
                    {issue.field ? `字段：${issue.field}` : null}
                    {issue.field && issue.code ? ' · ' : null}
                    {issue.code ? `规则：${issue.code}` : null}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
