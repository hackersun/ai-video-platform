import { Sparkles } from 'lucide-react';

/** 可见的「AI 生成」标识：用于播放器与发布物，满足生成式内容标识要求。 */
export function AiGeneratedLabel({ className = '' }: { className?: string }) {
  return (
    <span
      data-testid="ai-generated-label"
      title="本视频由 AI 生成"
      className={`inline-flex items-center gap-1 rounded-full border border-amber-400/40 bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-200 ${className}`}
    >
      <Sparkles className="h-3 w-3" aria-hidden />
      AI 生成
    </span>
  );
}
