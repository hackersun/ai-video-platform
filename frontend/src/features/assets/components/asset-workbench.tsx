'use client';

import { useEffect, useMemo, useState } from 'react';
import type { AssetCollectionKey, AssetWorkbenchItem } from '../asset-workbench-model';
import type { AssetEntityOption } from '../types';
import { matchesCollection } from '../asset-workbench-model';
import { AssetBulkBar } from './asset-bulk-bar';
import { AssetCollectionSidebar } from './asset-collection-sidebar';
import { AssetInspector } from './asset-inspector';
import { AssetPagination } from './asset-pagination';
import { AssetTable } from './asset-table';
import { AssetWorkbenchHeader } from './asset-workbench-header';

type Props = {
  assets: AssetWorkbenchItem[];
  novels: { id: string; title: string }[];
  selectedNovelId: string;
  search: string;
  loading: boolean;
  selectedIds: Set<string>;
  entityOptions: AssetEntityOption[];
  toMediaUrl: (url?: string) => string;
  categoryLabel: (category: string) => string;
  onNovelChange: (value: string) => void;
  onSearchChange: (value: string) => void;
  onRefresh: () => void;
  onCreate: () => void;
  onCompleteMissing: () => void;
  onToggle: (assetId: string) => void;
  onClearSelection: () => void;
  onPreview: (asset: AssetWorkbenchItem) => void;
  onEdit: (asset: AssetWorkbenchItem) => void;
  onRetry: (asset: AssetWorkbenchItem) => void;
  onRegenerate: (asset: AssetWorkbenchItem) => void;
  onArchive: (assetId: string) => void;
  onLock: (assetId: string) => void;
  onUnlock: (assetId: string) => void;
  onHistory: (asset: AssetWorkbenchItem) => void;
  onScopeGlobal: (asset: AssetWorkbenchItem) => void;
  onBatchLock: () => void;
  onBatchUnlock: () => void;
  onBatchTag: () => void;
  onBatchScope: () => void;
  onBatchRebuild: () => void;
  onBatchArchive: () => void;
  onDeactivateEntity: (entity: AssetEntityOption) => Promise<boolean>;
};

export function AssetWorkbench(props: Props) {
  const [collection, setCollection] = useState<AssetCollectionKey>('all');
  const [inspectedId, setInspectedId] = useState<string>();
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const filteredAssets = useMemo(() => {
    const query = props.search.trim().toLowerCase();
    return props.assets.filter((asset) => matchesCollection(asset, collection))
      .filter((asset) => !query || [asset.name, asset.description, ...(asset.tags || [])].some((value) => value?.toLowerCase().includes(query)));
  }, [collection, props.assets, props.search]);
  const totalPages = Math.max(1, Math.ceil(filteredAssets.length / pageSize));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const pageStart = (safeCurrentPage - 1) * pageSize;
  const pagedAssets = filteredAssets.slice(pageStart, pageStart + pageSize);
  const inspected = pagedAssets.find((asset) => asset.id === inspectedId) || pagedAssets[0];

  useEffect(() => {
    setCurrentPage(1);
  }, [collection, pageSize, props.search]);

  useEffect(() => {
    if (currentPage > totalPages) setCurrentPage(totalPages);
  }, [currentPage, totalPages]);

  const goToPage = (page: number) => {
    setCurrentPage(Math.min(Math.max(page, 1), totalPages));
  };

  return (
    <section data-testid="asset-workbench" className="overflow-hidden rounded-2xl border border-white/10 bg-slate-950/55 shadow-2xl shadow-black/20">
      <AssetWorkbenchHeader {...props} />
      <div className="grid min-w-0 lg:grid-cols-[190px_minmax(0,1fr)] xl:grid-cols-[190px_minmax(0,1fr)_300px]">
        <AssetCollectionSidebar assets={props.assets} active={collection} novelNames={props.novels.map((novel) => novel.title)} onChange={setCollection} />
        <main className="min-w-0 bg-white/[0.015]">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-2 text-xs text-white/40">
            <span>{filteredAssets.length} 项资产</span><span>列表视图</span>
          </div>
          <AssetTable {...props} assets={pagedAssets} inspectedId={inspected?.id} onInspect={(asset) => setInspectedId(asset.id)} />
          <AssetPagination
            currentPage={safeCurrentPage}
            pageSize={pageSize}
            totalItems={filteredAssets.length}
            onPageChange={goToPage}
            onPageSizeChange={setPageSize}
          />
          <AssetBulkBar
            count={props.selectedIds.size}
            onLock={props.onBatchLock}
            onUnlock={props.onBatchUnlock}
            onTag={props.onBatchTag}
            onScope={props.onBatchScope}
            onRebuild={props.onBatchRebuild}
            onArchive={props.onBatchArchive}
            onClear={props.onClearSelection}
          />
        </main>
        <div className="lg:col-span-2 xl:col-span-1">
          <AssetInspector {...props} asset={inspected} />
        </div>
      </div>
    </section>
  );
}
