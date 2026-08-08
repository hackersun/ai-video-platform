'use client';

import { Loader2, RefreshCw, Search, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

type Props = {
  query: { type?: string; status?: string; query?: string };
  selectedCount: number;
  refreshing: boolean;
  rebuilding: boolean;
  onQuery: (updates: Record<string, string | undefined>, resetPage?: boolean) => void;
  onReview: (action: 'approve' | 'reject') => void;
  onRefresh: () => void;
  onRebuild: () => void;
};

export function EntityReviewToolbar(props: Props) {
  return (
    <div className="space-y-3 border-b border-white/10 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <select aria-label="实体类型" value={props.query.type || ''} onChange={(event) => props.onQuery({ type: event.target.value || undefined }, true)} className="h-9 rounded-md border border-white/15 bg-slate-950 px-3 text-sm text-white">
          <option value="">全部类型</option><option value="character">角色</option><option value="scene">场景</option><option value="prop">道具</option><option value="event">事件</option>
        </select>
        <select aria-label="审核状态" value={props.query.status || ''} onChange={(event) => props.onQuery({ status: event.target.value || undefined }, true)} className="h-9 rounded-md border border-white/15 bg-slate-950 px-3 text-sm text-white">
          <option value="">全部状态</option><option value="candidate">待审核</option><option value="approved">已定稿</option><option value="rejected">已拒绝</option><option value="legacy_active">旧数据</option><option value="archived">已归档</option>
        </select>
        <div className="relative min-w-[220px] flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-white/35" />
          <Input aria-label="搜索资产" value={props.query.query || ''} onChange={(event) => props.onQuery({ q: event.target.value || undefined }, true)} className="pl-9" placeholder="搜索名称、别名、描述或原文证据" />
        </div>
        <Button variant="outline" onClick={props.onRefresh} disabled={props.refreshing}>
          <RefreshCw className={`mr-2 h-4 w-4 ${props.refreshing ? 'animate-spin' : ''}`} />刷新
        </Button>
        <Button variant="outline" className="border-cyan-500/40" onClick={props.onRebuild} disabled={props.rebuilding}>
          {props.rebuilding ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}AI 重新分析全书
        </Button>
      </div>
      <div className="flex min-h-9 flex-wrap items-center gap-2">
        <span className="text-sm text-white/60">已选择 {props.selectedCount} 项</span>
        <Button size="sm" disabled={!props.selectedCount} onClick={() => props.onReview('approve')}>批量定稿</Button>
        <Button size="sm" variant="outline" className="border-rose-500/40" disabled={!props.selectedCount} onClick={() => props.onReview('reject')}>批量拒绝</Button>
        <span className="text-xs text-white/40">选择会跨页保留；问题项会单独跳过并说明原因。</span>
      </div>
    </div>
  );
}
