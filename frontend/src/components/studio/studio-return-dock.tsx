'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { studioQuickTaskLabel } from '@/lib/studio-quick-actions';

function safeStudioReturn(raw: string | null) {
  return raw?.startsWith('/studio') && !raw.startsWith('//') ? raw : '/studio';
}

export function StudioReturnDock() {
  const searchParams = useSearchParams();
  if (searchParams.get('source') !== 'studio') return null;
  return (
    <Link
      data-testid="studio-return-dock"
      href={safeStudioReturn(searchParams.get('return_to'))}
      className="fixed bottom-4 left-1/2 z-50 inline-flex -translate-x-1/2 items-center gap-2 rounded-full border border-violet-300/30 bg-slate-950/95 px-4 py-2 text-sm font-medium text-violet-100 shadow-2xl backdrop-blur hover:bg-violet-950"
    >
      <ArrowLeft className="h-4 w-4" />返回工作台继续处理
    </Link>
  );
}

export function StudioTaskContext() {
  const searchParams = useSearchParams();
  const label = studioQuickTaskLabel(searchParams.get('focus') || '');
  if (searchParams.get('source') !== 'studio' || !label) return null;
  return (
    <div data-testid="studio-task-context" className="mb-5 flex items-center justify-between gap-3 rounded-lg border border-violet-300/20 bg-violet-500/10 px-4 py-3 text-sm text-violet-50">
      <span>当前快捷任务：<strong>{label}</strong></span>
      <span className="hidden text-xs text-violet-100/60 sm:inline">已保留当前小说、章节和工作流上下文</span>
    </div>
  );
}
