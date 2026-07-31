'use client';

import { useState } from 'react';
import { approveRequiredStoryEntities, prepareSeriesStoryLock, repairSeriesStoryAssets } from './api';
import type { StoryAssetRepairResult, StoryLockPreparation } from './types';

export function useStoryLockPreparation(runId: string, onPrepared: () => Promise<unknown>, onLoading: (value: boolean) => void, nativeAudio = false) {
  const [result, setResult] = useState<StoryLockPreparation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [repairResult, setRepairResult] = useState<StoryAssetRepairResult | null>(null);

  const prepare = async () => {
    setLoading(true);
    onLoading(true);
    setError('');
    try {
      const next = await prepareSeriesStoryLock(runId, nativeAudio);
      setResult(next);
      await onPrepared();
    } catch (reason: any) {
      setError(reason?.message || '故事锁准备失败');
    } finally {
      setLoading(false);
      onLoading(false);
    }
  };

  const approveRequired = async () => {
    const entityIds = result?.unresolved_entity_ids || [];
    if (!entityIds.length) return;
    setLoading(true);
    onLoading(true);
    setError('');
    try {
      const approval = await approveRequiredStoryEntities(entityIds);
      if (approval.updated_count !== entityIds.length || approval.skipped?.length) {
        throw new Error('部分必需实体存在证据或重复风险，请在实体库逐条复核');
      }
      const next = await prepareSeriesStoryLock(runId, nativeAudio);
      setResult(next);
      await onPrepared();
    } catch (reason: any) {
      setError(reason?.message || '必需实体定稿失败');
    } finally {
      setLoading(false);
      onLoading(false);
    }
  };

  const repairAndRetry = async () => {
    setLoading(true);
    onLoading(true);
    setError('');
    setRepairResult(null);
    try {
      const repaired = await repairSeriesStoryAssets(runId);
      setRepairResult(repaired);
      const next = await prepareSeriesStoryLock(runId, nativeAudio);
      setResult(next);
      await onPrepared();
    } catch (reason: any) {
      setError(reason?.message || '资产整理失败，请按提示检查后重试');
    } finally {
      setLoading(false);
      onLoading(false);
    }
  };

  return { result, repairResult, loading, error, prepare, approveRequired, repairAndRetry };
}
