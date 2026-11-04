'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient, type PublicationPipeline } from '@/lib/api-client';

const ACTIVE = new Set(['accepted', 'running', 'queued']);
export const isPipelineActive = (p?: PublicationPipeline | null) => Boolean(p && ACTIVE.has(p.status));

/** 读取某小说最近一次「一键生成视频」流水线，运行中每 3 秒轮询。 */
export function usePublicationPipeline(novelId: string, intervalMs = 3000) {
  const [pipeline, setPipeline] = useState<PublicationPipeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const rows = await apiClient.listPublicationPipelines(novelId, 1);
      setPipeline(rows?.[0] || null);
      setError('');
    } catch (e: any) {
      setError(e?.message || '读取生成进度失败');
    } finally {
      setLoading(false);
    }
  }, [novelId]);

  useEffect(() => { if (novelId) refresh(); }, [novelId, refresh]);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (isPipelineActive(pipeline)) timer.current = setTimeout(refresh, intervalMs);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [pipeline, refresh, intervalMs]);

  const run = useCallback(async (fn: () => Promise<PublicationPipeline>) => {
    setBusy(true);
    try {
      const next = await fn();
      setPipeline(next);
      setError('');
      return next;
    } catch (e: any) {
      setError(e?.message || '操作失败，请重试');
      return null;
    } finally {
      setBusy(false);
    }
  }, []);

  return {
    pipeline, loading, busy, error, refresh,
    start: () => run(() => apiClient.createPublicationPipeline(novelId)),
    pause: () => pipeline && run(() => apiClient.pausePublicationPipeline(pipeline.pipeline_id)),
    resume: () => pipeline && run(() => apiClient.resumePublicationPipeline(pipeline.pipeline_id)),
    cancel: () => pipeline && run(() => apiClient.cancelPublicationPipeline(pipeline.pipeline_id)),
  };
}
