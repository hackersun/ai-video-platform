'use client';

import Link from 'next/link';
import { AlertCircle, ArrowRight, CheckCircle2, Film, ListChecks } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { NovelProductionEntry } from '@/lib/studio-types';

const STAGE_LABELS: Record<string, string> = {
  content_prepare: '内容准备',
  series_plan: '整书计划',
  workflow_create: '本集工程',
  studio_fix: '工作室处理',
  studio_ready: '可继续生产',
  not_found: '不可用',
};

function tone(entry?: NovelProductionEntry | null, failed = false) {
  if (!entry || failed) {
    return {
      card: 'border-white/10 bg-white/[0.04] text-white/60',
      button: 'bg-cyan-600 hover:bg-cyan-700',
    };
  }
  if (entry.stage === 'studio_ready') {
    return {
      card: 'border-emerald-400/25 bg-emerald-500/10 text-emerald-50',
      button: 'bg-emerald-600 hover:bg-emerald-700',
    };
  }
  if (entry.stage === 'studio_fix') {
    return {
      card: 'border-amber-400/25 bg-amber-500/10 text-amber-50',
      button: 'bg-amber-600 hover:bg-amber-700',
    };
  }
  return {
    card: 'border-cyan-400/20 bg-cyan-500/10 text-cyan-50',
    button: 'bg-cyan-600 hover:bg-cyan-700',
  };
}

type NovelProductionEntryCardProps = {
  entry?: NovelProductionEntry | null;
  failed?: boolean;
  fallbackHref?: string;
  fallbackLabel?: string;
  novelId?: string;
};

export function NovelProductionEntryCard({
  entry,
  failed = false,
  fallbackHref,
  fallbackLabel,
  novelId,
}: NovelProductionEntryCardProps) {
  const unavailable = failed || entry === null;
  const resolvedFallbackHref = fallbackHref || (novelId ? `/novels/${novelId}` : '');
  const action = entry?.primary_action || (unavailable && resolvedFallbackHref
    ? {
        href: resolvedFallbackHref,
        label: fallbackLabel || '打开小说详情',
      }
    : null);
  const currentTone = tone(entry, unavailable);
  const stageLabel = unavailable
    ? '入口不可用'
    : STAGE_LABELS[entry?.stage || ''] || entry?.label || '制作入口';
  const description = unavailable
    ? '制作入口暂时无法读取，可先进入小说详情继续章节或设定准备。'
    : entry?.description || '正在读取制作入口状态';

  return (
    <div className={`rounded-lg border p-3 ${currentTone.card}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {entry?.stage === 'studio_ready' && !unavailable ? (
              <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
            ) : (
              <AlertCircle aria-hidden="true" className="h-4 w-4" />
            )}
            <Badge variant="outline" className="border-current text-current">
              {stageLabel}
            </Badge>
            {entry?.metrics ? (
              <span className="text-xs text-white/55">
                {entry.metrics.chapter_count || 0} 章 · {entry.metrics.episode_count || 0} 集 · {entry.metrics.workflow_count || 0} 工程
              </span>
            ) : null}
          </div>
          <div className="mt-1 line-clamp-2 text-sm text-white/70">
            {description}
          </div>
        </div>
        {action?.href ? (
          <Button asChild size="sm" className={`w-full min-w-0 shrink-0 sm:w-auto sm:max-w-[220px] ${currentTone.button}`}>
            <Link href={action.href} className="min-w-0">
              {entry?.stage === 'series_plan' ? (
                <ListChecks aria-hidden="true" className="mr-1.5 h-4 w-4 shrink-0" />
              ) : (
                <Film aria-hidden="true" className="mr-1.5 h-4 w-4 shrink-0" />
              )}
              <span className="min-w-0 truncate">{action.label}</span>
              <ArrowRight aria-hidden="true" className="ml-1.5 h-4 w-4 shrink-0" />
            </Link>
          </Button>
        ) : null}
      </div>
    </div>
  );
}
