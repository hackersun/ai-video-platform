'use client';

import type { ReactNode } from 'react';
import { Sparkles } from 'lucide-react';

export type StoryMetric = {
  label: string;
  value: ReactNode;
  helper?: string;
};

type StoryWorkbenchPanelProps = {
  heading: string;
  description?: string;
  title: string;
  subtitle?: string;
  excerpt?: string;
  excerptLabel?: string;
  metrics?: StoryMetric[];
  actions?: ReactNode;
  footer?: ReactNode;
};

export function getStoryExcerpt(value?: string | null, fallback = '暂无可预览内容', maxLength = 180) {
  const normalized = (value || '')
    .replace(/\r/g, '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .join('\n');

  if (!normalized) return fallback;
  return normalized.length > maxLength ? `${normalized.slice(0, maxLength)}…` : normalized;
}

export function StoryWorkbenchPanel({
  heading,
  description = '预览内容、核对生产状态，并从这里进入 AI 辅助流程。',
  title,
  subtitle,
  excerpt,
  excerptLabel = '预览',
  metrics = [],
  actions,
  footer,
}: StoryWorkbenchPanelProps) {
  return (
    <aside className="rounded-lg border border-white/10 bg-white/[0.055] shadow-sm shadow-black/20 xl:sticky xl:top-24">
      <div className="border-b border-white/10 px-4 py-4">
        <h2 className="text-base font-semibold text-white">{heading}</h2>
        <p className="mt-1 text-sm text-white/45">{description}</p>
      </div>
      <div className="space-y-4 p-4">
        <div>
          <h3 className="break-words text-lg font-semibold leading-7 text-white">{title}</h3>
          {subtitle && <p className="mt-1 text-sm text-white/45">{subtitle}</p>}
        </div>

        <div className="rounded-md border border-white/10 bg-black/20 p-3">
          <div className="mb-2 text-xs font-medium text-white/40">{excerptLabel}</div>
          <p className="whitespace-pre-wrap break-words text-sm leading-7 text-white/72">
            {excerpt || '暂无可预览内容'}
          </p>
        </div>

        {metrics.length > 0 && (
          <div className="grid grid-cols-2 gap-2">
            {metrics.map((item) => (
              <div key={item.label} className="rounded-md border border-white/10 bg-black/15 px-3 py-2">
                <div className="text-xs text-white/40">{item.label}</div>
                <div className="mt-1 text-sm font-semibold text-white">{item.value}</div>
                {item.helper && <div className="mt-1 truncate text-xs text-white/35">{item.helper}</div>}
              </div>
            ))}
          </div>
        )}

        {actions && (
          <div className="rounded-md border border-cyan-400/20 bg-cyan-500/[0.07] p-3">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-cyan-50">
              <Sparkles className="h-4 w-4" />
              AI 下一步
            </div>
            <div className="flex flex-col gap-2">{actions}</div>
          </div>
        )}

        {footer}
      </div>
    </aside>
  );
}
