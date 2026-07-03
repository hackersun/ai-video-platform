'use client';

import { AlertCircle, CheckCircle2, PackageCheck } from 'lucide-react';

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

type ReferencePackageDrop = {
  reason?: string;
  entity_name?: string;
  view_key?: string;
};

type ReferencePackageItem = {
  type?: string;
};

type ReferencePackageEvidence = {
  mode?: string;
  image_count?: number;
  video_count?: number;
  audio_count?: number;
  items?: ReferencePackageItem[];
  dropped?: ReferencePackageDrop[];
};

interface HistoryReferencePackageEvidenceProps {
  referencePackage?: ReferencePackageEvidence | null;
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

function packageCount(
  referencePackage: ReferencePackageEvidence,
  countKey: 'image_count' | 'video_count' | 'audio_count',
  itemType: string
) {
  const explicitCount = Number(referencePackage[countKey]);
  if (Number.isFinite(explicitCount) && explicitCount > 0) return explicitCount;
  const items = Array.isArray(referencePackage.items) ? referencePackage.items : [];
  return items.filter(item => item?.type === itemType).length;
}

export function getReferencePackageSummaryText(referencePackage?: ReferencePackageEvidence | null) {
  if (!referencePackage) return '';
  const imageCount = packageCount(referencePackage, 'image_count', 'image');
  const videoCount = packageCount(referencePackage, 'video_count', 'video');
  const dropped = Array.isArray(referencePackage.dropped) ? referencePackage.dropped : [];
  const droppedText = dropped
    .map(item => item.entity_name || item.view_key || item.reason || '')
    .filter(Boolean)
    .join(' ');
  return [
    '参考包',
    `${imageCount}图`,
    `${videoCount}视频`,
    dropped.length ? `裁剪${dropped.length}项` : '',
    droppedText,
  ].filter(Boolean).join(' ');
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

export function HistoryReferencePackageEvidence({ referencePackage, testId }: HistoryReferencePackageEvidenceProps) {
  if (!referencePackage) return null;

  const imageCount = packageCount(referencePackage, 'image_count', 'image');
  const videoCount = packageCount(referencePackage, 'video_count', 'video');
  const dropped = Array.isArray(referencePackage.dropped) ? referencePackage.dropped : [];
  if (imageCount === 0 && videoCount === 0 && dropped.length === 0) return null;

  return (
    <div
      data-testid={testId}
      className="mt-2 rounded border border-sky-500/25 bg-sky-500/10 px-2.5 py-1.5 text-xs text-sky-100"
    >
      <div className="flex flex-wrap items-center gap-1.5 font-medium">
        <PackageCheck className="h-3.5 w-3.5 shrink-0" />
        <span>参考包</span>
        <span className="font-normal opacity-80">{imageCount}图</span>
        <span className="font-normal opacity-80">{videoCount}视频</span>
        {dropped.length > 0 && (
          <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-amber-100">
            裁剪{dropped.length}项
          </span>
        )}
      </div>
      {dropped.length > 0 && (
        <div className="mt-1 space-y-0.5 text-sky-100/75">
          {dropped.slice(0, 2).map((item, index) => (
            <div key={`${item.entity_name || item.view_key || item.reason || 'dropped'}-${index}`} className="truncate">
              {item.entity_name || item.view_key || item.reason || '参考项'}
            </div>
          ))}
          {dropped.length > 2 && <div>还有 {dropped.length - 2} 项</div>}
        </div>
      )}
    </div>
  );
}
