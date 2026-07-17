import { Loader2, Plus, RefreshCw, Search, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';

type Props = {
  loading: boolean;
  search: string;
  selectedNovelId: string;
  novels: { id: string; title: string }[];
  onSearchChange: (value: string) => void;
  onNovelChange: (value: string) => void;
  onRefresh: () => void;
  onCreate: () => void;
  onCompleteMissing: () => void;
};

export function AssetWorkbenchHeader(props: Props) {
  return (
    <div className="border-b border-white/10 bg-gradient-to-r from-violet-500/[0.08] to-transparent p-4 sm:p-5">
      <h2 className="sr-only">资产库</h2>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">资产工作台</h1>
          <p className="mt-1 text-sm text-white/45">集中发现问题、检查版本并完成批量维护</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" className="border-white/15 bg-white/[0.03] text-white" onClick={props.onCreate}>
            <Plus className="mr-2 h-4 w-4" />新建资产
          </Button>
          <Button className="bg-violet-600 text-white hover:bg-violet-500" onClick={props.onCompleteMissing}>
            <Sparkles className="mr-2 h-4 w-4" />补齐缺失资产
          </Button>
        </div>
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-[220px_minmax(240px,1fr)_auto]">
        <Select
          aria-label="当前小说"
          value={props.selectedNovelId}
          onChange={(event) => props.onNovelChange(event.target.value)}
          options={[{ value: '', label: '全部小说' }, ...props.novels.map((novel) => ({ value: novel.id, label: novel.title }))]}
        />
        <div className="relative min-w-0">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-white/35" />
          <Input
            aria-label="搜索资产"
            value={props.search}
            onChange={(event) => props.onSearchChange(event.target.value)}
            placeholder="搜索资产名、角色名、场景名、道具名…"
            className="border-white/10 bg-black/20 pl-9 text-white"
          />
        </div>
        <Button variant="outline" className="border-white/15 text-white" onClick={props.onRefresh} disabled={props.loading}>
          {props.loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
          刷新
        </Button>
      </div>
    </div>
  );
}
