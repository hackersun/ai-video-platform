'use client';

import { Loader2, ShieldAlert } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { AssetEntityOption } from '../types';

type Props = {
  entity: AssetEntityOption;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function AssetEntityDeactivateDialog({ entity, busy, onCancel, onConfirm }: Props) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
      <div role="dialog" aria-label="停用制片对象" aria-modal="true" className="w-full max-w-md rounded-2xl border border-red-300/20 bg-slate-950 p-5 shadow-2xl">
        <div className="flex items-start gap-3"><div className="rounded-xl bg-red-500/10 p-2 text-red-200"><ShieldAlert className="h-5 w-5" /></div><div><h2 className="text-lg font-semibold text-white">停用制片对象</h2><p className="mt-1 text-sm leading-6 text-white/55">「{entity.name}」将不再出现在资产向导和编辑器中，并归档其 {entity.active_asset_count} 项活动资产。历史记录仍会保留。</p></div></div>
        <div className="mt-5 flex justify-end gap-2"><Button type="button" variant="outline" className="border-white/20 text-white" disabled={busy} onClick={onCancel}>取消</Button><Button type="button" className="bg-red-600 hover:bg-red-700" disabled={busy} onClick={onConfirm}>{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}确认停用</Button></div>
      </div>
    </div>
  );
}
