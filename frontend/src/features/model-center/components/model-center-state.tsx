import { AlertCircle, Loader2 } from 'lucide-react';

export function ModelCenterLoading({ label = '正在读取模型中心配置…' }: { label?: string }) {
  return <div className="flex min-h-52 items-center justify-center gap-2 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin" />{label}</div>;
}

export function ModelCenterError({ error, onRetry }: { error: Error; onRetry: () => void }) {
  return (
    <div className="m-4 rounded-lg border border-rose-400/30 bg-rose-500/10 p-4 text-sm text-rose-100">
      <div className="flex gap-2"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /><span>{error.message || '模型中心数据读取失败'}</span></div>
      <button type="button" onClick={onRetry} className="mt-3 rounded-md border border-rose-300/40 px-3 py-1.5 text-xs hover:bg-rose-400/10">重新读取</button>
    </div>
  );
}

export function ModelCenterEmpty({ title, description }: { title: string; description: string }) {
  return <div className="m-4 rounded-lg border border-dashed border-white/15 bg-slate-950/20 px-5 py-12 text-center"><p className="text-sm font-medium text-slate-200">{title}</p><p className="mt-1 text-xs text-slate-500">{description}</p></div>;
}
