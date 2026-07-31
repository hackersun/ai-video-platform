'use client';

import { Image, Loader2, RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';

export function FirstFrameControls({
  selectedCount,
  busy,
  failures,
  message,
  disabled,
  onGenerate,
  onRetry,
}: {
  selectedCount: number;
  busy: boolean;
  failures: Array<{ shotId: string; message: string }>;
  message: string;
  disabled: boolean;
  onGenerate: () => void;
  onRetry: () => void;
}) {
  if (!selectedCount) return null;
  return (
    <div className="space-y-2 rounded-lg border border-cyan-400/20 bg-cyan-500/5 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="outline" onClick={onGenerate} disabled={disabled || busy}>
          {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Image className="mr-2 h-4 w-4" />}
          生成 {selectedCount} 个镜头首帧
        </Button>
        {failures.length > 0 && (
          <Button size="sm" variant="outline" onClick={onRetry} disabled={disabled || busy}>
            <RefreshCw className="mr-2 h-4 w-4" />只重试 {failures.length} 个失败首帧
          </Button>
        )}
        <span className="text-xs text-white/50">首帧成功项不会重复调用模型；视频仅使用对应镜头首帧。</span>
      </div>
      {message && <div role="status" className={failures.length ? 'text-xs text-amber-100' : 'text-xs text-emerald-200'}>{message}</div>}
      {failures.map((item) => <div key={item.shotId} role="alert" className="text-xs text-red-200">镜头 {item.shotId}：{item.message}</div>)}
    </div>
  );
}
