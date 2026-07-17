import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';

type Props = {
  currentPage: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
};

const pageSizeOptions = [12, 24, 48].map((value) => ({
  value: String(value),
  label: `每页 ${value} 项`,
}));

export function AssetPagination(props: Props) {
  const totalPages = Math.max(1, Math.ceil(props.totalItems / props.pageSize));
  const start = props.totalItems > 0 ? (props.currentPage - 1) * props.pageSize + 1 : 0;
  const end = Math.min(props.currentPage * props.pageSize, props.totalItems);

  return (
    <div
      data-testid="asset-pagination"
      className="flex flex-col gap-3 border-t border-white/10 px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between"
    >
      <span className="text-white/45">显示 {start}-{end} / {props.totalItems}</span>
      <div className="flex items-center justify-between gap-2 sm:justify-end">
        <Select
          value={String(props.pageSize)}
          onChange={(event) => props.onPageSizeChange(Number(event.target.value))}
          options={pageSizeOptions}
          aria-label="每页资产数量"
          className="h-9 w-32"
        />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-9 w-9 text-white/70 hover:text-white"
          onClick={() => props.onPageChange(props.currentPage - 1)}
          disabled={props.currentPage <= 1}
          aria-label="上一页"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <span className="min-w-16 text-center text-white/55">
          {props.currentPage}/{totalPages}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-9 w-9 text-white/70 hover:text-white"
          onClick={() => props.onPageChange(props.currentPage + 1)}
          disabled={props.currentPage >= totalPages}
          aria-label="下一页"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
