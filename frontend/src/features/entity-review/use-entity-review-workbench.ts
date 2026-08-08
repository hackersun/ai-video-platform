'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { entityReviewApi } from './api';
import type { ReanalysisResult, RebuildResult, ReviewEntity, ReviewPage } from './types';

const EMPTY: ReviewPage = { items: [], page: 1, page_size: 50, total: 0, total_pages: 0,
  summary: { total: 0, candidate_count: 0, approved_count: 0, rejected_count: 0 } };

export function useEntityReviewWorkbench(novelId: string) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [data, setData] = useState<ReviewPage>(EMPTY);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busyIds, setBusyIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState('');
  const [reanalysis, setReanalysis] = useState<ReanalysisResult | null>(null);
  const [rebuild, setRebuild] = useState<RebuildResult | null>(null);
  const loaded = useRef(false);

  const query = useMemo(() => ({
    page: Math.max(1, Number(params.get('page') || 1)),
    pageSize: [20, 50, 100].includes(Number(params.get('page_size'))) ? Number(params.get('page_size')) : 50,
    type: params.get('type') || undefined,
    status: params.get('status') || 'candidate',
    query: params.get('q') || undefined,
  }), [params]);
  const activeId = params.get('entity') || data.items[0]?.id || '';
  const activeEntity = data.items.find((item) => item.id === activeId) || data.items[0] || null;

  const setQuery = useCallback((updates: Record<string, string | number | undefined>, resetPage = false) => {
    const next = new URLSearchParams(params.toString());
    if (resetPage) next.set('page', '1');
    Object.entries(updates).forEach(([key, value]) => value === undefined || value === '' ? next.delete(key) : next.set(key, String(value)));
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  }, [params, pathname, router]);

  const load = useCallback(async (_background = false) => {
    !loaded.current ? setInitialLoading(true) : setRefreshing(true);
    try {
      const result = await entityReviewApi.list(novelId, query);
      setData(result); setError(''); loaded.current = true;
    } catch (reason: any) { setError(reason?.message || '资产列表加载失败'); }
    finally { setInitialLoading(false); setRefreshing(false); }
  }, [novelId, query]);

  useEffect(() => { if (novelId) void load(); }, [load, novelId]);

  const review = useCallback(async (ids: string[], action: 'approve' | 'reject') => {
    setBusyIds((current) => new Set([...Array.from(current), ...ids]));
    try {
      const result = await entityReviewApi.bulk(novelId, ids, action);
      const updates = new Map(result.updated.map((item) => [item.id, item]));
      setData((current) => ({ ...current, items: current.items.map((item) => updates.get(item.id) || item), summary: result.summary }));
      setSelectedIds((current) => new Set(Array.from(current).filter((id) => !updates.has(id))));
      setError(result.skipped.length ? result.skipped.map((item) => `${item.id}: ${item.reason}`).join('；') : '');
      return result;
    } catch (reason: any) { setError(reason?.message || '审核操作失败'); throw reason; }
    finally { setBusyIds((current) => new Set(Array.from(current).filter((id) => !ids.includes(id)))); }
  }, [novelId]);

  const save = useCallback(async (entityId: string, patch: Partial<ReviewEntity>) => {
    const updated = await entityReviewApi.update(entityId, patch);
    setData((current) => ({ ...current, items: current.items.map((item) => item.id === entityId ? { ...item, ...updated } : item) }));
  }, []);
  const previewEntity = useCallback(async (entityId: string) => setReanalysis(await entityReviewApi.reanalyze(entityId, { mode: 'preview' })), []);
  const applyEntity = useCallback(async () => {
    if (!reanalysis) return;
    const result = await entityReviewApi.reanalyze(reanalysis.current.id, { mode: 'apply', preview_run_id: reanalysis.preview_run_id });
    setData((current) => ({ ...current, items: current.items.map((item) => item.id === result.current.id ? result.current : item) }));
    setReanalysis(null);
  }, [reanalysis]);
  const previewRebuild = useCallback(async () => setRebuild(await entityReviewApi.rebuild(novelId, { mode: 'preview' })), [novelId]);
  const applyRebuild = useCallback(async () => {
    if (!rebuild) return;
    await entityReviewApi.rebuild(novelId, { mode: 'apply', preview_run_id: rebuild.preview_run_id });
    setRebuild(null); setSelectedIds(new Set()); await load(true);
  }, [load, novelId, rebuild]);

  return { data, query, setQuery, selectedIds, setSelectedIds, activeEntity, initialLoading, refreshing,
    busyIds, error, load, review, save, reanalysis, previewEntity, applyEntity, rebuild, previewRebuild, applyRebuild };
}
