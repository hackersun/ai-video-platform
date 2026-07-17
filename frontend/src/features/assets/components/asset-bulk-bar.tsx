import { Archive, Layers3, Lock, RefreshCw, Tag, Unlock, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

type Props = {
  count: number;
  onLock: () => void;
  onUnlock: () => void;
  onTag: () => void;
  onScope: () => void;
  onRebuild: () => void;
  onArchive: () => void;
  onClear: () => void;
};

export function AssetBulkBar({ count, onLock, onUnlock, onTag, onScope, onRebuild, onArchive, onClear }: Props) {
  if (!count) return null;
  return (
    <div data-testid="asset-bulk-bar" className="sticky bottom-3 z-20 mx-3 flex flex-wrap items-center gap-2 rounded-xl border border-white/15 bg-slate-950/95 p-2.5 shadow-2xl shadow-black/40 backdrop-blur lg:mx-auto lg:max-w-3xl">
      <span className="px-2 text-sm font-medium text-white">已选择 {count} 项</span>
      <span className="hidden h-6 w-px bg-white/10 sm:block" />
      <Button size="sm" variant="outline" className="border-white/15 text-white" onClick={onLock}><Lock className="mr-1 h-3.5 w-3.5" />锁定</Button>
      <Button size="sm" variant="outline" className="border-white/15 text-white" onClick={onUnlock}><Unlock className="mr-1 h-3.5 w-3.5" />解锁</Button>
      <Button size="sm" variant="outline" className="border-white/15 text-white" onClick={onTag}><Tag className="mr-1 h-3.5 w-3.5" />改标签</Button>
      <Button size="sm" variant="outline" className="border-white/15 text-white" onClick={onScope}><Layers3 className="mr-1 h-3.5 w-3.5" />改作用域</Button>
      <Button size="sm" variant="outline" className="border-white/15 text-white" onClick={onRebuild}><RefreshCw className="mr-1 h-3.5 w-3.5" />重建资产包</Button>
      <Button size="sm" variant="outline" className="border-red-300/20 text-red-100" onClick={onArchive}><Archive className="mr-1 h-3.5 w-3.5" />归档</Button>
      <Button size="sm" variant="ghost" className="ml-auto text-white/55" aria-label="清除选择" onClick={onClear}><X className="h-4 w-4" /></Button>
    </div>
  );
}
