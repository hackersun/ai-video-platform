'use client';

import { Button } from '@/components/ui/button';
import { useStoryLockPreparation } from './use-story-lock-preparation';

export function StoryLockControl({ runId, disabled, nativeAudio, onPrepared, onLoading }: {
  runId: string;
  disabled: boolean;
  nativeAudio?: boolean;
  onPrepared: () => Promise<unknown>;
  onLoading: (value: boolean) => void;
}) {
  const { result, repairResult, loading, error, prepare, approveRequired, repairAndRetry } = useStoryLockPreparation(runId, onPrepared, onLoading, nativeAudio);
  const shortHash = result?.closure_hash ? result.closure_hash.slice(0, 10) : '';
  return <>
    <div className="flex flex-wrap gap-2">
      <Button size="sm" variant="outline" onClick={prepare} disabled={disabled || loading}>准备故事锁</Button>
      <Button size="sm" variant="outline" onClick={repairAndRetry} disabled={disabled || loading}>整理资产并重试</Button>
    </div>
    <div className="w-full text-xs text-white/55">若人物名带动作、道具是句子片段或跨章重复，使用“整理资产并重试”；已付费参考资产不会被自动覆盖。</div>
    {result && <div data-testid="story-lock-closure-status" className="w-full text-xs text-emerald-200">
      <div>故事锁：{result.status} · Bible v{result.version}{result.idempotent ? ' · 已复用' : ''} · 闭包 {shortHash}</div>
      <div>必需实体 {result.required_entity_ids.length} · 无关候选 {result.unrelated_candidate_count} · 自动批准 {result.auto_approved_count} · 手动批准 {result.manual_approved_count} · 未解决 {result.unresolved_count}</div>
      {result.unresolved_count > 0 && <Button className="mt-2" size="sm" variant="outline" onClick={approveRequired} disabled={disabled || loading}>确认定稿 {result.unresolved_count} 个必需实体</Button>}
    </div>}
    {repairResult && <div data-testid="story-asset-repair-result" className="w-full text-xs text-cyan-200">
      已整理 {repairResult.chapter_count} 章：移除 {repairResult.archived_noise_count} 个噪声候选，合并 {repairResult.merged_duplicate_count} 个跨章重复资产，修复 {repairResult.repaired_dialogue_count} 个对白归属，并已重新建立故事锁。
    </div>}
    {error && <div role="alert" className="w-full text-xs text-red-200">{error}</div>}
  </>;
}
