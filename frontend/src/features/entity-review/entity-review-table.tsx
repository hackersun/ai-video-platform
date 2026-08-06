'use client';

import { Check, Loader2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { ReviewEntity, ReviewPage } from './types';

const TYPE_LABEL: Record<string, string> = { character: '角色', scene: '场景', prop: '道具', event: '事件' };
const STATUS_LABEL: Record<string, string> = { candidate: '待审核', approved: '已定稿', rejected: '已拒绝', legacy_active: '旧数据', archived: '已归档' };

type Props = {
  data: ReviewPage;
  selectedIds: Set<string>;
  activeId?: string;
  busyIds: Set<string>;
  onSelected: (next: Set<string>) => void;
  onActive: (id: string) => void;
  onReview: (ids: string[], action: 'approve' | 'reject') => void;
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
};

export function EntityReviewTable(props: Props) {
  const pageIds = props.data.items.map((item) => item.id);
  const allSelected = pageIds.length > 0 && pageIds.every((id) => props.selectedIds.has(id));
  const togglePage = () => {
    const next = new Set(props.selectedIds);
    pageIds.forEach((id) => allSelected ? next.delete(id) : next.add(id));
    props.onSelected(next);
  };
  const toggle = (id: string) => {
    const next = new Set(props.selectedIds);
    next.has(id) ? next.delete(id) : next.add(id); props.onSelected(next);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="max-h-[62vh] min-h-[440px] overflow-auto">
        <table className="w-full min-w-[880px] text-left text-sm">
          <thead className="sticky top-0 z-10 border-b border-white/10 bg-slate-950 text-xs text-white/50">
            <tr><th className="w-12 px-3 py-3"><input aria-label="选择当前页" type="checkbox" checked={allSelected} onChange={togglePage} /></th><th className="px-3 py-3">实体</th><th className="px-3 py-3">类型</th><th className="px-3 py-3">质量</th><th className="px-3 py-3">状态</th><th className="px-3 py-3">证据</th><th className="px-3 py-3 text-right">操作</th></tr>
          </thead>
          <tbody>{props.data.items.map((entity) => <Row key={entity.id} entity={entity} selected={props.selectedIds.has(entity.id)} active={props.activeId === entity.id} busy={props.busyIds.has(entity.id)} onSelect={() => toggle(entity.id)} onActive={() => props.onActive(entity.id)} onReview={(action) => props.onReview([entity.id], action)} />)}</tbody>
        </table>
        {!props.data.items.length ? <div className="py-20 text-center text-sm text-white/45">当前筛选没有实体</div> : null}
      </div>
      <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 border-t border-white/10 bg-slate-950/95 px-3 py-2 text-sm">
        <span className="text-white/55">共 {props.data.total} 项 · 第 {props.data.page} / {Math.max(1, props.data.total_pages)} 页</span>
        <div className="flex items-center gap-2">
          <select aria-label="每页数量" value={props.data.page_size} onChange={(event) => props.onPageSize(Number(event.target.value))} className="h-8 rounded border border-white/15 bg-slate-950 px-2 text-white"><option value="20">20 / 页</option><option value="50">50 / 页</option><option value="100">100 / 页</option></select>
          <Button size="sm" variant="outline" disabled={props.data.page <= 1} onClick={() => props.onPage(props.data.page - 1)}>上一页</Button>
          <Button size="sm" variant="outline" disabled={props.data.page >= props.data.total_pages} onClick={() => props.onPage(props.data.page + 1)}>下一页</Button>
        </div>
      </div>
    </div>
  );
}

function Row({ entity, selected, active, busy, onSelect, onActive, onReview }: { entity: ReviewEntity; selected: boolean; active: boolean; busy: boolean; onSelect: () => void; onActive: () => void; onReview: (action: 'approve' | 'reject') => void }) {
  const quality = entity.extra_data?.quality || {};
  return <tr onClick={onActive} className={`border-b border-white/5 align-top hover:bg-white/[0.04] ${active ? 'bg-cyan-500/10' : ''}`}>
    <td className="px-3 py-3"><input aria-label={`选择${entity.name}`} type="checkbox" checked={selected} onClick={(event) => event.stopPropagation()} onChange={onSelect} /></td>
    <td className="px-3 py-3"><div className="max-w-[180px] truncate font-medium text-white">{entity.name}</div><div className="mt-1 max-w-[220px] truncate text-xs text-white/45">{entity.description || '待完善'}</div></td>
    <td className="px-3 py-3 text-white/70">{TYPE_LABEL[entity.entity_type]}</td><td className="px-3 py-3"><div className="text-white">{quality.score ?? entity.confidence}</div><div className="text-xs text-white/40">{quality.auto_decision || entity.source}</div></td>
    <td className="px-3 py-3"><span className="rounded-full border border-white/15 px-2 py-1 text-xs text-white/70">{STATUS_LABEL[entity.review_status] || entity.review_status}</span></td>
    <td className="px-3 py-3"><div className="max-h-12 max-w-[260px] overflow-hidden text-white/60">{entity.evidence || '缺少证据'}</div></td>
    <td className="px-3 py-3"><div className="flex justify-end gap-1"><Button aria-label={`定稿${entity.name}`} size="sm" variant="ghost" disabled={busy} onClick={(event) => { event.stopPropagation(); onReview('approve'); }}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}</Button><Button aria-label={`拒绝${entity.name}`} size="sm" variant="ghost" disabled={busy} onClick={(event) => { event.stopPropagation(); onReview('reject'); }}><X className="h-4 w-4" /></Button></div></td>
  </tr>;
}
