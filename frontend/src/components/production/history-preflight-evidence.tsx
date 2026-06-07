'use client';

import { AlertCircle, CheckCircle2 } from 'lucide-react';

type PreflightIssue = {
  code?: string;
  message?: string;
  severity?: string;
  field?: string;
};

type GenerationPreflight = {
  ready?: boolean;
  issues?: PreflightIssue[];
  blocking_issue_count?: number;
  warning_issue_count?: number;
};

interface HistoryPreflightEvidenceProps {
  preflight?: GenerationPreflight | null;
  testId?: string;
}

export function getPreflightSummaryText(preflight?: GenerationPreflight | null) {
  if (!preflight) return '';
  const issues = Array.isArray(preflight.issues) ? preflight.issues : [];
  const blockingCount = Number(preflight.blocking_issue_count ?? issues.filter(issue => issue.severity !== 'warning').length);
  const title = preflight.ready === false ? '预检未通过' : '预检通过';
  return [
    title,
    blockingCount ? `${blockingCount} 个阻断项` : '无阻断项',
    ...issues.map(issue => issue.message || issue.code || '').filter(Boolean),
  ].join(' ');
}

export function HistoryPreflightEvidence({ preflight, testId }: HistoryPreflightEvidenceProps) {
  if (!preflight) return null;

  const issues = Array.isArray(preflight.issues) ? preflight.issues : [];
  const blockingCount = Number(preflight.blocking_issue_count ?? issues.filter(issue => issue.severity !== 'warning').length);
  const failed = preflight.ready === false || blockingCount > 0;
  const Icon = failed ? AlertCircle : CheckCircle2;

  return (
    <div
      data-testid={testId}
      className={`mt-2 rounded border px-2.5 py-1.5 text-xs ${
        failed
          ? 'border-red-500/25 bg-red-500/10 text-red-100'
          : 'border-emerald-500/25 bg-emerald-500/10 text-emerald-100'
      }`}
    >
      <div className="flex items-center gap-1.5 font-medium">
        <Icon className="h-3.5 w-3.5 shrink-0" />
        <span>{failed ? '预检未通过' : '预检通过'}</span>
        <span className="font-normal opacity-70">
          {blockingCount > 0 ? `${blockingCount} 个阻断项` : '无阻断项'}
        </span>
      </div>
      {issues.length > 0 && (
        <div className="mt-1 space-y-0.5 opacity-80">
          {issues.slice(0, 3).map((issue, index) => (
            <div key={`${issue.code || 'issue'}-${index}`} className="truncate">
              {issue.message || issue.code || '预检问题'}
            </div>
          ))}
          {issues.length > 3 && <div>还有 {issues.length - 3} 项问题</div>}
        </div>
      )}
    </div>
  );
}
