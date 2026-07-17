'use client';

import { useState } from 'react';
import { Archive, Edit3, Eye, Globe2, History, ImageIcon, Lock, RefreshCw, Unlock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { AssetWorkbenchItem } from '../asset-workbench-model';
import type { AssetEntityOption } from '../types';
import { getAssetFailure, getConsistencyScore, workbenchStatus } from '../asset-workbench-model';
import { AssetEntityDeactivateDialog } from './asset-entity-deactivate-dialog';

type Props = {
  asset?: AssetWorkbenchItem;
  toMediaUrl: (url?: string) => string;
  categoryLabel: (category: string) => string;
  onPreview: (asset: AssetWorkbenchItem) => void;
  onEdit: (asset: AssetWorkbenchItem) => void;
  onRetry: (asset: AssetWorkbenchItem) => void;
  onLock: (assetId: string) => void;
  onUnlock: (assetId: string) => void;
  onHistory: (asset: AssetWorkbenchItem) => void;
  onScopeGlobal: (asset: AssetWorkbenchItem) => void;
  onArchive: (assetId: string) => void;
  entityOptions: AssetEntityOption[];
  onDeactivateEntity: (entity: AssetEntityOption) => Promise<boolean>;
};

export function AssetInspector(props: Props) {
  const [deactivateOpen, setDeactivateOpen] = useState(false);
  const [deactivating, setDeactivating] = useState(false);
  const asset = props.asset;
  if (!asset) return <aside data-testid="asset-inspector" className="p-5 text-sm text-white/40">选择一项资产查看详情</aside>;
  const failure = getAssetFailure(asset);
  const consistency = getConsistencyScore(asset);
  const status = workbenchStatus(asset);
  const preview = props.toMediaUrl(asset.thumbnail_url || asset.url);
  const entity = props.entityOptions.find((item) => item.id === asset.entity_id);

  const confirmDeactivate = async () => {
    if (!entity) return;
    setDeactivating(true);
    try {
      if (await props.onDeactivateEntity(entity)) setDeactivateOpen(false);
    } finally {
      setDeactivating(false);
    }
  };

  return (
    <aside data-testid="asset-inspector" className="min-w-0 border-t border-white/10 bg-black/15 p-4 lg:border-l lg:border-t-0">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="min-w-0 flex-1 truncate text-lg font-semibold text-white">{asset.name}</h2>
        <span className={`text-xs ${failure ? 'text-red-300' : 'text-white/45'}`}>● {status.label}</span>
      </div>
      <div className="mt-4 flex aspect-[4/3] items-center justify-center overflow-hidden rounded-xl border border-white/10 bg-black/30">
        {preview ? <img src={preview} alt={asset.name} className="h-full w-full object-contain" /> : <ImageIcon className="h-8 w-8 text-white/25" />}
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3"><div className="text-white/35">类型</div><div className="mt-1 text-white/75">{props.categoryLabel(asset.category)}</div></div>
        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3"><div className="text-white/35">版本</div><div className="mt-1 text-white/75">v{asset.version || 1}</div></div>
        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3"><div className="text-white/35">引用</div><div className="mt-1 text-white/75">{asset.usage_count || 0} 次</div></div>
        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3"><div className="text-white/35">一致性</div><div className={`mt-1 ${consistency !== null && consistency < 60 ? 'text-red-300' : 'text-emerald-300'}`}>{consistency ?? '未检测'}{consistency !== null ? ' 分' : ''}</div></div>
      </div>
      {failure && (
        <div className="mt-4 rounded-lg border border-red-400/20 bg-red-500/[0.08] p-3 text-xs leading-5 text-red-100">
          <div className="font-medium">问题详情</div><div className="mt-1 text-red-200/80">{failure.error}</div>
        </div>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" variant="outline" className="border-white/15 text-white" onClick={() => props.onPreview(asset)}><Eye className="mr-1 h-3.5 w-3.5" />预览</Button>
        <Button size="sm" variant="outline" className="border-white/15 text-white" onClick={() => props.onEdit(asset)}><Edit3 className="mr-1 h-3.5 w-3.5" />编辑</Button>
        {failure?.retryable && <Button size="sm" variant="outline" className="border-red-300/25 text-red-100" onClick={() => props.onRetry(asset)}><RefreshCw className="mr-1 h-3.5 w-3.5" />重试</Button>}
        {asset.is_locked
          ? <Button size="sm" variant="outline" className="border-amber-300/25 text-amber-100" onClick={() => props.onUnlock(asset.id)}><Unlock className="mr-1 h-3.5 w-3.5" />解锁</Button>
          : <Button size="sm" variant="outline" className="border-emerald-300/25 text-emerald-100" onClick={() => props.onLock(asset.id)}><Lock className="mr-1 h-3.5 w-3.5" />锁定</Button>}
        {asset.entity_id && <Button size="sm" variant="outline" className="border-white/15 text-white" onClick={() => props.onHistory(asset)}><History className="mr-1 h-3.5 w-3.5" />版本</Button>}
        <Button size="sm" variant="outline" className="border-white/15 text-white" onClick={() => props.onScopeGlobal(asset)}><Globe2 className="mr-1 h-3.5 w-3.5" />设为全局</Button>
        <Button size="sm" variant="outline" className="border-red-300/20 text-red-100" onClick={() => props.onArchive(asset.id)}><Archive className="mr-1 h-3.5 w-3.5" />归档当前资产</Button>
        {entity && <Button size="sm" variant="outline" className="border-red-300/30 text-red-100" onClick={() => setDeactivateOpen(true)}><Archive className="mr-1 h-3.5 w-3.5" />停用制片对象</Button>}
      </div>
      {entity && deactivateOpen && <AssetEntityDeactivateDialog entity={entity} busy={deactivating} onCancel={() => setDeactivateOpen(false)} onConfirm={confirmDeactivate} />}
    </aside>
  );
}
