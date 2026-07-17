'use client';

import { Button } from '@/components/ui/button';
import { useStoryLockPreparation } from './use-story-lock-preparation';

export function StoryLockControl({ runId, disabled, onPrepared, onLoading }: {
  runId: string;
  disabled: boolean;
  onPrepared: () => Promise<unknown>;
  onLoading: (value: boolean) => void;
}) {
  const { result, loading, error, prepare, approveRequired } = useStoryLockPreparation(runId, onPrepared, onLoading);
  const shortHash = result?.closure_hash ? result.closure_hash.slice(0, 10) : '';
  return <>
    <Button size="sm" variant="outline" onClick={prepare} disabled={disabled || loading}>准备故事锁</Button>
    {result && <div data-testid="story-lock-closure-status" className="w-full text-xs text-emerald-200">
      <div>故事锁：{result.status} · Bible v{result.version}{result.idempotent ? ' · 已复用' : ''} · 闭包 {shortHash}</div>
      <div>必需实体 {result.required_entity_ids.length} · 无关候选 {result.unrelated_candidate_count} · 自动批准 {result.auto_approved_count} · 手动批准 {result.manual_approved_count} · 未解决 {result.unresolved_count}</div>
      {result.unresolved_count > 0 && <Button className="mt-2" size="sm" variant="outline" onClick={approveRequired} disabled={disabled || loading}>确认定稿 {result.unresolved_count} 个必需实体</Button>}
    </div>}
    {error && <div role="alert" className="w-full text-xs text-red-200">{error}</div>}
  </>;
}
