import { AlertCircle, Boxes, Clock3, ImageOff, Lock, Map, Package, UserRound } from 'lucide-react';
import type { AssetCollectionKey, AssetWorkbenchItem } from '../asset-workbench-model';
import { matchesCollection } from '../asset-workbench-model';

type Props = {
  assets: AssetWorkbenchItem[];
  active: AssetCollectionKey;
  novelNames: string[];
  onChange: (value: AssetCollectionKey) => void;
};

const collections = [
  { key: 'all', label: '全部资产', icon: Boxes },
  { key: 'attention', label: '待处理', icon: Clock3 },
  { key: 'failed', label: '生成失败', icon: AlertCircle },
  { key: 'draft', label: '待定稿', icon: ImageOff },
  { key: 'locked', label: '已锁定', icon: Lock },
] as const;

const categories = [
  { key: 'character', label: '角色', icon: UserRound },
  { key: 'scene', label: '场景', icon: Map },
  { key: 'prop', label: '道具', icon: Package },
] as const;

export function AssetCollectionSidebar({ assets, active, novelNames, onChange }: Props) {
  const renderItem = ({ key, label, icon: Icon }: typeof collections[number] | typeof categories[number]) => {
    const count = assets.filter((asset) => matchesCollection(asset, key)).length;
    return (
      <button
        key={key}
        type="button"
        data-testid={`asset-collection-${key}`}
        onClick={() => onChange(key)}
        className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition lg:w-full ${
          active === key ? 'bg-violet-500/20 text-violet-100 ring-1 ring-violet-400/30' : 'text-white/60 hover:bg-white/[0.06] hover:text-white'
        }`}
      >
        <Icon className="h-4 w-4" />
        <span className="flex-1 whitespace-nowrap">{label}</span>
        <span className="text-xs tabular-nums text-white/35">{count}</span>
      </button>
    );
  };

  return (
    <aside className="border-b border-white/10 bg-black/10 p-3 lg:border-b-0 lg:border-r lg:p-4">
      <div className="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-white/35">智能集合</div>
      <div className="flex gap-2 overflow-x-auto pb-2 lg:block lg:space-y-1 lg:overflow-visible lg:pb-0">
        {collections.map(renderItem)}
      </div>
      <div className="mt-4 hidden border-t border-white/10 pt-4 lg:block">
        <div className="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-white/35">资产类型</div>
        <div className="space-y-1">{categories.map(renderItem)}</div>
      </div>
      {novelNames.length > 0 && (
        <div className="mt-4 hidden border-t border-white/10 pt-4 lg:block">
          <div className="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-white/35">当前小说</div>
          {novelNames.slice(0, 3).map((name) => <div key={name} className="truncate py-1 text-sm text-white/60">{name}</div>)}
        </div>
      )}
    </aside>
  );
}
