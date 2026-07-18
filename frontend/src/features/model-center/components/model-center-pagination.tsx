'use client';

export function ModelCenterPagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  return <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500"><span>共 {total} 条 · 第 {page} / {pageCount} 页</span><div className="flex gap-2"><button type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)} className="model-center-quiet">上一页</button><button type="button" disabled={page >= pageCount} onClick={() => onPageChange(page + 1)} className="model-center-quiet">下一页</button></div></div>;
}
