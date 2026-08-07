import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { promptUsageApi } from '../prompt-usage-api';
import type { PromptUsageMap, PromptUsageStage } from '../prompt-usage-types';

const issueStatuses = new Set(['internal_fallback', 'invalid_binding']);

export function usePromptUsageMap() {
  const [data, setData] = useState<PromptUsageMap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [selectedStageId, setSelectedStageId] = useState<string | null>(null);
  const [problemsOnly, setProblemsOnly] = useState(false);
  const generation = useRef(0);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    const request = ++generation.current;
    setLoading(true);
    setError(null);
    try {
      const response = await promptUsageApi.getMap();
      if (!mounted.current || request !== generation.current) return response;
      setData(response);
      setSelectedStageId((current) => current || response.groups[0]?.stages[0]?.id || null);
      return response;
    } catch (reason) {
      const nextError = reason instanceof Error ? reason : new Error('提示词使用地图读取失败');
      if (mounted.current && request === generation.current) setError(nextError);
      throw nextError;
    } finally {
      if (mounted.current && request === generation.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh().catch(() => undefined);
    return () => { mounted.current = false; generation.current += 1; };
  }, [refresh]);

  const visibleGroups = useMemo(() => (data?.groups || []).map((group) => ({
    ...group,
    stages: problemsOnly ? group.stages.filter((stage) => issueStatuses.has(stage.status)) : group.stages,
  })).filter((group) => group.stages.length > 0), [data, problemsOnly]);

  useEffect(() => {
    const visible = visibleGroups.flatMap((group) => group.stages);
    if (visible.length && !visible.some((stage) => stage.id === selectedStageId)) {
      setSelectedStageId(visible[0].id);
    }
  }, [selectedStageId, visibleGroups]);

  const selectedStage: PromptUsageStage | null = data?.groups
    .flatMap((group) => group.stages)
    .find((stage) => stage.id === selectedStageId) || null;

  return {
    data, visibleGroups, selectedStage, selectedStageId, problemsOnly,
    loading, error, refresh,
    selectStage: setSelectedStageId,
    toggleProblemsOnly: () => setProblemsOnly((value) => !value),
  };
}
