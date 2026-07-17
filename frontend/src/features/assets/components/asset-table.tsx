import { Archive, Edit3, ImageIcon, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { AssetWorkbenchItem } from '../asset-workbench-model';
import { getAssetFailure, workbenchStatus } from '../asset-workbench-model';

type Props = {
  assets: AssetWorkbenchItem[];
  selectedIds: Set<string>;
  inspectedId?: string;
  toMediaUrl: (url?: string) => string;
  categoryLabel: (category: string) => string;
  onInspect: (asset: AssetWorkbenchItem) => void;
  onToggle: (assetId: string) => void;
  onEdit: (asset: AssetWorkbenchItem) => void;
  onRegenerate: (asset: AssetWorkbenchItem) => void;
  onArchive: (assetId: string) => void;
};

const toneClasses = {
  red: 'border-red-400/25 bg-red-500/10 text-red-200',
  green: 'border-emerald-400/25 bg-emerald-500/10 text-emerald-200',
  cyan: 'border-cyan-400/25 bg-cyan-500/10 text-cyan-200',
  amber: 'border-amber-400/25 bg-amber-500/10 text-amber-200',
};

export function AssetTable(props: Props) {
  if (props.assets.length === 0) {
    return <div className="flex min-h-64 items-center justify-center p-8 text-sm text-white/45">当前集合暂无资产</div>;
  }

  return (
    <div className="min-w-0">
      <div className="hidden grid-cols-[32px_minmax(240px,2fr)_130px_120px_90px_108px] gap-3 border-b border-white/10 px-4 py-2 text-xs text-white/35 xl:grid">
        <span /><span>资产</span><span>类型 / 视图</span><span>状态</span><span>引用次数</span><span>更新时间</span>
      </div>
      <div className="divide-y divide-white/[0.07]">
        {props.assets.map((asset) => {
          const failure = getAssetFailure(asset);
          const status = workbenchStatus(asset);
          const preview = props.toMediaUrl(asset.thumbnail_url || asset.url);
          const viewLabel = asset.generation_params?.view_label || asset.generation_params?.view_key;
          return (
            <div
              key={asset.id}
              data-testid="asset-table-row"
              className={`group relative cursor-pointer px-3 py-3 transition hover:bg-white/[0.045] ${props.inspectedId === asset.id ? 'bg-violet-500/[0.09] ring-1 ring-inset ring-violet-400/20' : ''}`}
              onClick={() => props.onInspect(asset)}
            >
              <div data-testid="asset-card" className="grid min-w-0 gap-3 xl:grid-cols-[32px_minmax(240px,2fr)_130px_120px_90px_108px] xl:items-center">
                <div onClick={(event) => event.stopPropagation()}>
                  <input
                    type="checkbox"
                    aria-label={`选择${asset.name}`}
                    checked={props.selectedIds.has(asset.id)}
                    onChange={() => props.onToggle(asset.id)}
                    className="h-4 w-4 rounded border-white/20 accent-violet-500"
                  />
                </div>
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-14 w-20 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-white/10 bg-black/30">
                    {preview ? <img src={preview} alt={asset.name} className="h-full w-full object-cover" /> : <ImageIcon className="h-5 w-5 text-white/25" />}
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-white">{asset.name}</div>
                    <div className="mt-1 truncate text-xs text-white/40">{asset.description || '暂无描述'}</div>
                    {failure && <div className="mt-1 line-clamp-1 text-xs text-red-300">{failure.error}</div>}
                  </div>
                </div>
                <div className="text-xs text-white/55"><span className="xl:hidden">类型 · </span>{props.categoryLabel(asset.category)}{viewLabel ? ` / ${viewLabel}` : ''}</div>
                <div><span className={`inline-flex rounded-full border px-2 py-1 text-xs ${toneClasses[status.tone]}`}>{status.label}</span></div>
                <div className="text-xs tabular-nums text-white/55"><span className="xl:hidden">引用 · </span>{asset.usage_count || 0}</div>
                <div className="flex items-center justify-between gap-2 text-xs text-white/40">
                  <span>{asset.updated_at ? new Date(asset.updated_at).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }) : '—'}</span>
                  <div className="flex gap-1 opacity-100 xl:absolute xl:right-3 xl:top-1/2 xl:-translate-y-1/2 xl:bg-slate-950/90 xl:opacity-0 xl:group-hover:opacity-100" onClick={(event) => event.stopPropagation()}>
                    {(asset.entity_id && (viewLabel || asset.generation_params?.view_angle)) && <Button size="sm" variant="outline" title="重生成" aria-label="重生成" className="h-8 w-8 border-white/15 p-0 text-white" onClick={() => props.onRegenerate(asset)}><RefreshCw className="h-3.5 w-3.5" /></Button>}
                    <Button size="sm" variant="outline" title="编辑" aria-label="编辑" className="h-8 w-8 border-white/15 p-0 text-white" onClick={() => props.onEdit(asset)}><Edit3 className="h-3.5 w-3.5" /></Button>
                    <Button size="sm" variant="outline" title="归档" aria-label="归档" className="h-8 w-8 border-red-300/20 p-0 text-red-200" onClick={() => props.onArchive(asset.id)}><Archive className="h-3.5 w-3.5" /></Button>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
